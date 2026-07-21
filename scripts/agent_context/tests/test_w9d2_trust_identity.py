from __future__ import annotations

import subprocess
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.trust_identity import CRITICAL_PATHS, build_trust_identity, verify_trust_identity


class W9d2TrustIdentityTests(unittest.TestCase):
    """Frozen H-2/M-4 negative cases for the reviewed launch trust root."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "workspace"
        self.root.mkdir()
        for relative in CRITICAL_PATHS:
            path = self.root / relative
            if relative == ".workspace/contracts":
                path.mkdir(parents=True)
                (path / "contract.md").write_text("contract\n", encoding="utf-8")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"{relative}\n", encoding="utf-8")
        self.capability = ".workspace/capability.json"
        (self.root / self.capability).write_text("{}\n", encoding="utf-8")
        self.home = Path(self.temporary.name) / "codex-home"
        self.home.mkdir()
        (self.home / "config.toml").write_text("[projects]\n", encoding="utf-8")
        self.child = self.root / "child"
        self.child.mkdir()
        (self.child / "AGENTS.md").write_text("child\n", encoding="utf-8")
        self._commit(self.child)
        self._commit(self.root)
        self.binary = Path(self.temporary.name) / "codex-fixture"
        shutil.copyfile(Path(sys.executable).resolve(), self.binary)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _commit(directory: Path) -> None:
        subprocess.run(("git", "init", "-q"), cwd=directory, check=True)
        subprocess.run(("git", "add", "."), cwd=directory, check=True)
        subprocess.run(
            ("git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"),
            cwd=directory, check=True,
        )

    def _identity(self) -> dict[str, object]:
        old_home = __import__("os").environ.get("CODEX_HOME")
        __import__("os").environ["CODEX_HOME"] = str(self.home)
        try:
            return build_trust_identity(
                workspace_root=self.root, selected_repositories=(self.child,),
                capability_path=self.capability, codex_binary=self.binary,
                codex_version="fixture",
            )
        finally:
            if old_home is None:
                __import__("os").environ.pop("CODEX_HOME", None)
            else:
                __import__("os").environ["CODEX_HOME"] = old_home

    def _verify(self, identity: dict[str, object]) -> None:
        old_home = __import__("os").environ.get("CODEX_HOME")
        __import__("os").environ["CODEX_HOME"] = str(self.home)
        try:
            verify_trust_identity(
                identity, workspace_root=self.root, selected_repositories=(self.child,),
                capability_path=self.capability, codex_binary=self.binary,
                codex_version="fixture",
            )
        finally:
            if old_home is None:
                __import__("os").environ.pop("CODEX_HOME", None)
            else:
                __import__("os").environ["CODEX_HOME"] = old_home

    def test_floating_bootstrap_input_fails(self) -> None:
        identity = self._identity()
        (self.root / ".devcontainer/setup.sh").write_text("floating bootstrap\n", encoding="utf-8")
        with self.assertRaisesRegex(w2b1.AgentContextError, "dirty or staged") as failure:
            self._verify(identity)
        self.assertEqual(failure.exception.code, "E_TRUST")

    def test_hash_mismatched_bootstrap_input_fails(self) -> None:
        identity = self._identity()
        (self.home / "config.toml").write_text("[projects]\ndrift = true\n", encoding="utf-8")
        with self.assertRaisesRegex(w2b1.AgentContextError, "drifted") as failure:
            self._verify(identity)
        self.assertEqual(failure.exception.code, "E_TRUST")

    def test_two_clean_build_identities_match(self) -> None:
        first = self._identity()
        # A second independently materialized clean checkout with identical
        # tracked bytes has the same tree/tool identity after cloning root and
        # child Git histories rather than reusing their worktrees.
        second_root = Path(self.temporary.name) / "workspace-copy"
        subprocess.run(("git", "clone", "-q", str(self.root), str(second_root)), check=True)
        subprocess.run(("git", "clone", "-q", str(self.child), str(second_root / "child")), check=True)
        old_home = __import__("os").environ.get("CODEX_HOME")
        __import__("os").environ["CODEX_HOME"] = str(self.home)
        try:
            second = build_trust_identity(
                workspace_root=second_root, selected_repositories=(second_root / "child",),
                capability_path=self.capability, codex_binary=self.binary, codex_version="fixture",
            )
        finally:
            if old_home is None:
                __import__("os").environ.pop("CODEX_HOME", None)
            else:
                __import__("os").environ["CODEX_HOME"] = old_home
        self.assertEqual(first["root"], second["root"])
        self.assertEqual(first["children"], second["children"])
        self.assertEqual(first["codex"], second["codex"])
        self.assertEqual(first["critical_files"], second["critical_files"])

    def test_binary_global_config_or_platform_drift_fails(self) -> None:
        identity = self._identity()
        original = self.binary.read_bytes()
        self.binary.write_bytes(original + b"drift")
        with self.assertRaisesRegex(w2b1.AgentContextError, "drifted"):
            self._verify(identity)
        self.binary.write_bytes(original)

        with mock.patch(
            "agent_context.trust_identity._config_inventory",
            return_value=[{"kind": "global", "path": "global:config.toml", "sha256": "a" * 64}],
        ):
            with self.assertRaisesRegex(w2b1.AgentContextError, "drifted"):
                self._verify(identity)

        with mock.patch("agent_context.trust_identity.platform.release", return_value="drifted"):
            with self.assertRaisesRegex(w2b1.AgentContextError, "drifted"):
                self._verify(identity)

    def test_capability_lock_config_or_instruction_drift_fails(self) -> None:
        identity = self._identity()
        cases = (
            self.root / self.capability,
            self.root / ".devcontainer/devcontainer-lock.json",
            self.home / "config.toml",
            self.child / "AGENTS.md",
        )
        for path in cases:
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(original + b"drift\n")
                with self.assertRaises(w2b1.AgentContextError):
                    self._verify(identity)
                path.write_bytes(original)

    def test_dirty_or_staged_root_fails(self) -> None:
        identity = self._identity()
        agents = self.root / "AGENTS.md"
        agents.write_text("dirty root\n", encoding="utf-8")
        with self.assertRaisesRegex(w2b1.AgentContextError, "dirty or staged"):
            self._verify(identity)
        subprocess.run(("git", "add", "AGENTS.md"), cwd=self.root, check=True)
        with self.assertRaisesRegex(w2b1.AgentContextError, "dirty or staged"):
            self._verify(identity)

    def test_parent_tree_receipt_fails(self) -> None:
        parent_identity = self._identity()
        (self.root / "AGENTS.md").write_text("new reviewed tree\n", encoding="utf-8")
        subprocess.run(("git", "add", "AGENTS.md"), cwd=self.root, check=True)
        subprocess.run(
            ("git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "commit", "-qm", "new tree"),
            cwd=self.root, check=True,
        )
        with self.assertRaisesRegex(w2b1.AgentContextError, "drifted"):
            self._verify(parent_identity)

    def test_selected_child_identity_or_instruction_drift_fails(self) -> None:
        identity = self._identity()
        instruction = self.child / "AGENTS.md"
        instruction.write_text("changed child instruction\n", encoding="utf-8")
        with self.assertRaises(w2b1.AgentContextError):
            self._verify(identity)
        subprocess.run(("git", "add", "AGENTS.md"), cwd=self.child, check=True)
        subprocess.run(
            ("git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "commit", "-qm", "child identity"),
            cwd=self.child, check=True,
        )
        with self.assertRaises(w2b1.AgentContextError):
            self._verify(identity)


if __name__ == "__main__":
    unittest.main()
