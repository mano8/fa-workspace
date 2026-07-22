from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import child_rollout, w2b1


WORKSPACE = Path(__file__).resolve().parents[3]
ROLLED_OUT_REPOSITORIES = (
    "auth-sdk-m8", "media-sdk-m8", "fastapi-m8", "imgtools_m8",
    "security-tests-m8", "fa-auth-m8", "media-service-m8", "media-worker-m8",
    "prompt-engine-m8", "reparto-docente-m8", "fa-ui-m8", "astro-ui-m8",
    "astro-auth-m8", "astro-media-m8", "astro-prompt-m8", "astro-reparto-m8",
)
LIVE_ROLLOUTS_AVAILABLE = all(
    (WORKSPACE / repository / name).is_file()
    for repository in ROLLED_OUT_REPOSITORIES
    for name in ("AGENTS.md", "CLAUDE.md", "REPOSITORY_CONTEXT.md")
)


class ChildRolloutContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = w2b1.parse_strict_json(
            (WORKSPACE / ".workspace/repo-types.json").read_bytes()
        )
        self.record = w2b1.parse_strict_json(
            (WORKSPACE / child_rollout.ROLLOUT_RECORD).read_bytes()
        )

    def test_frozen_boundaries_remain_valid_after_all_rollouts(self) -> None:
        child_rollout.validate_rollout_record(
            WORKSPACE,
            self.registry,
            self.record,
            verify_live_inputs=False,
        )
        self.assertEqual(len(self.record["boundaries"]), 16)
        self.assertTrue(
            all(
                boundary["exact_allowlist"] == child_rollout.EXACT_ALLOWLIST
                for boundary in self.record["boundaries"]
            )
        )

    @unittest.skipUnless(LIVE_ROLLOUTS_AVAILABLE, "live child repositories are external")
    def test_live_completed_c02_through_c16_rollouts_have_one_neutral_owner(self) -> None:
        for repository_id in ROLLED_OUT_REPOSITORIES[1:]:
            child = WORKSPACE / repository_id
            sources = {
                name: (child / name).read_bytes()
                for name in ("AGENTS.md", "CLAUDE.md", "REPOSITORY_CONTEXT.md")
            }
            for name, raw in sources.items():
                with self.subTest(repository=repository_id, source=name):
                    self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                    self.assertNotIn(b"\r", raw)
                    self.assertTrue(raw.endswith(b"\n"))
                    raw.decode("utf-8")
                    self.assertNotIn(b"/.workspace", raw)
                    self.assertNotIn(b"/workspace", raw)
            self.assertIn(b"REPOSITORY_CONTEXT.md", sources["AGENTS.md"])
            self.assertIn(b"REPOSITORY_CONTEXT.md", sources["CLAUDE.md"])
            self.assertNotIn(b"## Layer", sources["AGENTS.md"])
            self.assertNotIn(b"## Layer", sources["CLAUDE.md"])
            self.assertIn(b"## Layer", sources["REPOSITORY_CONTEXT.md"])

            for agent, entrypoint in (("codex", "AGENTS.md"), ("claude", "CLAUDE.md")):
                with self.subTest(repository=repository_id, agent=agent, mode="parent-found"):
                    nested = child_rollout.resolve_child_instruction_context(
                        child,
                        repository_id=repository_id,
                        agent=agent,
                        workspace_root=WORKSPACE,
                    )
                    self.assertEqual(nested.local_sources, ("REPOSITORY_CONTEXT.md", entrypoint))
                    self.assertTrue(nested.workspace_enhancement_available)
                with self.subTest(repository=repository_id, agent=agent, mode="parent-absent"):
                    standalone = child_rollout.resolve_child_instruction_context(
                        child, repository_id=repository_id, agent=agent
                    )
                    self.assertEqual(standalone.local_sources, ("REPOSITORY_CONTEXT.md", entrypoint))
                    self.assertFalse(standalone.workspace_enhancement_available)

    @unittest.skipUnless(LIVE_ROLLOUTS_AVAILABLE, "live child repositories are external")
    def test_live_c01_rollout_has_one_neutral_owner_in_both_modes(self) -> None:
        child = WORKSPACE / "auth-sdk-m8"
        sources = {
            name: (child / name).read_bytes()
            for name in ("AGENTS.md", "CLAUDE.md", "REPOSITORY_CONTEXT.md")
        }
        for name, raw in sources.items():
            with self.subTest(source=name):
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", raw)
                self.assertTrue(raw.endswith(b"\n"))
                self.assertNotIn(b"/.workspace", raw)
                self.assertNotIn(b"/workspace", raw)
        self.assertIn(b"REPOSITORY_CONTEXT.md", sources["AGENTS.md"])
        self.assertIn(b"REPOSITORY_CONTEXT.md", sources["CLAUDE.md"])
        self.assertNotIn(b"## Layer", sources["AGENTS.md"])
        self.assertNotIn(b"## Layer", sources["CLAUDE.md"])
        self.assertIn(b"## Layer", sources["REPOSITORY_CONTEXT.md"])

        for agent, entrypoint in (("codex", "AGENTS.md"), ("claude", "CLAUDE.md")):
            with self.subTest(agent=agent, mode="parent-found"):
                nested = child_rollout.resolve_child_instruction_context(
                    child,
                    repository_id="auth-sdk-m8",
                    agent=agent,
                    workspace_root=WORKSPACE,
                )
                self.assertEqual(nested.local_sources, ("REPOSITORY_CONTEXT.md", entrypoint))
                self.assertTrue(nested.workspace_enhancement_available)
            with self.subTest(agent=agent, mode="parent-absent"):
                standalone = child_rollout.resolve_child_instruction_context(
                    child,
                    repository_id="auth-sdk-m8",
                    agent=agent,
                )
                self.assertEqual(
                    standalone.local_sources, ("REPOSITORY_CONTEXT.md", entrypoint)
                )
                self.assertFalse(standalone.workspace_enhancement_available)

    def test_validator_rejects_allowlist_or_source_evidence_drift(self) -> None:
        bad_allowlist = copy.deepcopy(self.record)
        bad_allowlist["boundaries"][0]["exact_allowlist"].append("pyproject.toml")
        with self.assertRaisesRegex(child_rollout.ChildRolloutError, "three-path"):
            child_rollout.validate_rollout_record(WORKSPACE, self.registry, bad_allowlist)
        bad_source = copy.deepcopy(self.record)
        bad_source["source_evidence"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(child_rollout.ChildRolloutError, "source evidence drifted"):
            child_rollout.validate_rollout_record(WORKSPACE, self.registry, bad_source)

    def test_resolver_proves_parent_found_and_parent_absent_for_both_agents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            child = root / "auth-sdk-m8"
            (root / ".workspace").mkdir(parents=True)
            child.mkdir()
            (root / ".m8-workspace-root").write_bytes(b"m8-workspace-v2\n")
            shutil.copy2(
                WORKSPACE / ".workspace/repo-types.json",
                root / ".workspace/repo-types.json",
            )
            for name in ("AGENTS.md", "CLAUDE.md", "REPOSITORY_CONTEXT.md"):
                (child / name).write_text(
                    f"# {name}\n\nPortable child-local context.\n",
                    encoding="utf-8",
                    newline="\n",
                )
            standalone = Path(temporary) / "standalone-auth-sdk-m8"
            shutil.copytree(child, standalone)

            for agent, entrypoint in (("codex", "AGENTS.md"), ("claude", "CLAUDE.md")):
                with self.subTest(agent=agent, mode="parent-found"):
                    nested = child_rollout.resolve_child_instruction_context(
                        child,
                        repository_id="auth-sdk-m8",
                        agent=agent,
                        workspace_root=root,
                    )
                    self.assertEqual(nested.mode, "parent-found")
                    self.assertEqual(
                        nested.local_sources, ("REPOSITORY_CONTEXT.md", entrypoint)
                    )
                    self.assertTrue(nested.workspace_enhancement_available)
                    self.assertTrue(nested.canonical_receipt_required)
                with self.subTest(agent=agent, mode="parent-absent"):
                    local = child_rollout.resolve_child_instruction_context(
                        standalone,
                        repository_id="auth-sdk-m8",
                        agent=agent,
                    )
                    self.assertEqual(local.mode, "parent-absent")
                    self.assertEqual(
                        local.local_sources, ("REPOSITORY_CONTEXT.md", entrypoint)
                    )
                    self.assertFalse(local.workspace_enhancement_available)
                    self.assertFalse(local.canonical_receipt_required)

    def test_parent_enhancement_rejects_invalid_or_unregistered_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            child = root / "unregistered"
            (root / ".workspace").mkdir(parents=True)
            child.mkdir()
            (root / ".m8-workspace-root").write_bytes(b"wrong\n")
            (root / ".workspace/repo-types.json").write_text(
                json.dumps(self.registry) + "\n", encoding="utf-8", newline="\n"
            )
            for name in ("AGENTS.md", "REPOSITORY_CONTEXT.md"):
                (child / name).write_text("local\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(child_rollout.ChildRolloutError, "marker identity"):
                child_rollout.resolve_child_instruction_context(
                    child,
                    repository_id="auth-sdk-m8",
                    agent="codex",
                    workspace_root=root,
                )


if __name__ == "__main__":
    unittest.main()
