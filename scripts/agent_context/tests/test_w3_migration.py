from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1


WORKSPACE = Path(__file__).resolve().parents[3]

class W3MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = w2b1.parse_strict_json(
            (WORKSPACE / ".workspace/repo-types.json").read_bytes()
        )
        cls.index = w2b1.parse_strict_json(
            (WORKSPACE / ".workspace/policy.index.json").read_bytes()
        )
        cls.historical = w2b1.parse_strict_json(
            (
                WORKSPACE
                / "scripts/agent_context/fixtures/historical/v1-routing-2026-07-19.json"
            ).read_bytes()
        )

    def test_w4_activates_the_closed_faceted_v2_pair(self) -> None:
        w2b1.validate_workspace_configuration_v2(self.registry, self.index)
        self.assertEqual(self.registry["schema_version"], 2)
        self.assertEqual(self.index["schema_version"], 2)
        self.assertEqual(self.index["mode"], "faceted")
        self.assertEqual(len(self.registry["repositories"]), 16)

    def test_registry_contains_only_classified_direct_child_repositories(self) -> None:
        """The root fixture is sufficient; no child clone is a test dependency."""
        registered = {item["id"] for item in self.registry["repositories"]}
        self.assertEqual(registered, set(self.historical["registry"]))
        self.assertNotIn("docker_compose", registered)
        self.assertNotIn("traefik", registered)
        self.assertNotIn("fa-ui-m8/app", registered)

    def test_registry_preserves_the_step_3_1_classification_without_migration_metadata(self) -> None:
        classification = w2b1.parse_strict_json(
            (
                WORKSPACE
                / "scripts/agent_context/fixtures/evidence/w3-repository-classification-2026-07-19.json"
            ).read_bytes()
        )
        expected = [
            {
                "id": repository["id"],
                "path": repository["path"],
                "kind": repository["kind"],
                "layer": repository["layer"],
                "facets": repository["facets"],
            }
            for repository in classification["repositories"]
        ]
        self.assertEqual(self.registry["repositories"], expected)

    def test_historical_fixture_is_non_authoritative_and_live_schemas_reject_it(self) -> None:
        self.assertEqual(self.historical["fixture_type"], "historical-v1-routing")
        expected_bundles = {
            item["id"]: item["migration_v1_bundle"]
            for item in w2b1.parse_strict_json(
                (
                    WORKSPACE
                    / "scripts/agent_context/fixtures/evidence/w3-repository-classification-2026-07-19.json"
                ).read_bytes()
            )["repositories"]
        }
        self.assertEqual(self.historical["registry"], expected_bundles)
        self.assertNotIn("migration", self.registry["repositories"][0])
        self.assertNotIn("compatibility_bundles", self.index)
        with self.assertRaisesRegex(w2b1.AgentContextError, "unknown fields"):
            w2b1.validate_policy_index_v2({
                **self.index,
                "compatibility_bundles": self.historical["policy_index"],
            })


if __name__ == "__main__":
    unittest.main()
