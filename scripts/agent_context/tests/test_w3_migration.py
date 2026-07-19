from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1


WORKSPACE = Path(__file__).resolve().parents[3]

V1_REGISTRY = {
    "auth-sdk-m8": "python",
    "media-sdk-m8": "python",
    "fastapi-m8": "python",
    "imgtools_m8": "python",
    "security-tests-m8": "python",
    "fa-auth-m8": "python",
    "media-service-m8": "python",
    "media-worker-m8": "python",
    "prompt-engine-m8": "python",
    "reparto-docente-m8": "python",
    "fa-ui-m8": "typescript",
    "astro-ui-m8": "astro-ui",
    "astro-auth-m8": "astro-plugin",
    "astro-media-m8": "astro-plugin",
    "astro-prompt-m8": "astro-plugin",
    "astro-reparto-m8": "astro-plugin",
}

V1_BUNDLES = {
    "python": [
        "context/python.md",
        "context/env.md",
        "context/git.md",
        "contracts/workspace.contract.md",
    ],
    "typescript": [
        "context/typescript.md",
        "context/env.md",
        "context/git.md",
        "contracts/workspace.contract.md",
    ],
    "astro-plugin": [
        "context/typescript.md",
        "context/astro-plugin.md",
        "context/env.md",
        "context/git.md",
        "contracts/workspace.contract.md",
    ],
    "astro-ui": [
        "context/typescript.md",
        "context/astro-plugin.md",
        "context/env.md",
        "context/git.md",
        "contracts/workspace.contract.md",
    ],
    "docker": [
        "context/docker.md",
        "context/env.md",
        "context/git.md",
        "contracts/workspace.contract.md",
    ],
    "contracts": ["contracts/workspace.contract.md"],
}


class W3MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = w2b1.parse_strict_json(
            (WORKSPACE / ".workspace/repo-types.json").read_bytes()
        )
        cls.index = w2b1.parse_strict_json(
            (WORKSPACE / ".workspace/policy.index.json").read_bytes()
        )

    def test_w4_activates_the_closed_faceted_v2_pair(self) -> None:
        w2b1.validate_workspace_configuration_v2(self.registry, self.index)
        self.assertEqual(self.registry["schema_version"], 2)
        self.assertEqual(self.index["schema_version"], 2)
        self.assertEqual(self.index["mode"], "faceted")
        self.assertEqual(len(self.registry["repositories"]), 16)

    def test_registry_contains_only_live_direct_child_repositories(self) -> None:
        registered = {item["id"] for item in self.registry["repositories"]}
        direct_git_children = {
            child.name
            for child in WORKSPACE.iterdir()
            if child.is_dir() and (child / ".git").is_dir()
        }
        self.assertEqual(registered, direct_git_children)
        self.assertNotIn("docker_compose", registered)
        self.assertNotIn("traefik", registered)
        self.assertNotIn("fa-ui-m8/app", registered)

    def test_registry_preserves_the_step_3_1_classification(self) -> None:
        classification = w2b1.parse_strict_json(
            (
                WORKSPACE
                / ".workspace/status/fa-workspace/agent-configuration-token-efficiency-w3-repository-classification-2026-07-19.json"
            ).read_bytes()
        )
        expected = [
            {
                "id": repository["id"],
                "path": repository["path"],
                "kind": repository["kind"],
                "layer": repository["layer"],
                "facets": repository["facets"],
                "migration": {"v1_bundle": repository["migration_v1_bundle"]},
            }
            for repository in classification["repositories"]
        ]
        self.assertEqual(self.registry["repositories"], expected)

    def test_w3_selectors_remain_present_but_are_not_active_faceted_input(self) -> None:
        self.assertEqual(
            {item["id"]: item["migration"]["v1_bundle"] for item in self.registry["repositories"]},
            V1_REGISTRY,
        )
        self.assertNotIn("compatibility_bundles", self.index)


if __name__ == "__main__":
    unittest.main()
