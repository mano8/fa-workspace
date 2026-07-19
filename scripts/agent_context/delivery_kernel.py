"""Inactive W2b3 client-neutral delivery kernel.

This module deliberately has no client hooks, launcher, or real transport
adapter.  It turns a W2b2 faceted ``ResolvedContext`` into an isolated prepared
runtime state and accepts a transport callback only for the exact final
handoff.  The active v2 transitional resolver remains path-selection only
until a later adapter explicitly enables a demonstrated client mode.
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


class TransportAdapter(Protocol):
    """The sole callback permitted to create a ``HANDED_OFF`` receipt."""

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


@dataclass(frozen=True)
class PreparedDelivery:
    """A prepared, but not handed-off, single generation."""

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
    """Secure isolated state and exact-once handoff for one context generation."""

    def prepare(self, request: DeliveryRequest) -> PreparedDelivery:
        """Validate all preflight inputs and atomically persist ``PREPARED``."""
        self._validate_request(request)
        runtime_dir = self._new_runtime_dir(request.workspace_root)
        try:
            self._rehash_sources(request)
            session = self._new_session(request)
            self._write_json(runtime_dir, "session.json", session, replace=False)
            prepared_receipt = self._transition(
                runtime_dir,
                session,
                "PREPARED",
                channel_id=request.channel_id,
                delivered_bytes=0,
                failure_code="OK",
            )
            session = self._read_json(runtime_dir, "session.json", w2b1.validate_session)
            return PreparedDelivery(request, runtime_dir, session, prepared_receipt)
        except w2b1.AgentContextError as error:
            self._record_failure(runtime_dir, request, error.code)
            raise
        except OSError as error:
            self._record_failure(runtime_dir, request, "E_RUNTIME")
            _fail("E_RUNTIME", f"runtime storage failed: {error}")

    def handoff(self, prepared: PreparedDelivery, adapter: TransportAdapter) -> DeliveryResult:
        """Use one exact payload callback; only its exact confirmation hands off."""
        request = prepared.request
        lock_acquired = False
        try:
            with self._exclusive_lock(prepared.runtime_dir):
                lock_acquired = True
                self._validate_runtime_dir(prepared.runtime_dir, request.workspace_root)
                session = self._read_json(prepared.runtime_dir, "session.json", w2b1.validate_session)
                if session["state"] != "PREPARED" or session["generation"] != request.resolved.envelope["generation"]:
                    _fail("E_RECEIPT", "only the current PREPARED generation may hand off")
                self._rehash_sources(request)
                confirmation = adapter.deliver(
                    payload=request.resolved.envelope_bytes,
                    envelope_sha256=request.resolved.envelope_sha256,
                    channel_id=request.channel_id,
                )
                if (
                    confirmation.envelope_sha256 != request.resolved.envelope_sha256
                    or confirmation.delivered_bytes != len(request.resolved.envelope_bytes)
                ):
                    _fail("E_CHANNEL", "transport callback did not confirm the exact payload")
                receipt = self._transition(
                    prepared.runtime_dir,
                    session,
                    "HANDED_OFF",
                    channel_id=request.channel_id,
                    delivered_bytes=len(request.resolved.envelope_bytes),
                    failure_code="OK",
                )
                final_session = self._read_json(prepared.runtime_dir, "session.json", w2b1.validate_session)
                return DeliveryResult(prepared.runtime_dir, final_session, receipt)
        except w2b1.AgentContextError as error:
            # A competing process did not own this generation and therefore
            # must not rewrite its receipt/session to FAILED.
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
                    if entry.name not in permitted:
                        _fail("E_RUNTIME", "runtime cleanup found an unexpected entry")
                    info = entry.lstat()
                    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                        _fail("E_RUNTIME", "runtime cleanup found an unsafe entry")
                    if os.name == "posix" and (
                        info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077
                    ):
                        _fail("E_RUNTIME", "runtime cleanup found a non-owner-only entry")
                for entry in entries:
                    entry.unlink()
                runtime_dir.rmdir()
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
                prior = self._read_json(runtime_dir, "session.json", w2b1.validate_session)
                if prior["state"] != "HANDED_OFF":
                    _fail("E_LIFECYCLE", "only a handed-off generation may resume")
                if prior["client_session_id"] != request.client_session_id:
                    _fail("E_LIFECYCLE", "resume client-session identity changed")
                if request.resolved.envelope["generation"] != prior["generation"] + 1:
                    _fail("E_LIFECYCLE", "resume generation must increment exactly once")
                if (
                    prior["manifest_id"] != request.resolved.manifest["manifest_id"]
                    or prior["capability_evidence_id"] != request.capability_evidence_id
                    or prior["native_evidence_ids"] != sorted({entry["native_evidence_id"] for entry in request.resolved.manifest["entries"] if entry["native_evidence_id"]})
                    or prior["authorization_ids"] != request.resolved.manifest["authorization_ids"]
                ):
                    _fail("E_RECEIPT", "resume receipt linkage no longer exactly matches")
                self._rehash_sources(request)
                session = dict(prior)
                session.update(
                    generation=request.resolved.envelope["generation"], state="RESOLVED",
                    envelope_sha256=request.resolved.envelope_sha256, updated_at=_now(),
                )
                w2b1.validate_session(session)
                self._write_json(runtime_dir, "session.json", session, replace=True)
                receipt = self._transition(
                    runtime_dir, session, "PREPARED", channel_id=request.channel_id,
                    delivered_bytes=0, failure_code="OK",
                )
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
            w2b1.validate_manifest(request.resolved.manifest)
            if request.resolved.envelope_sha256 != _digest(request.resolved.envelope_bytes):
                _fail("E_SOURCE", "envelope hash does not cover the supplied bytes")
            if w2b1.canonical_bytes(request.resolved.envelope) != request.resolved.envelope_bytes:
                _fail("E_SOURCE", "envelope object and supplied bytes differ")
            if request.resolved.envelope["manifest_id"] != request.resolved.manifest["manifest_id"]:
                _fail("E_RECEIPT", "envelope and manifest identifiers differ")
            w2b1._identifier(request.client_session_id, "client_session_id")
            w2b1._sha256(request.capability_evidence_id, "capability_evidence_id")
        except w2b1.AgentContextError:
            raise
        manifest = request.resolved.manifest
        row = request.capability_row
        if not request.trusted or manifest["reviewed_tree"] != dict(request.reviewed_tree):
            _fail("E_TRUST", "trusted reviewed workspace identity cannot be proved")
        if manifest["capability_evidence_id"] != request.capability_evidence_id:
            _fail("E_CAPABILITY", "capability evidence identity differs from the manifest")
        required = {
            "agent", "platform", "mode", "status", "channel_id", "verified_channel_limit",
            "client_context_allowance", "reserved_margin", "start_supported",
            "client_session_identity_available",
        }
        if not isinstance(row, Mapping) or not required.issubset(row):
            _fail("E_CAPABILITY", "capability row is absent or incomplete")
        if any(row[key] != manifest[key] for key in ("agent", "platform", "mode")):
            _fail("E_CAPABILITY", "capability row does not match the manifest mode")
        if row["status"] != "REQUIRED":
            _fail("E_UNSUPPORTED_MODE", "canonical delivery is not frozen for this mode")
        if not row["start_supported"] or not row["client_session_identity_available"]:
            _fail("E_LIFECYCLE", "mode cannot provide a canonical start/session identity")
        if row["channel_id"] != request.channel_id:
            _fail("E_CHANNEL", "requested channel is not the verified channel")
        if not all(isinstance(row[key], int) and not isinstance(row[key], bool) for key in ("verified_channel_limit", "client_context_allowance", "reserved_margin")):
            _fail("E_CAPABILITY", "capability limits must be integers")
        accounting = manifest["accounting"]
        expected_limit = min(
            accounting["policy_hard_limit"], row["verified_channel_limit"],
            row["client_context_allowance"] - row["reserved_margin"],
        )
        if expected_limit < 0 or accounting["effective_hard_limit"] != expected_limit:
            _fail("E_BUDGET", "effective hard limit is absent or inconsistent")
        if accounting["model_visible_total"] > expected_limit:
            _fail("E_BUDGET", "model-visible context exceeds its effective hard limit")
        if len(request.resolved.envelope_bytes) > row["verified_channel_limit"]:
            _fail("E_CHANNEL", "serialized envelope exceeds the verified channel limit")

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
            "native_evidence_ids": sorted({entry["native_evidence_id"] for entry in manifest["entries"] if entry["native_evidence_id"]}),
            "authorization_ids": manifest["authorization_ids"],
            "created_at": _now(),
            "updated_at": _now(),
            "previous_receipt_sha256": ZERO_SHA256,
        }

    def _transition(self, runtime_dir: Path, session: Mapping[str, Any], state: str, *, channel_id: str, delivered_bytes: int, failure_code: str) -> dict[str, Any]:
        current = session["state"]
        if (current, state) not in {("RESOLVED", "PREPARED"), ("RESOLVED", "FAILED"), ("PREPARED", "HANDED_OFF"), ("PREPARED", "FAILED")}:
            _fail("E_RECEIPT", f"illegal receipt transition {current} -> {state}")
        receipt = _receipt({
            "schema_version": 2, "receipt_id": ZERO_SHA256,
            "launch_id": session["launch_id"], "client_session_id": session["client_session_id"],
            "generation": session["generation"], "manifest_id": session["manifest_id"],
            "envelope_sha256": session["envelope_sha256"], "capability_evidence_id": session["capability_evidence_id"],
            "native_evidence_ids": session["native_evidence_ids"], "authorization_ids": session["authorization_ids"],
            "previous_state": current, "state": state, "channel_id": channel_id,
            "delivered_bytes": delivered_bytes, "failure_code": failure_code, "recorded_at": _now(),
        })
        next_session = dict(session)
        next_session.update(state=state, updated_at=receipt["recorded_at"], previous_receipt_sha256=receipt["receipt_id"])
        w2b1.validate_session(next_session)
        self._write_json(runtime_dir, "receipt.json", receipt, replace=True)
        self._write_json(runtime_dir, "session.json", next_session, replace=True)
        return receipt

    def _record_failure(self, runtime_dir: Path, request: DeliveryRequest, code: str) -> None:
        try:
            session = self._read_json(runtime_dir, "session.json", w2b1.validate_session)
            if session["state"] in {"RESOLVED", "PREPARED"}:
                self._transition(runtime_dir, session, "FAILED", channel_id=request.channel_id, delivered_bytes=0, failure_code=code)
        except (OSError, w2b1.AgentContextError):
            pass

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
