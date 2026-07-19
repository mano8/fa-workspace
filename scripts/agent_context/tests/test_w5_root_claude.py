from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.validate_root_claude import (
    MAX_BOOTSTRAP_BYTES,
    RootClaudeValidationError,
    validate_root_claude,
)


WORKSPACE = Path(__file__).resolve().parents[3]


class W5RootClaudeTests(unittest.TestCase):
    def _copy_root_claude(self, destination: Path) -> Path:
        shutil.copy2(WORKSPACE / "CLAUDE.md", destination / "CLAUDE.md")
        return destination / "CLAUDE.md"

    def test_current_bootstrap_is_compact_and_claude_only(self) -> None:
        report = validate_root_claude(WORKSPACE)
        self.assertLessEqual(report.byte_count, MAX_BOOTSTRAP_BYTES)
        self.assertEqual(report.reference_count, 7)

    def test_marker_must_be_visible_not_html_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._copy_root_claude(root)
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "`Workspace instruction set: m8-workspace-v2`",
                    "<!-- Workspace instruction set: m8-workspace-v2 -->",
                ),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(RootClaudeValidationError, "forbidden"):
                validate_root_claude(root)

    def test_root_agents_import_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._copy_root_claude(root)
            path.write_text(
                path.read_text(encoding="utf-8") + "\n@AGENTS.md\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(RootClaudeValidationError, "imports root AGENTS"):
                validate_root_claude(root)

    def test_stale_or_host_specific_content_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._copy_root_claude(root)
            path.write_text(
                path.read_text(encoding="utf-8") + "\nUse /workspace directly.\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(RootClaudeValidationError, "forbidden"):
                validate_root_claude(root)


if __name__ == "__main__":
    unittest.main()
