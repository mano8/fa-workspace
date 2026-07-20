"""Validate the root-owned agent-context control plane without child execution.

The default (``strict``) pass reads only tracked workspace inputs.  It checks
the static trust roots and reports absent child instruction files as diagnostics
instead of treating a child checkout as a workspace-validation dependency.
Optional artifact arguments validate an already-produced resolver/delivery
generation; they never create a runtime session or invoke an agent.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context import w2b1
from agent_context import codex_adapter
from agent_context import resolve_context
from agent_context.validate_claude_settings import validate_claude_settings
from agent_context.validate_codex_config import validate_codex_config
from agent_context.validate_invariants import validate_workspace_invariants
from agent_context.validate_migration_guards import validate_migration_guards
from agent_context.validate_root_agents import validate_root_agents
from agent_context.validate_root_claude import validate_root_claude


CAPABILITY_EVIDENCE = Path(codex_adapter.CAPABILITY_EVIDENCE_PATH)
ROOT_INPUTS = (
    Path(".m8-workspace-root"), Path("AGENTS.md"), Path("CLAUDE.md"),
    Path(".claude/settings.json"), Path(".codex/config.toml"),
    Path(".workspace/repo-types.json"), Path(".workspace/policy.index.json"),
    Path(".workspace/policy.metadata.json"), Path(".workspace/invariants.json"),
    Path(".workspace/contracts/agent-context-w2a.contract.md"),
    Path("scripts/codex-repo.sh"), Path("scripts/codex-repo.ps1"),
)


class WorkspaceValidationError(ValueError):
    """Raised for a root control-plane contract violation."""


@dataclass(frozen=True)
class WorkspaceValidationReport:
    policy_count: int
    repository_count: int
    child_diagnostics: tuple[str, ...]
    artifact_validated: bool


def _fail(message: str) -> None:
    raise WorkspaceValidationError(message)


def _tracked_paths(workspace: Path) -> set[str]:
    completed = subprocess.run(
        ["git", "-C", str(workspace), "ls-files", "-z"], check=False, capture_output=True
    )
    if completed.returncode:
        _fail("could not inspect tracked workspace inputs")
    return {item for item in completed.stdout.decode("utf-8").split("\0") if item}


def _read_normalized(path: Path, description: str) -> bytes:
    try:
        raw = path.read_bytes()
        raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        _fail(f"could not read {description} as strict UTF-8: {error}")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        _fail(f"{description} must be UTF-8 without BOM, LF, and final newline")
    return raw


def _regular_contained(workspace: Path, relative: str, description: str) -> Path:
    try:
        w2b1._canonical_path(relative, description)
        candidate = workspace.joinpath(*relative.split("/"))
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(workspace)
        if candidate.is_symlink() or not resolved.is_file():
            _fail(f"{description} must be a contained regular file")
        return resolved
    except (OSError, ValueError, w2b1.AgentContextError) as error:
        _fail(f"{description} is unsafe or unavailable: {error}")


def _validate_capability_evidence(workspace: Path) -> None:
    # Evidence reports are intentionally ignored runtime/status artifacts.  A
    # strict workspace pass therefore proves only the tracked contract's pinned
    # identity and the adapter's matching requirement; the launcher performs
    # live client/config/native-source freshness checks before every handoff.
    contract = _read_normalized(
        workspace / ".workspace/contracts/agent-context-w2a.contract.md", "agent-context contract"
    )
    if codex_adapter.CAPABILITY_EVIDENCE_SHA256.encode() not in contract:
        _fail("agent-context contract does not link the current capability-evidence hash")
    row = codex_adapter.CURRENT_CODEX_CAPABILITY
    expected = {
        "agent": "codex", "platform": "devcontainer", "mode": "non-interactive",
        "status": "REQUIRED", "inspection_mechanism": "codex debug prompt-input",
        "channel_id": "cli-config-developer-instructions", "verified_channel_limit": 32768,
        "client_context_allowance": 65536, "reserved_margin": 32768,
        "start_supported": True, "resume_supported": True, "clear_supported": True,
        "compact_supported": False, "launcher_identity_available": True,
        "client_session_identity_available": True, "blocks_closeout": True,
    }
    if row != expected:
        _fail("Codex capability row drifted from the frozen required capability evidence")


def _validate_policy_sources(
    workspace: Path, registry: Mapping[str, Any], index: Mapping[str, Any], metadata: Mapping[str, Any]
) -> int:
    try:
        units, _, _ = resolve_context._metadata_catalog(metadata)
    except w2b1.AgentContextError as error:
        _fail(f"policy metadata is invalid: {error}")
    try:
        resolve_context._validate_registry_scope(registry, units)
        selected = tuple(index["always"]) + tuple(
            policy_id for policies in index["facets"].values() for policy_id in policies
        ) + tuple(
            policy_id for task in index["tasks"].values() for policy_id in task["policies"]
        )
        resolve_context._validate_authority(selected, units)
        resolve_context._validate_selected_scope(selected, units, tuple(item["id"] for item in registry["repositories"]))
    except w2b1.AgentContextError as error:
        _fail(f"policy authority or repository scope is invalid: {error}")
    for unit in units.values():
        source = _regular_contained(workspace, unit["path"], f"policy source {unit['id']}")
        _read_normalized(source, f"policy source {unit['id']}")
    return len(units)


def _validate_artifacts(
    workspace: Path, manifest_path: Path | None, envelope_path: Path | None,
    session_path: Path | None, receipt_path: Path | None,
) -> bool:
    supplied = (manifest_path, envelope_path, session_path, receipt_path)
    if not any(supplied):
        return False
    if not all(supplied):
        _fail("manifest, envelope, session, and receipt must be supplied together")
    try:
        runtime_root = workspace / ".workspace/.runtime"
        runtime_dir = session_path.resolve(strict=True).parent
        if receipt_path.resolve(strict=True).parent != runtime_dir:
            _fail("session and receipt must belong to one runtime session directory")
        if runtime_dir.parent != runtime_root.resolve(strict=True) or not runtime_dir.name.startswith("session-"):
            _fail("runtime artifacts must be contained in one direct session-* runtime child")
        directory_info = runtime_dir.lstat()
        if stat.S_ISLNK(directory_info.st_mode) or not stat.S_ISDIR(directory_info.st_mode):
            _fail("runtime artifact directory is unsafe")
        if os.name == "posix" and (directory_info.st_uid != os.getuid() or stat.S_IMODE(directory_info.st_mode) & 0o077):
            _fail("runtime artifact directory is not owner-only")
        permitted_runtime_names = {"session.json", "receipt.json", ".lock"}
        if any(child.name not in permitted_runtime_names for child in runtime_dir.iterdir()):
            _fail("runtime session contains non-metadata content")
        for path in supplied:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                _fail("runtime artifact is not a regular file")
            if path in {session_path, receipt_path} and os.name == "posix" and (
                info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077
            ):
                _fail("runtime artifact is not owner-only")
        manifest = w2b1.parse_strict_json(manifest_path.read_bytes())
        envelope_raw = envelope_path.read_bytes()
        envelope = w2b1.parse_strict_json(envelope_raw)
        session = w2b1.parse_strict_json(session_path.read_bytes())
        receipt = w2b1.parse_strict_json(receipt_path.read_bytes())
        w2b1.validate_manifest(manifest)
        w2b1.validate_session(session)
        w2b1.validate_receipt(receipt)
        if w2b1.canonical_bytes(envelope) != envelope_raw:
            _fail("envelope is not exact canonical JCS bytes")
        rebuilt, serialized, digest = w2b1.build_envelope(
            manifest_id=manifest["manifest_id"], generation=session["generation"], entries=envelope["entries"]
        )
        if rebuilt != envelope or digest != receipt["envelope_sha256"] or serialized != envelope_raw:
            _fail("envelope hash or canonical framing does not match the receipt")
        shared = ("launch_id", "client_session_id", "generation", "manifest_id", "envelope_sha256",
                  "capability_evidence_id", "native_evidence_ids", "repositories", "tasks", "operations",
                  "authorization_ids", "authorization_provenance")
        if any(session[key] != receipt[key] for key in shared):
            _fail("session and receipt linkage differs")
        if receipt["state"] != session["state"] or receipt["state"] not in {"HANDED_OFF", "FAILED", "PREPARED"}:
            _fail("receipt/session lifecycle state is inconsistent")
        if receipt["state"] == "HANDED_OFF" and receipt["delivered_bytes"] != len(envelope_raw):
            _fail("handed-off receipt did not record the exact envelope byte count")
        if receipt["state"] != "HANDED_OFF" and receipt["delivered_bytes"] != 0:
            _fail("non-handed-off receipt must not claim delivered bytes")
        manifest_entries = {entry["path"]: entry for entry in manifest["entries"]}
        envelope_entries = {entry["path"]: entry for entry in envelope["entries"]}
        if set(envelope_entries) != {
            entry["path"] for entry in manifest["entries"] if entry["delivery"] == "inject"
        }:
            _fail("manifest injection entries do not match the envelope exactly")
        for path, entry in manifest_entries.items():
            source = _regular_contained(workspace, path, f"manifest source {path}")
            raw = source.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["source_sha256"] or len(raw) != entry["source_bytes"]:
                _fail("manifest source hash or byte count drifted")
            injected = envelope_entries.get(path)
            if injected is not None and (
                injected["source_sha256"] != entry["source_sha256"]
                or injected["source_bytes"] != entry["source_bytes"]
            ):
                _fail("manifest and envelope source identity differs")
        accounting = manifest["accounting"]
        expected_limit = min(
            accounting["policy_hard_limit"], accounting["verified_channel_limit"],
            accounting["client_context_allowance"] - accounting["reserved_margin"],
        )
        raw_injected = sum(entry["source_bytes"] for entry in envelope["entries"])
        total = (
            accounting["native_model_visible_bytes"] + len(envelope_raw)
            + accounting["other_model_visible_bootstrap_bytes"]
        )
        if expected_limit < 0 or accounting["effective_hard_limit"] != expected_limit:
            _fail("effective context budget arithmetic is inconsistent")
        if accounting["model_visible_total"] != total or total > expected_limit:
            _fail("model-visible context accounting is inconsistent or over budget")
        if accounting["serialized_injected_envelope_bytes"] != len(envelope_raw):
            _fail("manifest does not record the exact serialized envelope bytes")
        if accounting["raw_injected_source_bytes"] != raw_injected:
            _fail("raw injected-source accounting is inconsistent")
        if accounting["serialization_overhead_bytes"] != len(envelope_raw) - raw_injected:
            _fail("serialization overhead accounting is inconsistent")
        if accounting["estimated_tokens"] != (total + 3) // 4:
            _fail("estimated-token accounting is inconsistent")
    except (OSError, w2b1.AgentContextError) as error:
        _fail(f"runtime artifact validation failed: {error}")
    return True


def validate_workspace(
    workspace: Path, *, manifest_path: Path | None = None, envelope_path: Path | None = None,
    session_path: Path | None = None, receipt_path: Path | None = None,
    tracked_paths: Sequence[str] | None = None,
) -> WorkspaceValidationReport:
    """Validate root-owned configuration; child state is static diagnostic-only."""
    workspace = workspace.resolve()
    tracked = set(tracked_paths) if tracked_paths is not None else _tracked_paths(workspace)
    missing = sorted(str(path) for path in ROOT_INPUTS if str(path) not in tracked)
    if missing:
        _fail("required root-owned inputs are not tracked: " + ", ".join(missing))
    for path in ROOT_INPUTS:
        _read_normalized(workspace / path, str(path))
    validate_root_agents(workspace)
    validate_root_claude(workspace)
    validate_claude_settings(workspace)
    validate_codex_config(workspace)
    validate_migration_guards(workspace)
    validate_workspace_invariants(workspace, tracked_paths=tuple(tracked))
    _validate_capability_evidence(workspace)
    try:
        registry = w2b1.parse_strict_json((workspace / ".workspace/repo-types.json").read_bytes())
        index = w2b1.parse_strict_json((workspace / ".workspace/policy.index.json").read_bytes())
        metadata = w2b1.parse_strict_json((workspace / ".workspace/policy.metadata.json").read_bytes())
        w2b1.validate_workspace_configuration_v2(registry, index)
    except (OSError, w2b1.AgentContextError) as error:
        _fail(f"registry/index validation failed: {error}")
    policy_count = _validate_policy_sources(workspace, registry, index, metadata)
    diagnostics: list[str] = []
    for item in registry["repositories"]:
        child = workspace / item["path"]
        agents = child / "AGENTS.md"
        if not child.is_dir():
            diagnostics.append(f"missing child checkout: {item['id']}")
        elif not agents.is_file() or agents.is_symlink():
            diagnostics.append(f"missing regular child AGENTS.md: {item['id']}")
    artifact_validated = _validate_artifacts(
        workspace, manifest_path, envelope_path, session_path, receipt_path
    )
    return WorkspaceValidationReport(policy_count, len(registry["repositories"]), tuple(diagnostics), artifact_validated)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--envelope", type=Path)
    parser.add_argument("--session", type=Path)
    parser.add_argument("--receipt", type=Path)
    arguments = parser.parse_args(argv)
    try:
        report = validate_workspace(
            arguments.workspace, manifest_path=arguments.manifest, envelope_path=arguments.envelope,
            session_path=arguments.session, receipt_path=arguments.receipt,
        )
    except WorkspaceValidationError as error:
        print(f"workspace validation failed: {error}")
        return 2
    print(
        f"workspace validation passed: {report.policy_count} policy units, "
        f"{report.repository_count} registered repositories, {len(report.child_diagnostics)} child diagnostics"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
