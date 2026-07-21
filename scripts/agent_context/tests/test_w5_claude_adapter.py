from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.claude_adapter import (
    CURRENT_CLAUDE_CONFIGURATION,
    ClaudeAdapterConfiguration,
    ClaudeChannelEvidence,
    ClaudeDeliveryAdapter,
    ClaudeNativeInspection,
)
from agent_context.delivery_kernel import DeliveryKernel, DeliveryRequest, FakeTransportAdapter
from agent_context.resolve_context import ResolvedContext


WORKSPACE = Path(__file__).resolve().parents[3]


def _required_capability(channel_id: str) -> dict[str, object]:
    return {
        "agent": "claude", "platform": "devcontainer", "mode": "non-interactive",
        "status": "REQUIRED", "inspection_mechanism": "synthetic-claude-inspection",
        "channel_id": channel_id, "verified_channel_limit": 32768,
        "client_context_allowance": 65536, "reserved_margin": 32768,
        "start_supported": True, "resume_supported": True, "clear_supported": True,
        "compact_supported": False, "launcher_identity_available": True,
        "client_session_identity_available": True, "blocks_closeout": True,
    }


class W5ClaudeAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / ".claude").mkdir()
        (self.root / "nested" / ".claude").mkdir(parents=True)
        (self.root / "CLAUDE.md").write_text("root\n", encoding="utf-8")
        (self.root / ".claude" / "on-demand.md").write_text("on demand\n", encoding="utf-8")
        (self.root / "nested" / "CLAUDE.md").write_text("nested\n", encoding="utf-8")
        (self.root / "nested" / ".claude" / "rule.md").write_text("nested rule\n", encoding="utf-8")
        self.capability = _required_capability("claude-hook-additional-context")
        self.adapter = ClaudeDeliveryAdapter(
            ClaudeAdapterConfiguration(
                capability_row=self.capability,
                channels=ClaudeChannelEvidence(32768, "synthetic-stdin", 65536),
                project_hook_configured=True,
            )
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _inspection(self, paths: tuple[str, ...]) -> ClaudeNativeInspection:
        return ClaudeNativeInspection(
            mechanism="synthetic-claude-inspection",
            trusted_project=True,
            active_hook=True,
            source_sha256={
                path: hashlib.sha256((self.root / path).read_bytes()).hexdigest()
                for path in paths
            },
        )

    def _request(self) -> DeliveryRequest:
        source = self.root / "policy.md"
        source.write_bytes(b"policy\n")
        raw = source.read_bytes()
        source_hash = hashlib.sha256(raw).hexdigest()
        entry = {
            "policy_id": "workspace.policy", "repository_id": "$workspace",
            "scope_prefix": ".", "path": "policy.md", "authority_tier": "workspace",
            "source_sha256": source_hash, "source_bytes": len(raw),
            "leading_bom_bytes": 0, "serialized_content_bytes": len(raw), "content": "policy\n",
        }
        manifest = {
            "schema_version": 2, "manifest_id": "0" * 64,
            "reviewed_tree": {"algorithm": "git-sha1", "value": "b" * 40},
            "agent": "claude", "platform": "devcontainer", "mode": "non-interactive",
            "capability_evidence_id": w2b1.canonical_sha256(self.capability),
            "repositories": [], "tasks": [], "operations": [], "authorization_ids": [],
            "authorization_provenance": [],
            "entries": [{
                "policy_id": "workspace.policy", "source_kind": "policy", "repository_id": "$workspace",
                "scope_prefix": ".", "path": "policy.md", "delivery": "inject",
                "source_sha256": source_hash, "source_bytes": len(raw),
                "metadata_sha256": "c" * 64, "native_evidence_id": None,
                "envelope_entry_sha256": w2b1.canonical_sha256(entry),
            }],
            "accounting": {
                "policy_hard_limit": 32768, "verified_channel_limit": 32768,
                "client_context_allowance": 65536, "reserved_margin": 32768,
                "effective_hard_limit": 32768, "native_model_visible_bytes": 0,
                "serialized_injected_envelope_bytes": 0,
                "other_model_visible_bootstrap_bytes": 0, "model_visible_total": 0,
                "raw_injected_source_bytes": len(raw), "serialization_overhead_bytes": 0,
                "estimated_tokens": 0, "excluded_external_layers": ["synthetic-test-only"],
            },
        }
        for _ in range(2):
            manifest["manifest_id"] = w2b1.canonical_sha256(
                {key: value for key, value in manifest.items() if key != "manifest_id"}
            )
            envelope, envelope_bytes, envelope_hash = w2b1.build_envelope(
                manifest_id=manifest["manifest_id"], generation=0, entries=[entry]
            )
            accounting = manifest["accounting"]
            accounting["serialized_injected_envelope_bytes"] = len(envelope_bytes)
            accounting["model_visible_total"] = len(envelope_bytes)
            accounting["serialization_overhead_bytes"] = len(envelope_bytes) - len(raw)
            accounting["estimated_tokens"] = (len(envelope_bytes) + 3) // 4
        manifest["manifest_id"] = w2b1.canonical_sha256(
            {key: value for key, value in manifest.items() if key != "manifest_id"}
        )
        envelope, envelope_bytes, envelope_hash = w2b1.build_envelope(
            manifest_id=manifest["manifest_id"], generation=0, entries=[entry]
        )
        return DeliveryRequest(
            workspace_root=self.root,
            resolved=ResolvedContext(manifest, envelope, envelope_bytes, envelope_hash),
            capability_row=self.capability, trusted=True,
            reviewed_tree={"algorithm": "git-sha1", "value": "b" * 40},
            capability_evidence_id=w2b1.canonical_sha256(self.capability),
            client_session_id="claude.synthetic", channel_id="claude-hook-additional-context",
        )

    def test_current_evidence_fails_before_hook_or_runtime_activation(self) -> None:
        with self.assertRaisesRegex(w2b1.AgentContextError, "not supported") as failure:
            ClaudeDeliveryAdapter(CURRENT_CLAUDE_CONFIGURATION).preflight(
                workspace_root=self.root,
                expected_native_paths=("CLAUDE.md",),
                inspection=self._inspection(("CLAUDE.md",)),
            )
        self.assertEqual(failure.exception.code, "E_UNSUPPORTED_MODE")
        self.assertFalse(CURRENT_CLAUDE_CONFIGURATION.project_hook_configured)

    def test_root_nested_on_demand_and_standalone_inspection_hashes_are_exact(self) -> None:
        paths = (
            ".claude/on-demand.md", "CLAUDE.md", "nested/.claude/rule.md", "nested/CLAUDE.md",
        )
        self.adapter.preflight(
            workspace_root=self.root, expected_native_paths=paths, inspection=self._inspection(paths)
        )
        standalone = self.root / "standalone"
        standalone.mkdir()
        (standalone / "CLAUDE.md").write_text("standalone\n", encoding="utf-8")
        standalone_path = ("CLAUDE.md",)
        standalone_inspection = ClaudeNativeInspection(
            mechanism="synthetic-claude-inspection", trusted_project=True, active_hook=True,
            source_sha256={"CLAUDE.md": hashlib.sha256((standalone / "CLAUDE.md").read_bytes()).hexdigest()},
        )
        self.adapter.preflight(
            workspace_root=standalone, expected_native_paths=standalone_path,
            inspection=standalone_inspection,
        )

        current_root_path = ("CLAUDE.md",)
        current_root_inspection = ClaudeNativeInspection(
            mechanism="synthetic-claude-inspection", trusted_project=True, active_hook=True,
            source_sha256={
                "CLAUDE.md": hashlib.sha256((WORKSPACE / "CLAUDE.md").read_bytes()).hexdigest()
            },
        )
        self.adapter.preflight(
            workspace_root=WORKSPACE, expected_native_paths=current_root_path,
            inspection=current_root_inspection,
        )

    def test_synthetic_exact_handoff_uses_kernel_receipt_once(self) -> None:
        request = self._request()
        result = self.adapter.prepare_and_handoff(
            request=request, expected_native_paths=("CLAUDE.md",),
            inspection=self._inspection(("CLAUDE.md",)), transport=FakeTransportAdapter(),
            kernel=DeliveryKernel(),
        )
        self.assertEqual(result.session["state"], "COMPLETED")
        self.assertEqual(result.receipt["state"], "COMPLETED")
        self.assertEqual(result.receipt["delivered_bytes"], len(request.resolved.envelope_bytes))

    def test_channel_selection_never_truncates_or_uses_a_pointer(self) -> None:
        channels = ClaudeChannelEvidence(10, "synthetic-stdin", 20)
        self.assertEqual(channels.select(10), "claude-hook-additional-context")
        self.assertEqual(channels.select(20), "synthetic-stdin")
        with self.assertRaisesRegex(w2b1.AgentContextError, "no verified") as failure:
            channels.select(21)
        self.assertEqual(failure.exception.code, "E_CHANNEL")


if __name__ == "__main__":
    unittest.main()
