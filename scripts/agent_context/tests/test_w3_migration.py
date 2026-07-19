from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.resolve_context import resolve_compatibility_context


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

    def test_active_files_are_the_closed_transitional_v2_pair(self) -> None:
        w2b1.validate_workspace_configuration_v2(self.registry, self.index)
        self.assertEqual(self.registry["schema_version"], 2)
        self.assertEqual(self.index["schema_version"], 2)
        self.assertEqual(self.index["mode"], "transitional-v1-bundles")
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

    def test_every_repository_resolves_its_unchanged_legacy_bundle(self) -> None:
        repository_ids = tuple(reversed(sorted(V1_REGISTRY)))
        result = resolve_compatibility_context(
            self.registry, self.index, repository_ids
        )
        self.assertEqual(result.repositories, tuple(sorted(V1_REGISTRY)))
        self.assertEqual(
            [(entry["repository_id"], entry["bundle"], entry["paths"]) for entry in result.entries],
            [
                (repository_id, V1_REGISTRY[repository_id], V1_BUNDLES[V1_REGISTRY[repository_id]])
                for repository_id in sorted(V1_REGISTRY)
            ],
        )
        for entry in result.entries:
            for path in entry["paths"]:
                self.assertTrue((WORKSPACE / ".workspace" / path).is_file(), path)

    def test_in_memory_v1_projection_is_an_atomic_rollback_fixture(self) -> None:
        projected_registry, projected_bundles = w2b1.project_transitional_v1_configuration(
            self.registry, self.index
        )
        self.assertEqual(projected_registry, V1_REGISTRY)
        self.assertEqual(projected_bundles, V1_BUNDLES)

    def test_missing_selector_or_unknown_bundle_fails_closed(self) -> None:
        malformed_registry = {
            **self.registry,
            "repositories": [
                {**self.registry["repositories"][0], "migration": {"v1_bundle": "missing"}},
                *self.registry["repositories"][1:],
            ],
        }
        with self.assertRaisesRegex(w2b1.AgentContextError, "no compatibility bundle"):
            w2b1.validate_workspace_configuration_v2(malformed_registry, self.index)


if __name__ == "__main__":
    unittest.main()
