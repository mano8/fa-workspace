"""Statically validate the compact root Codex bootstrap for Phase 5.3."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


MAX_BOOTSTRAP_BYTES = 2048
VERSION_MARKER = "Workspace instruction set: m8-workspace-v2"
REQUIRED_REFERENCES = (
    ".workspace/architecture.md",
    ".workspace/invariants.json",
    ".workspace/context/env.md",
    ".workspace/repo-types.json",
    ".workspace/policy.index.json",
    ".workspace/policy.metadata.json",
    ".workspace/contracts/agent-context-w2a.contract.md",
)
REQUIRED_PHRASES = (
    "registered direct child",
    "apply only within that repository",
    "cannot authorize sibling work",
    "always` units, then declared facets",
    "explicitly requested task overlays",
    "recorded human authorization",
    "This bootstrap does not invoke the resolver or\nhand off context.",
    "This file never imports `CLAUDE.md`.",
)
FORBIDDEN_PHRASES = (
    "/workspace",
    "/.workspace",
    "transitional-v1-bundles",
    "co-authored-by",
)


class RootAgentsValidationError(ValueError):
    """Raised when the root Codex bootstrap stops meeting its static contract."""


@dataclass(frozen=True)
class RootAgentsValidationReport:
    byte_count: int
    reference_count: int


def _fail(message: str) -> None:
    raise RootAgentsValidationError(message)


def validate_root_agents(workspace: Path) -> RootAgentsValidationReport:
    """Validate size, encoding, canonical links, scope, and delivery wording."""

    path = workspace.resolve() / "AGENTS.md"
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        _fail(f"could not read root AGENTS.md as strict UTF-8: {error}")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        _fail("root AGENTS.md must be UTF-8 without BOM, LF, and final newline")
    if len(raw) > MAX_BOOTSTRAP_BYTES:
        _fail(f"root AGENTS.md exceeds {MAX_BOOTSTRAP_BYTES}-byte bootstrap budget")
    if VERSION_MARKER not in text:
        _fail("root AGENTS.md is missing the visible workspace instruction-set marker")
    missing_references = [reference for reference in REQUIRED_REFERENCES if reference not in text]
    if missing_references:
        _fail("root AGENTS.md is missing canonical references: " + ", ".join(missing_references))
    missing_phrases = [phrase for phrase in REQUIRED_PHRASES if phrase not in text]
    if missing_phrases:
        _fail("root AGENTS.md is missing required scope, task, or delivery wording")
    present_forbidden = [phrase for phrase in FORBIDDEN_PHRASES if phrase.casefold() in text.casefold()]
    if present_forbidden:
        _fail("root AGENTS.md contains forbidden stale or host-specific content: " + ", ".join(present_forbidden))
    return RootAgentsValidationReport(
        byte_count=len(raw), reference_count=len(REQUIRED_REFERENCES)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace", type=Path, default=Path(__file__).resolve().parents[2]
    )
    arguments = parser.parse_args()
    try:
        report = validate_root_agents(arguments.workspace)
    except RootAgentsValidationError as error:
        print(f"root AGENTS validation failed: {error}")
        return 2
    print(
        "root AGENTS validation passed: "
        f"{report.byte_count} bytes, {report.reference_count} canonical references"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
