"""Phase 10 W9f exact-tree review-bundle builder and verifier.

The final review is deliberately an external evidence document: recording a
runtime receipt in the reviewed Git tree would itself change the tree that the
receipt attests.  This module makes that boundary explicit.  It emits a
metadata-only JSON bundle under the ignored status area, while this tracked
builder and its tests define the reproducible, fail-closed format.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context import w2b1
from agent_context.trust_identity import build_trust_identity


SCHEMA_VERSION = 1
REQUIRED_CHECKS = {
    "root-suite", "workspace-validator", "invariant-validator", "w9a-validator",
    "budget-reproduction", "supply-chain", "sbom-freshness", "ruff",
    "multi-repository-parity", "authorization-negatives", "submission-crash-matrix",
    "lifecycle-cleanup", "trust-drift", "child-standalone-static",
}
FINDING_FIELDS = {"id", "severity", "status", "negative_tests", "closure_artifacts"}
BUNDLE_FIELDS = {
    "schema_version", "reviewed_root", "children", "trust_identity", "checks",
    "live_receipt", "findings", "input_limitation",
}


class ReviewBundleError(ValueError):
    """Raised when a W9f bundle is incomplete, stale, or non-reproducible."""


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(("git", *arguments), cwd=root, capture_output=True, check=False)
    if result.returncode:
        raise ReviewBundleError(f"Git command failed: {' '.join(arguments)}")
    try:
        return result.stdout.decode("ascii", "strict").strip()
    except UnicodeDecodeError as error:
        raise ReviewBundleError("Git identity output is not ASCII") from error


def _git_identity(root: Path) -> dict[str, str]:
    if _git(root, "status", "--porcelain=v1", "--untracked-files=no"):
        raise ReviewBundleError(f"reviewed Git checkout is dirty: {root}")
    return {"commit": _git(root, "rev-parse", "HEAD"), "tree": _git(root, "rev-parse", "HEAD^{tree}")}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = w2b1.parse_strict_json(path.read_bytes())
    except (OSError, w2b1.AgentContextError) as error:
        raise ReviewBundleError(f"cannot parse required JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ReviewBundleError(f"required JSON object is invalid: {path}")
    return value


def _regular_json(path: Path) -> dict[str, Any]:
    try:
        info = path.lstat()
    except OSError as error:
        raise ReviewBundleError(f"live receipt is unavailable: {error}") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ReviewBundleError("live receipt must be a regular file")
    return _read_json(path)


def _children(workspace: Path) -> list[dict[str, str]]:
    registry = _read_json(workspace / ".workspace/repo-types.json")
    repositories = registry.get("repositories")
    if not isinstance(repositories, list):
        raise ReviewBundleError("repository registry has no repository list")
    children: list[dict[str, str]] = []
    for repository in repositories:
        if not isinstance(repository, dict) or not isinstance(repository.get("id"), str) or not isinstance(repository.get("path"), str):
            raise ReviewBundleError("repository registry entry is invalid")
        path = workspace / repository["path"]
        if not path.is_dir() or not (path / ".git").exists():
            raise ReviewBundleError(f"registered child is missing its direct Git identity: {repository['path']}")
        identity = _git_identity(path)
        agents = path / "AGENTS.md"
        try:
            digest = hashlib.sha256(agents.read_bytes()).hexdigest()
        except OSError as error:
            raise ReviewBundleError(f"registered child instruction is missing: {repository['path']}: {error}") from error
        children.append({"id": repository["id"], "path": repository["path"], **identity, "agents_sha256": digest})
    return sorted(children, key=lambda item: item["id"])


def _finding_dispositions(workspace: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    register = _read_json(workspace / ".workspace/contracts/agent-context-w9a-findings.json")
    findings = register.get("findings")
    limitations = register.get("input_limitations")
    if not isinstance(findings, list) or not isinstance(limitations, list) or len(limitations) != 1:
        raise ReviewBundleError("W9a finding register is incomplete")
    disposition: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise ReviewBundleError("W9a finding entry is invalid")
        disposition.append({
            "id": finding["id"], "severity": finding["severity"], "status": "CLOSED_BY_W9F_EVIDENCE",
            "negative_tests": finding["negative_tests"], "closure_artifacts": finding["closure_artifacts"],
        })
    limitation = limitations[0]
    if not isinstance(limitation, dict):
        raise ReviewBundleError("W9a input limitation is invalid")
    return sorted(disposition, key=lambda item: item["id"]), {
        "id": limitation["id"], "status": "REPLACED_BY_SELF_CONTAINED_EXACT_TREE_BUNDLE",
    }


def build_bundle(
    *, workspace: Path, live_runtime: Path, checks: Sequence[Mapping[str, Any]],
    codex_binary: Path, codex_version: str,
) -> dict[str, Any]:
    """Create a metadata-only exact-tree bundle after all checks have passed."""
    root = workspace.resolve(strict=True)
    children = _children(root)
    receipt = _regular_json(live_runtime / "receipt.json")
    session = _regular_json(live_runtime / "session.json")
    if receipt.get("state") != "COMPLETED" or session.get("state") != "COMPLETED":
        raise ReviewBundleError("live receipt and session must both be COMPLETED")
    if receipt.get("reviewed_tree") not in (None, {"algorithm": "git-sha1", "value": _git_identity(root)["tree"]}):
        raise ReviewBundleError("live receipt is bound to a different reviewed tree")
    findings, limitation = _finding_dispositions(root)
    identity = build_trust_identity(
        workspace_root=root, selected_repositories=tuple(root / child["path"] for child in children),
        capability_path="scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md",
        codex_binary=codex_binary, codex_version=codex_version,
    )
    normalized_checks = [dict(item) for item in checks]
    return {
        "schema_version": SCHEMA_VERSION,
        "reviewed_root": _git_identity(root),
        "children": children,
        "trust_identity": identity,
        "checks": normalized_checks,
        "live_receipt": {"session": session, "receipt": receipt},
        "findings": findings,
        "input_limitation": limitation,
    }


def canonical_bytes(bundle: Mapping[str, Any]) -> bytes:
    return w2b1.canonical_bytes(dict(bundle)) + b"\n"


def validate_bundle(bundle: Mapping[str, Any], *, workspace: Path) -> None:
    """Fail closed on missing identities, stale tree proof, or omitted evidence."""
    if set(bundle) != BUNDLE_FIELDS or bundle.get("schema_version") != SCHEMA_VERSION:
        raise ReviewBundleError("review bundle has an invalid closed shape")
    root = workspace.resolve(strict=True)
    if bundle["reviewed_root"] != _git_identity(root):
        raise ReviewBundleError("review bundle root commit/tree or clean proof drifted")
    expected_children = _children(root)
    if bundle["children"] != expected_children:
        raise ReviewBundleError("review bundle child Git or instruction identity drifted")
    checks = bundle["checks"]
    if not isinstance(checks, list) or {item.get("id") for item in checks if isinstance(item, Mapping)} != REQUIRED_CHECKS:
        raise ReviewBundleError("review bundle is missing one or more minimum checks")
    for check in checks:
        if not isinstance(check, Mapping) or check.get("exit_code") != 0 or not isinstance(check.get("command"), str):
            raise ReviewBundleError("review bundle contains a failed or malformed check")
    live = bundle["live_receipt"]
    if not isinstance(live, Mapping) or not isinstance(live.get("session"), Mapping) or not isinstance(live.get("receipt"), Mapping):
        raise ReviewBundleError("review bundle lacks its metadata-only live receipt")
    if live["session"].get("state") != "COMPLETED" or live["receipt"].get("state") != "COMPLETED":
        raise ReviewBundleError("review bundle live receipt is not completed")
    findings = bundle["findings"]
    if not isinstance(findings, list) or len(findings) != 11 or {item.get("id") for item in findings if isinstance(item, Mapping)} != {"C-1", "C-2", "H-1", "H-2", "H-3", "M-1", "M-2", "M-3", "M-4", "L-1", "L-2"}:
        raise ReviewBundleError("review bundle is missing finding evidence")
    for finding in findings:
        if not isinstance(finding, Mapping) or set(finding) != FINDING_FIELDS or finding.get("status") != "CLOSED_BY_W9F_EVIDENCE":
            raise ReviewBundleError("review bundle finding disposition is invalid")
    limitation = bundle["input_limitation"]
    if limitation != {"id": "zip-reproducibility", "status": "REPLACED_BY_SELF_CONTAINED_EXACT_TREE_BUNDLE"}:
        raise ReviewBundleError("review bundle does not close the ZIP input limitation")


def write_bundle(path: Path, bundle: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(bundle))
    os.chmod(path, 0o600)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="build or verify a metadata-only W9f exact-tree review bundle")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--live-runtime", type=Path, required=True)
    parser.add_argument("--checks", type=Path, required=True, help="strict JSON array of completed minimum checks")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codex-binary", type=Path)
    parser.add_argument("--codex-version")
    arguments = parser.parse_args(argv)
    try:
        checks_value = _read_json_array(arguments.checks)
        binary = arguments.codex_binary or Path(shutil.which("codex") or "")
        try:
            binary = binary.resolve(strict=True)
        except OSError as error:
            raise ReviewBundleError(f"Codex binary cannot be resolved: {error}") from error
        if not binary.is_file():
            raise ReviewBundleError("Codex binary is unavailable")
        version = arguments.codex_version or _codex_version(binary)
        bundle = build_bundle(
            workspace=arguments.workspace, live_runtime=arguments.live_runtime,
            checks=checks_value, codex_binary=binary, codex_version=version,
        )
        validate_bundle(bundle, workspace=arguments.workspace)
        write_bundle(arguments.output, bundle)
    except ReviewBundleError as error:
        print(f"W9f review bundle failed: {error}")
        return 1
    print(f"W9f review bundle written: {arguments.output}")
    return 0


def _read_json_array(path: Path) -> list[Mapping[str, Any]]:
    try:
        value = w2b1.parse_strict_json(path.read_bytes())
    except (OSError, w2b1.AgentContextError) as error:
        raise ReviewBundleError(f"cannot parse check results {path}: {error}") from error
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ReviewBundleError("check results must be a strict JSON array of objects")
    return list(value)


def _codex_version(binary: Path) -> str:
    result = subprocess.run((str(binary), "--version"), capture_output=True, check=False)
    if result.returncode:
        raise ReviewBundleError("Codex version probe failed")
    try:
        return result.stdout.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as error:
        raise ReviewBundleError("Codex version probe is not UTF-8") from error


if __name__ == "__main__":
    raise SystemExit(main())
