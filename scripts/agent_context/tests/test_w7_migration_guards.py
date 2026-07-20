from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.validate_migration_guards import (
    MigrationGuardError,
    validate_migration_guards,
)


WORKSPACE = Path(__file__).resolve().parents[3]


class MigrationGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "workspace"
        self.root.mkdir()
        for name in ("AGENTS.md", "CLAUDE.md", ".gitignore"):
            shutil.copy2(WORKSPACE / name, self.root / name)
        for directory in (".claude", ".codex", ".githooks"):
            shutil.copytree(WORKSPACE / directory, self.root / directory)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_current_root_migration_guards_pass(self) -> None:
        report = validate_migration_guards(self.root)
        self.assertEqual(report.checked_file_count, 4)
        self.assertEqual(report.checked_hook_count, 2)

    def test_host_workspace_path_fails(self) -> None:
        path = self.root / "AGENTS.md"
        path.write_text(path.read_text(encoding="utf-8") + "Use /workspace.\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(MigrationGuardError, "host/workspace paths"):
            validate_migration_guards(self.root)

    def test_cross_agent_imports_fail_in_both_directions(self) -> None:
        for source, target in (("AGENTS.md", "CLAUDE.md"), ("CLAUDE.md", "AGENTS.md")):
            with self.subTest(source=source):
                path = self.root / source
                path.write_text(path.read_text(encoding="utf-8") + f"@{target}\n", encoding="utf-8", newline="\n")
                with self.assertRaisesRegex(MigrationGuardError, "imports"):
                    validate_migration_guards(self.root)
                shutil.copy2(WORKSPACE / source, path)

    def test_todo_plan_protection_and_authorship_metadata_fail(self) -> None:
        hook = self.root / ".githooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(MigrationGuardError, "TODO-plan protection hook"):
            validate_migration_guards(self.root)
        shutil.copy2(WORKSPACE / ".githooks/pre-commit", hook)
        settings = self.root / ".claude/settings.json"
        settings.write_text(
            settings.read_text(encoding="utf-8") + "\nco-authored-by: forbidden\n",
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaisesRegex(MigrationGuardError, "authorship metadata"):
            validate_migration_guards(self.root)


if __name__ == "__main__":
    unittest.main()
