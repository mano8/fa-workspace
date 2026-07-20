"""Statically validate the portable root Codex project configuration for Phase 6.1."""

from __future__ import annotations

import argparse
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EXPECTED_SETTINGS: dict[str, Any] = {
    "approval_policy": "on-request",
    "sandbox_mode": "workspace-write",
    "web_search": "cached",
    "windows": {"sandbox": "unelevated"},
}


class CodexConfigValidationError(ValueError):
    """Raised when root Codex settings stop meeting the Phase 6.1 contract."""


@dataclass(frozen=True)
class CodexConfigValidationReport:
    byte_count: int
    setting_count: int


def _fail(message: str) -> None:
    raise CodexConfigValidationError(message)


def _read_config(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
            _fail("project Codex configuration must be UTF-8 without BOM, LF, and final newline")
        value = tomllib.loads(raw.decode("utf-8", errors="strict"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        _fail(f"could not read project Codex configuration as strict TOML UTF-8: {error}")
    if not isinstance(value, dict):
        _fail("project Codex configuration must be a TOML table")
    return raw, value


def validate_codex_config(workspace: Path) -> CodexConfigValidationReport:
    """Validate portable, least-privilege, project-shared Codex settings."""

    path = workspace.resolve() / ".codex" / "config.toml"
    raw, config = _read_config(path)
    if config != EXPECTED_SETTINGS:
        _fail(
            "project Codex configuration must contain only on-request approval, "
            "workspace-write sandboxing, cached search, and unelevated Windows sandboxing"
        )
    return CodexConfigValidationReport(
        byte_count=len(raw), setting_count=len(EXPECTED_SETTINGS)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace", type=Path, default=Path(__file__).resolve().parents[2]
    )
    arguments = parser.parse_args()
    try:
        report = validate_codex_config(arguments.workspace)
    except CodexConfigValidationError as error:
        print(f"Codex configuration validation failed: {error}")
        return 2
    print(
        "Codex configuration validation passed: "
        f"{report.byte_count} bytes, {report.setting_count} top-level settings"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
