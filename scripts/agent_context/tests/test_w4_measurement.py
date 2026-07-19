from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.measure_w4_context import build_report


WORKSPACE = Path(__file__).resolve().parents[3]


class W4MeasurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_report(WORKSPACE, "2026-07-19T15:10:00Z")

    def test_replacement_gates_are_derived_from_reproduced_step_0_6_baselines(self) -> None:
        gates = self.report["replacement_gates"]
        self.assertEqual(gates["auth-sdk-implementation-target"]["maximum_bytes"], 11364)
        self.assertEqual(gates["astro-plugin-implementation-target"]["maximum_bytes"], 15871)

    def test_codex_records_use_non_overlapping_exact_accounting(self) -> None:
        measured = [item for item in self.report["codex_records"] if item["result"].startswith("PASS")]
        self.assertEqual({item["fixture_id"] for item in measured}, {"sdk-implementation", "worker-environment", "astro-host-implementation", "astro-plugin-implementation"})
        for record in measured:
            with self.subTest(fixture=record["fixture_id"]):
                self.assertEqual(
                    record["baseline_native_evidence"]["bytes"],
                    len((WORKSPACE / "AGENTS.md").read_bytes()),
                )
                self.assertEqual(record["other_model_visible_bootstrap_bytes"], 0)
                self.assertEqual(
                    record["model_visible_total"],
                    record["baseline_native_evidence"]["bytes"]
                    + record["serialized_injected_envelope_bytes"],
                )
                self.assertTrue(record["raw_injected_content"]["not_added_to_model_visible_total"])
                self.assertLessEqual(record["model_visible_total"], record["effective_hard_limit"])

    def test_unsupported_authorization_and_capability_rows_are_explicitly_not_measured(self) -> None:
        blocked = {item["fixture_id"]: item["reason"] for item in self.report["codex_records"] if item["result"] == "NOT_MEASURED"}
        self.assertIn("api-service-commit", blocked)
        self.assertIn("shared-ui-release", blocked)
        self.assertIn("host-cross-repository", blocked)
        self.assertEqual(len(self.report["claude_records"]), 10)
        self.assertTrue(all(item["capability_status"] == "LIMITED" for item in self.report["claude_records"]))
        self.assertTrue(all(item["result"] == "NOT_MEASURED" for item in self.report["claude_records"]))
        required_accounting_fields = {
            "baseline_native_evidence", "manifest_visibility", "raw_injected_content",
            "serialized_injected_envelope_bytes", "serialization_overhead_bytes",
            "other_model_visible_bootstrap_bytes", "model_visible_total", "hashes",
            "policy_ceiling", "channel_client_allowance", "verified_channel_limit",
            "reserved_margin", "effective_hard_limit", "result",
        }
        for record in self.report["claude_records"]:
            with self.subTest(fixture=record["fixture_id"]):
                self.assertTrue(required_accounting_fields.issubset(record))
                self.assertIsNone(record["baseline_native_evidence"])
                self.assertIsNone(record["manifest_visibility"])
                self.assertIsNone(record["serialized_injected_envelope_bytes"])
                self.assertIsNone(record["model_visible_total"])
                self.assertIsNone(record["effective_hard_limit"])


if __name__ == "__main__":
    unittest.main()
