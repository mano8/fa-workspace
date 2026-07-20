from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.validate_codex_config import (
    CodexConfigValidationError,
    EXPECTED_SETTINGS,
    validate_codex_config,
)


WORKSPACE = Path(__file__).resolve().parents[3]


class W6CodexConfigTests(unittest.TestCase):
    def _copy_config(self, destination: Path) -> Path:
        config_dir = destination / ".codex"
        config_dir.mkdir()
        path = config_dir / "config.toml"
        shutil.copy2(WORKSPACE / ".codex" / "config.toml", path)
        return path

    def test_current_config_is_portable_and_least_privilege(self) -> None:
        report = validate_codex_config(WORKSPACE)
        self.assertEqual(report.setting_count, len(EXPECTED_SETTINGS))
        self.assertGreater(report.byte_count, 0)

    def test_model_and_effort_pins_fail(self) -> None:
        for pin in ('model = "gpt-5"\n', 'model_reasoning_effort = "medium"\n'):
            with self.subTest(pin=pin), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = self._copy_config(root)
                path.write_text(
                    path.read_text(encoding="utf-8") + pin,
                    encoding="utf-8",
                    newline="\n",
                )
                with self.assertRaisesRegex(CodexConfigValidationError, "must contain only"):
                    validate_codex_config(root)

    def test_elevated_windows_sandbox_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._copy_config(root)
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'sandbox = "unelevated"', 'sandbox = "elevated"'
                ),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(CodexConfigValidationError, "unelevated"):
                validate_codex_config(root)

    def test_cached_search_cannot_be_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._copy_config(root)
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'web_search = "cached"', 'web_search = "live"'
                ),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(CodexConfigValidationError, "must contain only"):
                validate_codex_config(root)


if __name__ == "__main__":
    unittest.main()
