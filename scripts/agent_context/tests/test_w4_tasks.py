from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.delivery_kernel import (
    DeliveryKernel,
    DeliveryRequest,
    FakeTransportAdapter,
)
from agent_context.resolve_context import ResolutionRequest, resolve_context


WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE_SHA = "a" * 64


def _capability() -> dict[str, object]:
    return {
        "agent": "codex",
        "platform": "devcontainer",
        "mode": "non-interactive",
        "status": "REQUIRED",
        "inspection_mechanism": "fixture",
        "channel_id": "fixture",
        "verified_channel_limit": 32768,
        "client_context_allowance": 65536,
        "reserved_margin": 32768,
        "start_supported": True,
        "resume_supported": True,
        "clear_supported": True,
        "compact_supported": False,
        "launcher_identity_available": True,
        "client_session_identity_available": True,
        "blocks_closeout": True,
    }


class W4TaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = w2b1.parse_strict_json(
            (WORKSPACE / ".workspace/repo-types.json").read_bytes()
        )
        cls.index = w2b1.parse_strict_json(
            (WORKSPACE / ".workspace/policy.index.json").read_bytes()
        )
        cls.metadata = w2b1.parse_strict_json(
            (WORKSPACE / ".workspace/policy.metadata.json").read_bytes()
        )
        cls.sources = [
            {
                "path": unit["path"],
                "sha256": hashlib.sha256(
                    (WORKSPACE / unit["path"]).read_bytes()
                ).hexdigest(),
            }
            for unit in sorted(cls.metadata["units"], key=lambda item: item["path"])
        ]

    def _authorization(
        self, repositories: tuple[str, ...], operations: tuple[str, ...]
    ) -> dict[str, object]:
        return {
            "authorization_id": "human.task",
            "kind": "explicit-user-message",
            "authorized_by": "workspace-owner",
            "source_ref": "conversation:phase-4-step-4.4",
            "source_sha256": SOURCE_SHA,
            "repositories": sorted(repositories),
            "operations": sorted(operations),
            "issued_at": "2026-07-19T00:00:00Z",
        }

    def _resolve(
        self,
        *,
        repositories: tuple[str, ...] = ("auth-sdk-m8",),
        tasks: tuple[str, ...] = (),
        operations: tuple[str, ...] = (),
        authorized: bool = False,
    ):
        authorizations = (
            (self._authorization(repositories, operations),) if authorized else ()
        )
        capability = _capability()
        return resolve_context(
            ResolutionRequest(
                root=WORKSPACE,
                registry=self.registry,
                policy_index=self.index,
                policy_metadata=self.metadata,
                capability_row=capability,
                reviewed_tree={"algorithm": "git-sha1", "value": "b" * 40},
                agent="codex",
                platform="devcontainer",
                mode="non-interactive",
                repositories=repositories,
                tasks=tasks,
                operations=operations,
                authorizations=authorizations,
                injection_evidence={
                    "generation": 0,
                    "native_discovery_disabled": True,
                    "exact_once_handoff_proven": True,
                    "sources": self.sources,
                },
            )
        )

    def test_task_catalog_has_nonempty_step_4_4_slices_and_operation_authority(
        self,
    ) -> None:
        expected = {
            "branch": (["task.git.branch"], "mutating"),
            "commit": (["task.git.commit"], "mutating"),
            "cross-repository": (["task.cross-repository"], "cross-repository"),
            "environment": (["task.environment"], "none"),
            "headroom": (["task.headroom"], "none"),
            "headroom-wrapper": (["task.headroom-wrapper"], "mutating"),
            "pull-request": (["task.git.pull-request"], "mutating"),
            "push": (["task.git.push"], "mutating"),
            "release": (["task.release"], "mutating"),
            "testing": (["task.testing"], "none"),
        }
        for task, (policies, authorization) in expected.items():
            with self.subTest(task=task):
                self.assertEqual(self.index["tasks"][task]["policies"], policies)
                self.assertEqual(
                    self.index["tasks"][task]["authorization"], authorization
                )

    def test_task_slices_retain_the_classified_semantics_before_compression(
        self,
    ) -> None:
        required_text = {
            "environment.md": (
                ".env.example",
                "M8_PYTHON",
                "packageManager",
                "SkipAvailability",
            ),
            "testing.md": (
                "regression tests",
                "ruff format .",
                "mypy . --ignore-missing-imports",
                "installed-tarball fixtures",
            ),
            "git-branch.md": ("kebab-case", "explicit human authorization"),
            "git-commit.md": ("status before committing", "typecheck"),
            "git-pull-request.md": ("fenced `markdown` block",),
            "git-push.md": ("main branch", "exact selected"),
            "release.md": ("child-owned", "does not authorize"),
            "cross-repository.md": (
                "canonical explicit repository set",
                "HTTP APIs",
            ),
            "headroom.md": ("large non-secret logs", "exact details"),
            "headroom-wrapper.md": ("base URL", "exact operation"),
        }
        for filename, fragments in required_text.items():
            content = (WORKSPACE / ".workspace/policies/tasks" / filename).read_text(
                encoding="utf-8"
            )
            for fragment in fragments:
                with self.subTest(filename=filename, fragment=fragment):
                    self.assertIn(fragment, content)

    def test_default_and_facet_only_resolution_select_no_task_overlay(self) -> None:
        result = self._resolve()
        self.assertEqual(result.manifest["tasks"], [])
        self.assertEqual(result.manifest["operations"], [])
        self.assertEqual(result.manifest["authorization_provenance"], [])
        self.assertFalse(
            any(
                entry["policy_id"].startswith("task.")
                for entry in result.manifest["entries"]
            )
        )

    def test_nonmutating_tasks_are_opt_in_and_restore_only_their_slices(self) -> None:
        expected = {
            "environment": "task.environment",
            "headroom": "task.headroom",
            "testing": "task.testing",
        }
        for task, policy_id in expected.items():
            with self.subTest(task=task):
                result = self._resolve(tasks=(task,))
                selected = {entry["policy_id"] for entry in result.manifest["entries"]}
                self.assertIn(policy_id, selected)
                self.assertEqual(
                    {item for item in selected if item.startswith("task.")},
                    {policy_id},
                )

    def test_each_mutating_git_release_or_wrapper_task_requires_human_record(
        self,
    ) -> None:
        expected = {
            "branch": "task.git.branch",
            "commit": "task.git.commit",
            "headroom-wrapper": "task.headroom-wrapper",
            "pull-request": "task.git.pull-request",
            "push": "task.git.push",
            "release": "task.release",
        }
        for task, policy_id in expected.items():
            with self.subTest(task=task):
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    self._resolve(tasks=(task,), operations=(task,))
                self.assertEqual(failure.exception.code, "E_AUTHORIZATION")
                result = self._resolve(
                    tasks=(task,), operations=(task,), authorized=True
                )
                self.assertIn(
                    policy_id,
                    {entry["policy_id"] for entry in result.manifest["entries"]},
                )
                provenance = result.manifest["authorization_provenance"]
                self.assertEqual(provenance[0]["source_sha256"], SOURCE_SHA)
                self.assertEqual(result.manifest["repositories"], ["auth-sdk-m8"])
                self.assertEqual(result.manifest["operations"], [task])

        with self.assertRaises(w2b1.AgentContextError) as wrong_operation:
            self._resolve(tasks=("commit",), operations=("analyze",), authorized=True)
        self.assertEqual(wrong_operation.exception.code, "E_AUTHORIZATION")

    def test_cross_repository_scope_and_provenance_reach_the_receipt(self) -> None:
        repositories = ("auth-sdk-m8", "media-sdk-m8")
        operations = ("analyze",)
        with self.assertRaises(w2b1.AgentContextError) as missing_task:
            self._resolve(repositories=repositories)
        self.assertEqual(missing_task.exception.code, "E_AUTHORIZATION")
        with self.assertRaises(w2b1.AgentContextError) as missing_authorization:
            self._resolve(
                repositories=repositories,
                tasks=("cross-repository",),
                operations=operations,
            )
        self.assertEqual(missing_authorization.exception.code, "E_AUTHORIZATION")

        resolved = self._resolve(
            repositories=repositories,
            tasks=("cross-repository",),
            operations=operations,
            authorized=True,
        )
        capability = _capability()
        kernel = DeliveryKernel()
        prepared = kernel.prepare(
            DeliveryRequest(
                workspace_root=WORKSPACE,
                resolved=resolved,
                capability_row=capability,
                trusted=True,
                reviewed_tree={"algorithm": "git-sha1", "value": "b" * 40},
                capability_evidence_id=w2b1.canonical_sha256(capability),
                client_session_id="w4.task.fixture",
                channel_id="fixture",
            )
        )
        try:
            delivered = kernel.handoff(prepared, FakeTransportAdapter())
            self.assertEqual(delivered.receipt["repositories"], sorted(repositories))
            self.assertEqual(delivered.receipt["tasks"], ["cross-repository"])
            self.assertEqual(delivered.receipt["operations"], ["analyze"])
            self.assertEqual(
                delivered.receipt["authorization_provenance"],
                resolved.manifest["authorization_provenance"],
            )
        finally:
            kernel.cleanup(prepared.runtime_dir, WORKSPACE)


if __name__ == "__main__":
    unittest.main()
