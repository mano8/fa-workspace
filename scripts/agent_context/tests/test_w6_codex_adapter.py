from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.codex_adapter import (
    CodexDeliveryAdapter,
    CommandResult,
    _thread_started_id,
    find_workspace_root,
)
from agent_context.codex_repo_launcher import _load_authorization


class W6CodexAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.version_calls = 0
        self.exec_calls = 0
        self.mutate_before_transport = False
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "workspace with spaces"
        self.root.mkdir()
        (self.root / ".m8-workspace-root").write_text("m8-workspace-v2\n", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("root instructions\n", encoding="utf-8")
        (self.root / ".codex").mkdir()
        (self.root / ".codex" / "config.toml").write_text(
            'approval_policy = "on-request"\nsandbox_mode = "workspace-write"\nweb_search = "cached"\n[windows]\nsandbox = "unelevated"\n',
            encoding="utf-8",
        )
        self.repo = self.root / "repo-a"
        self.repo.mkdir()
        (self.repo / ".git").mkdir()
        (self.repo / "AGENTS.md").write_text("child instructions\n", encoding="utf-8")
        self.sibling = self.root / "repo-b"
        self.sibling.mkdir()
        (self.sibling / ".git").mkdir()
        (self.sibling / "AGENTS.md").write_text("sibling instructions\n", encoding="utf-8")
        workspace = self.root / ".workspace"
        policies = workspace / "policies"
        policies.mkdir(parents=True)
        (policies / "always.md").write_text("always policy\n", encoding="utf-8")
        (policies / "repo.md").write_text("repo policy\n", encoding="utf-8")
        (policies / "sibling.md").write_text("sibling policy\n", encoding="utf-8")
        (policies / "cross.md").write_text("cross repository policy\n", encoding="utf-8")
        (workspace / "repo-types.json").write_text(json.dumps({
            "schema_version": 2, "repositories": [
                {"id": "repo-a", "path": "repo-a", "kind": "sdk", "layer": "platform",
                 "facets": ["python"]},
                {"id": "repo-b", "path": "repo-b", "kind": "sdk", "layer": "platform",
                 "facets": ["python-b"]},
            ],
        }), encoding="utf-8")
        (workspace / "policy.index.json").write_text(json.dumps({
            "schema_version": 2, "mode": "faceted", "budgets": {"preferred_bytes": 24576, "hard_bytes": 32768},
            "always": ["always.policy"], "facet_ids": ["python", "python-b"],
            "facets": {"python": ["repo.policy"], "python-b": ["sibling.policy"]},
            "tasks": {"cross-repository": {"policies": ["cross.policy"], "authorization": "cross-repository"}},
            "exclusions": {},
        }), encoding="utf-8")
        (workspace / "policy.metadata.json").write_text(json.dumps({
            "units": [
                self._unit("always.policy", ".workspace/policies/always.md", True),
                self._unit("repo.policy", ".workspace/policies/repo.md", False),
                self._unit("sibling.policy", ".workspace/policies/sibling.md", False),
                self._unit("cross.policy", ".workspace/policies/cross.md", False),
            ], "invariants": ["OWNERSHIP"], "capabilities": [],
        }), encoding="utf-8")
        self.evidence = self.root / "evidence.md"
        self.evidence.write_text("frozen evidence\n", encoding="utf-8")
        self.home = self.root / "codex-home"
        self.home.mkdir()
        (self.home / "config.toml").write_text(
            f'[projects."{self.root}"]\ntrust_level = "trusted"\n', encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"],
            cwd=self.root, check=True,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _unit(policy_id: str, path: str, required: bool) -> dict[str, object]:
        return {
            "id": policy_id, "path": path, "authority_tier": "workspace",
            "scope": {"repository_id": "$workspace", "prefix": "."},
            "invariant_ids": ["OWNERSHIP"], "conflicts_with": [], "may_override": [],
            "required": required, "capabilities_granted": [],
        }

    def _runner(self, command: tuple[str, ...] | list[str], cwd: Path) -> CommandResult:
        if command[1:] == ("--version",):
            self.version_calls += 1
            if self.mutate_before_transport and self.version_calls == 2:
                (self.repo / "AGENTS.md").write_text("changed after inspection\n", encoding="utf-8")
            return CommandResult(0, b"codex-cli fixture\n")
        if command[3:5] == ("debug", "prompt-input"):
            self.assertEqual(command[1], "-c")
            self.assertTrue(command[2].startswith("developer_instructions="))
            marker = command[5]
            source = (cwd / "AGENTS.md").read_text()
            texts = [marker, f"# AGENTS.md instructions\n\n<INSTRUCTIONS>\n{source}</INSTRUCTIONS>"]
            messages = [{"content": [{"type": "input_text", "text": text}]} for text in texts]
            return CommandResult(0, json.dumps(messages).encode())
        if command[3:5] == ("exec", "--strict-config"):
            self.assertEqual(command[1], "-c")
            self.assertTrue(command[2].startswith("developer_instructions="))
            self.exec_calls += 1
            return CommandResult(0, b'{"type":"thread.started","thread_id":"thread.fixture"}\n')
        self.fail(f"unexpected Codex command: {command}")

    def _adapter(self) -> CodexDeliveryAdapter:
        return CodexDeliveryAdapter(runner=self._runner, codex_command="fixture-codex")

    def _patches(self):
        binary = self.root / "fixture-codex"
        binary.write_bytes(b"fixture Codex executable")
        return patch.multiple(
            "agent_context.codex_adapter",
            CAPABILITY_EVIDENCE_PATH="evidence.md",
            CAPABILITY_EVIDENCE_SHA256=hashlib.sha256(self.evidence.read_bytes()).hexdigest(),
            EXPECTED_CODEX_VERSION="codex-cli fixture",
            EXPECTED_CODEX_SHA256=hashlib.sha256(binary.read_bytes()).hexdigest(),
            shutil_which=lambda _command: binary,
        )

    def test_marker_only_discovery_and_direct_child_resolution(self) -> None:
        with self._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.home)}):
            self.assertEqual(find_workspace_root(self.repo), self.root)
            repository, resolved, inspection = self._adapter().resolve_single_repository(
                workspace_root=self.root, repository_id="repo-a",
            )
        self.assertEqual(repository, self.repo)
        self.assertEqual(inspection.source_sha256["AGENTS.md"], hashlib.sha256((self.root / "AGENTS.md").read_bytes()).hexdigest())
        self.assertEqual([entry["delivery"] for entry in resolved.manifest["entries"]], ["inject", "inject", "native", "inject"])
        self.assertEqual(resolved.manifest["entries"][2]["path"], "AGENTS.md")
        self.assertEqual(resolved.manifest["entries"][3]["repository_id"], "repo-a")
        self.assertEqual(resolved.manifest["repositories"], ["repo-a"])

    def test_exact_transport_handoff_uses_kernel_receipt_and_thread_identity(self) -> None:
        with self._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.home)}):
            result = self._adapter().prepare_and_handoff(
                workspace_root=self.root, repository_id="repo-a", prompt="inspect the repository",
            )
        self.assertEqual(result.receipt["state"], "COMPLETED")
        self.assertEqual(result.receipt["client_session_id"], "thread.fixture")
        self.assertGreater(result.receipt["delivered_bytes"], 0)
        self.assertFalse((result.runtime_dir / "receipt.json").read_bytes().count(b"always policy"))

    def test_missing_native_child_or_untrusted_project_fails_before_execution(self) -> None:
        (self.repo / "AGENTS.md").unlink()
        with self._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.home)}):
            with self.assertRaisesRegex(w2b1.AgentContextError, "native AGENTS") as failure:
                self._adapter().resolve_single_repository(workspace_root=self.root, repository_id="repo-a")
        self.assertEqual(failure.exception.code, "E_NATIVE_EVIDENCE")
        (self.repo / "AGENTS.md").write_text("child instructions\n", encoding="utf-8")
        (self.home / "config.toml").write_text("", encoding="utf-8")
        with self._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.home)}):
            with self.assertRaisesRegex(w2b1.AgentContextError, "not explicitly trusted") as failure:
                self._adapter().resolve_single_repository(workspace_root=self.root, repository_id="repo-a")
        self.assertEqual(failure.exception.code, "E_TRUST")

    def test_no_marker_or_no_thread_started_never_claims_delivery(self) -> None:
        (self.root / ".m8-workspace-root").unlink()
        with self.assertRaisesRegex(w2b1.AgentContextError, "no canonical") as failure:
            find_workspace_root(self.repo)
        self.assertEqual(failure.exception.code, "E_SCOPE_UNAVAILABLE")
        with self.assertRaisesRegex(w2b1.AgentContextError, "thread.started") as failure:
            _thread_started_id(b'{"type":"turn.started"}\n')
        self.assertEqual(failure.exception.code, "E_LIFECYCLE")

    def test_multi_repository_reordering_has_one_exact_authorized_handoff(self) -> None:
        authorization = {
            "authorization_id": "human.cross", "kind": "explicit-user-message",
            "authorized_by": "fixture user", "source_ref": "conversation:fixture",
            "source_sha256": "a" * 64, "repositories": ["repo-a", "repo-b"],
            "operations": ["analyze"], "issued_at": "2026-07-20T00:00:00Z",
        }
        with self._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.home)}):
            _, first, inspection = self._adapter().resolve_repositories(
                workspace_root=self.root, repository_ids=("repo-b", "repo-a"),
                tasks=("cross-repository",), operations=("analyze",),
                authorizations=(authorization,),
            )
            _, second, _ = self._adapter().resolve_repositories(
                workspace_root=self.root, repository_ids=("repo-a", "repo-b"),
                tasks=("cross-repository",), operations=("analyze",),
                authorizations=(authorization,),
            )
            result = self._adapter().prepare_and_handoff_repositories(
                workspace_root=self.root, repository_ids=("repo-b", "repo-a"),
                tasks=("cross-repository",), operations=("analyze",),
                authorizations=(authorization,), prompt="compare siblings",
            )
        self.assertEqual(first.manifest["manifest_id"], second.manifest["manifest_id"])
        self.assertEqual(first.envelope_sha256, second.envelope_sha256)
        self.assertEqual(sorted(inspection.source_sha256), ["AGENTS.md", "repo-a/AGENTS.md", "repo-b/AGENTS.md"])
        self.assertEqual(result.receipt["state"], "COMPLETED")
        self.assertEqual(result.receipt["repositories"], ["repo-a", "repo-b"])
        self.assertEqual(result.receipt["authorization_ids"], ["human.cross"])

    def test_multi_repository_and_mutating_scope_cannot_self_authorize(self) -> None:
        with self._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.home)}):
            with self.assertRaisesRegex(w2b1.AgentContextError, "explicit human authorization") as missing:
                self._adapter().prepare_and_handoff_repositories(
                    workspace_root=self.root, repository_ids=("repo-a", "repo-b"),
                    tasks=("cross-repository",), operations=("analyze",),
                    prompt="must not start",
                )
        self.assertEqual(missing.exception.code, "E_AUTHORIZATION")
        self.assertEqual(self.exec_calls, 0)

    def test_canonical_adapter_rejects_unverified_legacy_authorization(self) -> None:
        legacy = {
            "authorization_id": "human.cross", "kind": "explicit-user-message",
            "authorized_by": "fixture user", "source_ref": "conversation:fixture",
            "source_sha256": "a" * 64, "repositories": ["repo-a", "repo-b"],
            "operations": ["analyze"], "issued_at": "2026-07-20T00:00:00Z",
        }
        adapter = CodexDeliveryAdapter(
            runner=self._runner, codex_command="fixture-codex", strict_trust_identity=True,
        )
        with self.assertRaisesRegex(w2b1.AgentContextError, "externally verified") as failure:
            adapter.resolve_repositories(
                workspace_root=self.root, repository_ids=("repo-a", "repo-b"),
                tasks=("cross-repository",), operations=("analyze",),
                authorizations=(legacy,),
            )
        self.assertEqual(failure.exception.code, "E_AUTHORIZATION")
        self.assertEqual(self.exec_calls, 0)

    def test_adversarial_identifiers_and_direct_child_escapes_fail_before_exec(self) -> None:
        with self._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.home)}):
            with self.assertRaisesRegex(w2b1.AgentContextError, "canonical identifier") as traversal:
                self._adapter().resolve_repositories(
                    workspace_root=self.root, repository_ids=("../repo-a",),
                )
            self.assertEqual(traversal.exception.code, "E_USAGE")
            with self.assertRaisesRegex(w2b1.AgentContextError, "duplicate repository") as duplicate:
                self._adapter().resolve_repositories(
                    workspace_root=self.root, repository_ids=("repo-a", "repo-a"),
                )
            self.assertEqual(duplicate.exception.code, "E_USAGE")
            (self.sibling / "AGENTS.md").unlink()
            (self.sibling / "AGENTS.md").symlink_to(self.root / "AGENTS.md")
            with self.assertRaisesRegex(w2b1.AgentContextError, "regular native") as escaped:
                self._adapter().resolve_repositories(
                    workspace_root=self.root, repository_ids=("repo-b",),
                )
            self.assertEqual(escaped.exception.code, "E_NATIVE_EVIDENCE")

    def test_native_drift_after_inspection_blocks_the_user_task(self) -> None:
        self.mutate_before_transport = True
        with self._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.home)}):
            with self.assertRaisesRegex(w2b1.AgentContextError, "changed after inspection") as drift:
                self._adapter().prepare_and_handoff_repositories(
                    workspace_root=self.root, repository_ids=("repo-a",), prompt="must not start",
                )
        self.assertEqual(drift.exception.code, "E_NATIVE_EVIDENCE")
        self.assertEqual(self.exec_calls, 0)

    def test_authorization_records_cannot_escape_or_follow_a_symlink(self) -> None:
        authorization_dir = self.root / "authorizations"
        authorization_dir.mkdir()
        record = authorization_dir / "approved.json"
        record.write_text("{}", encoding="utf-8")
        self.assertEqual(_load_authorization(self.root, "authorizations/approved.json"), {})
        with self.assertRaisesRegex(w2b1.AgentContextError, "unsafe") as traversal:
            _load_authorization(self.root, "../approved.json")
        self.assertEqual(traversal.exception.code, "E_SCOPE_UNAVAILABLE")
        link = authorization_dir / "linked.json"
        link.symlink_to(record)
        with self.assertRaisesRegex(w2b1.AgentContextError, "regular workspace-relative") as symlink:
            _load_authorization(self.root, "authorizations/linked.json")
        self.assertEqual(symlink.exception.code, "E_SCOPE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
