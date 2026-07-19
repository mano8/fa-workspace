from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.resolve_context import ResolutionRequest, resolve_context


WORKSPACE = Path(__file__).resolve().parents[3]


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


class W4AstroTaskTests(unittest.TestCase):
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

    def _resolve(self, *tasks: str):
        return resolve_context(
            ResolutionRequest(
                root=WORKSPACE,
                registry=self.registry,
                policy_index=self.index,
                policy_metadata=self.metadata,
                capability_row=_capability(),
                reviewed_tree={"algorithm": "git-sha1", "value": "b" * 40},
                agent="codex",
                platform="devcontainer",
                mode="non-interactive",
                repositories=("astro-auth-m8",),
                tasks=tasks,
                injection_evidence={
                    "generation": 0,
                    "native_discovery_disabled": True,
                    "exact_once_handoff_proven": True,
                    "sources": self.sources,
                },
            )
        )

    def test_core_has_no_opt_in_procedure(self) -> None:
        core = (WORKSPACE / ".workspace/context/astro-plugin.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Core invariants", core)
        self.assertIn("does not prescribe those procedures", core)
        for heading in (
            "Host-registration contract",
            "UI delivery",
            "Commands (uniform scripts)",
        ):
            self.assertNotIn(heading, core)

    def test_default_plugin_resolution_has_no_astro_task_overlay(self) -> None:
        result = self._resolve()
        selected = {entry["policy_id"] for entry in result.manifest["entries"]}
        self.assertFalse(any(policy.startswith("task.astro-") for policy in selected))

    def test_each_astro_task_restores_its_required_content_exactly_once(self) -> None:
        expected = {
            "astro-auth-adapter": (
                "task.astro-auth-adapter",
                ("warn, rather than throw", "*AuthAdapter", "fa-auth-astro"),
            ),
            "astro-host": (
                "task.astro-host",
                ("PUBLIC_*_API_BASE", "dynamic `import()`", "host API"),
            ),
            "astro-plugin-testing": (
                "task.astro-plugin-testing",
                (
                    "build:registry",
                    "install-from-tarball smoke test",
                    "fresh Astro fixture",
                ),
            ),
            "astro-registry-scaffolding": (
                "task.astro-registry-scaffolding",
                (
                    "explicit package export subpaths",
                    "registry rebuild",
                    "shared data-table block",
                ),
            ),
        }
        for task, (policy_id, fragments) in expected.items():
            with self.subTest(task=task):
                result = self._resolve(task)
                selected = [entry["policy_id"] for entry in result.manifest["entries"]]
                self.assertEqual(selected.count(policy_id), 1)
                self.assertEqual(
                    [item for item in selected if item.startswith("task.astro-")],
                    [policy_id],
                )
                content = next(
                    entry["content"]
                    for entry in result.envelope["entries"]
                    if entry["policy_id"] == policy_id
                )
                for fragment in fragments:
                    self.assertIn(fragment, content)

    def test_generic_release_remains_a_single_opt_in_release_overlay(self) -> None:
        self.assertEqual(self.index["tasks"]["release"]["policies"], ["task.release"])


if __name__ == "__main__":
    unittest.main()
