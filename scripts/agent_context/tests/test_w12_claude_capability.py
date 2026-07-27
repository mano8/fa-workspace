"""Step 12.1 frozen installed-Claude capability-matrix fixtures.

These tests are offline.  They never invoke a client, start a server, or read a
child repository; they check that the frozen matrix recomputes from the tracked
probe, stays inside the contracts' limit and status rules, and does not silently
promote Claude delivery before Steps 12.2--12.6 do that work.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import claude_adapter, codex_adapter, probe_claude_capabilities, w2b1
from agent_context.resolve_context import ResolutionRequest, resolve_context
from agent_context.shared_validation import validate_resolved


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "scripts/agent_context/fixtures/evidence/w12-claude-capability-evidence-2026-07-27.json"
REPORT = ROOT / "scripts/agent_context/fixtures/evidence/w12-claude-capability-evidence-2026-07-27.md"
PROBE = ROOT / "scripts/agent_context/probe_claude_capabilities.py"
REQUIRED_ROW_KEYS = {
    "agent", "platform", "mode", "status", "inspection_mechanism", "channel_id",
    "verified_channel_limit", "client_context_allowance", "reserved_margin",
    "start_supported", "resume_supported", "clear_supported", "compact_supported",
    "launcher_identity_available", "client_session_identity_available",
    "blocks_closeout",
}
STATUSES = {"REQUIRED", "OPTIONAL", "LIMITED", "UNSUPPORTED"}


class W12ClaudeCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.rows = self.evidence["rows"]

    def test_artifacts_are_utf8_lf_and_final_newline_terminated(self) -> None:
        for path in (EVIDENCE, REPORT, PROBE):
            raw = path.read_bytes()
            raw.decode("utf-8", "strict")
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), path)
            self.assertNotIn(b"\r", raw, path)
            self.assertTrue(raw.endswith(b"\n"), path)

    def test_frozen_probe_identity_matches_the_tracked_probe(self) -> None:
        self.assertEqual(
            self.evidence["probe"]["source_sha256"],
            hashlib.sha256(PROBE.read_bytes()).hexdigest(),
        )
        self.assertEqual(self.evidence["probe"]["source"], "scripts/agent_context/probe_claude_capabilities.py")
        self.assertFalse(self.evidence["probe"]["vendor_api_contacted"])
        self.assertEqual(self.evidence["probe"]["workspace_files_touched"], 0)

    def test_every_row_identity_recomputes_from_its_capability_row(self) -> None:
        for row in self.rows:
            with self.subTest(row=row["row_id"]):
                self.assertEqual(set(row["capability_row"]), REQUIRED_ROW_KEYS)
                self.assertIn(row["capability_row"]["status"], STATUSES)
                self.assertEqual(row["capability_row"]["agent"], "claude")
                self.assertEqual(
                    row["capability_evidence_id"],
                    w2b1.canonical_sha256(row["capability_row"]),
                )
        identifiers = [row["capability_evidence_id"] for row in self.rows]
        self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_effective_hard_limits_recompute_from_the_measurement_formula(self) -> None:
        policy = self.evidence["policy_hard_limit"]
        for row in self.rows:
            capability = row["capability_row"]
            expected = min(
                policy,
                capability["verified_channel_limit"],
                capability["client_context_allowance"] - capability["reserved_margin"],
            )
            with self.subTest(row=row["row_id"]):
                self.assertEqual(row["effective_hard_limit"], max(expected, 0))
                self.assertGreaterEqual(row["effective_hard_limit"], 0)
                self.assertLessEqual(row["effective_hard_limit"], policy)

    def test_frozen_fixtures_reproduce_exactly_from_the_probe(self) -> None:
        for row in self.rows:
            for fixture in row["byte_exact_fixtures"]:
                with self.subTest(row=row["row_id"], bytes=fixture["bytes"]):
                    raw = probe_claude_capabilities.build_fixture(fixture["bytes"], fixture["mode"])
                    self.assertEqual(len(raw), fixture["bytes"])
                    self.assertEqual(len(raw.decode("utf-8")), fixture["characters"])
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), fixture["sha256"])
                    self.assertLessEqual(fixture["bytes"], row["capability_row"]["verified_channel_limit"])

    def test_hook_channel_boundary_is_frozen_below_its_substitution_point(self) -> None:
        channel = self.evidence["channels"]["claude-hook-additional-context"]
        self.assertEqual(channel["max_exact_characters"], 10000)
        self.assertEqual(channel["min_rejected_characters"], 10001)
        self.assertLessEqual(channel["verified_channel_limit_bytes"], channel["max_exact_characters"])
        self.assertIn("persisted-output", channel["over_limit_behavior"])
        for row in self.rows:
            if row["capability_row"]["channel_id"] == "claude-hook-additional-context":
                self.assertEqual(
                    row["capability_row"]["verified_channel_limit"],
                    channel["verified_channel_limit_bytes"],
                )

    def test_required_rows_carry_complete_delivery_evidence(self) -> None:
        required = [row for row in self.rows if row["capability_row"]["status"] == "REQUIRED"]
        self.assertTrue(required)
        for row in required:
            with self.subTest(row=row["row_id"]):
                capability = row["capability_row"]
                self.assertTrue(capability["start_supported"])
                self.assertTrue(capability["client_session_identity_available"])
                self.assertNotEqual(capability["inspection_mechanism"], "unavailable")
                self.assertTrue(row["byte_exact_fixtures"])
                self.assertTrue(capability["blocks_closeout"])
                self.assertFalse(capability["compact_supported"])
        for row in self.rows:
            if row["capability_row"]["status"] != "REQUIRED":
                self.assertFalse(row["capability_row"]["blocks_closeout"], row["row_id"])

    def test_unsupported_row_freezes_no_channel(self) -> None:
        unsupported = [row for row in self.rows if row["capability_row"]["status"] == "UNSUPPORTED"]
        self.assertTrue(unsupported)
        for row in unsupported:
            self.assertEqual(row["capability_row"]["channel_id"], "none")
            self.assertEqual(row["capability_row"]["verified_channel_limit"], 0)
            self.assertEqual(row["capability_row"]["inspection_mechanism"], "unavailable")
            self.assertEqual(row["byte_exact_fixtures"], [])

    def test_native_inspection_records_a_real_mechanism_and_its_limitation(self) -> None:
        inspection = self.evidence["native_load_inspection"]
        self.assertEqual(inspection["mechanism"], "claude-loopback-model-input-capture")
        self.assertEqual(inspection["in_band_mechanism"], "unavailable")
        self.assertIn("model self-report", inspection["rejected_mechanisms"])
        self.assertIn("separate", inspection["limitation"])
        self.assertEqual(
            inspection["verified_source_sha256"],
            "1ba85bf593fd71859f37703449c516f2404829ea7bc17a83b910f8576a6b1a11",
        )

    def test_duplicate_injection_risk_is_recorded_for_step_12_4(self) -> None:
        self.assertIn("SessionStart", self.evidence["channels"]["claude-hook-additional-context"]["events_verified"])
        self.assertIn("SessionStart", self.evidence["hook_events_executed_by_probe"])
        self.assertIn("SessionStart", REPORT.read_text(encoding="utf-8"))

    def test_freeze_does_not_promote_claude_delivery_yet(self) -> None:
        self.assertEqual(
            claude_adapter.CURRENT_CLAUDE_CONFIGURATION.capability_row["status"], "LIMITED"
        )
        self.assertFalse(claude_adapter.CURRENT_CLAUDE_CONFIGURATION.project_hook_configured)
        report = REPORT.read_text(encoding="utf-8")
        self.assertIn("freezes capability only", report)
        self.assertIn("activates no hook", report)

    def _resolve(self, row_id: str, bootstrap_bytes: int):
        registry = w2b1.parse_strict_json((ROOT / ".workspace/repo-types.json").read_bytes())
        index = w2b1.parse_strict_json((ROOT / ".workspace/policy.index.json").read_bytes())
        metadata = w2b1.parse_strict_json((ROOT / ".workspace/policy.metadata.json").read_bytes())
        capability = next(row["capability_row"] for row in self.rows if row["row_id"] == row_id)
        sources = [
            {
                "path": unit["path"],
                "sha256": hashlib.sha256((ROOT / unit["path"]).read_bytes()).hexdigest(),
            }
            for unit in sorted(metadata["units"], key=lambda item: item["path"])
        ]
        resolved = resolve_context(
            ResolutionRequest(
                root=ROOT, registry=registry, policy_index=index, policy_metadata=metadata,
                capability_row=capability,
                reviewed_tree={"algorithm": "git-sha1", "value": "b" * 40},
                agent=capability["agent"], platform=capability["platform"],
                mode=capability["mode"], repositories=("fa-auth-m8",),
                other_model_visible_bootstrap_bytes=bootstrap_bytes,
                injection_evidence={
                    "generation": 0, "native_discovery_disabled": True,
                    "exact_once_handoff_proven": True, "sources": sources,
                },
            )
        )
        return capability, resolved

    def test_frozen_rows_drive_the_resolver_and_recompute_their_identity(self) -> None:
        capability, resolved = self._resolve(
            "claude-devcontainer-non-interactive-append-system-prompt", 0
        )
        self.assertEqual(
            resolved.manifest["capability_evidence_id"], w2b1.canonical_sha256(capability)
        )
        self.assertEqual(
            len(resolved.envelope_bytes),
            self.evidence["measurement"]["serialized_injected_envelope_bytes"],
        )

    def test_measurement_boundary_selects_the_full_content_row_for_fa_auth_m8(self) -> None:
        measurement = self.evidence["measurement"]
        native = measurement["native_model_visible_bytes"]
        self.assertEqual(
            measurement["model_visible_total"],
            native + measurement["serialized_injected_envelope_bytes"],
        )
        capability, resolved = self._resolve(
            "claude-devcontainer-non-interactive-hook-additional-context", native
        )
        with self.assertRaises(w2b1.AgentContextError) as failure:
            validate_resolved(
                workspace=ROOT, manifest=resolved.manifest, envelope=resolved.envelope,
                envelope_bytes=resolved.envelope_bytes, capability_row=capability,
                channel_id=capability["channel_id"],
            )
        self.assertEqual(failure.exception.code, "E_BUDGET")
        self.assertFalse(measurement["fits_hook_row"])

        capability, resolved = self._resolve(
            "claude-devcontainer-non-interactive-append-system-prompt", native
        )
        validate_resolved(
            workspace=ROOT, manifest=resolved.manifest, envelope=resolved.envelope,
            envelope_bytes=resolved.envelope_bytes, capability_row=capability,
            channel_id=capability["channel_id"],
        )
        self.assertEqual(
            resolved.manifest["accounting"]["model_visible_total"],
            measurement["model_visible_total"],
        )
        self.assertTrue(measurement["fits_full_content_row"])

    def test_codex_capability_authority_is_untouched(self) -> None:
        codex_evidence = ROOT / codex_adapter.CAPABILITY_EVIDENCE_PATH
        self.assertEqual(
            hashlib.sha256(codex_evidence.read_bytes()).hexdigest(),
            codex_adapter.CAPABILITY_EVIDENCE_SHA256,
        )
        self.assertTrue(self.evidence["supersedes"]["codex_rows_unchanged"])


if __name__ == "__main__":
    unittest.main()
