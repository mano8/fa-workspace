"""Enforce the narrow Phase 7 migration guards for root-owned configuration.

This is deliberately not a general security scanner. Secret scanning remains
owned by the established dedicated tooling; these checks only preserve the
portable bootstrap, cross-agent separation, TODO-plan hook protection, and the
authorship restriction already stated in the workspace Git policy.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


MIGRATION_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    ".claude/settings.json",
    ".codex/config.toml",
)
FORBIDDEN_HOST_PATHS = ("/workspace", "\\workspace", "/.workspace", "\\.workspace")
FORBIDDEN_AUTHORSHIP_METADATA = ("co-authored-by",)
TODO_PLAN_PROBE = ".workspace/plans/.migration-guard-fixture.md"
REQUIRED_HOOKS = ("pre-commit", "pre-push")
TODO_HOOK_GUARD = "git check-ignore --no-index --stdin -q"
CROSS_AGENT_IMPORTS = {
    "AGENTS.md": "CLAUDE.md",
    "CLAUDE.md": "AGENTS.md",
}


class MigrationGuardError(ValueError):
    """Raised when a root migration protection is weakened."""


@dataclass(frozen=True)
class MigrationGuardReport:
    checked_file_count: int
    checked_hook_count: int


def _fail(message: str) -> None:
    raise MigrationGuardError(message)


def _read_migration_file(workspace: Path, relative_path: str) -> str:
    path = workspace / relative_path
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        _fail(f"could not read {relative_path} as strict UTF-8: {error}")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        _fail(f"{relative_path} must be UTF-8 without BOM, LF, and final newline")
    return text


def _forbidden_import_pattern(target: str) -> re.Pattern[str]:
    escaped_target = re.escape(target)
    return re.compile(
        rf"(?im)^\s*(?:@|import\s+)(?:\./|/)?{escaped_target}\s*$"
    )


def _validate_todo_plan_protection(workspace: Path) -> None:
    try:
        ignored = subprocess.run(
            ["git", "-C", str(workspace), "check-ignore", "--no-index", "-q", TODO_PLAN_PROBE],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        _fail(f"could not verify TODO-plan ignore protection: {error}")
    if ignored.returncode != 0:
        _fail("TODO-plan probe is no longer ignored")
    for name in REQUIRED_HOOKS:
        try:
            hook = (workspace / ".githooks" / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            _fail(f"could not read TODO-plan protection hook {name}: {error}")
        if TODO_HOOK_GUARD not in hook:
            _fail(f"TODO-plan protection hook {name} no longer checks ignored staged paths")


def validate_migration_guards(workspace: Path) -> MigrationGuardReport:
    """Validate only the root migration protections required by Phase 7.4."""

    workspace = workspace.resolve()
    contents = {
        relative_path: _read_migration_file(workspace, relative_path)
        for relative_path in MIGRATION_FILES
    }
    for relative_path, text in contents.items():
        lowered = text.casefold()
        present_paths = [value for value in FORBIDDEN_HOST_PATHS if value.casefold() in lowered]
        if present_paths:
            _fail(f"{relative_path} contains forbidden host/workspace paths: {', '.join(present_paths)}")
        present_authorship = [
            value for value in FORBIDDEN_AUTHORSHIP_METADATA if value.casefold() in lowered
        ]
        if present_authorship:
            _fail(f"{relative_path} contains forbidden authorship metadata: {', '.join(present_authorship)}")
    for source, target in CROSS_AGENT_IMPORTS.items():
        if _forbidden_import_pattern(target).search(contents[source]):
            _fail(f"{source} imports {target}")
    _validate_todo_plan_protection(workspace)
    return MigrationGuardReport(len(MIGRATION_FILES), len(REQUIRED_HOOKS))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[2])
    arguments = parser.parse_args(argv)
    try:
        report = validate_migration_guards(arguments.workspace)
    except MigrationGuardError as error:
        print(f"migration guard validation failed: {error}")
        return 2
    print(
        "migration guard validation passed: "
        f"{report.checked_file_count} root configuration files, {report.checked_hook_count} hooks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
