"""Build and replay the Phase 10 W9f exact-tree review bundle.

The bundle remains ignored metadata because adding a live receipt to Git would
change the tree it attests.  Unlike the provisional W9f format, success is not
accepted from caller-supplied labels: this module executes the fixed check
matrix, verifies every frozen test method and tracked closure artifact, and
recomputes Git, child, toolchain, configuration, trust, and receipt identities.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context import w2b1
from agent_context.trust_identity import build_trust_identity


SCHEMA_VERSION = 2
CHECK_COMMANDS: dict[str, tuple[str, ...]] = {
    "authorization-negatives": ("python", "-m", "unittest", "scripts.agent_context.tests.test_w9b_authorization", "-q"),
    "budget-reproduction": ("python", "scripts/agent_context/budget_promotion.py", "--workspace", ".", "--enforce-preferred"),
    "child-standalone-static": ("python", "-m", "unittest", "scripts.agent_context.tests.test_w8_child_rollout", "-q"),
    "documentation-consistency": ("python", "-m", "unittest", "scripts.agent_context.tests.test_w9e_documentation", "-q"),
    "invariant-validator": ("python", "scripts/agent_context/validate_invariants.py", "--workspace", "."),
    "lifecycle-cleanup": ("python", "-m", "unittest", "scripts.agent_context.tests.test_w9d3_lifecycle", "-q"),
    "multi-repository-parity": ("python", "-m", "unittest", "scripts.agent_context.tests.test_w9d1_multi_repository", "-q"),
    "root-suite": ("python", "-m", "unittest", "discover", "-s", "scripts/agent_context/tests", "-q"),
    "ruff": ("ruff", "check", "--no-cache", "scripts/agent_context"),
    "sbom-freshness": ("python", "scripts/agent_context/generate_root_sbom.py", "--workspace", ".", "--check"),
    "submission-crash-matrix": ("python", "-m", "unittest", "scripts.agent_context.tests.test_w9c_submission_state", "-q"),
    "supply-chain": ("python", "scripts/agent_context/validate_supply_chain.py", "--workspace", "."),
    "supply-chain-negatives": ("python", "-m", "unittest", "scripts.agent_context.tests.test_w9e_supply_chain", "-q"),
    "trust-drift": ("python", "-m", "unittest", "scripts.agent_context.tests.test_w9d2_trust_identity", "-q"),
    "w9a-validator": ("python", "scripts/agent_context/validate_w9a_contract.py", "--workspace", "."),
    "w9f-focused": ("python", "-m", "unittest", "scripts.agent_context.tests.test_w9f_review_bundle", "-q"),
    "workspace-validator": ("python", "scripts/agent_context/validate_workspace.py", "--workspace", "."),
}
REQUIRED_CHECKS = frozenset(CHECK_COMMANDS)
CHECK_FIELDS = {"id", "command", "exit_code", "stdout_sha256", "stderr_sha256"}
FINDING_FIELDS = {"id", "severity", "status", "negative_tests", "closure_artifacts"}
BUNDLE_FIELDS = {
    "schema_version", "reviewed_root", "children", "trust_identity", "checks",
    "live_receipt", "closure_inventory", "findings", "input_limitation",
}
NORMALIZED_DURATION = re.compile(rb"Ran (\d+) tests? in [0-9.]+s")


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
    return {
        "commit": _git(root, "rev-parse", "HEAD"),
        "tree": _git(root, "rev-parse", "HEAD^{tree}"),
    }


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
        if (
            not isinstance(repository, dict)
            or not isinstance(repository.get("id"), str)
            or not isinstance(repository.get("path"), str)
        ):
            raise ReviewBundleError("repository registry entry is invalid")
        path = workspace / repository["path"]
        if not path.is_dir() or not (path / ".git").exists():
            raise ReviewBundleError(
                f"registered child is missing its direct Git identity: {repository['path']}"
            )
        identity = _git_identity(path)
        agents = path / "AGENTS.md"
        try:
            digest = hashlib.sha256(agents.read_bytes()).hexdigest()
        except OSError as error:
            raise ReviewBundleError(
                f"registered child instruction is missing: {repository['path']}: {error}"
            ) from error
        children.append({
            "id": repository["id"], "path": repository["path"],
            **identity, "agents_sha256": digest,
        })
    return sorted(children, key=lambda item: item["id"])


def _test_location(qualified: str) -> tuple[Path, str, str]:
    parts = qualified.split(".")
    if len(parts) < 3:
        raise ReviewBundleError(f"named negative test is malformed: {qualified}")
    return Path(*parts[:-2]).with_suffix(".py"), parts[-2], parts[-1]


def _closure_inventory(workspace: Path) -> dict[str, list[Any]]:
    register = _read_json(workspace / ".workspace/contracts/agent-context-w9a-findings.json")
    items = register.get("findings", []) + register.get("input_limitations", [])
    if not isinstance(items, list) or len(items) != 12:
        raise ReviewBundleError("W9a closure register must contain eleven findings and one limitation")
    artifact_paths = sorted({path for item in items for path in item.get("closure_artifacts", [])})
    named_tests = sorted({name for item in items for name in item.get("negative_tests", [])})
    artifacts: list[dict[str, str]] = []
    for relative in artifact_paths:
        if not isinstance(relative, str):
            raise ReviewBundleError("closure artifact path is not a string")
        try:
            w2b1._canonical_path(relative, "closure artifact")
        except w2b1.AgentContextError as error:
            raise ReviewBundleError(error.message) from error
        path = workspace / relative
        try:
            info = path.lstat()
            tracked = _git(workspace, "ls-files", "--error-unmatch", "--", relative)
        except (OSError, ReviewBundleError) as error:
            raise ReviewBundleError(f"closure artifact is missing or untracked: {relative}") from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or tracked != relative:
            raise ReviewBundleError(f"closure artifact is not one tracked regular file: {relative}")
        artifacts.append({"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    for qualified in named_tests:
        path, class_name, method_name = _test_location(qualified)
        absolute = workspace / path
        try:
            tree = ast.parse(absolute.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError) as error:
            raise ReviewBundleError(f"named negative test cannot be parsed: {qualified}: {error}") from error
        found = any(
            isinstance(node, ast.ClassDef)
            and node.name == class_name
            and any(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name == method_name
                for child in node.body
            )
            for node in tree.body
        )
        if not found:
            raise ReviewBundleError(f"named negative test method is missing: {qualified}")
    return {"artifacts": artifacts, "negative_tests": named_tests}


def _finding_dispositions(workspace: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    register = _read_json(workspace / ".workspace/contracts/agent-context-w9a-findings.json")
    findings = register.get("findings")
    limitations = register.get("input_limitations")
    if not isinstance(findings, list) or not isinstance(limitations, list) or len(limitations) != 1:
        raise ReviewBundleError("W9a finding register is incomplete")
    disposition = [{
        "id": finding["id"], "severity": finding["severity"],
        "status": "CLOSED_BY_REPLAYED_W9F_EVIDENCE",
        "negative_tests": finding["negative_tests"],
        "closure_artifacts": finding["closure_artifacts"],
    } for finding in findings]
    return sorted(disposition, key=lambda item: item["id"]), {
        "id": limitations[0]["id"],
        "status": "REPLACED_BY_REPLAYED_EXACT_TREE_BUNDLE",
    }


def _normalize_output(raw: bytes) -> bytes:
    return NORMALIZED_DURATION.sub(rb"Ran \1 tests", raw.replace(b"\r\n", b"\n"))


def _resolved_command(workspace: Path, command: Sequence[str]) -> tuple[str, ...]:
    if not command:
        raise ReviewBundleError("empty W9f check command")
    executable = command[0]
    if executable == "python":
        # Preserve the active virtual-environment entry point. Resolving its
        # symlink selects the base interpreter and silently drops venv packages.
        executable = str(Path(sys.executable).absolute())
    elif executable == "ruff":
        sibling = Path(sys.executable).absolute().parent / "ruff"
        resolved = sibling if sibling.is_file() else shutil.which("ruff")
        if resolved is None:
            raise ReviewBundleError("Ruff is unavailable for W9f replay")
        executable = str(Path(resolved).absolute())
    return (executable, *command[1:])


def run_checks(workspace: Path) -> list[dict[str, Any]]:
    """Execute the frozen root-only W9f matrix and bind normalized output."""
    environment = dict(os.environ)
    environment.update(PYTHONDONTWRITEBYTECODE="1", RUFF_NO_CACHE="1")
    results: list[dict[str, Any]] = []
    for check_id, logical in sorted(CHECK_COMMANDS.items()):
        command = _resolved_command(workspace, logical)
        completed = subprocess.run(
            command, cwd=workspace, capture_output=True, check=False, env=environment,
        )
        stdout = _normalize_output(completed.stdout)
        stderr = _normalize_output(completed.stderr)
        result = {
            "id": check_id, "command": list(logical), "exit_code": completed.returncode,
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        }
        if completed.returncode:
            raise ReviewBundleError(
                f"W9f check failed: {check_id}: {stderr.decode('utf-8', 'replace')[-1000:]}"
            )
        results.append(result)
    return results


def _validate_checks(checks: Any) -> None:
    if not isinstance(checks, list) or {
        item.get("id") for item in checks if isinstance(item, Mapping)
    } != REQUIRED_CHECKS:
        raise ReviewBundleError("review bundle is missing one or more minimum checks")
    for item in checks:
        if (
            not isinstance(item, Mapping) or set(item) != CHECK_FIELDS
            or item.get("command") != list(CHECK_COMMANDS.get(item.get("id"), ()))
            or item.get("exit_code") != 0
        ):
            raise ReviewBundleError("review bundle contains a failed or malformed check")
        w2b1._sha256(item.get("stdout_sha256"), "check stdout_sha256")
        w2b1._sha256(item.get("stderr_sha256"), "check stderr_sha256")


def _selected_trust_sha(identity: Mapping[str, Any], repositories: Sequence[str]) -> str:
    selected = set(repositories)
    value = deepcopy(dict(identity))
    children = value.get("children")
    if not isinstance(children, list):
        raise ReviewBundleError("trust identity children are invalid")
    value["children"] = [child for child in children if child.get("path") in selected]
    if {child.get("path") for child in value["children"]} != selected:
        raise ReviewBundleError("live receipt repositories do not match trust identity children")
    value["trust_identity_sha256"] = "0" * 64
    return w2b1.canonical_sha256({
        key: item for key, item in value.items() if key != "trust_identity_sha256"
    })


def _validate_live_receipt(live: Any, trust_identity: Mapping[str, Any]) -> None:
    if not isinstance(live, Mapping):
        raise ReviewBundleError("review bundle lacks its metadata-only live receipt")
    session = live.get("session")
    receipt = live.get("receipt")
    try:
        w2b1.validate_session(session)
        w2b1.validate_receipt(receipt)
    except w2b1.AgentContextError as error:
        raise ReviewBundleError(f"live receipt schema is invalid: {error}") from error
    if session["state"] != "COMPLETED" or receipt["state"] != "COMPLETED":
        raise ReviewBundleError("live receipt and session are not completed")
    shared = (
        "launch_id", "client_session_id", "generation", "manifest_id", "envelope_sha256",
        "capability_evidence_id", "trust_identity_sha256", "native_evidence_ids",
        "repositories", "tasks", "operations", "authorization_ids",
        "authorization_provenance", "sources",
    )
    if any(session[field] != receipt[field] for field in shared):
        raise ReviewBundleError("live session and receipt linkage diverges")
    if session["previous_receipt_sha256"] != receipt["receipt_id"]:
        raise ReviewBundleError("live session does not link its terminal receipt")
    expected_receipt_id = w2b1.canonical_sha256({
        key: item for key, item in receipt.items() if key != "receipt_id"
    })
    if receipt["receipt_id"] != expected_receipt_id:
        raise ReviewBundleError("live receipt identifier does not recompute")
    if receipt["trust_identity_sha256"] != _selected_trust_sha(
        trust_identity, receipt["repositories"]
    ):
        raise ReviewBundleError("live receipt trust identity is stale or mismatched")
    if receipt["authorization_ids"] and trust_identity.get("authorization_trust_store_sha256") is None:
        raise ReviewBundleError("authorized live receipt lacks an external trust-store identity")


def build_bundle(
    *, workspace: Path, live_runtime: Path, codex_binary: Path, codex_version: str,
    authorization_trust_store: Path | None = None,
    checks: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a W9f bundle only after current evidence has been executed."""
    root = workspace.resolve(strict=True)
    children = _children(root)
    closure = _closure_inventory(root)
    check_results = [dict(item) for item in checks] if checks is not None else run_checks(root)
    _validate_checks(check_results)
    identity = build_trust_identity(
        workspace_root=root,
        selected_repositories=tuple(root / child["path"] for child in children),
        capability_path="scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md",
        codex_binary=codex_binary, codex_version=codex_version,
        authorization_trust_store=authorization_trust_store,
    )
    live = {
        "session": _regular_json(live_runtime / "session.json"),
        "receipt": _regular_json(live_runtime / "receipt.json"),
    }
    _validate_live_receipt(live, identity)
    findings, limitation = _finding_dispositions(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "reviewed_root": _git_identity(root),
        "children": children,
        "trust_identity": identity,
        "checks": check_results,
        "live_receipt": live,
        "closure_inventory": closure,
        "findings": findings,
        "input_limitation": limitation,
    }


def canonical_bytes(bundle: Mapping[str, Any]) -> bytes:
    return w2b1.canonical_bytes(dict(bundle)) + b"\n"


def validate_bundle(
    bundle: Mapping[str, Any], *, workspace: Path,
    codex_binary: Path | None = None, codex_version: str | None = None,
    authorization_trust_store: Path | None = None, replay_checks: bool = True,
    check_runner: Callable[[Path], list[dict[str, Any]]] = run_checks,
) -> None:
    """Recompute identities and, by default, replay the complete check matrix."""
    if set(bundle) != BUNDLE_FIELDS or bundle.get("schema_version") != SCHEMA_VERSION:
        raise ReviewBundleError("review bundle has an invalid closed shape")
    root = workspace.resolve(strict=True)
    if bundle["reviewed_root"] != _git_identity(root):
        raise ReviewBundleError("review bundle root commit/tree or clean proof drifted")
    expected_children = _children(root)
    if bundle["children"] != expected_children:
        raise ReviewBundleError("review bundle child Git or instruction identity drifted")
    _validate_checks(bundle["checks"])
    if replay_checks and bundle["checks"] != check_runner(root):
        raise ReviewBundleError("review bundle check replay differs from recorded results")
    expected_closure = _closure_inventory(root)
    if bundle["closure_inventory"] != expected_closure:
        raise ReviewBundleError("review bundle closure inventory drifted")
    binary = codex_binary or Path(shutil.which("codex") or "")
    try:
        binary = binary.resolve(strict=True)
    except OSError as error:
        raise ReviewBundleError(f"Codex binary cannot be resolved: {error}") from error
    version = codex_version or _codex_version(binary)
    expected_trust = build_trust_identity(
        workspace_root=root,
        selected_repositories=tuple(root / child["path"] for child in expected_children),
        capability_path="scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md",
        codex_binary=binary, codex_version=version,
        authorization_trust_store=authorization_trust_store,
    )
    if bundle["trust_identity"] != expected_trust:
        raise ReviewBundleError("review bundle trust identity drifted")
    _validate_live_receipt(bundle["live_receipt"], expected_trust)
    expected_findings, expected_limitation = _finding_dispositions(root)
    if bundle["findings"] != expected_findings:
        raise ReviewBundleError("review bundle finding evidence is missing or stale")
    for finding in bundle["findings"]:
        if set(finding) != FINDING_FIELDS:
            raise ReviewBundleError("review bundle finding disposition has an invalid shape")
    if bundle["input_limitation"] != expected_limitation:
        raise ReviewBundleError("review bundle does not replace the prior input limitation")


def write_bundle(path: Path, bundle: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(bundle))
    os.chmod(path, 0o600)


def _codex_version(binary: Path) -> str:
    result = subprocess.run((str(binary), "--version"), capture_output=True, check=False)
    if result.returncode:
        raise ReviewBundleError("Codex version probe failed")
    try:
        return result.stdout.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as error:
        raise ReviewBundleError("Codex version probe is not UTF-8") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="build or replay a W9f exact-tree review bundle")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live-runtime", type=Path)
    parser.add_argument("--verify", action="store_true", help="replay and verify an existing bundle")
    parser.add_argument("--codex-binary", type=Path)
    parser.add_argument("--codex-version")
    parser.add_argument("--authorization-trust-store", type=Path)
    arguments = parser.parse_args(argv)
    try:
        binary = arguments.codex_binary or Path(shutil.which("codex") or "")
        binary = binary.resolve(strict=True)
        version = arguments.codex_version or _codex_version(binary)
        if arguments.verify:
            validate_bundle(
                _read_json(arguments.output), workspace=arguments.workspace,
                codex_binary=binary, codex_version=version,
                authorization_trust_store=arguments.authorization_trust_store,
            )
            print(f"W9f review bundle replay passed: {arguments.output}")
            return 0
        if arguments.live_runtime is None:
            raise ReviewBundleError("--live-runtime is required when building a bundle")
        bundle = build_bundle(
            workspace=arguments.workspace, live_runtime=arguments.live_runtime,
            codex_binary=binary, codex_version=version,
            authorization_trust_store=arguments.authorization_trust_store,
        )
        validate_bundle(
            bundle, workspace=arguments.workspace, codex_binary=binary,
            codex_version=version,
            authorization_trust_store=arguments.authorization_trust_store,
            replay_checks=False,
        )
        write_bundle(arguments.output, bundle)
    except (OSError, ReviewBundleError, w2b1.AgentContextError) as error:
        print(f"W9f review bundle failed: {error}")
        return 1
    print(f"W9f review bundle written: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
