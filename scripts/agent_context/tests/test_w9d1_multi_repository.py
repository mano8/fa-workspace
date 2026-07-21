from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.codex_adapter import CodexDeliveryAdapter
from agent_context.tests.test_w6_codex_adapter import W6CodexAdapterTests


class W9d1MultiRepositoryTests(unittest.TestCase):
    """Required-row parity fixtures for one root execution hierarchy."""

    def setUp(self) -> None:
        self.fixture = W6CodexAdapterTests()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def _authorization(self) -> dict[str, object]:
        return {
            "authorization_id": "human.cross", "kind": "explicit-user-message",
            "authorized_by": "fixture user", "source_ref": "conversation:fixture",
            "source_sha256": "a" * 64, "repositories": ["repo-a", "repo-b"],
            "operations": ["analyze"], "issued_at": "2026-07-20T00:00:00Z",
        }

    def _resolve(self, repositories: tuple[str, ...]):
        with self.fixture._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.fixture.home)}):
            return self.fixture._adapter().resolve_repositories(
                workspace_root=self.fixture.root, repository_ids=repositories,
                tasks=("cross-repository",), operations=("analyze",),
                authorizations=(self._authorization(),),
            )

    def test_single_repository_uses_root_execution_model(self) -> None:
        with self.fixture._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.fixture.home)}):
            _, resolved, inspection = self.fixture._adapter().resolve_repositories(
                workspace_root=self.fixture.root, repository_ids=("repo-a",),
            )
        agents = [entry for entry in resolved.manifest["entries"] if entry["source_kind"] == "instruction"]
        self.assertEqual([(entry["path"], entry["delivery"]) for entry in agents], [
            ("AGENTS.md", "native"), ("repo-a/AGENTS.md", "inject"),
        ])
        self.assertEqual(set(inspection.active_source_sha256), {"AGENTS.md"})

    def test_root_native_child_inject_sources_are_exact_once(self) -> None:
        _, resolved, _ = self._resolve(("repo-a", "repo-b"))
        agents = [entry for entry in resolved.manifest["entries"] if entry["source_kind"] == "instruction"]
        self.assertEqual([entry["path"] for entry in agents], ["AGENTS.md", "repo-a/AGENTS.md", "repo-b/AGENTS.md"])
        self.assertEqual([entry["delivery"] for entry in agents], ["native", "inject", "inject"])
        injected = [entry["path"] for entry in resolved.envelope["entries"]]
        self.assertEqual(injected.count("repo-a/AGENTS.md"), 1)
        self.assertEqual(injected.count("repo-b/AGENTS.md"), 1)
        self.assertNotIn("AGENTS.md", injected)

    def test_native_evidence_ids_are_populated(self) -> None:
        _, resolved, _ = self._resolve(("repo-a", "repo-b"))
        native = next(entry for entry in resolved.manifest["entries"] if entry["path"] == "AGENTS.md")
        self.assertIsInstance(native["native_evidence_id"], str)
        self.assertIsNone(native["envelope_entry_sha256"])
        for entry in resolved.manifest["entries"]:
            if entry["delivery"] == "inject":
                self.assertIsNone(entry["native_evidence_id"])
                self.assertIsInstance(entry["envelope_entry_sha256"], str)

    def test_reversed_repository_order_has_identical_source_set(self) -> None:
        _, first, _ = self._resolve(("repo-b", "repo-a"))
        _, second, _ = self._resolve(("repo-a", "repo-b"))
        self.assertEqual(first.manifest["entries"], second.manifest["entries"])
        self.assertEqual(first.manifest["accounting"], second.manifest["accounting"])
        self.assertEqual(first.envelope_bytes, second.envelope_bytes)

    def test_conflicting_siblings_remain_repository_scoped(self) -> None:
        self.fixture.repo.joinpath("AGENTS.md").write_text("same path words, repo a\n", encoding="utf-8")
        self.fixture.sibling.joinpath("AGENTS.md").write_text("same path words, repo b\n", encoding="utf-8")
        _, resolved, _ = self._resolve(("repo-a", "repo-b"))
        entries = {entry["path"]: entry for entry in resolved.envelope["entries"]}
        self.assertEqual(entries["repo-a/AGENTS.md"]["repository_id"], "repo-a")
        self.assertEqual(entries["repo-a/AGENTS.md"]["scope_prefix"], "repo-a")
        self.assertEqual(entries["repo-b/AGENTS.md"]["repository_id"], "repo-b")
        self.assertEqual(entries["repo-b/AGENTS.md"]["scope_prefix"], "repo-b")

    def test_transport_manifest_receipt_and_measurement_recompute(self) -> None:
        commands: list[tuple[tuple[str, ...], Path]] = []

        def runner(command, cwd):
            commands.append((tuple(command), cwd))
            return self.fixture._runner(command, cwd)

        with self.fixture._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.fixture.home)}):
            result = CodexDeliveryAdapter(runner=runner, codex_command="fixture-codex").prepare_and_handoff_repositories(
                workspace_root=self.fixture.root, repository_ids=("repo-b", "repo-a"),
                tasks=("cross-repository",), operations=("analyze",),
                authorizations=(self._authorization(),), prompt="compare siblings",
            )
        sources = result.receipt["sources"]
        injected = [source for source in sources if source["delivery"] == "inject"]
        self.assertEqual({source["path"] for source in injected}, {
            entry["path"] for entry in result.receipt["sources"] if entry["delivery"] == "inject"
        })
        self.assertEqual(result.receipt["state"], "COMPLETED")
        self.assertGreater(result.receipt["delivered_bytes"], 0)
        # The receipt inventory is the manifest inventory used by the transport;
        # the kernel's source rehash runs immediately before SUBMISSION_STARTED.
        self.assertEqual(result.receipt["sources"], result.session["sources"])
        exec_commands = [item for item in commands if item[0][3:5] == ("exec", "--strict-config")]
        self.assertEqual(len(exec_commands), 1)
        self.assertEqual(exec_commands[0][1], self.fixture.root)
        self.assertEqual(exec_commands[0][0][-3], "-C")
        self.assertEqual(exec_commands[0][0][-2], str(self.fixture.root))
        self.assertEqual(exec_commands[0][0][-1], "compare siblings")


if __name__ == "__main__":
    unittest.main()
