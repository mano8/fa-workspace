"""Statically validate the compact root Claude bootstrap for Phase 5.4."""

from __future__ import annotations

import argparse
import re
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
    "cannot authorize sibling\nwork",
    "current Claude capability evidence is limited",
    "recorded human authorization",
    "This bootstrap does not invoke the resolver or hand off context.",
    "This\nfile never imports `AGENTS.md`.",
)
FORBIDDEN_PHRASES = (
    "/workspace",
    "/.workspace",
    "transitional-v1-bundles",
    "co-authored-by",
    "<!--",
    "codex",
)
FORBIDDEN_IMPORT_PATTERNS = (
    r"(?im)^\s*@(?:/)?AGENTS\.md\s*$",
    r"(?im)^\s*import\s+.*AGENTS\.md\s*$",
)


class RootClaudeValidationError(ValueError):
    """Raised when the root Claude bootstrap stops meeting its static contract."""


@dataclass(frozen=True)
class RootClaudeValidationReport:
    byte_count: int
    reference_count: int


def _fail(message: str) -> None:
    raise RootClaudeValidationError(message)


def validate_root_claude(workspace: Path) -> RootClaudeValidationReport:
    """Validate size, visible marker, canonical links, scope, and no cross-agent import."""

    path = workspace.resolve() / "CLAUDE.md"
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        _fail(f"could not read root CLAUDE.md as strict UTF-8: {error}")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        _fail("root CLAUDE.md must be UTF-8 without BOM, LF, and final newline")
    if len(raw) > MAX_BOOTSTRAP_BYTES:
        _fail(f"root CLAUDE.md exceeds {MAX_BOOTSTRAP_BYTES}-byte bootstrap budget")
    if VERSION_MARKER not in text:
        _fail("root CLAUDE.md is missing the visible workspace instruction-set marker")
    missing_references = [reference for reference in REQUIRED_REFERENCES if reference not in text]
    if missing_references:
        _fail("root CLAUDE.md is missing canonical references: " + ", ".join(missing_references))
    missing_phrases = [phrase for phrase in REQUIRED_PHRASES if phrase not in text]
    if missing_phrases:
        _fail("root CLAUDE.md is missing required scope, capability, task, or delivery wording")
    present_forbidden = [phrase for phrase in FORBIDDEN_PHRASES if phrase.casefold() in text.casefold()]
    if present_forbidden:
        _fail("root CLAUDE.md contains forbidden stale, hidden, or cross-agent content: " + ", ".join(present_forbidden))
    if any(re.search(pattern, text) for pattern in FORBIDDEN_IMPORT_PATTERNS):
        _fail("root CLAUDE.md imports root AGENTS.md")
    return RootClaudeValidationReport(
        byte_count=len(raw), reference_count=len(REQUIRED_REFERENCES)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace", type=Path, default=Path(__file__).resolve().parents[2]
    )
    arguments = parser.parse_args()
    try:
        report = validate_root_claude(arguments.workspace)
    except RootClaudeValidationError as error:
        print(f"root CLAUDE validation failed: {error}")
        return 2
    print(
        "root CLAUDE validation passed: "
        f"{report.byte_count} bytes, {report.reference_count} canonical references"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
