"""Step 12.4 exact Claude hook channel and single injection authority.

These tests are offline.  They never invoke the Claude client and never contact
a vendor API: the byte-exactness of the channel is proved by the tracked Step
12.4 round-trip artifact, which a real client produced against a loopback
recorder, and this suite proves what the gate, the kernel storage, and the
adapter do with that evidence.

Coverage is the whole authority: the gate returns the exact armed envelope,
claims each launcher-controlled generation exactly once, refuses every
unverified state with no claim, stores nothing outside the kernel's owner-only
runtime session, and never becomes a second injection authority.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import claude_delivery_adapter as adapter
from agent_context import claude_hook_gate as gate
from agent_context import w2b1
from agent_context.delivery_kernel import DeliveryKernel


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "scripts/agent_context/fixtures/evidence/w12-claude-hook-channel-evidence-2026-07-28.json"
REPORT = ROOT / "scripts/agent_context/fixtures/evidence/w12-claude-hook-channel-evidence-2026-07-28.md"
HOOK_ROW = "claude-devcontainer-non-interactive-hook-additional-context"
SESSION = "7d3c1c94-2f21-4a1a-9a4f-1f2a3b4c5d6e"
LAUNCH = "launch-" + "a" * 32
# The envelope the gate must return byte-exactly, with the escaping, CRLF, and
# non-ASCII content a real policy envelope can carry.
ENVELOPE = '{"entries":[{"content":"a\\\\\\"é—\r\\n\\t~`|"}],"generation":0}'.encode()


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class ArmedRuntime:
    """One owner-only runtime session armed exactly as the transport arms it."""

    def __init__(self, base: Path, *, generation: int = 0) -> None:
        self.workspace_root = base
        self.kernel = DeliveryKernel()
        self.runtime_dir = self.kernel._new_runtime_dir(base)
        self.generation = generation

    def arm(self, payload: bytes = ENVELOPE, **overrides: object) -> dict[str, object]:
        state: dict[str, object] = {
            "schema_version": 1, "channel_id": gate.CHANNEL_ID, "launch_id": LAUNCH,
            "client_session_id": SESSION, "generation": self.generation,
            "manifest_id": _digest(b"fixture-manifest"), "envelope_sha256": _digest(payload),
            "envelope_bytes": len(payload), "verified_channel_limit": 10000,
            "effective_hard_limit": 10000, "model_visible_total": len(payload) + 21,
            "round_trip_evidence_id": adapter.HOOK_ROUND_TRIP_EVIDENCE,
            "capability_evidence_id": _digest(b"fixture-capability"),
            "launch_scope": str(self.workspace_root),
        }
        state.update(overrides)
        self.kernel.write_channel_artifact(
            self.runtime_dir, gate.CHANNEL_ENVELOPE_ARTIFACT, payload, replace=True,
        )
        self.kernel.write_channel_artifact(
            self.runtime_dir, gate.CHANNEL_STATE_ARTIFACT, w2b1.canonical_bytes(state),
            replace=True,
        )
        return state

    def payload(self, **overrides: object) -> dict[str, object]:
        request = {
            "hook_event_name": gate.HOOK_EVENT, "session_id": SESSION,
            "cwd": str(self.workspace_root), "prompt": "fixture prompt",
        }
        request.update(overrides)
        return request

    def claims(self) -> list[str]:
        return sorted(
            child.name for child in self.runtime_dir.iterdir()
            if child.name.startswith("channel-claim-")
        )


class W12ClaudeHookGateTests(unittest.TestCase):
    """The gate is the only pre-task injection authority, and only once."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.armed = ArmedRuntime(self.base)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_the_gate_returns_the_exact_armed_envelope_and_claims_it_once(self) -> None:
        self.armed.arm()
        output = gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], gate.HOOK_EVENT)
        self.assertEqual(specific["additionalContext"].encode("utf-8"), ENVELOPE)
        self.assertEqual(self.armed.claims(), ["channel-claim-000000.json"])
        claim = json.loads(
            (self.armed.runtime_dir / gate.claim_artifact(0)).read_text(encoding="utf-8")
        )
        self.assertEqual(claim["envelope_sha256"], _digest(ENVELOPE))
        self.assertEqual(claim["delivered_bytes"], len(ENVELOPE))
        self.assertEqual(claim["client_session_id"], SESSION)
        self.assertEqual(claim["launch_id"], LAUNCH)

    def test_a_repeated_prompt_in_one_generation_never_delivers_a_second_copy(self) -> None:
        self.armed.arm()
        first = gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        second = gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        third = gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        self.assertIn("additionalContext", first["hookSpecificOutput"])
        for repeat in (second, third):
            self.assertEqual(repeat, {"hookSpecificOutput": {"hookEventName": gate.HOOK_EVENT}})
        self.assertEqual(self.armed.claims(), ["channel-claim-000000.json"])

    def test_the_next_generation_is_a_separate_exactly_once_claim(self) -> None:
        self.armed.arm()
        gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        # A resumed launch arms the same session directory for generation one.
        self.armed.generation = 1
        self.armed.arm(payload=ENVELOPE + b" ")
        output = gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        self.assertEqual(
            output["hookSpecificOutput"]["additionalContext"].encode("utf-8"), ENVELOPE + b" "
        )
        self.assertEqual(
            self.armed.claims(), ["channel-claim-000000.json", "channel-claim-000001.json"]
        )

    def test_every_unverified_state_is_refused_with_no_claim(self) -> None:
        cases: list[tuple[str, dict, dict]] = [
            # code, arm overrides, hook payload overrides
            ("E_CHANNEL", {}, {"hook_event_name": "SessionStart"}),
            ("E_CHANNEL", {}, {"hook_event_name": "PreToolUse"}),
            ("E_LIFECYCLE", {}, {"session_id": "other-session"}),
            ("E_LIFECYCLE", {}, {"session_id": None}),
            ("E_SCOPE_UNAVAILABLE", {}, {"cwd": "/"}),
            ("E_CHANNEL", {"channel_id": "claude-cli-append-system-prompt"}, {}),
            ("E_CHANNEL", {"envelope_sha256": "0" * 64}, {}),
            ("E_CHANNEL", {"envelope_bytes": 3}, {}),
            ("E_CHANNEL", {"verified_channel_limit": 4}, {}),
            ("E_CHANNEL", {"schema_version": 2}, {}),
            ("E_CHANNEL", {"launch_id": "Not An Identifier"}, {}),
            ("E_BUDGET", {"model_visible_total": 10001}, {}),
        ]
        for code, armed, payload in cases:
            with self.subTest(code=code, armed=sorted(armed), payload=sorted(payload)):
                self.tearDown()
                self.setUp()
                self.armed.arm(**armed)
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    gate.gate(
                        runtime_dir=self.armed.runtime_dir, payload=self.armed.payload(**payload),
                    )
                self.assertEqual(failure.exception.code, code)
                self.assertEqual(self.armed.claims(), [])

    def test_an_armed_envelope_that_drifted_is_never_offered(self) -> None:
        self.armed.arm()
        self.armed.kernel.write_channel_artifact(
            self.armed.runtime_dir, gate.CHANNEL_ENVELOPE_ARTIFACT, ENVELOPE + b"drift",
            replace=True,
        )
        with self.assertRaises(w2b1.AgentContextError) as failure:
            gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        self.assertEqual(failure.exception.code, "E_CHANNEL")
        self.assertEqual(self.armed.claims(), [])

    def test_a_state_with_unknown_or_missing_fields_fails_closed(self) -> None:
        for mutate in (
            lambda state: state.pop("launch_scope"),
            lambda state: state.update(extra="unexpected"),
        ):
            with self.subTest(mutate=mutate):
                self.tearDown()
                self.setUp()
                state = self.armed.arm()
                mutate(state)
                self.armed.kernel.write_channel_artifact(
                    self.armed.runtime_dir, gate.CHANNEL_STATE_ARTIFACT,
                    w2b1.canonical_bytes(state), replace=True,
                )
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
                self.assertEqual(failure.exception.code, "E_CHANNEL")

    def test_an_unarmed_or_unsafe_runtime_session_delivers_nothing(self) -> None:
        with self.assertRaises(w2b1.AgentContextError) as failure:
            gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        self.assertEqual(failure.exception.code, "E_RUNTIME")
        self.armed.arm()
        if os.name == "posix":
            os.chmod(self.armed.runtime_dir / gate.CHANNEL_STATE_ARTIFACT, 0o644)
            with self.assertRaises(w2b1.AgentContextError) as failure:
                gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
            self.assertEqual(failure.exception.code, "E_RUNTIME")
            self.assertEqual(self.armed.claims(), [])

    def test_the_cli_blocks_the_prompt_on_any_failure_and_prints_json_on_success(self) -> None:
        self.armed.arm()
        stream = io.StringIO()
        with mock.patch.object(
            sys, "stdin", mock.Mock(buffer=io.BytesIO(json.dumps(self.armed.payload()).encode()))
        ), redirect_stdout(stream):
            status = gate.main(["--runtime-dir", str(self.armed.runtime_dir)])
        self.assertEqual(status, 0)
        self.assertEqual(
            json.loads(stream.getvalue())["hookSpecificOutput"]["additionalContext"].encode("utf-8"),
            ENVELOPE,
        )
        for raw in (b"not json", b"[]", json.dumps({"hook_event_name": "SessionStart"}).encode()):
            with self.subTest(raw=raw[:16]):
                with mock.patch.object(
                    sys, "stdin", mock.Mock(buffer=io.BytesIO(raw))
                ), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as reason:
                    status = gate.main(["--runtime-dir", str(self.armed.runtime_dir)])
                self.assertEqual(status, gate.BLOCKING_EXIT_CODE)
                self.assertTrue(reason.getvalue().startswith("E_"))

    def test_the_gate_runs_as_the_launcher_registers_it(self) -> None:
        """The reviewed file is executable through the exact registered command."""
        self.armed.arm()
        command = [
            sys.executable, str(ROOT / adapter.GATE_MODULE_PATH),
            "--runtime-dir", str(self.armed.runtime_dir),
        ]
        result = subprocess.run(
            command, input=json.dumps(self.armed.payload()).encode("utf-8"),
            capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"].encode("utf-8"),
            ENVELOPE,
        )


class W12ClaudeChannelStorageTests(unittest.TestCase):
    """Channel artifacts obey the same runtime-security policy as the receipt."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.kernel = DeliveryKernel()
        self.runtime_dir = self.kernel._new_runtime_dir(self.base)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_only_flat_channel_names_are_accepted(self) -> None:
        for name in (
            "../escape.json", "channel-../escape", "channel-a/b", "session.json",
            "channel-", "CHANNEL-state.json", "channel-state.json\x00", 5,
        ):
            with self.subTest(name=name):
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    self.kernel.write_channel_artifact(self.runtime_dir, name, b"x")
                self.assertEqual(failure.exception.code, "E_RUNTIME")

    def test_artifacts_are_owner_only_atomic_and_no_replace_by_default(self) -> None:
        path = self.kernel.write_channel_artifact(
            self.runtime_dir, gate.CHANNEL_ENVELOPE_ARTIFACT, b"payload"
        )
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            self.kernel.read_channel_artifact(
                self.runtime_dir, gate.CHANNEL_ENVELOPE_ARTIFACT
            ),
            b"payload",
        )
        with self.assertRaises(w2b1.AgentContextError) as failure:
            self.kernel.write_channel_artifact(
                self.runtime_dir, gate.CHANNEL_ENVELOPE_ARTIFACT, b"other"
            )
        self.assertEqual(failure.exception.code, "E_CONCURRENCY")
        self.kernel.write_channel_artifact(
            self.runtime_dir, gate.CHANNEL_ENVELOPE_ARTIFACT, b"other", replace=True
        )
        self.assertEqual(
            self.kernel.read_channel_artifact(
                self.runtime_dir, gate.CHANNEL_ENVELOPE_ARTIFACT
            ),
            b"other",
        )

    def test_a_symlinked_or_group_readable_artifact_is_never_read(self) -> None:
        self.kernel.write_channel_artifact(self.runtime_dir, "channel-state.json", b"{}")
        os.chmod(self.runtime_dir / "channel-state.json", 0o640)
        with self.assertRaises(w2b1.AgentContextError) as failure:
            self.kernel.read_channel_artifact(self.runtime_dir, "channel-state.json")
        self.assertEqual(failure.exception.code, "E_RUNTIME")
        (self.runtime_dir / "channel-link.bin").symlink_to(self.base / "outside")
        with self.assertRaises(w2b1.AgentContextError) as failure:
            self.kernel.read_channel_artifact(self.runtime_dir, "channel-link.bin")
        self.assertEqual(failure.exception.code, "E_RUNTIME")

    def test_cleanup_removes_channel_artifacts_and_still_rejects_anything_else(self) -> None:
        self.kernel.write_channel_artifact(self.runtime_dir, "channel-state.json", b"{}")
        self.kernel.write_channel_artifact(self.runtime_dir, "channel-claim-000000.json", b"{}")
        (self.runtime_dir / "unexpected.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(w2b1.AgentContextError) as failure:
            self.kernel.cleanup(self.runtime_dir, self.base)
        self.assertEqual(failure.exception.code, "E_RUNTIME")
        (self.runtime_dir / "unexpected.txt").unlink()
        self.kernel.cleanup(self.runtime_dir, self.base)
        self.assertFalse(self.runtime_dir.exists())


class W12ClaudeHookChannelEvidenceTests(unittest.TestCase):
    """The tracked Step 12.4 artifact must describe this exact tree."""

    def setUp(self) -> None:
        self.artifact = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_artifacts_are_utf8_lf_and_final_newline_terminated(self) -> None:
        for path in (
            EVIDENCE, REPORT, ROOT / adapter.GATE_MODULE_PATH,
            ROOT / "scripts/agent_context/probe_claude_hook_channel.py",
            Path(__file__),
        ):
            raw = path.read_bytes()
            with self.subTest(path=path.name):
                raw.decode("utf-8", "strict")
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", raw)
                self.assertTrue(raw.endswith(b"\n"))

    def test_the_adapter_pins_this_exact_artifact(self) -> None:
        self.assertEqual(
            _digest(EVIDENCE.read_bytes()), adapter.HOOK_CHANNEL_EVIDENCE_SHA256
        )
        self.assertEqual(
            adapter.HOOK_CHANNEL_EVIDENCE_PATH,
            str(EVIDENCE.relative_to(ROOT)),
        )

    def test_every_recorded_identity_recomputes_from_the_tracked_tree(self) -> None:
        for item in self.artifact["depends_on"]:
            with self.subTest(path=item["artifact"]):
                self.assertTrue((ROOT / item["artifact"]).is_file())
                if item["sha256"] is None:
                    # The Step 12.3 record pins this adapter, and this adapter
                    # pins this artifact, so a hash in both directions cannot
                    # converge; that record carries superseded_by instead.
                    self.assertEqual(item["step"], "12.3")
                    continue
                self.assertEqual(item["sha256"], _digest((ROOT / item["artifact"]).read_bytes()))
        for relative in (self.artifact["probe"]["source"], self.artifact["gate"]["source"]):
            with self.subTest(path=relative):
                self.assertEqual(
                    _digest((ROOT / relative).read_bytes()),
                    self.artifact["probe"]["source_sha256"]
                    if relative == self.artifact["probe"]["source"]
                    else self.artifact["gate"]["source_sha256"],
                )

    def test_the_frozen_round_trip_recomputes_and_proves_exact_once_delivery(self) -> None:
        record = self.artifact["round_trip"]
        self.assertEqual(
            w2b1.canonical_sha256(
                {key: value for key, value in record.items() if key != "round_trip_evidence_id"}
            ),
            record["round_trip_evidence_id"],
        )
        self.assertEqual(record["round_trip_evidence_id"], adapter.HOOK_ROUND_TRIP_EVIDENCE)
        self.assertTrue(record["exact_model_input"])
        self.assertEqual(record["model_visible_occurrences"], 1)
        self.assertEqual(record["second_prompt_model_visible_occurrences"], 1)
        self.assertEqual(record["claims_after_second_prompt"], 1)
        self.assertEqual(record["hook_event"], gate.HOOK_EVENT)
        self.assertEqual(record["channel_id"], adapter.HOOK_CHANNEL_ID)
        self.assertEqual(record["gate_source_sha256"], _digest((ROOT / adapter.GATE_MODULE_PATH).read_bytes()))
        self.assertEqual(record["envelope_bytes"], self.artifact["observations"]["round_trip"]["envelope_bytes"])

    def test_the_recorded_boundary_and_refusals_stay_fail_closed(self) -> None:
        boundary = {item["fixture_bytes"]: item for item in self.artifact["observations"]["boundary"]}
        self.assertTrue(boundary[10000]["exact_model_input"])
        self.assertFalse(boundary[10001]["exact_model_input"])
        self.assertTrue(boundary[10001]["persisted_output_substituted"])
        for refusal in self.artifact["observations"]["gate_refusals"]:
            with self.subTest(case=refusal["case"]):
                self.assertFalse(refusal["delivered"])
                self.assertEqual(refusal["claims"], [])
        self.assertTrue(self.artifact["observations"]["foreign_authority"]["settings_hooks_merge"])
        sources = self.artifact["observations"]["setting_sources"]
        self.assertTrue(sources["default"]["native_project_memory_present"])
        self.assertFalse(sources["user-only"]["native_project_memory_present"])

    def test_the_driven_run_delivered_the_envelope_once_over_the_hook_row(self) -> None:
        run = self.artifact["driven_run"]
        self.assertEqual(run["selected_row"], HOOK_ROW)
        self.assertEqual(run["channel_id"], adapter.HOOK_CHANNEL_ID)
        self.assertEqual(run["rejected_rows"], [])
        self.assertEqual(run["registered_hook_events"], [])
        self.assertEqual(run["round_trip_evidence_id"], adapter.HOOK_ROUND_TRIP_EVIDENCE)
        self.assertEqual(run["receipt"]["state"], "COMPLETED")
        self.assertEqual(run["receipt"]["previous_state"], "SUBMISSION_STARTED")
        self.assertEqual(run["receipt"]["channel_id"], adapter.HOOK_CHANNEL_ID)
        self.assertEqual(run["envelope_model_visible_occurrences"], 1)
        self.assertTrue(run["armed_envelope_matches_receipt"])
        # The launcher's own registration is the only injection authority: the
        # envelope never appears as a client argument.
        self.assertIn("--settings", run["command"])
        self.assertNotIn("--append-system-prompt", run["command"])
        self.assertEqual(run["claim"]["envelope_sha256"], run["receipt"]["envelope_sha256"])
        self.assertEqual(run["claim"]["delivered_bytes"], run["receipt"]["delivered_bytes"])
        accounting = run["accounting"]
        self.assertLessEqual(accounting["model_visible_total"], accounting["effective_hard_limit"])
        self.assertEqual(accounting["effective_hard_limit"], self.artifact["verified_channel_limit"])
        # The still-current native source must match the live tree.
        source = run["native_sources"][0]
        self.assertEqual(source["sha256"], _digest((ROOT / source["path"]).read_bytes()))

    def test_the_recorded_row_fit_survey_covers_every_registered_repository(self) -> None:
        registry = json.loads((ROOT / ".workspace/repo-types.json").read_text(encoding="utf-8"))
        survey = self.artifact["row_fit_survey"]
        self.assertEqual(
            sorted(survey["hook_row_fits"] + survey["falls_through_to_full_content"]),
            sorted(item["id"] for item in registry["repositories"]),
        )
        self.assertIn(self.artifact["driven_run"]["repository"], survey["hook_row_fits"])

    def test_the_frozen_row_and_limits_match_the_capability_matrix(self) -> None:
        capability = json.loads(
            (ROOT / "scripts/agent_context/fixtures/evidence/w12-claude-capability-evidence-2026-07-27.json")
            .read_text(encoding="utf-8")
        )
        row = next(item for item in capability["rows"] if item["row_id"] == HOOK_ROW)
        self.assertEqual(self.artifact["row_id"], HOOK_ROW)
        self.assertEqual(self.artifact["capability_evidence_id"], row["capability_evidence_id"])
        self.assertEqual(
            self.artifact["verified_channel_limit"], row["capability_row"]["verified_channel_limit"]
        )
        self.assertEqual(self.artifact["client"]["sha256"], capability["client"]["sha256"])


class W12ClaudeRoundTripBindingTests(unittest.TestCase):
    """The adapter re-proves the frozen round trip on every resolution."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        evidence = self.root / "scripts/agent_context/fixtures/evidence"
        evidence.mkdir(parents=True)
        (evidence / EVIDENCE.name).write_bytes(EVIDENCE.read_bytes())
        target = self.root / adapter.GATE_MODULE_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / adapter.GATE_MODULE_PATH).read_bytes())
        capability = json.loads(
            (ROOT / adapter.CAPABILITY_EVIDENCE_PATH).read_text(encoding="utf-8")
        )
        self.rows = adapter._capability_rows(capability)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_the_frozen_record_is_accepted_only_while_it_still_describes_this_row(self) -> None:
        record = adapter._hook_channel_evidence(self.root, self.rows)
        self.assertEqual(record["round_trip_evidence_id"], adapter.HOOK_ROUND_TRIP_EVIDENCE)

    def test_a_changed_gate_identity_or_record_makes_the_row_ineligible(self) -> None:
        cases: list[tuple[str, dict[str, object] | None]] = [
            ("changed gate", None),
            ("tampered identity", {"exact_model_input": False}),
            ("tampered row", {"verified_channel_limit": 32768}),
            ("tampered event", {"hook_event": "SessionStart"}),
            ("tampered exactly-once", {"claims_after_second_prompt": 2}),
            ("missing record", {}),
        ]
        for label, changes in cases:
            with self.subTest(case=label):
                self.tearDown()
                self.setUp()
                if changes is None:
                    (self.root / adapter.GATE_MODULE_PATH).write_bytes(b"# other\n")
                elif not changes:
                    self._target().write_text("{}\n", encoding="utf-8")
                else:
                    self._rewrite(**changes)
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    adapter._hook_channel_evidence(self.root, self.rows)
                self.assertEqual(failure.exception.code, "E_CHANNEL")

    def _target(self) -> Path:
        return self.root / "scripts/agent_context/fixtures/evidence" / EVIDENCE.name

    def _rewrite(self, **changes: object) -> None:
        """Rewrite the record with a recomputed identity, as a forger would."""
        artifact = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        record = dict(artifact["round_trip"])
        record.update(changes)
        record["round_trip_evidence_id"] = w2b1.canonical_sha256(
            {key: value for key, value in record.items() if key != "round_trip_evidence_id"}
        )
        self._target().write_text(
            json.dumps({**artifact, "round_trip": record}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
