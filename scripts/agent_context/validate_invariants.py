"""Validate canonical workspace-invariant ownership and references."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context import w2b1


INVARIANT_ID = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
DEFINITION = re.compile(r"^### `(?P<id>[A-Z][A-Z0-9-]+)`$", re.MULTILINE)
REFERENCE = re.compile(
    r"\[`(?P<id>[A-Z][A-Z0-9-]+)`\]"
    r"\((?P<path>[^)#]*)#(?P<anchor>[a-z0-9-]+)\)"
)


class InvariantValidationError(ValueError):
    """Raised when invariant ownership or a reference is invalid."""


@dataclass(frozen=True)
class InvariantValidationReport:
    invariant_count: int
    definition_count: int
    reference_count: int
    tracked_tool_copy_count: int


def _fail(message: str) -> None:
    raise InvariantValidationError(message)


def _catalog(workspace: Path) -> dict[str, PurePosixPath]:
    catalog_path = workspace / ".workspace/invariants.json"
    try:
        value = w2b1.parse_strict_json(catalog_path.read_bytes())
    except (OSError, w2b1.AgentContextError) as error:
        _fail(f"invalid invariant catalog: {error}")
    if not isinstance(value, dict) or set(value) != {"schema_version", "invariants"}:
        _fail("invariant catalog must contain only schema_version and invariants")
    if value["schema_version"] != 1 or not isinstance(value["invariants"], list):
        _fail("invariant catalog schema_version or invariants is invalid")

    owners: dict[str, PurePosixPath] = {}
    supplied_ids: list[str] = []
    for position, supplied in enumerate(value["invariants"]):
        if not isinstance(supplied, dict) or set(supplied) != {"id", "owner"}:
            _fail(f"invariant catalog entry {position} must contain only id and owner")
        invariant_id = supplied["id"]
        owner = supplied["owner"]
        if not isinstance(invariant_id, str) or INVARIANT_ID.fullmatch(invariant_id) is None:
            _fail(f"invalid invariant id at entry {position}")
        if invariant_id in owners:
            _fail(f"duplicate invariant catalog id: {invariant_id}")
        if not isinstance(owner, str):
            _fail(f"invalid invariant owner for {invariant_id}")
        owner_path = PurePosixPath(owner)
        if owner_path.is_absolute() or ".." in owner_path.parts or owner_path.suffix != ".md":
            _fail(f"invariant owner must be a workspace-relative Markdown path: {owner}")
        owners[invariant_id] = owner_path
        supplied_ids.append(invariant_id)
    if not owners:
        _fail("invariant catalog must not be empty")
    if supplied_ids != sorted(supplied_ids):
        _fail("invariant catalog entries must be sorted by id")
    return owners


def _normative_markdown(workspace: Path) -> tuple[Path, ...]:
    shared = workspace / ".workspace"
    paths = [shared / "architecture.md"]
    paths.extend(sorted((shared / "context").glob("**/*.md")))
    paths.extend(sorted((shared / "contracts").glob("**/*.md")))
    return tuple(paths)


def _read_markdown(path: Path) -> str:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        _fail(f"could not read normative Markdown {path}: {error}")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        _fail(f"normative Markdown must be UTF-8 without BOM, LF, and final newline: {path}")
    return text


def _tracked_paths(workspace: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "-C", str(workspace), "ls-files", "-z", "--", ".claude", ".codex"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        _fail("could not inspect tracked tool-specific paths")
    return tuple(path for path in result.stdout.decode("utf-8").split("\0") if path)


def _is_authoritative_tool_copy(path: str) -> bool:
    candidate = PurePosixPath(path)
    if not candidate.parts or candidate.parts[0] not in {".claude", ".codex"}:
        return False
    relative = PurePosixPath(*candidate.parts[1:])
    return (
        relative in {
            PurePosixPath("architecture.md"),
            PurePosixPath("invariants.json"),
            PurePosixPath("policy.index.json"),
            PurePosixPath("repo-types.json"),
        }
        or (relative.parts and relative.parts[0] in {"context", "contracts"})
    )


def validate_workspace_invariants(
    workspace: Path, *, tracked_paths: Sequence[str] | None = None
) -> InvariantValidationReport:
    """Validate unique definitions, resolved references, and tool-dir ownership."""

    workspace = workspace.resolve()
    owners = _catalog(workspace)
    documents = _normative_markdown(workspace)
    texts = {path: _read_markdown(path) for path in documents}

    definitions: dict[str, list[Path]] = {}
    for path, text in texts.items():
        for match in DEFINITION.finditer(text):
            definitions.setdefault(match.group("id"), []).append(path)
    unknown_definitions = sorted(set(definitions) - set(owners))
    if unknown_definitions:
        _fail(f"unregistered invariant definitions: {', '.join(unknown_definitions)}")
    for invariant_id, owner in owners.items():
        expected_owner = (workspace / ".workspace" / Path(owner)).resolve()
        locations = definitions.get(invariant_id, [])
        if locations != [expected_owner]:
            rendered = ", ".join(str(path) for path in locations) or "none"
            _fail(
                f"invariant {invariant_id} must have exactly one definition in "
                f"{expected_owner}; found {rendered}"
            )

    reference_count = 0
    for source, text in texts.items():
        for match in REFERENCE.finditer(text):
            reference_count += 1
            invariant_id = match.group("id")
            if invariant_id not in owners:
                _fail(f"unresolved invariant reference {invariant_id} in {source}")
            target_text = match.group("path")
            target = source if not target_text else (source.parent / target_text).resolve()
            expected = (workspace / ".workspace" / Path(owners[invariant_id])).resolve()
            expected_anchor = invariant_id.lower()
            if target != expected or match.group("anchor") != expected_anchor:
                _fail(f"invariant reference {invariant_id} in {source} targets the wrong owner")

    inspected_paths = tuple(tracked_paths) if tracked_paths is not None else _tracked_paths(workspace)
    authoritative_copies = sorted(
        path for path in inspected_paths if _is_authoritative_tool_copy(path)
    )
    if authoritative_copies:
        _fail(
            "authoritative shared copies are tracked under tool-specific directories: "
            + ", ".join(authoritative_copies)
        )
    return InvariantValidationReport(
        invariant_count=len(owners),
        definition_count=sum(len(locations) for locations in definitions.values()),
        reference_count=reference_count,
        tracked_tool_copy_count=0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace", type=Path, default=Path(__file__).resolve().parents[2]
    )
    arguments = parser.parse_args()
    try:
        report = validate_workspace_invariants(arguments.workspace)
    except InvariantValidationError as error:
        print(f"invariant validation failed: {error}")
        return 2
    print(
        "invariant validation passed: "
        f"{report.invariant_count} invariants, "
        f"{report.definition_count} definitions, "
        f"{report.reference_count} references, "
        "0 tracked tool-specific copies"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
