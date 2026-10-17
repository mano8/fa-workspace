from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.validate_root_claude import (
    CONVENTIONS_IMPORT_PATH,
    MAX_BOOTSTRAP_BYTES,
    RootClaudeValidationError,
    validate_root_claude,
)


WORKSPACE = Path(__file__).resolve().parents[3]


class W5RootClaudeTests(unittest.TestCase):
    def _copy_root_claude(self, destination: Path) -> Path:
        shutil.copy2(WORKSPACE / "CLAUDE.md", destination / "CLAUDE.md")
        conventions = destination / CONVENTIONS_IMPORT_PATH
        conventions.parent.mkdir(parents=True)
        shutil.copy2(WORKSPACE / CONVENTIONS_IMPORT_PATH, conventions)
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


    def test_conventions_owner_is_imported_exactly_once(self) -> None:
        line = f"@{CONVENTIONS_IMPORT_PATH}\n"
        variants = {
            "missing": lambda text: text.replace(line, ""),
            "extra": lambda text: text + "\n@.workspace/context/env.md\n",
            "repeated": lambda text: text + "\n" + line,
        }
        for name, change in variants.items():
            with self.subTest(variant=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = self._copy_root_claude(root)
                self.assertIn(line, path.read_text(encoding="utf-8"))
                path.write_text(
                    change(path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n"
                )
                with self.assertRaisesRegex(RootClaudeValidationError, "must import exactly"):
                    validate_root_claude(root)

    def test_imported_conventions_owner_must_exist_with_lf_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_root_claude(root)
            (root / CONVENTIONS_IMPORT_PATH).unlink()
            with self.assertRaisesRegex(RootClaudeValidationError, "not a regular file"):
                validate_root_claude(root)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_root_claude(root)
            (root / CONVENTIONS_IMPORT_PATH).write_bytes(b"# conventions\r\n")
            with self.assertRaisesRegex(RootClaudeValidationError, "LF"):
                validate_root_claude(root)


if __name__ == "__main__":
    unittest.main()
