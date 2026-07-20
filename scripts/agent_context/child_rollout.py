"""Phase 8.1 standalone-child rollout contract validation and selection.

This module does not edit a child or activate a client.  It validates the
root-owned C01--C16 boundary record and models the two permitted instruction
selection modes used by synthetic resolver fixtures: optional parent
enhancement when a reviewed workspace is supplied, and local-only standalone
operation when it is absent.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from agent_context import w2b1


ROLLOUT_RECORD = Path(
    ".workspace/contracts/child-repository-rollout-v1.boundaries.json"
)
CONTRACT_ID = "m8-child-repository-rollout-v1"
AGENT_ENTRYPOINTS = {"claude": "CLAUDE.md", "codex": "AGENTS.md"}
EXACT_ALLOWLIST = ["AGENTS.md", "CLAUDE.md", "REPOSITORY_CONTEXT.md"]
CLASSIFICATIONS = {"neutral-asymmetric", "neutral-semantic-duplicate"}
TOP_FIELDS = {
    "schema_version",
    "contract_id",
    "frozen_on",
    "source_evidence",
    "boundaries",
}
SOURCE_FIELDS = {"path", "sha256"}
BOUNDARY_FIELDS = {
    "boundary_id",
    "phase_step",
    "repository_id",
    "classification",
    "decision",
    "input_files",
    "exact_allowlist",
    "required_neutral_owner",
    "reconciliation_gates",
    "observed_auxiliary_sources",
}
INPUT_FIELDS = {"path", "bytes", "sha256"}


class ChildRolloutError(ValueError):
    """Raised when the frozen rollout boundary or mode is invalid."""


@dataclass(frozen=True)
class ChildInstructionSelection:
    """Local instruction sources and optional-parent disposition for one child."""

    repository_id: str
    agent: str
    mode: str
    local_sources: tuple[str, str]
    workspace_enhancement_available: bool
    canonical_receipt_required: bool


def _fail(message: str) -> None:
    raise ChildRolloutError(message)


def _closed(value: Any, fields: set[str], description: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"{description} fields do not match the frozen shape")
    return value


def _regular_contained(root: Path, relative: str, description: str) -> Path:
    try:
        w2b1._canonical_path(relative, description)
        candidate = root.joinpath(*relative.split("/"))
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError, w2b1.AgentContextError) as error:
        _fail(f"{description} is unavailable or escapes its owner: {error}")
    if candidate.is_symlink() or not resolved.is_file():
        _fail(f"{description} must be a contained regular file")
    return resolved


def _normalized_bytes(path: Path, description: str) -> bytes:
    try:
        raw = path.read_bytes()
        raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        _fail(f"{description} is not strict UTF-8: {error}")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        _fail(f"{description} must be UTF-8 without BOM, LF, and final newline")
    return raw


def validate_rollout_record(
    workspace: Path,
    registry: Mapping[str, Any],
    record: Mapping[str, Any],
    *,
    verify_live_inputs: bool = False,
    verify_live_boundary_ids: set[str] | None = None,
) -> None:
    """Validate the closed root record, optionally rehashing saved live inputs."""
    workspace = workspace.resolve()
    _closed(record, TOP_FIELDS, "rollout record")
    if record["schema_version"] != 1 or record["contract_id"] != CONTRACT_ID:
        _fail("rollout record identity is not the frozen Phase 8.1 contract")
    if record["frozen_on"] != "2026-07-20":
        _fail("rollout record frozen date is unexpected")
    try:
        w2b1.validate_registry_v2(registry, index_mode="faceted")
    except w2b1.AgentContextError as error:
        _fail(f"registry is invalid for child rollout: {error}")

    sources = record["source_evidence"]
    if not isinstance(sources, list) or not sources:
        _fail("source_evidence must be a non-empty array")
    source_paths: list[str] = []
    for index, supplied in enumerate(sources):
        source = _closed(supplied, SOURCE_FIELDS, f"source_evidence[{index}]")
        path = source["path"]
        if not isinstance(path, str) or not isinstance(source["sha256"], str):
            _fail("source evidence path/hash must be strings")
        target = _regular_contained(workspace, path, f"source evidence {path}")
        if hashlib.sha256(target.read_bytes()).hexdigest() != source["sha256"]:
            _fail(f"source evidence drifted: {path}")
        source_paths.append(path)
    if source_paths != sorted(set(source_paths)):
        _fail("source evidence paths must be unique and sorted")

    repositories = {item["id"]: item for item in registry["repositories"]}
    boundaries = record["boundaries"]
    if not isinstance(boundaries, list) or len(boundaries) != len(repositories):
        _fail("rollout record must contain one boundary per registered repository")
    known_boundary_ids = {f"C{offset:02d}" for offset in range(1, len(boundaries) + 1)}
    if verify_live_boundary_ids is not None:
        if not verify_live_inputs:
            _fail("live boundary selection requires live input verification")
        if not verify_live_boundary_ids <= known_boundary_ids:
            _fail("live boundary selection contains an unknown boundary")
    elif verify_live_inputs:
        verify_live_boundary_ids = known_boundary_ids

    seen_repositories: set[str] = set()
    for offset, supplied in enumerate(boundaries, start=1):
        boundary = _closed(supplied, BOUNDARY_FIELDS, f"boundary C{offset:02d}")
        expected_id = f"C{offset:02d}"
        if boundary["boundary_id"] != expected_id:
            _fail("boundaries must retain C01--C16 order")
        expected_step = f"8.{offset + 1}"
        if boundary["phase_step"] != expected_step:
            _fail(f"{expected_id} has the wrong Phase 8 step")
        repository_id = boundary["repository_id"]
        if repository_id not in repositories or repository_id in seen_repositories:
            _fail(f"{expected_id} has an unknown or duplicate repository")
        seen_repositories.add(repository_id)
        if boundary["classification"] not in CLASSIFICATIONS:
            _fail(f"{expected_id} has an unknown classification")
        if boundary["decision"] != "extract-neutral-local-context":
            _fail(f"{expected_id} has an unsupported migration decision")
        if boundary["exact_allowlist"] != EXACT_ALLOWLIST:
            _fail(f"{expected_id} must use the frozen three-path allowlist")
        if boundary["required_neutral_owner"] != "REPOSITORY_CONTEXT.md":
            _fail(f"{expected_id} must use the frozen neutral owner")
        gates = boundary["reconciliation_gates"]
        if not isinstance(gates, list) or not gates or any(
            not isinstance(gate, str) or not gate for gate in gates
        ):
            _fail(f"{expected_id} must declare reconciliation gates")
        if boundary["observed_auxiliary_sources"] != []:
            _fail(f"{expected_id} has unapproved auxiliary agent sources")
        inputs = boundary["input_files"]
        if not isinstance(inputs, list) or [item.get("path") for item in inputs] != [
            "AGENTS.md",
            "CLAUDE.md",
        ]:
            _fail(f"{expected_id} must record the two classified input files")
        for supplied_input in inputs:
            item = _closed(supplied_input, INPUT_FIELDS, f"{expected_id} input")
            if (
                not isinstance(item["bytes"], int)
                or item["bytes"] < 0
                or not isinstance(item["sha256"], str)
            ):
                _fail(f"{expected_id} input identity is invalid")
            try:
                w2b1._sha256(item["sha256"], f"{expected_id} input sha256")
            except w2b1.AgentContextError as error:
                _fail(str(error))
            if boundary["boundary_id"] in (verify_live_boundary_ids or set()):
                relative = f"{repositories[repository_id]['path']}/{item['path']}"
                raw = _regular_contained(workspace, relative, f"{expected_id} input").read_bytes()
                if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                    _fail(f"{expected_id} live input drifted: {item['path']}")
    if seen_repositories != set(repositories):
        _fail("rollout record does not cover the exact registry repository set")


def resolve_child_instruction_context(
    child_root: Path,
    *,
    repository_id: str,
    agent: str,
    workspace_root: Path | None = None,
) -> ChildInstructionSelection:
    """Select child-local sources with an optional reviewed-parent enhancement."""
    if agent not in AGENT_ENTRYPOINTS:
        _fail("agent must be codex or claude")
    child_root = child_root.resolve(strict=True)
    entrypoint = AGENT_ENTRYPOINTS[agent]
    for relative in ("REPOSITORY_CONTEXT.md", entrypoint):
        source = _regular_contained(child_root, relative, f"child source {relative}")
        _normalized_bytes(source, f"child source {relative}")
    local_sources = ("REPOSITORY_CONTEXT.md", entrypoint)
    if workspace_root is None:
        return ChildInstructionSelection(
            repository_id,
            agent,
            "parent-absent",
            local_sources,
            False,
            False,
        )

    workspace_root = workspace_root.resolve(strict=True)
    marker = _regular_contained(workspace_root, ".m8-workspace-root", "workspace marker")
    if marker.read_bytes() != b"m8-workspace-v2\n":
        _fail("workspace marker identity is invalid")
    try:
        registry = w2b1.parse_strict_json(
            _regular_contained(
                workspace_root, ".workspace/repo-types.json", "workspace registry"
            ).read_bytes()
        )
        w2b1.validate_registry_v2(registry, index_mode="faceted")
    except w2b1.AgentContextError as error:
        _fail(f"workspace registry is invalid: {error}")
    matches = [item for item in registry["repositories"] if item["id"] == repository_id]
    if len(matches) != 1:
        _fail("child is not registered exactly once in the supplied workspace")
    expected = workspace_root / matches[0]["path"]
    if expected.resolve(strict=True) != child_root or child_root.parent != workspace_root:
        _fail("child is not the registered direct child of the supplied workspace")
    return ChildInstructionSelection(
        repository_id,
        agent,
        "parent-found",
        local_sources,
        True,
        True,
    )
