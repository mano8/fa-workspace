from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.validate_claude_settings import (
    ASK_RULES,
    DENY_RULES,
    ClaudeSettingsValidationError,
    validate_claude_settings,
)


WORKSPACE = Path(__file__).resolve().parents[3]


class W5ClaudeSettingsTests(unittest.TestCase):
    def _copy_settings(self, destination: Path) -> Path:
        settings_dir = destination / ".claude"
        settings_dir.mkdir()
        path = settings_dir / "settings.json"
        shutil.copy2(WORKSPACE / ".claude" / "settings.json", path)
        return path

    def test_current_settings_are_portable_and_least_privilege(self) -> None:
        report = validate_claude_settings(WORKSPACE)
        self.assertEqual(report.ask_rule_count, len(ASK_RULES))
        self.assertEqual(report.deny_rule_count, len(DENY_RULES))
        self.assertGreater(report.byte_count, 0)

    def test_auto_memory_must_be_explicitly_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._copy_settings(root)
            settings = json.loads(path.read_text(encoding="utf-8"))
            settings["autoMemoryEnabled"] = True
            path.write_text(json.dumps(settings) + "\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ClaudeSettingsValidationError, "auto-memory"):
                validate_claude_settings(root)

    def test_personal_approval_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._copy_settings(root)
            settings = json.loads(path.read_text(encoding="utf-8"))
            settings["permissions"]["allow"] = ["Bash(git push *)"]
            path.write_text(json.dumps(settings) + "\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ClaudeSettingsValidationError, "personal command approvals"):
                validate_claude_settings(root)

    def test_unmeasured_path_rule_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._copy_settings(root)
            settings = json.loads(path.read_text(encoding="utf-8"))
            settings["permissions"]["deny"].append("Read(./secrets/**)")
            path.write_text(json.dumps(settings) + "\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ClaudeSettingsValidationError, "measured local-sensitive paths"):
                validate_claude_settings(root)


if __name__ == "__main__":
    unittest.main()
