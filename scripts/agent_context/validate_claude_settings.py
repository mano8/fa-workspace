"""Statically validate the portable root Claude project settings for Phase 5.5."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_URL = "https://json.schemastore.org/claude-code-settings.json"
ALLOW_RULES = (
    "Bash(pip-audit -r *)",
    "Bash(bandit -r *)",
    "Bash(python -m pytest *)",
    "Bash(ruff format *)",
    "Bash(ruff format --check *)",
)
ASK_RULES = (
    "Bash(rm *)",
    "Bash(git clean *)",
    "Bash(git reset *)",
    "Bash(git restore *)",
    "Bash(git push *)",
    "Bash(curl *)",
    "Bash(wget *)",
    "WebFetch",
    "Bash(docker compose *)",
)
DENY_RULES = (
    "Read(./.env.local)",
    "Read(./.env.devcontainer)",
    "Read(./.claude/settings.local.json)",
)
FORBIDDEN_KEYS = frozenset(
    {
        "additionalDirectories",
        "attribution",
        "autoMemoryDirectory",
        "env",
        "hooks",
    }
)


class ClaudeSettingsValidationError(ValueError):
    """Raised when root Claude settings stop meeting the Phase 5.5 contract."""


@dataclass(frozen=True)
class ClaudeSettingsValidationReport:
    byte_count: int
    allow_rule_count: int
    ask_rule_count: int
    deny_rule_count: int


def _fail(message: str) -> None:
    raise ClaudeSettingsValidationError(message)


def _read_settings(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(f"could not read project Claude settings as strict JSON UTF-8: {error}")
    if not isinstance(value, dict):
        _fail("project Claude settings must be a JSON object")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        _fail("project Claude settings must be UTF-8 without BOM, LF, and final newline")
    return raw, value


def validate_claude_settings(workspace: Path) -> ClaudeSettingsValidationReport:
    """Validate portable, least-privilege, project-shared Claude settings."""

    path = workspace.resolve() / ".claude" / "settings.json"
    raw, settings = _read_settings(path)
    expected_keys = {"$schema", "autoMemoryEnabled", "permissions"}
    if set(settings) != expected_keys:
        _fail("project Claude settings contain unsupported shared configuration keys")
    if settings["$schema"] != SCHEMA_URL:
        _fail("project Claude settings must use the official Claude settings schema")
    if settings["autoMemoryEnabled"] is not False:
        _fail("project Claude auto-memory must be explicitly disabled")

    permissions = settings["permissions"]
    if not isinstance(permissions, dict):
        _fail("project Claude permissions must be an object")
    expected_permission_keys = {"defaultMode", "allow", "ask", "deny"}
    if set(permissions) != expected_permission_keys:
        _fail("project Claude permissions contain unsupported or missing keys")
    if permissions["defaultMode"] != "default":
        _fail("project Claude permissions must retain the default approval mode")
    if tuple(permissions["allow"]) != ALLOW_RULES:
        _fail("project Claude settings contain unreviewed or personal command approvals")
    if tuple(permissions["ask"]) != ASK_RULES:
        _fail("project Claude confirmation rules must cover only defined destructive/network actions")
    if tuple(permissions["deny"]) != DENY_RULES:
        _fail("project Claude deny rules must cover only measured local-sensitive paths")
    if FORBIDDEN_KEYS.intersection(settings) or FORBIDDEN_KEYS.intersection(permissions):
        _fail("project Claude settings contain personal paths, attribution, or active tooling")
    return ClaudeSettingsValidationReport(
        byte_count=len(raw), allow_rule_count=len(ALLOW_RULES),
        ask_rule_count=len(ASK_RULES), deny_rule_count=len(DENY_RULES)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace", type=Path, default=Path(__file__).resolve().parents[2]
    )
    arguments = parser.parse_args()
    try:
        report = validate_claude_settings(arguments.workspace)
    except ClaudeSettingsValidationError as error:
        print(f"Claude settings validation failed: {error}")
        return 2
    print(
        "Claude settings validation passed: "
        f"{report.byte_count} bytes, {report.allow_rule_count} shared allow rules, "
        f"{report.ask_rule_count} confirmation rules, "
        f"{report.deny_rule_count} local-sensitive path rules"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
