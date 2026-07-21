"""One strict parity validator for resolved and persisted delivery artifacts.

Offline workspace validation and the production kernel deliberately call these
same routines.  The routines do not create state, invoke a client, or accept
untrusted paths; callers retain containment/ownership checks for persisted
files.  Failures use the stable ``AgentContextError`` classes consumed by both
paths.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agent_context import w2b1


def _fail(code: str, message: str) -> None:
    raise w2b1.AgentContextError(code, message)


def _source(workspace: Path, path: str) -> bytes:
    try:
        w2b1._canonical_path(path, "manifest source path")
        candidate = workspace.joinpath(*path.split("/"))
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(workspace)
        if candidate.is_symlink() or not resolved.is_file():
            _fail("E_SOURCE", "manifest source is not a contained regular file")
        return resolved.read_bytes()
    except (OSError, ValueError) as error:
        _fail("E_SOURCE", f"manifest source cannot be read: {error}")


def _validate_accounting(manifest: Mapping[str, Any], envelope_raw: bytes) -> None:
    accounting = manifest["accounting"]
    entries = manifest["entries"]
    native = sum(entry["source_bytes"] for entry in entries if entry["delivery"] == "native")
    injected = sum(entry["source_bytes"] for entry in entries if entry["delivery"] == "inject")
    effective = min(
        accounting["policy_hard_limit"], accounting["verified_channel_limit"],
        accounting["client_context_allowance"] - accounting["reserved_margin"],
    )
    total = native + len(envelope_raw) + accounting["other_model_visible_bootstrap_bytes"]
    expected = {
        "effective_hard_limit": effective,
        "native_model_visible_bytes": native,
        "serialized_injected_envelope_bytes": len(envelope_raw),
        "model_visible_total": total,
        "raw_injected_source_bytes": injected,
        "serialization_overhead_bytes": len(envelope_raw) - injected,
        "estimated_tokens": (total + 3) // 4,
    }
    if effective < 0 or any(accounting[key] != value for key, value in expected.items()):
        _fail("E_BUDGET", "manifest byte or token accounting does not recompute exactly")
    if total > effective:
        _fail("E_BUDGET", "model-visible context exceeds its effective hard limit")


def validate_resolved(
    *, workspace: Path, manifest: Mapping[str, Any], envelope: Mapping[str, Any],
    envelope_bytes: bytes, capability_row: Mapping[str, Any] | None = None,
    reviewed_tree: Mapping[str, Any] | None = None, capability_evidence_id: str | None = None,
    trust_identity_sha256: str | None = None, channel_id: str | None = None,
) -> None:
    """Validate the exact resolver/transport inputs before a live submission."""
    try:
        w2b1.validate_manifest(dict(manifest))
        if w2b1.canonical_bytes(dict(envelope)) != envelope_bytes:
            _fail("E_SOURCE", "envelope is not exact canonical JCS bytes")
        rebuilt, serialized, digest = w2b1.build_envelope(
            manifest_id=manifest["manifest_id"], generation=envelope["generation"],
            entries=envelope["entries"],
        )
    except w2b1.AgentContextError as error:
        _fail(error.code, error.message)
    if rebuilt != envelope or serialized != envelope_bytes or hashlib.sha256(envelope_bytes).hexdigest() != digest:
        _fail("E_SOURCE", "envelope framing or hash does not recompute exactly")
    manifest_entries = {entry["path"]: entry for entry in manifest["entries"]}
    if len(manifest_entries) != len(manifest["entries"]):
        _fail("E_SOURCE", "manifest contains duplicate canonical source paths")
    envelope_entries = {entry["path"]: entry for entry in envelope["entries"]}
    injected_paths = {entry["path"] for entry in manifest["entries"] if entry["delivery"] == "inject"}
    if set(envelope_entries) != injected_paths:
        _fail("E_SOURCE", "manifest injection entries do not match the envelope exactly")
    for path, entry in manifest_entries.items():
        raw = _source(workspace, path)
        if hashlib.sha256(raw).hexdigest() != entry["source_sha256"] or len(raw) != entry["source_bytes"]:
            _fail("E_SOURCE", "manifest source hash or byte count drifted")
        injected = envelope_entries.get(path)
        if injected is not None:
            try:
                expected = w2b1.source_entry_from_bytes(raw, {
                    "policy_id": entry["policy_id"], "repository_id": entry["repository_id"],
                    "scope_prefix": entry["scope_prefix"], "path": path,
                    # The manifest omits this field; the envelope schema still
                    # validates its declared value and identity below.
                    "authority_tier": injected["authority_tier"],
                }, allow_legacy_leading_bom=True)
            except w2b1.AgentContextError as error:
                _fail(error.code, error.message)
            if injected != expected or entry["envelope_entry_sha256"] != w2b1.canonical_sha256(injected):
                _fail("E_SOURCE", "manifest and envelope source entry identity differs")
        elif entry["native_evidence_id"] is None:
            _fail("E_NATIVE_EVIDENCE", "native manifest source lacks native evidence")
    _validate_accounting(manifest, envelope_bytes)
    if capability_row is not None:
        required = {"agent", "platform", "mode", "status", "channel_id", "verified_channel_limit", "client_context_allowance", "reserved_margin", "start_supported", "client_session_identity_available"}
        if not required.issubset(capability_row):
            _fail("E_CAPABILITY", "capability row is absent or incomplete")
        if any(capability_row[key] != manifest[key] for key in ("agent", "platform", "mode")):
            _fail("E_CAPABILITY", "capability row does not match the manifest mode")
        if manifest["capability_evidence_id"] != w2b1.canonical_sha256(dict(capability_row)):
            _fail("E_CAPABILITY", "manifest capability-evidence identity differs")
        if any(manifest["accounting"][key] != capability_row[key] for key in ("verified_channel_limit", "client_context_allowance", "reserved_margin")):
            _fail("E_CAPABILITY", "manifest capability limits differ from the verified row")
        if capability_row["status"] != "REQUIRED" or not capability_row["start_supported"] or not capability_row["client_session_identity_available"]:
            _fail("E_UNSUPPORTED_MODE", "canonical delivery is not supported by the verified capability row")
        if channel_id is not None and capability_row["channel_id"] != channel_id:
            _fail("E_CHANNEL", "requested channel is not the verified channel")
    if reviewed_tree is not None and manifest["reviewed_tree"] != dict(reviewed_tree):
        _fail("E_TRUST", "trusted reviewed workspace identity cannot be proved")
    if capability_evidence_id is not None and manifest["capability_evidence_id"] != capability_evidence_id:
        _fail("E_CAPABILITY", "capability evidence identity differs from the manifest")
    if trust_identity_sha256 is not None:
        try:
            w2b1._sha256(trust_identity_sha256, "trust_identity_sha256")
        except w2b1.AgentContextError as error:
            _fail("E_TRUST", error.message)


def validate_persisted(
    *, workspace: Path, manifest: Mapping[str, Any], envelope: Mapping[str, Any],
    envelope_bytes: bytes, session: Mapping[str, Any], receipt: Mapping[str, Any],
) -> None:
    """Validate offline artifacts with the same source/accounting core."""
    validate_resolved(workspace=workspace, manifest=manifest, envelope=envelope, envelope_bytes=envelope_bytes)
    try:
        w2b1.validate_session(dict(session))
        w2b1.validate_receipt(dict(receipt))
    except w2b1.AgentContextError as error:
        _fail(error.code, error.message)
    shared = ("launch_id", "client_session_id", "generation", "manifest_id", "envelope_sha256", "capability_evidence_id", "trust_identity_sha256", "native_evidence_ids", "repositories", "tasks", "operations", "authorization_ids", "authorization_provenance", "sources")
    if any(session[key] != receipt[key] for key in shared):
        _fail("E_RECEIPT", "session and receipt linkage differs")
    if session["sources"] != manifest["entries"] or receipt["sources"] != manifest["entries"]:
        _fail("E_RECEIPT", "session or receipt source inventory differs from the manifest")
    if receipt["state"] != session["state"] or receipt["state"] not in {"COMPLETED", "EXECUTION_AMBIGUOUS", "FAILED", "PREPARED", "SUBMISSION_STARTED"}:
        _fail("E_RECEIPT", "receipt/session lifecycle state is inconsistent")
    if receipt["envelope_sha256"] != hashlib.sha256(envelope_bytes).hexdigest():
        _fail("E_RECEIPT", "receipt envelope hash differs from exact envelope bytes")
    submitted = {"SUBMISSION_STARTED", "COMPLETED", "EXECUTION_AMBIGUOUS"}
    if receipt["state"] in submitted and receipt["delivered_bytes"] != len(envelope_bytes):
        _fail("E_RECEIPT", "submitted receipt did not record the exact envelope byte count")
    if receipt["state"] in {"PREPARED", "FAILED"} and receipt["delivered_bytes"] != 0:
        _fail("E_RECEIPT", "pre-submission receipt must not claim delivered bytes")
