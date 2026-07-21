"""Conservative client-neutral submission kernel.

This module deliberately has no client hooks, launcher, or real transport
adapter.  It turns a W2b2 faceted ``ResolvedContext`` into an isolated prepared
runtime state and accepts a transport callback only after a durable
``SUBMISSION_STARTED`` journal record.  The installed Codex transport has no
separate verified context-acceptance event, so this module intentionally makes
no handoff or exactly-once execution claim.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
import tempfile
from contextlib import contextmanager
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Protocol

from agent_context import w2b1
from agent_context.shared_validation import validate_persisted, validate_resolved
from agent_context.resolve_context import ResolvedContext


ZERO_SHA256 = "0" * 64
RUNTIME_DIRECTORY = ".workspace/.runtime"


class ExitCode(IntEnum):
    OK = 0
    E_USAGE = 2
    E_SCHEMA = 3
    E_UNKNOWN_ID = 4
    E_SCOPE_UNAVAILABLE = 5
    E_AUTHORITY = 6
    E_AUTHORIZATION = 7
    E_SOURCE = 8
    E_NATIVE_EVIDENCE = 9
    E_TRUST = 10
    E_RUNTIME = 11
    E_CONCURRENCY = 12
    E_CHANNEL = 13
    E_BUDGET = 14
    E_LIFECYCLE = 15
    E_RECEIPT = 16
    E_CAPABILITY = 17
    E_UNSUPPORTED_MODE = 18
    E_INTERNAL = 19


EXIT_CODES = {item.name: int(item) for item in ExitCode}


def exit_code(error: w2b1.AgentContextError) -> int:
    """Return the frozen numeric exit code, defaulting unexpected errors safely."""
    return EXIT_CODES.get(error.code, int(ExitCode.E_INTERNAL))


def _fail(code: str, message: str) -> None:
    raise w2b1.AgentContextError(code, message)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _receipt(value: dict[str, Any]) -> dict[str, Any]:
    value["receipt_id"] = w2b1.canonical_sha256(
        {key: item for key, item in value.items() if key != "receipt_id"}
    )
    w2b1.validate_receipt(value)
    return value


@dataclass(frozen=True)
class TransportConfirmation:
    """Metadata-only proof returned by a client-neutral transport callback."""

    envelope_sha256: str
    delivered_bytes: int
    # A client may expose its session identity only after its pre-task gate has
    # begun.  The kernel starts with a launcher-owned pending identifier and
    # replaces it atomically before recording HANDED_OFF.
    client_session_id: str | None = None


class TransportAdapter(Protocol):
    """One task submission callback; success is not context acceptance proof."""

    def deliver(
        self, *, payload: bytes, envelope_sha256: str, channel_id: str
    ) -> TransportConfirmation: ...


@dataclass(frozen=True)
class FakeTransportAdapter:
    """Deterministic test adapter; it does not invoke or emulate an agent."""

    returned_sha256: str | None = None
    returned_bytes: int | None = None

    def deliver(
        self, *, payload: bytes, envelope_sha256: str, channel_id: str
    ) -> TransportConfirmation:
        del channel_id
        return TransportConfirmation(
            self.returned_sha256 or envelope_sha256,
            len(payload) if self.returned_bytes is None else self.returned_bytes,
        )


@dataclass(frozen=True)
class DeliveryRequest:
    """Inputs that a future client-specific preflight supplies to the kernel."""

    workspace_root: Path
    resolved: ResolvedContext
    capability_row: Mapping[str, Any]
    trusted: bool
    reviewed_tree: Mapping[str, Any]
    capability_evidence_id: str
    client_session_id: str
    channel_id: str
    # The client-neutral test seam uses zero; production adapters provide a
    # nonzero reviewed-tree/environment identity on every launch.
    trust_identity_sha256: str = ZERO_SHA256


@dataclass(frozen=True)
class PreparedDelivery:
    """A prepared, not-yet-submitted, single generation."""

    request: DeliveryRequest
    runtime_dir: Path
    session: Mapping[str, Any]
    receipt: Mapping[str, Any]


@dataclass(frozen=True)
class DeliveryResult:
    """Terminal result.  The receipt contains hashes and metadata only."""

    runtime_dir: Path
    session: Mapping[str, Any]
    receipt: Mapping[str, Any]


class DeliveryKernel:
    """Secure isolated state with a single immutable journal authority."""

    def __init__(self, *, fault_hook: Callable[[str], None] | None = None) -> None:
        # Test-only crash/kill seams name real persistence and transport
        # boundaries. A production caller supplies no hook.
        self._fault_hook = fault_hook

    def _fault(self, boundary: str) -> None:
        if self._fault_hook is not None:
            self._fault_hook(boundary)

    def prepare(self, request: DeliveryRequest) -> PreparedDelivery:
        """Validate all preflight inputs and atomically persist ``PREPARED``."""
        self._validate_request(request)
        runtime_dir = self._new_runtime_dir(request.workspace_root)
        try:
            self._rehash_sources(request)
            session = self._new_session(request)
            self._append_journal(runtime_dir, session, "RESOLVED", "RESOLVED", request.channel_id, 0, "OK")
            self._write_views(runtime_dir, session, self._latest_journal(runtime_dir))
            prepared_receipt = self._transition(
                runtime_dir,
                session,
                "PREPARED",
                channel_id=request.channel_id,
                delivered_bytes=0,
                failure_code="OK",
            )
            self._validate_persisted_request(runtime_dir, request)
            session = self._read_json(runtime_dir, "session.json", w2b1.validate_session)
            return PreparedDelivery(request, runtime_dir, session, prepared_receipt)
        except w2b1.AgentContextError as error:
            self._record_failure(runtime_dir, request, error.code)
            raise
        except OSError as error:
            self._record_failure(runtime_dir, request, "E_RUNTIME")
            _fail("E_RUNTIME", f"runtime storage failed: {error}")

    def handoff(self, prepared: PreparedDelivery, adapter: TransportAdapter) -> DeliveryResult:
        """Durably begin one submission and never silently retry ambiguity."""
        request = prepared.request
        lock_acquired = False
        try:
            with self._exclusive_lock(prepared.runtime_dir):
                lock_acquired = True
                self._validate_runtime_dir(prepared.runtime_dir, request.workspace_root)
                session = self._authoritative_session(prepared.runtime_dir)
                if session["state"] != "PREPARED" or session["generation"] != request.resolved.envelope["generation"]:
                    _fail("E_RECEIPT", "only the current PREPARED generation may start submission")
                self._rehash_sources(request)
                self._fault("before-submission-journal")
                self._transition(
                    prepared.runtime_dir, session, "SUBMISSION_STARTED",
                    channel_id=request.channel_id,
                    delivered_bytes=len(request.resolved.envelope_bytes), failure_code="OK",
                )
                session = self._authoritative_session(prepared.runtime_dir)
                self._fault("after-submission-journal")
                self._fault("before-transport")
                confirmation = adapter.deliver(
                    payload=request.resolved.envelope_bytes,
                    envelope_sha256=request.resolved.envelope_sha256,
                    channel_id=request.channel_id,
                )
                self._fault("after-transport")
                if (
                    confirmation.envelope_sha256 != request.resolved.envelope_sha256
                    or confirmation.delivered_bytes != len(request.resolved.envelope_bytes)
                ):
                    _fail("E_CHANNEL", "transport callback did not confirm the exact payload")
                client_session_id = getattr(confirmation, "client_session_id", None)
                if client_session_id is not None:
                    try:
                        w2b1._identifier(
                            client_session_id,
                            "transport client_session_id",
                        )
                    except w2b1.AgentContextError:
                        _fail("E_LIFECYCLE", "transport returned an invalid client-session identity")
                    session = dict(session)
                    session["client_session_id"] = client_session_id
                    w2b1.validate_session(session)
                receipt = self._transition(
                    prepared.runtime_dir,
                    session,
                    "COMPLETED",
                    channel_id=request.channel_id,
                    delivered_bytes=len(request.resolved.envelope_bytes),
                    failure_code="OK",
                )
                self._validate_persisted_request(prepared.runtime_dir, request)
                final_session = self._read_json(prepared.runtime_dir, "session.json", w2b1.validate_session)
                return DeliveryResult(prepared.runtime_dir, final_session, receipt)
        except w2b1.AgentContextError as error:
            # A competing process does not own this generation and must not
            # alter its authoritative journal.
            if lock_acquired:
                self._record_failure(prepared.runtime_dir, request, error.code)
            raise
        except Exception as error:  # Adapter failures must never permit a task.
            if lock_acquired:
                self._record_failure(prepared.runtime_dir, request, "E_CHANNEL")
            _fail("E_CHANNEL", f"transport callback failed: {type(error).__name__}")

    def compact(self, prepared: PreparedDelivery) -> None:
        """The only frozen required mode has no compaction lifecycle."""
        self._record_failure(prepared.runtime_dir, prepared.request, "E_LIFECYCLE")
        _fail("E_LIFECYCLE", "compaction is unsupported for this delivery mode")

    def fresh(self, prior_runtime_dir: Path | None, request: DeliveryRequest) -> PreparedDelivery:
        """Start a new launch at generation zero and discard prior reuse state.

        A fresh launch is intentionally not a client-native ``clear``.  When a
        caller names a prior runtime directory it is validated and removed with
        the same owner-only containment checks as retention cleanup, so the old
        receipt can no longer be resumed.
        """
        if request.resolved.envelope["generation"] != 0:
            _fail("E_LIFECYCLE", "fresh launch must begin at generation zero")
        if prior_runtime_dir is not None:
            self.cleanup(prior_runtime_dir, request.workspace_root)
        return self.prepare(request)

    def cleanup(self, runtime_dir: Path, workspace_root: Path) -> None:
        """Remove one validated direct runtime child without following paths.

        This is deliberately conservative: an interrupted session may contain
        no state files, but an unexpected entry, symlink, permission change, or
        containment failure is a runtime error and is left untouched.
        """
        try:
            with self._exclusive_lock(runtime_dir):
                self._validate_runtime_dir(runtime_dir, workspace_root)
                permitted = {"session.json", "receipt.json", ".lock"}
                entries = list(runtime_dir.iterdir())
                for entry in entries:
                    if entry.name not in permitted and not (
                        entry.name.startswith("journal-") and entry.name.endswith(".json")
                    ):
                        _fail("E_RUNTIME", "runtime cleanup found an unexpected entry")
                    info = entry.lstat()
                    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                        _fail("E_RUNTIME", "runtime cleanup found an unsafe entry")
                    if os.name == "posix" and (
                        info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077
                    ):
                        _fail("E_RUNTIME", "runtime cleanup found a non-owner-only entry")
                self._fault("cleanup-before-remove")
                for entry in entries:
                    entry.unlink()
                runtime_dir.rmdir()
                self._fault("cleanup-after-remove")
        except w2b1.AgentContextError:
            raise
        except OSError as error:
            _fail("E_RUNTIME", f"runtime cleanup failed: {error}")

    def cleanup_retained(self, workspace_root: Path, *, max_sessions: int) -> int:
        """Bound retained direct runtime children, refusing unsafe discovery."""
        if not isinstance(max_sessions, int) or isinstance(max_sessions, bool) or max_sessions < 0:
            _fail("E_USAGE", "max_sessions must be a non-negative integer")
        runtime_root = self._runtime_root(workspace_root)
        try:
            children: list[tuple[int, Path]] = []
            for child in runtime_root.iterdir():
                info = child.lstat()
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                    _fail("E_RUNTIME", "runtime retention found an unsafe child")
                if not child.name.startswith("session-"):
                    _fail("E_RUNTIME", "runtime retention found an unexpected child")
                if os.name == "posix" and (
                    info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077
                ):
                    _fail("E_RUNTIME", "runtime retention found a non-owner-only child")
                children.append((info.st_mtime_ns, child))
        except OSError as error:
            _fail("E_RUNTIME", f"runtime retention cannot inspect children: {error}")
        removed = 0
        for _, child in sorted(children, key=lambda item: (item[0], item[1].name))[:-max_sessions or None]:
            self.cleanup(child, workspace_root)
            removed += 1
        return removed

    def resume(self, runtime_dir: Path, request: DeliveryRequest) -> PreparedDelivery:
        """Begin the next verified generation for the same client session.

        The caller supplies a freshly resolved generation.  This method never
        rebuilds a manifest or envelope and it never performs a handoff.
        """
        self._validate_request(request)
        if request.capability_row.get("resume_supported") is not True:
            _fail("E_LIFECYCLE", "resume is unsupported for this delivery mode")
        lock_acquired = False
        try:
            with self._exclusive_lock(runtime_dir):
                lock_acquired = True
                self._validate_runtime_dir(runtime_dir, request.workspace_root)
                prior = self._authoritative_session(runtime_dir)
                if prior["state"] != "COMPLETED":
                    _fail("E_LIFECYCLE", "only a completed generation may resume")
                if prior["client_session_id"] != request.client_session_id:
                    _fail("E_LIFECYCLE", "resume client-session identity changed")
                if request.resolved.envelope["generation"] != prior["generation"] + 1:
                    _fail("E_LIFECYCLE", "resume generation must increment exactly once")
                if (
                    prior["manifest_id"] != request.resolved.manifest["manifest_id"]
                    or prior["capability_evidence_id"] != request.capability_evidence_id
                    or prior["trust_identity_sha256"] != request.trust_identity_sha256
                    or prior["native_evidence_ids"] != sorted({entry["native_evidence_id"] for entry in request.resolved.manifest["entries"] if entry["native_evidence_id"]})
                    or prior["repositories"] != request.resolved.manifest["repositories"]
                    or prior["tasks"] != request.resolved.manifest["tasks"]
                    or prior["operations"] != request.resolved.manifest["operations"]
                    or prior["authorization_ids"] != request.resolved.manifest["authorization_ids"]
                    or prior["authorization_provenance"] != request.resolved.manifest["authorization_provenance"]
                ):
                    _fail("E_RECEIPT", "resume receipt linkage no longer exactly matches")
                self._rehash_sources(request)
                session = dict(prior)
                session.update(
                    generation=request.resolved.envelope["generation"], state="RESOLVED",
                    envelope_sha256=request.resolved.envelope_sha256, updated_at=_now(),
                )
                w2b1.validate_session(session)
                self._append_journal(runtime_dir, session, "RESOLVED", prior["state"], request.channel_id, 0, "OK")
                self._write_views(runtime_dir, session, self._latest_journal(runtime_dir))
                receipt = self._transition(
                    runtime_dir, session, "PREPARED", channel_id=request.channel_id,
                    delivered_bytes=0, failure_code="OK",
                )
                self._validate_persisted_request(runtime_dir, request)
                current = self._read_json(runtime_dir, "session.json", w2b1.validate_session)
                return PreparedDelivery(request, runtime_dir, current, receipt)
        except w2b1.AgentContextError as error:
            if lock_acquired:
                self._record_failure(runtime_dir, request, error.code)
            raise
        except OSError as error:
            if lock_acquired:
                self._record_failure(runtime_dir, request, "E_RUNTIME")
            _fail("E_RUNTIME", f"runtime resume failed: {error}")

    def _validate_request(self, request: DeliveryRequest) -> None:
        try:
            w2b1._identifier(request.client_session_id, "client_session_id")
        except w2b1.AgentContextError:
            raise
        if not request.trusted:
            _fail("E_TRUST", "trusted reviewed workspace identity cannot be proved")
        validate_resolved(
            workspace=request.workspace_root.resolve(), manifest=request.resolved.manifest,
            envelope=request.resolved.envelope, envelope_bytes=request.resolved.envelope_bytes,
            capability_row=request.capability_row, reviewed_tree=request.reviewed_tree,
            capability_evidence_id=request.capability_evidence_id,
            trust_identity_sha256=request.trust_identity_sha256, channel_id=request.channel_id,
        )

    def _validate_persisted_request(self, runtime_dir: Path, request: DeliveryRequest) -> None:
        """Use the same strict validator after each production state transition."""
        validate_persisted(
            workspace=request.workspace_root.resolve(), manifest=request.resolved.manifest,
            envelope=request.resolved.envelope, envelope_bytes=request.resolved.envelope_bytes,
            session=self._read_json(runtime_dir, "session.json", w2b1.validate_session),
            receipt=self._read_json(runtime_dir, "receipt.json", w2b1.validate_receipt),
        )

    def _new_session(self, request: DeliveryRequest) -> dict[str, Any]:
        manifest = request.resolved.manifest
        return {
            "schema_version": 2,
            "launch_id": f"launch-{secrets.token_hex(16)}",
            "client_session_id": request.client_session_id,
            "generation": request.resolved.envelope["generation"],
            "state": "RESOLVED",
            "manifest_id": manifest["manifest_id"],
            "envelope_sha256": request.resolved.envelope_sha256,
            "capability_evidence_id": request.capability_evidence_id,
            "trust_identity_sha256": request.trust_identity_sha256,
            "native_evidence_ids": sorted({entry["native_evidence_id"] for entry in manifest["entries"] if entry["native_evidence_id"]}),
            "repositories": manifest["repositories"],
            "tasks": manifest["tasks"],
            "operations": manifest["operations"],
            "authorization_ids": manifest["authorization_ids"],
            "authorization_provenance": manifest["authorization_provenance"],
            "sources": manifest["entries"],
            "created_at": _now(),
            "updated_at": _now(),
            "previous_receipt_sha256": ZERO_SHA256,
        }

    def _transition(self, runtime_dir: Path, session: Mapping[str, Any], state: str, *, channel_id: str, delivered_bytes: int, failure_code: str) -> dict[str, Any]:
        current = session["state"]
        if (current, state) not in {
            ("RESOLVED", "PREPARED"), ("RESOLVED", "FAILED"),
            ("PREPARED", "SUBMISSION_STARTED"), ("PREPARED", "FAILED"),
            ("SUBMISSION_STARTED", "COMPLETED"),
            ("SUBMISSION_STARTED", "EXECUTION_AMBIGUOUS"),
        }:
            _fail("E_RECEIPT", f"illegal receipt transition {current} -> {state}")
        receipt = _receipt({
            "schema_version": 2, "receipt_id": ZERO_SHA256,
            "launch_id": session["launch_id"], "client_session_id": session["client_session_id"],
            "generation": session["generation"], "manifest_id": session["manifest_id"],
            "envelope_sha256": session["envelope_sha256"], "capability_evidence_id": session["capability_evidence_id"],
            "trust_identity_sha256": session["trust_identity_sha256"],
            "native_evidence_ids": session["native_evidence_ids"], "repositories": session["repositories"],
            "tasks": session["tasks"], "operations": session["operations"],
            "authorization_ids": session["authorization_ids"],
            "authorization_provenance": session["authorization_provenance"],
            "sources": session["sources"],
            "previous_state": current, "state": state, "channel_id": channel_id,
            "delivered_bytes": delivered_bytes, "failure_code": failure_code, "recorded_at": _now(),
        })
        next_session = dict(session)
        next_session.update(state=state, updated_at=receipt["recorded_at"], previous_receipt_sha256=receipt["receipt_id"])
        w2b1.validate_session(next_session)
        record = self._append_journal(
            runtime_dir, next_session, state, current, channel_id, delivered_bytes,
            failure_code, receipt=receipt,
        )
        self._write_views(runtime_dir, next_session, record)
        return receipt

    def _record_failure(self, runtime_dir: Path, request: DeliveryRequest, code: str) -> None:
        try:
            session = self._authoritative_session(runtime_dir)
            if session["state"] in {"RESOLVED", "PREPARED"}:
                self._transition(runtime_dir, session, "FAILED", channel_id=request.channel_id, delivered_bytes=0, failure_code=code)
            elif session["state"] == "SUBMISSION_STARTED":
                # The external process may already have accepted the combined
                # context/task invocation.  This is terminal and non-retryable.
                self._transition(
                    runtime_dir, session, "EXECUTION_AMBIGUOUS",
                    channel_id=request.channel_id,
                    delivered_bytes=session.get("submitted_bytes", len(request.resolved.envelope_bytes)),
                    failure_code=code,
                )
        except (OSError, w2b1.AgentContextError):
            pass

    def _append_journal(
        self, runtime_dir: Path, session: Mapping[str, Any], state: str,
        previous_state: str, channel_id: str, delivered_bytes: int,
        failure_code: str, *, receipt: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Atomically create the next immutable hash-chained journal record."""
        prior = self._latest_journal(runtime_dir, required=False)
        if receipt is None:
            receipt = _receipt({
                "schema_version": 2, "receipt_id": ZERO_SHA256,
                "launch_id": session["launch_id"], "client_session_id": session["client_session_id"],
                "generation": session["generation"], "manifest_id": session["manifest_id"],
                "envelope_sha256": session["envelope_sha256"],
                "capability_evidence_id": session["capability_evidence_id"],
                "trust_identity_sha256": session["trust_identity_sha256"],
                "native_evidence_ids": session["native_evidence_ids"], "repositories": session["repositories"],
                "tasks": session["tasks"], "operations": session["operations"],
                "authorization_ids": session["authorization_ids"],
                "authorization_provenance": session["authorization_provenance"], "sources": session["sources"],
                "previous_state": previous_state, "state": state, "channel_id": channel_id,
                "delivered_bytes": delivered_bytes, "failure_code": failure_code, "recorded_at": _now(),
            })
        record = {
            "schema_version": 1,
            "sequence": 0 if prior is None else prior["sequence"] + 1,
            "previous_journal_sha256": ZERO_SHA256 if prior is None else prior["journal_id"],
            "receipt": dict(receipt),
            "journal_id": ZERO_SHA256,
        }
        record["journal_id"] = w2b1.canonical_sha256(
            {key: value for key, value in record.items() if key != "journal_id"}
        )
        self._validate_journal(record, prior)
        self._write_json(runtime_dir, f"journal-{record['sequence']:06d}.json", record, replace=False)
        return record

    @staticmethod
    def _validate_journal(value: Any, prior: Mapping[str, Any] | None) -> None:
        if not isinstance(value, dict) or set(value) != {
            "schema_version", "sequence", "previous_journal_sha256", "receipt", "journal_id",
        }:
            _fail("E_RECEIPT", "generation journal has an invalid closed shape")
        if value["schema_version"] != 1 or not isinstance(value["sequence"], int) or value["sequence"] < 0:
            _fail("E_RECEIPT", "generation journal has an invalid sequence")
        try:
            w2b1._sha256(value["previous_journal_sha256"], "journal previous hash")
            w2b1._sha256(value["journal_id"], "journal identity")
            w2b1.validate_receipt(value["receipt"])
        except w2b1.AgentContextError as error:
            _fail("E_RECEIPT", error.message)
        expected = w2b1.canonical_sha256({key: item for key, item in value.items() if key != "journal_id"})
        if value["journal_id"] != expected:
            _fail("E_RECEIPT", "generation journal hash does not match JCS content")
        if prior is None:
            valid = value["sequence"] == 0 and value["previous_journal_sha256"] == ZERO_SHA256
        else:
            valid = value["sequence"] == prior["sequence"] + 1 and value["previous_journal_sha256"] == prior["journal_id"]
        if not valid:
            _fail("E_RECEIPT", "generation journal hash chain is discontinuous")

    def _latest_journal(self, runtime_dir: Path, *, required: bool = True) -> dict[str, Any] | None:
        self._validate_dir(runtime_dir, runtime_dir.parent, allow_root=False)
        records: list[dict[str, Any]] = []
        try:
            names = sorted(child.name for child in runtime_dir.iterdir() if child.name.startswith("journal-"))
            for index, name in enumerate(names):
                if name != f"journal-{index:06d}.json":
                    _fail("E_RECEIPT", "generation journal filenames are discontinuous")
                record = self._read_json(runtime_dir, name, lambda item: None)
                self._validate_journal(record, records[-1] if records else None)
                records.append(record)
        except OSError as error:
            _fail("E_RUNTIME", f"generation journal cannot be read: {error}")
        if not records and required:
            _fail("E_RECEIPT", "generation journal is missing")
        return records[-1] if records else None

    def _write_views(self, runtime_dir: Path, session: Mapping[str, Any], record: Mapping[str, Any]) -> None:
        receipt = record["receipt"]
        derived = dict(session)
        derived.update(
            state=receipt["state"], updated_at=receipt["recorded_at"],
            previous_receipt_sha256=receipt["receipt_id"],
        )
        w2b1.validate_session(derived)
        self._fault("receipt-view-before-write")
        self._write_json(runtime_dir, "receipt.json", receipt, replace=True)
        self._fault("receipt-view-after-write")
        self._fault("session-view-before-write")
        self._write_json(runtime_dir, "session.json", derived, replace=True)
        self._fault("session-view-after-write")

    def _authoritative_session(self, runtime_dir: Path) -> dict[str, Any]:
        """Reject a missing/divergent derived view without changing the journal."""
        record = self._latest_journal(runtime_dir)
        assert record is not None
        receipt = self._read_json(runtime_dir, "receipt.json", w2b1.validate_receipt)
        session = self._read_json(runtime_dir, "session.json", w2b1.validate_session)
        if receipt != record["receipt"]:
            _fail("E_RECEIPT", "receipt view diverges from the authoritative generation journal")
        shared = (
            "launch_id", "client_session_id", "generation", "manifest_id", "envelope_sha256",
            "capability_evidence_id", "trust_identity_sha256", "native_evidence_ids", "repositories", "tasks", "operations",
            "authorization_ids", "authorization_provenance", "sources",
        )
        if any(session[key] != receipt[key] for key in shared) or session["state"] != receipt["state"]:
            _fail("E_RECEIPT", "session view diverges from the authoritative generation journal")
        if session["previous_receipt_sha256"] != receipt["receipt_id"]:
            _fail("E_RECEIPT", "session view does not link the authoritative journal receipt")
        return session

    def _rehash_sources(self, request: DeliveryRequest) -> None:
        root = request.workspace_root.resolve(strict=True)
        for entry in request.resolved.manifest["entries"]:
            try:
                w2b1._canonical_path(entry["path"], "manifest entry path")
                candidate = root.joinpath(*entry["path"].split("/"))
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
                if candidate.is_symlink() or not resolved.is_file():
                    _fail("E_SOURCE", "manifest source is not a contained regular file")
                raw = resolved.read_bytes()
            except (OSError, ValueError) as error:
                _fail("E_SOURCE", f"manifest source cannot be rehashed: {error}")
            if _digest(raw) != entry["source_sha256"] or len(raw) != entry["source_bytes"]:
                _fail("E_SOURCE", "manifest source drifted after resolution")

    def _runtime_root(self, workspace_root: Path) -> Path:
        root = workspace_root.resolve(strict=True)
        runtime_root = root.joinpath(*RUNTIME_DIRECTORY.split("/"))
        try:
            workspace_metadata = runtime_root.parent
            if workspace_metadata.exists():
                metadata_info = workspace_metadata.lstat()
                if stat.S_ISLNK(metadata_info.st_mode) or not stat.S_ISDIR(metadata_info.st_mode):
                    _fail("E_RUNTIME", "workspace metadata directory is unsafe")
            else:
                workspace_metadata.mkdir(mode=0o700)
            runtime_root.mkdir(mode=0o700, exist_ok=True)
            self._validate_dir(runtime_root, root, allow_root=True)
            if os.name == "posix":
                os.chmod(runtime_root, 0o700)
        except OSError as error:
            _fail("E_RUNTIME", f"cannot establish isolated runtime root: {error}")
        return runtime_root

    def _new_runtime_dir(self, workspace_root: Path) -> Path:
        runtime_root = self._runtime_root(workspace_root)
        for _ in range(8):
            directory = runtime_root / f"session-{secrets.token_hex(24)}"
            try:
                directory.mkdir(mode=0o700)
                self._validate_runtime_dir(directory, workspace_root)
                return directory
            except FileExistsError:
                continue
            except OSError as error:
                _fail("E_RUNTIME", f"cannot create runtime session: {error}")
        _fail("E_CONCURRENCY", "could not allocate a unique runtime session")

    def _validate_runtime_dir(self, directory: Path, workspace_root: Path) -> None:
        root = workspace_root.resolve(strict=True)
        runtime_root = root.joinpath(*RUNTIME_DIRECTORY.split("/"))
        self._validate_dir(runtime_root, root, allow_root=True)
        self._validate_dir(directory, runtime_root, allow_root=False)

    def _validate_dir(self, directory: Path, contained_by: Path, *, allow_root: bool) -> None:
        try:
            resolved = directory.resolve(strict=True)
            resolved.relative_to(contained_by.resolve(strict=True))
            info = directory.lstat()
        except (OSError, ValueError) as error:
            _fail("E_RUNTIME", f"runtime containment check failed: {error}")
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or (not allow_root and resolved == contained_by.resolve()):
            _fail("E_RUNTIME", "runtime directory is unsafe")
        if os.name == "posix":
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                _fail("E_RUNTIME", "runtime directory is not owner-only")

    def _read_json(self, directory: Path, name: str, validator: Callable[[Any], None]) -> dict[str, Any]:
        self._validate_dir(directory, directory.parent, allow_root=False)
        path = directory / name
        try:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                _fail("E_RUNTIME", "runtime file is unsafe")
            if os.name == "posix" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077):
                _fail("E_RUNTIME", "runtime file is not owner-only")
            parsed = w2b1.parse_strict_json(path.read_bytes())
            validator(parsed)
            return parsed
        except OSError as error:
            _fail("E_RUNTIME", f"runtime state cannot be read: {error}")

    def _write_json(self, directory: Path, name: str, value: Mapping[str, Any], *, replace: bool) -> None:
        self._validate_dir(directory, directory.parent, allow_root=False)
        destination = directory / name
        if not replace and destination.exists():
            _fail("E_CONCURRENCY", "runtime state already exists")
        raw = w2b1.canonical_bytes(dict(value))
        fd, temporary_name = tempfile.mkstemp(prefix=f".{name}.", dir=directory)
        temporary = Path(temporary_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if not replace:
                # ``link`` provides a no-replace commit on POSIX filesystems.
                try:
                    os.link(temporary, destination)
                except FileExistsError:
                    _fail("E_CONCURRENCY", "runtime state creation collided")
                temporary.unlink()
            else:
                os.replace(temporary, destination)
        except OSError as error:
            _fail("E_RUNTIME", f"runtime state cannot be written atomically: {error}")
        finally:
            if temporary.exists():
                temporary.unlink()

    @contextmanager
    def _exclusive_lock(self, directory: Path):
        """Reject competing writers before any transport callback can run."""
        if os.name != "posix":
            _fail("E_RUNTIME", "owner-only concurrent runtime locking is unavailable")
        import fcntl

        lock_path = directory / ".lock"
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            os.fchmod(fd, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                _fail("E_CONCURRENCY", "another runtime writer owns this generation")
            yield
        except OSError as error:
            _fail("E_RUNTIME", f"runtime lock cannot be acquired: {error}")
        finally:
            if "fd" in locals():
                try:
                    os.close(fd)
                except OSError:
                    pass
