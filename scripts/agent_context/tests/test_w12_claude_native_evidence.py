"""Step 12.2 Claude native-load evidence mechanism and frozen artifact.

These tests are offline.  They never invoke a client, start a server, or read a
child repository's source tree beyond the instruction files the frozen evidence
already names.  They check that the parser is byte-exact and fails closed, that
the frozen evidence recomputes from the current tree, that the resolver produces
exactly the frozen native/inject classification, and that the native-evidence
identity reaches a kernel receipt.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import claude_adapter, claude_native_evidence as cne, w2b1
from agent_context.delivery_kernel import DeliveryKernel, DeliveryRequest, FakeTransportAdapter
from agent_context.resolve_context import ResolutionRequest, resolve_context
from agent_context.shared_validation import validate_resolved


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "scripts/agent_context/fixtures/evidence/w12-claude-native-load-evidence-2026-07-28.json"
REPORT = ROOT / "scripts/agent_context/fixtures/evidence/w12-claude-native-load-evidence-2026-07-28.md"
TOOL = ROOT / "scripts/agent_context/claude_native_evidence.py"
CAPABILITY = ROOT / "scripts/agent_context/fixtures/evidence/w12-claude-capability-evidence-2026-07-27.json"
SECTION_PREAMBLE = (
    "<system-reminder>\nAs you answer the user's questions, you can use the following context:\n"
    "# claudeMd\nCodebase and user instructions are shown below.\n\n"
)


def _capture_text(root: Path, paths: tuple[str, ...], trailer: str = "# userEmail\nnobody\n") -> str:
    """Rebuild the client's observed project-memory framing for a fixture."""
    blocks = [SECTION_PREAMBLE]
    for path in paths:
        content = (root / path).read_text(encoding="utf-8")
        blocks.append(
            f"Contents of {root / path} (project instructions, checked into the codebase):\n\n"
            f"{content}\n"
        )
    return "".join(blocks) + trailer


def _load(root: Path, texts: list[str], **overrides: object) -> cne.ClaudeNativeLoad:
    sources, external = cne.parse_active_sources(texts, root)
    joined = "\n".join(texts)
    settings = {"project": {}, "user": None, "registered_hook_events": []}
    fields: dict[str, object] = {
        "mechanism": cne.MECHANISM, "workspace_root": root.resolve(strict=True), "project": ".",
        "client_identity": "/opt/claude/2.1.220", "client_version": "2.1.220 (Claude Code)",
        "client_sha256": "a" * 64, "trust_state": "trusted", "settings": settings,
        "config_sha256": w2b1.canonical_sha256(settings), "captured_at": "2026-07-28T00:00:00Z",
        "sources": sources, "external_labels": external, "request_count": 1,
        "model_input_sha256": hashlib.sha256(joined.encode("utf-8")).hexdigest(),
        "model_input_bytes": len(joined.encode("utf-8")), "visible_text": joined,
    }
    fields.update(overrides)
    return cne.ClaudeNativeLoad(**fields)  # type: ignore[arg-type]


class W12ClaudeNativeParserTests(unittest.TestCase):
    """The mechanism enumerates and proves; it never assumes."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        (self.root / "CLAUDE.md").write_text("# root memory\n", encoding="utf-8")
        (self.root / "child").mkdir()
        (self.root / "child" / "CLAUDE.md").write_text("# child memory\n", encoding="utf-8")
        (self.root / "child" / "REPOSITORY_CONTEXT.md").write_text("# neutral\n", encoding="utf-8")
        (self.root / "policy.md").write_text("# policy body\n", encoding="utf-8")
        self.paths = ("CLAUDE.md", "child/CLAUDE.md", "child/REPOSITORY_CONTEXT.md")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_active_sources_are_enumerated_from_the_clients_own_labels(self) -> None:
        sources, external = cne.parse_active_sources([_capture_text(self.root, self.paths)], self.root)
        self.assertEqual([source.path for source in sources], sorted(self.paths))
        self.assertEqual(external, ())
        for source in sources:
            raw = (self.root / source.path).read_bytes()
            self.assertEqual(source.source_bytes, len(raw))
            self.assertEqual(source.source_sha256, hashlib.sha256(raw).hexdigest())
            self.assertEqual(source.label, cne.PROJECT_MEMORY_LABEL)

    def test_a_label_whose_content_drifted_fails_closed(self) -> None:
        text = _capture_text(self.root, ("CLAUDE.md",))
        (self.root / "CLAUDE.md").write_text("# root memory changed\n", encoding="utf-8")
        with self.assertRaises(w2b1.AgentContextError) as failure:
            cne.parse_active_sources([text], self.root)
        self.assertEqual(failure.exception.code, "E_NATIVE_EVIDENCE")
        self.assertIn("byte-exactly", failure.exception.message)

    def test_a_second_copy_of_an_active_source_fails_closed(self) -> None:
        text = _capture_text(self.root, ("CLAUDE.md",))
        duplicate = (self.root / "CLAUDE.md").read_text(encoding="utf-8")
        with self.assertRaises(w2b1.AgentContextError) as failure:
            cne.parse_active_sources([text, duplicate], self.root)
        self.assertEqual(failure.exception.code, "E_NATIVE_EVIDENCE")
        self.assertIn("exactly once", failure.exception.message)

    def test_missing_or_split_memory_sections_fail_closed(self) -> None:
        for texts in ([], ["no memory here"], [_capture_text(self.root, ("CLAUDE.md",))] * 2):
            with self.subTest(blocks=len(texts)):
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    cne.parse_active_sources(texts, self.root)
                self.assertEqual(failure.exception.code, "E_NATIVE_EVIDENCE")

    def test_a_label_outside_the_workspace_is_reported_not_ignored(self) -> None:
        text = _capture_text(
            self.root, ("CLAUDE.md",),
            trailer=(
                "Contents of /elsewhere/CLAUDE.md (user's private global instructions):\n\n"
                "# user memory\n\n# userEmail\nnobody\n"
            ),
        )
        sources, external = cne.parse_active_sources([text], self.root)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].path, "CLAUDE.md")
        self.assertEqual(external, ("/elsewhere/CLAUDE.md",))
        load = _load(self.root, [_capture_text(self.root, ("CLAUDE.md",))], external_labels=external)
        with self.assertRaises(w2b1.AgentContextError) as failure:
            cne.build_native_evidence(load, capability_row=_row())
        self.assertEqual(failure.exception.code, "E_NATIVE_EVIDENCE")

    def test_absence_is_proved_and_a_present_candidate_fails_closed(self) -> None:
        text = _capture_text(self.root, ("CLAUDE.md",))
        absent = cne.verify_absent([text], self.root, ["policy.md"])
        self.assertEqual(
            absent["policy.md"], hashlib.sha256((self.root / "policy.md").read_bytes()).hexdigest()
        )
        with self.assertRaises(w2b1.AgentContextError) as failure:
            cne.verify_absent([text], self.root, ["CLAUDE.md"])
        self.assertEqual(failure.exception.code, "E_NATIVE_EVIDENCE")

    def test_evidence_binds_client_trust_mechanism_and_capability(self) -> None:
        texts = [_capture_text(self.root, ("CLAUDE.md",))]
        load = _load(self.root, texts)
        evidence = cne.build_native_evidence(
            load, capability_row=_row(), expected_client_sha256="a" * 64
        )
        self.assertEqual(
            evidence["native_evidence_id"],
            w2b1.canonical_sha256(
                {key: value for key, value in evidence.items() if key != "native_evidence_id"}
            ),
        )
        self.assertEqual(evidence["inspection_mechanism"], cne.MECHANISM)
        self.assertEqual(evidence["trust_state"], "trusted")
        cases = (
            ("E_CAPABILITY", {"capability_row": {**_row(), "inspection_mechanism": "guesswork"}}),
            ("E_CAPABILITY", {"capability_row": {**_row(), "agent": "codex"}}),
            ("E_CAPABILITY", {"expected_client_sha256": "b" * 64}),
        )
        for code, kwargs in cases:
            with self.subTest(code=code, kwargs=sorted(kwargs)):
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    cne.build_native_evidence(load, **{"capability_row": _row(), **kwargs})
                self.assertEqual(failure.exception.code, code)
        for state in ("untrusted", "unrecorded"):
            with self.subTest(trust=state):
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    cne.build_native_evidence(
                        _load(self.root, texts, trust_state=state), capability_row=_row()
                    )
                self.assertEqual(failure.exception.code, "E_TRUST")

    def test_injection_evidence_refuses_native_sources_and_double_injection(self) -> None:
        texts = [_capture_text(self.root, ("CLAUDE.md",))]
        load = _load(self.root, texts)
        injection = cne.build_injection_evidence(load, generation=0, paths=["policy.md"])
        self.assertTrue(injection["native_discovery_disabled"])
        self.assertTrue(injection["exact_once_handoff_proven"])
        self.assertEqual([item["path"] for item in injection["sources"]], ["policy.md"])
        with self.assertRaises(w2b1.AgentContextError) as failure:
            cne.build_injection_evidence(load, generation=0, paths=["CLAUDE.md"])
        self.assertEqual(failure.exception.code, "E_NATIVE_EVIDENCE")
        duplicated = _load(
            self.root, texts,
            settings={
                "project": {}, "user": None,
                "registered_hook_events": list(cne.DUPLICATE_INJECTION_EVENTS),
            },
        )
        with self.assertRaises(w2b1.AgentContextError) as failure:
            cne.build_injection_evidence(duplicated, generation=0, paths=["policy.md"])
        self.assertEqual(failure.exception.code, "E_CHANNEL")

    def test_instruction_sources_map_only_claude_instruction_files_in_scope(self) -> None:
        load = _load(self.root, [_capture_text(self.root, self.paths)])
        sources = cne.instruction_sources(load, repositories=("child",))
        self.assertEqual(
            [(item["policy_id"], item["path"], item["authority_tier"]) for item in sources],
            [
                ("instruction.root.claude", "CLAUDE.md", "workspace"),
                ("instruction.child.claude", "child/CLAUDE.md", "repository"),
                ("instruction.child.repository-context", "child/REPOSITORY_CONTEXT.md", "repository"),
            ],
        )
        with self.assertRaises(w2b1.AgentContextError) as failure:
            cne.instruction_sources(load, repositories=("other",))
        self.assertEqual(failure.exception.code, "E_SCOPE_UNAVAILABLE")
        with self.assertRaises(w2b1.AgentContextError) as failure:
            cne.instruction_sources(load, repositories=("child",), injected_paths=("CLAUDE.md",))
        self.assertEqual(failure.exception.code, "E_NATIVE_EVIDENCE")
        root_only = _load(self.root, [_capture_text(self.root, ("CLAUDE.md",))])
        injected = cne.instruction_sources(
            root_only, repositories=("child",), injected_paths=("child/CLAUDE.md",)
        )
        self.assertEqual([item["path"] for item in injected], ["CLAUDE.md", "child/CLAUDE.md"])

    def test_manifest_binding_is_compared_in_both_directions(self) -> None:
        load = _load(self.root, [_capture_text(self.root, ("CLAUDE.md",))])
        evidence = cne.build_native_evidence(load, capability_row=_row())
        digest = hashlib.sha256((self.root / "CLAUDE.md").read_bytes()).hexdigest()
        native_entry = {
            "path": "CLAUDE.md", "delivery": "native", "source_sha256": digest,
            "native_evidence_id": evidence["native_evidence_id"],
        }
        inject_entry = {
            "path": "policy.md", "delivery": "inject",
            "source_sha256": hashlib.sha256((self.root / "policy.md").read_bytes()).hexdigest(),
            "native_evidence_id": None,
        }
        manifest = {"entries": [native_entry, inject_entry]}
        self.assertEqual(cne.verify_manifest_native_binding(manifest, evidence), {"CLAUDE.md": digest})
        broken = (
            [{**native_entry, "native_evidence_id": "c" * 64}, inject_entry],
            [{**native_entry, "source_sha256": "d" * 64}, inject_entry],
            [{**native_entry, "delivery": "inject", "native_evidence_id": None}, inject_entry],
            [{**inject_entry, "native_evidence_id": evidence["native_evidence_id"]}],
            [inject_entry],
        )
        for entries in broken:
            with self.subTest(entries=[entry["path"] for entry in entries]):
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    cne.verify_manifest_native_binding({"entries": entries}, evidence)
                self.assertEqual(failure.exception.code, "E_NATIVE_EVIDENCE")


def _row(**overrides: object) -> dict[str, object]:
    """One synthetic REQUIRED Claude row carrying the frozen mechanism."""
    row = {
        "agent": "claude", "platform": "devcontainer", "mode": "non-interactive",
        "status": "REQUIRED", "inspection_mechanism": cne.MECHANISM,
        "channel_id": "claude-cli-append-system-prompt", "verified_channel_limit": 65536,
        "client_context_allowance": 262144, "reserved_margin": 32768,
        "start_supported": True, "resume_supported": True, "clear_supported": True,
        "compact_supported": False, "launcher_identity_available": True,
        "client_session_identity_available": True, "blocks_closeout": True,
    }
    row.update(overrides)
    return row


class W12ClaudeNativeEvidenceFreezeTests(unittest.TestCase):
    """The frozen artifact must recompute from the current tree."""

    def setUp(self) -> None:
        self.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))
        self.rows = {row["row_id"]: row for row in self.capability["rows"]}

    def test_artifacts_are_utf8_lf_and_final_newline_terminated(self) -> None:
        for path in (EVIDENCE, REPORT, TOOL):
            raw = path.read_bytes()
            raw.decode("utf-8", "strict")
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), path)
            self.assertNotIn(b"\r", raw, path)
            self.assertTrue(raw.endswith(b"\n"), path)

    def test_frozen_tool_and_capability_identities_match_the_tracked_files(self) -> None:
        self.assertEqual(
            self.evidence["tool"]["source_sha256"], hashlib.sha256(TOOL.read_bytes()).hexdigest()
        )
        self.assertEqual(self.evidence["tool"]["source"], "scripts/agent_context/claude_native_evidence.py")
        self.assertFalse(self.evidence["tool"]["vendor_api_contacted"])
        self.assertEqual(self.evidence["tool"]["workspace_files_written"], 0)
        self.assertEqual(
            self.evidence["depends_on"]["sha256"], hashlib.sha256(CAPABILITY.read_bytes()).hexdigest()
        )
        self.assertEqual(self.evidence["mechanism"]["id"], cne.MECHANISM)
        self.assertEqual(self.evidence["mechanism"]["in_band_mechanism"], "unavailable")
        self.assertIn("model self-report", self.evidence["mechanism"]["rejected_mechanisms"])

    def test_every_proven_and_absent_source_still_hashes_the_same(self) -> None:
        for scope in self.evidence["scopes"]:
            for source in scope["native_sources"]:
                with self.subTest(scope=scope["scope_id"], path=source["path"]):
                    raw = (ROOT / source["path"]).read_bytes()
                    self.assertEqual(source["source_bytes"], len(raw))
                    self.assertEqual(source["source_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(
                scope["native_model_visible_bytes"],
                sum(source["source_bytes"] for source in scope["native_sources"]),
            )
            self.assertEqual(scope["external_labels"], [])
        for source in self.evidence["proved_absent"]:
            with self.subTest(path=source["path"]):
                self.assertEqual(
                    source["sha256"], hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest()
                )

    def test_the_child_scope_stays_blocked_until_a_human_accepts_trust(self) -> None:
        child = next(scope for scope in self.evidence["scopes"] if scope["scope_id"] == "selected-child")
        self.assertEqual(child["trust_state"], "untrusted")
        self.assertEqual(child["status"], "BLOCKED_UNTRUSTED_PROJECT")
        self.assertEqual(child["fail_closed"]["code"], "E_TRUST")
        self.assertEqual(
            [source["path"] for source in child["native_sources"]],
            ["CLAUDE.md", "fa-auth-m8/CLAUDE.md", "fa-auth-m8/REPOSITORY_CONTEXT.md"],
        )
        # Step 12.1 measured exactly this native set for the child launch scope.
        self.assertEqual(
            child["native_model_visible_bytes"],
            json.loads(CAPABILITY.read_text(encoding="utf-8"))["measurement"][
                "native_model_visible_bytes"
            ],
        )

    def test_frozen_identities_recompute_from_their_own_records(self) -> None:
        configuration = self.evidence["configuration"]
        recomputed = w2b1.canonical_sha256(
            {key: value for key, value in configuration.items() if key != "config_sha256"}
        )
        self.assertEqual(configuration["config_sha256"], recomputed)
        self.assertEqual(configuration["registered_hook_events"], [])
        self.assertEqual(
            configuration["project"][".claude/settings.json"],
            hashlib.sha256((ROOT / ".claude/settings.json").read_bytes()).hexdigest(),
        )
        for item in self.evidence["native_evidence"]:
            record = item["record"]
            with self.subTest(row=item["row_id"]):
                self.assertEqual(
                    record["native_evidence_id"],
                    w2b1.canonical_sha256(
                        {key: value for key, value in record.items() if key != "native_evidence_id"}
                    ),
                )
                self.assertEqual(record["config_sha256"], configuration["config_sha256"])
                self.assertEqual(
                    record["capability_evidence_id"],
                    w2b1.canonical_sha256(self.rows[item["row_id"]]["capability_row"]),
                )
                self.assertEqual(record["client_version"], self.evidence["client"]["version"])
        self.assertEqual(self.evidence["client"]["sha256"], self.capability["client"]["sha256"])
        self.assertTrue(self.evidence["client"]["matches_capability_evidence"])

    def _resolve(self, record: dict) -> tuple[dict, object]:
        capability = self.rows[record["row_id"]]["capability_row"]
        native = next(
            item["record"] for item in self.evidence["native_evidence"]
            if item["row_id"] == record["row_id"]
        )
        injected = [
            item["path"] for item in record["entries"]
            if item["delivery"] == "inject" and item["path"] not in {
                source["path"] for source in self.evidence["scopes"][0]["native_sources"]
            }
        ]
        absent = {item["path"]: item["sha256"] for item in self.evidence["proved_absent"]}
        resolved = resolve_context(
            ResolutionRequest(
                root=ROOT,
                registry=w2b1.parse_strict_json((ROOT / ".workspace/repo-types.json").read_bytes()),
                policy_index=w2b1.parse_strict_json((ROOT / ".workspace/policy.index.json").read_bytes()),
                policy_metadata=w2b1.parse_strict_json(
                    (ROOT / ".workspace/policy.metadata.json").read_bytes()
                ),
                capability_row=capability,
                reviewed_tree={"algorithm": "git-sha1", "value": "b" * 40},
                agent="claude", platform=capability["platform"], mode=capability["mode"],
                repositories=("fa-auth-m8",), native_evidence=native,
                injection_evidence={
                    "generation": 0, "native_discovery_disabled": True,
                    "exact_once_handoff_proven": True,
                    "sources": [
                        {"path": path, "sha256": absent[path]} for path in sorted(absent)
                    ],
                },
                instruction_sources=tuple(record["instruction_sources"]),
                generation=0,
            )
        )
        self.assertEqual(cne.verify_manifest_native_binding(resolved.manifest, native), {
            source["path"]: source["source_sha256"]
            for source in self.evidence["scopes"][0]["native_sources"]
        })
        del injected
        return capability, resolved

    def test_every_frozen_classification_reproduces_exactly(self) -> None:
        self.assertEqual(len(self.evidence["classification"]), 4)
        for record in self.evidence["classification"]:
            with self.subTest(variant=record["variant"], row=record["row_id"]):
                capability, resolved = self._resolve(record)
                self.assertEqual(resolved.manifest["manifest_id"], record["manifest_id"])
                self.assertEqual(resolved.envelope_sha256, record["envelope_sha256"])
                self.assertEqual(
                    [
                        {
                            "path": entry["path"], "delivery": entry["delivery"],
                            "source_bytes": entry["source_bytes"],
                            "native_evidence_id": entry["native_evidence_id"],
                        }
                        for entry in resolved.manifest["entries"]
                    ],
                    record["entries"],
                )
                accounting = resolved.manifest["accounting"]
                for key, value in record["accounting"].items():
                    self.assertEqual(accounting[key], value, key)
                if record["validation"] == "ACCEPTED":
                    validate_resolved(
                        workspace=ROOT, manifest=resolved.manifest, envelope=resolved.envelope,
                        envelope_bytes=resolved.envelope_bytes, capability_row=capability,
                        channel_id=capability["channel_id"],
                    )
                else:
                    with self.assertRaises(w2b1.AgentContextError) as failure:
                        validate_resolved(
                            workspace=ROOT, manifest=resolved.manifest, envelope=resolved.envelope,
                            envelope_bytes=resolved.envelope_bytes, capability_row=capability,
                            channel_id=capability["channel_id"],
                        )
                    self.assertEqual(failure.exception.code, record["fail_closed"]["code"])

    def test_the_hook_row_is_selectable_only_by_model_visible_total(self) -> None:
        totals = {
            (record["variant"], record["row_id"]): record for record in self.evidence["classification"]
        }
        hook = "claude-devcontainer-non-interactive-hook-additional-context"
        full = "claude-devcontainer-non-interactive-append-system-prompt"
        fitting = totals[("workspace-only", hook)]
        overrunning = totals[("with-injected-child-instructions", hook)]
        self.assertEqual(fitting["validation"], "ACCEPTED")
        self.assertLessEqual(
            fitting["accounting"]["model_visible_total"], fitting["accounting"]["effective_hard_limit"]
        )
        self.assertEqual(overrunning["validation"], "REJECTED")
        self.assertEqual(overrunning["fail_closed"]["code"], "E_BUDGET")
        self.assertGreater(
            overrunning["accounting"]["model_visible_total"],
            overrunning["accounting"]["effective_hard_limit"],
        )
        # The same envelope always fits the full-content row.
        self.assertEqual(totals[("with-injected-child-instructions", full)]["validation"], "ACCEPTED")

    def test_frozen_receipts_carry_the_native_evidence_identity(self) -> None:
        accepted = [
            record for record in self.evidence["classification"] if record["validation"] == "ACCEPTED"
        ]
        self.assertTrue(accepted)
        for record in accepted:
            with self.subTest(variant=record["variant"], row=record["row_id"]):
                receipt = record["receipt_binding"]
                self.assertEqual(receipt["state"], "COMPLETED")
                self.assertEqual(receipt["native_evidence_ids"], [record["native_evidence_id"]])
                self.assertEqual(receipt["manifest_id"], record["manifest_id"])
                self.assertEqual(receipt["envelope_sha256"], record["envelope_sha256"])

    def test_step_12_2_promotes_no_claude_row_and_registers_no_hook(self) -> None:
        self.assertEqual(
            claude_adapter.CURRENT_CLAUDE_CONFIGURATION.capability_row["status"], "LIMITED"
        )
        self.assertFalse(claude_adapter.CURRENT_CLAUDE_CONFIGURATION.project_hook_configured)
        settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("hooks", settings)
        self.assertIn("Step 12.3", REPORT.read_text(encoding="utf-8"))


class W12ClaudeNativeReceiptBindingTests(unittest.TestCase):
    """A native entry must reach the receipt through the shared kernel."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        (self.root / "CLAUDE.md").write_text("# root memory\n", encoding="utf-8")
        (self.root / "policy.md").write_text("# policy body\n", encoding="utf-8")
        self.capability = _row(channel_id="claude-cli-append-system-prompt")
        load = _load(self.root, [_capture_text(self.root, ("CLAUDE.md",))])
        self.evidence = cne.build_native_evidence(load, capability_row=self.capability)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_kernel_receipt_lists_the_native_evidence_identity_once(self) -> None:
        native_raw = (self.root / "CLAUDE.md").read_bytes()
        policy_raw = (self.root / "policy.md").read_bytes()
        entry = w2b1.source_entry_from_bytes(policy_raw, {
            "policy_id": "workspace.policy", "repository_id": "$workspace", "scope_prefix": ".",
            "path": "policy.md", "authority_tier": "workspace",
        })
        manifest = {
            "schema_version": 2, "manifest_id": "0" * 64,
            "reviewed_tree": {"algorithm": "git-sha1", "value": "b" * 40},
            "agent": "claude", "platform": "devcontainer", "mode": "non-interactive",
            "capability_evidence_id": w2b1.canonical_sha256(self.capability),
            "repositories": [], "tasks": [], "operations": [], "authorization_ids": [],
            "authorization_provenance": [],
            "entries": [
                {
                    "policy_id": "instruction.root.claude", "source_kind": "instruction",
                    "repository_id": "$workspace", "scope_prefix": ".", "path": "CLAUDE.md",
                    "delivery": "native",
                    "source_sha256": hashlib.sha256(native_raw).hexdigest(),
                    "source_bytes": len(native_raw), "metadata_sha256": "c" * 64,
                    "native_evidence_id": self.evidence["native_evidence_id"],
                    "envelope_entry_sha256": None,
                },
                {
                    "policy_id": "workspace.policy", "source_kind": "policy",
                    "repository_id": "$workspace", "scope_prefix": ".", "path": "policy.md",
                    "delivery": "inject",
                    "source_sha256": hashlib.sha256(policy_raw).hexdigest(),
                    "source_bytes": len(policy_raw), "metadata_sha256": "c" * 64,
                    "native_evidence_id": None,
                    "envelope_entry_sha256": w2b1.canonical_sha256(entry),
                },
            ],
            "accounting": {
                "policy_hard_limit": 32768, "verified_channel_limit": 65536,
                "client_context_allowance": 262144, "reserved_margin": 32768,
                "effective_hard_limit": 32768, "native_model_visible_bytes": len(native_raw),
                "serialized_injected_envelope_bytes": 0,
                "other_model_visible_bootstrap_bytes": 0, "model_visible_total": 0,
                "raw_injected_source_bytes": len(policy_raw), "serialization_overhead_bytes": 0,
                "estimated_tokens": 0, "excluded_external_layers": ["synthetic-test-only"],
            },
        }
        for _ in range(2):
            manifest["manifest_id"] = w2b1.canonical_sha256(
                {key: value for key, value in manifest.items() if key != "manifest_id"}
            )
            _, envelope_bytes, _ = w2b1.build_envelope(
                manifest_id=manifest["manifest_id"], generation=0, entries=[entry]
            )
            accounting = manifest["accounting"]
            accounting["serialized_injected_envelope_bytes"] = len(envelope_bytes)
            accounting["model_visible_total"] = len(native_raw) + len(envelope_bytes)
            accounting["serialization_overhead_bytes"] = len(envelope_bytes) - len(policy_raw)
            accounting["estimated_tokens"] = (accounting["model_visible_total"] + 3) // 4
        manifest["manifest_id"] = w2b1.canonical_sha256(
            {key: value for key, value in manifest.items() if key != "manifest_id"}
        )
        envelope, envelope_bytes, envelope_hash = w2b1.build_envelope(
            manifest_id=manifest["manifest_id"], generation=0, entries=[entry]
        )
        cne.verify_manifest_native_binding(manifest, self.evidence)
        from agent_context.resolve_context import ResolvedContext

        request = DeliveryRequest(
            workspace_root=self.root,
            resolved=ResolvedContext(manifest, envelope, envelope_bytes, envelope_hash),
            capability_row=self.capability, trusted=True,
            reviewed_tree=manifest["reviewed_tree"],
            capability_evidence_id=w2b1.canonical_sha256(self.capability),
            client_session_id="claude.synthetic",
            channel_id="claude-cli-append-system-prompt",
        )
        kernel = DeliveryKernel()
        result = kernel.handoff(kernel.prepare(request), FakeTransportAdapter())
        self.assertEqual(result.receipt["state"], "COMPLETED")
        self.assertEqual(
            result.receipt["native_evidence_ids"], [self.evidence["native_evidence_id"]]
        )
        self.assertEqual(result.session["native_evidence_ids"], result.receipt["native_evidence_ids"])


if __name__ == "__main__":
    unittest.main()
