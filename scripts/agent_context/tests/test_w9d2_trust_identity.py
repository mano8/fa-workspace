from __future__ import annotations

import hashlib
import json
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
        self.node = Path(self.temporary.name) / "node-fixture"
        shutil.copyfile(Path(sys.executable).resolve(), self.node)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _commit(directory: Path) -> None:
        subprocess.run(("git", "init", "-q"), cwd=directory, check=True)
        subprocess.run(
            ("git", "-c", "advice.addEmbeddedRepo=false", "add", "."),
            cwd=directory,
            check=True,
            capture_output=True,
        )
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
                codex_version="fixture", node_binary=self.node,
                node_version="fixture-node",
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
                codex_version="fixture", node_binary=self.node,
                node_version="fixture-node",
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
                node_binary=self.node, node_version="fixture-node",
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

        node_original = self.node.read_bytes()
        self.node.write_bytes(node_original + b"drift")
        with self.assertRaisesRegex(w2b1.AgentContextError, "drifted"):
            self._verify(identity)
        self.node.write_bytes(node_original)

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
            self.root / ".devcontainer/bootstrap-lock.json",
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


class W12ClaudeTrustIdentityTests(unittest.TestCase):
    """Step 12.3 reuses one builder; only the Claude members differ."""

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
        (self.root / ".claude").mkdir(exist_ok=True)
        self.settings = self.root / ".claude" / "settings.json"
        self.settings.write_text('{"autoMemoryEnabled": false}\n', encoding="utf-8")
        self.child = self.root / "child"
        self.child.mkdir()
        (self.child / "AGENTS.md").write_text("child agents\n", encoding="utf-8")
        (self.child / "CLAUDE.md").write_text("child memory\n", encoding="utf-8")
        W9d2TrustIdentityTests._commit(self.child)
        W9d2TrustIdentityTests._commit(self.root)
        self.home = Path(self.temporary.name) / "claude-home"
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
        self.trust_record = self.home / ".claude.json"
        self._write_trust(True)
        self.binary = Path(self.temporary.name) / "claude-fixture"
        shutil.copyfile(Path(sys.executable).resolve(), self.binary)
        self.node = Path(self.temporary.name) / "node-fixture"
        shutil.copyfile(Path(sys.executable).resolve(), self.node)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_trust(self, trusted: bool) -> None:
        self.trust_record.write_text(
            json.dumps({"projects": {str(self.root): {"hasTrustDialogAccepted": trusted}}}),
            encoding="utf-8",
        )

    def _kwargs(self) -> dict[str, object]:
        return {
            "workspace_root": self.root, "selected_repositories": (self.child,),
            "capability_path": self.capability, "agent": "claude",
            "claude_binary": self.binary, "claude_version": "2.1.220 (fixture)",
            "project_trust_scope": self.root, "node_binary": self.node,
            "node_version": "fixture-node", "home": self.home,
        }

    def test_a_claude_identity_binds_its_client_settings_and_recorded_trust(self) -> None:
        identity = build_trust_identity(**self._kwargs())
        self.assertEqual(identity["agent"], "claude")
        self.assertEqual(identity["project_trust"], {"scope": ".", "state": "trusted"})
        self.assertEqual(identity["claude"]["version"], "2.1.220 (fixture)")
        self.assertEqual(
            [item["kind"] for item in identity["configuration"]],
            ["project", "project-local", "user"],
        )
        # The volatile client state file is never hashed into the identity.
        self.assertNotIn(".claude.json", json.dumps(identity))
        self.assertEqual(
            identity["children"][0]["instruction_sha256"],
            hashlib.sha256((self.child / "CLAUDE.md").read_bytes()).hexdigest(),
        )
        verify_trust_identity(identity, **self._kwargs())

    def test_claude_client_settings_instruction_or_trust_drift_fails(self) -> None:
        identity = build_trust_identity(**self._kwargs())
        for name, mutate in (
            ("client", lambda: self.binary.write_bytes(self.binary.read_bytes() + b"drift")),
            ("settings", lambda: self.settings.write_text("{}\n", encoding="utf-8")),
            ("user-settings", lambda: (self.home / ".claude" / "settings.json").write_text(
                '{"drift": true}\n', encoding="utf-8"
            )),
            ("trust", lambda: self._write_trust(False)),
        ):
            with self.subTest(input=name):
                self.setUp()
                identity = build_trust_identity(**self._kwargs())
                mutate()
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    verify_trust_identity(identity, **self._kwargs())
                self.assertEqual(failure.exception.code, "E_TRUST")

    def test_an_incomplete_or_unknown_agent_identity_is_refused(self) -> None:
        for overrides, fragment in (
            ({"claude_binary": None}, "client binary"),
            ({"project_trust_scope": None}, "client binary"),
            ({"agent": "other"}, "instruction contract"),
        ):
            with self.subTest(overrides=sorted(overrides)):
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    build_trust_identity(**{**self._kwargs(), **overrides})
                self.assertEqual(failure.exception.code, "E_TRUST")
                self.assertIn(fragment, failure.exception.message)

    def test_the_codex_identity_keeps_exactly_its_previous_members(self) -> None:
        identity = build_trust_identity(
            workspace_root=self.root, selected_repositories=(self.child,),
            capability_path=self.capability, codex_binary=self.binary, codex_version="fixture",
            node_binary=self.node, node_version="fixture-node", home=self.home,
        )
        self.assertEqual(set(identity), {
            "schema_version", "root", "children", "critical_files", "codex", "node", "python",
            "platform", "configuration", "authorization_trust_store_sha256", "trust_identity_sha256",
        })
        self.assertEqual(
            identity["children"][0]["instruction_sha256"],
            hashlib.sha256((self.child / "AGENTS.md").read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
