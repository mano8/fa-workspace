from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.delivery_kernel import (
    DeliveryKernel,
    DeliveryRequest,
    ExitCode,
    FakeTransportAdapter,
    exit_code,
)
from agent_context.resolve_context import ResolvedContext


def _capability() -> dict[str, object]:
    return {
        "agent": "codex", "platform": "devcontainer", "mode": "non-interactive",
        "status": "REQUIRED", "inspection_mechanism": "probe",
        "channel_id": "fake-full-content", "verified_channel_limit": 32768,
        "client_context_allowance": 65536, "reserved_margin": 32768,
        "start_supported": True, "resume_supported": True, "clear_supported": True,
        "compact_supported": False, "launcher_identity_available": True,
        "client_session_identity_available": True, "blocks_closeout": True,
    }


class DeliveryKernelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        source = self.root / "policy.md"
        source.write_bytes(b"policy\r\n")
        raw = source.read_bytes()
        self.capability = _capability()
        source_hash = hashlib.sha256(raw).hexdigest()
        entry = {
            "policy_id": "workspace.policy", "repository_id": "$workspace",
            "scope_prefix": ".", "path": "policy.md", "authority_tier": "workspace",
            "source_sha256": source_hash, "source_bytes": len(raw),
            "leading_bom_bytes": 0, "serialized_content_bytes": len(raw), "content": "policy\r\n",
        }
        provisional = {
            "schema_version": 2, "manifest_id": "0" * 64,
            "reviewed_tree": {"algorithm": "git-sha1", "value": "b" * 40},
            "agent": "codex", "platform": "devcontainer", "mode": "non-interactive",
            "capability_evidence_id": w2b1.canonical_sha256(self.capability),
            "repositories": [], "tasks": [], "operations": [],
            "authorization_ids": [], "authorization_provenance": [],
            "entries": [{
                "policy_id": entry["policy_id"], "repository_id": entry["repository_id"],
                "scope_prefix": entry["scope_prefix"], "path": entry["path"], "delivery": "inject",
                "source_sha256": source_hash, "source_bytes": len(raw),
                "metadata_sha256": "c" * 64, "native_evidence_id": None,
            }],
            "accounting": {
                "policy_hard_limit": 32768, "verified_channel_limit": 32768,
                "client_context_allowance": 65536, "reserved_margin": 32768,
                "effective_hard_limit": 32768, "native_model_visible_bytes": 0,
                "serialized_injected_envelope_bytes": 0, "other_model_visible_bootstrap_bytes": 0,
                "model_visible_total": 0, "raw_injected_source_bytes": len(raw),
                "serialization_overhead_bytes": 0, "estimated_tokens": 0,
                "excluded_external_layers": [],
            },
        }
        provisional_id = w2b1.canonical_sha256({key: value for key, value in provisional.items() if key != "manifest_id"})
        provisional["manifest_id"] = provisional_id
        envelope, envelope_bytes, envelope_hash = w2b1.build_envelope(manifest_id=provisional_id, generation=0, entries=[entry])
        accounting = provisional["accounting"]
        accounting["serialized_injected_envelope_bytes"] = len(envelope_bytes)
        accounting["model_visible_total"] = len(envelope_bytes)
        accounting["serialization_overhead_bytes"] = len(envelope_bytes) - len(raw)
        accounting["estimated_tokens"] = (len(envelope_bytes) + 3) // 4
        provisional["manifest_id"] = w2b1.canonical_sha256({key: value for key, value in provisional.items() if key != "manifest_id"})
        envelope, envelope_bytes, envelope_hash = w2b1.build_envelope(manifest_id=provisional["manifest_id"], generation=0, entries=[entry])
        self.resolved = ResolvedContext(provisional, envelope, envelope_bytes, envelope_hash)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _request(self) -> DeliveryRequest:
        return DeliveryRequest(
            workspace_root=self.root, resolved=self.resolved, capability_row=self.capability,
            trusted=True, reviewed_tree={"algorithm": "git-sha1", "value": "b" * 40},
            capability_evidence_id=w2b1.canonical_sha256(self.capability),
            client_session_id="client.session", channel_id="fake-full-content",
        )

    def _request_at_channel_limit(self, limit: int) -> DeliveryRequest:
        """Rebuild the immutable manifest/envelope fixture for one exact limit."""
        capability = dict(self.capability)
        capability["verified_channel_limit"] = limit
        capability_id = w2b1.canonical_sha256(capability)
        manifest = deepcopy(self.resolved.manifest)
        accounting = manifest["accounting"]
        manifest["capability_evidence_id"] = capability_id
        accounting["verified_channel_limit"] = limit
        accounting["effective_hard_limit"] = min(
            accounting["policy_hard_limit"],
            capability["verified_channel_limit"],
            capability["client_context_allowance"] - capability["reserved_margin"],
        )
        entries = self.resolved.envelope["entries"]
        for _ in range(2):
            manifest["manifest_id"] = w2b1.canonical_sha256(
                {key: value for key, value in manifest.items() if key != "manifest_id"}
            )
            envelope, envelope_bytes, envelope_hash = w2b1.build_envelope(
                manifest_id=manifest["manifest_id"], generation=0, entries=entries
            )
            accounting["serialized_injected_envelope_bytes"] = len(envelope_bytes)
            accounting["model_visible_total"] = len(envelope_bytes)
            accounting["serialization_overhead_bytes"] = len(envelope_bytes) - accounting["raw_injected_source_bytes"]
            accounting["estimated_tokens"] = (len(envelope_bytes) + 3) // 4
        manifest["manifest_id"] = w2b1.canonical_sha256(
            {key: value for key, value in manifest.items() if key != "manifest_id"}
        )
        envelope, envelope_bytes, envelope_hash = w2b1.build_envelope(
            manifest_id=manifest["manifest_id"], generation=0, entries=entries
        )
        resolved = ResolvedContext(manifest, envelope, envelope_bytes, envelope_hash)
        return DeliveryRequest(
            workspace_root=self.root, resolved=resolved, capability_row=capability,
            trusted=True, reviewed_tree={"algorithm": "git-sha1", "value": "b" * 40},
            capability_evidence_id=capability_id, client_session_id="client.session",
            channel_id="fake-full-content",
        )

    def test_exact_fake_callback_is_the_only_handoff_transition(self) -> None:
        kernel = DeliveryKernel()
        prepared = kernel.prepare(self._request())
        self.assertEqual(prepared.session["state"], "PREPARED")
        self.assertEqual(prepared.receipt["state"], "PREPARED")
        result = kernel.handoff(prepared, FakeTransportAdapter())
        self.assertEqual(result.session["state"], "HANDED_OFF")
        self.assertEqual(result.receipt["delivered_bytes"], len(self.resolved.envelope_bytes))
        self.assertFalse((result.runtime_dir / "receipt.json").is_symlink())

    def test_callback_mismatch_and_source_drift_fail_before_handoff(self) -> None:
        kernel = DeliveryKernel()
        prepared = kernel.prepare(self._request())
        with self.assertRaisesRegex(w2b1.AgentContextError, "exact payload") as mismatch:
            kernel.handoff(prepared, FakeTransportAdapter(returned_bytes=0))
        self.assertEqual(exit_code(mismatch.exception), ExitCode.E_CHANNEL)
        failed = w2b1.parse_strict_json((prepared.runtime_dir / "session.json").read_bytes())
        self.assertEqual(failed["state"], "FAILED")

        fresh = kernel.prepare(self._request())
        (self.root / "policy.md").write_bytes(b"changed\n")
        with self.assertRaisesRegex(w2b1.AgentContextError, "source drifted") as drift:
            kernel.handoff(fresh, FakeTransportAdapter())
        self.assertEqual(exit_code(drift.exception), ExitCode.E_SOURCE)

    def test_exact_channel_threshold_is_accepted_and_one_byte_over_is_rejected(self) -> None:
        exact_request = self._request_at_channel_limit(len(self.resolved.envelope_bytes))
        exact = DeliveryKernel().prepare(exact_request)
        self.assertEqual(
            exact.request.resolved.manifest["accounting"]["effective_hard_limit"],
            len(self.resolved.envelope_bytes),
        )
        DeliveryKernel().handoff(exact, FakeTransportAdapter())

        over_request = self._request_at_channel_limit(len(self.resolved.envelope_bytes) - 1)
        with self.assertRaisesRegex(w2b1.AgentContextError, "effective hard limit") as over:
            DeliveryKernel().prepare(over_request)
        self.assertEqual(exit_code(over.exception), ExitCode.E_BUDGET)

    def test_compact_is_a_stable_lifecycle_failure(self) -> None:
        prepared = DeliveryKernel().prepare(self._request())
        with self.assertRaisesRegex(w2b1.AgentContextError, "compaction") as failure:
            DeliveryKernel().compact(prepared)
        self.assertEqual(exit_code(failure.exception), ExitCode.E_LIFECYCLE)

    def test_resume_requires_the_same_session_and_next_generation(self) -> None:
        kernel = DeliveryKernel()
        first = kernel.handoff(kernel.prepare(self._request()), FakeTransportAdapter())
        envelope, envelope_bytes, envelope_hash = w2b1.build_envelope(
            manifest_id=self.resolved.manifest["manifest_id"], generation=1,
            entries=self.resolved.envelope["entries"],
        )
        next_resolved = ResolvedContext(
            self.resolved.manifest, envelope, envelope_bytes, envelope_hash
        )
        request = DeliveryRequest(**{**self._request().__dict__, "resolved": next_resolved})
        resumed = kernel.resume(first.runtime_dir, request)
        self.assertEqual(resumed.session["generation"], 1)
        self.assertEqual(resumed.session["state"], "PREPARED")

    def test_exactly_one_concurrent_handoff_can_reach_the_fake_adapter(self) -> None:
        class BlockingAdapter:
            def __init__(self) -> None:
                self.entered = threading.Event()
                self.release = threading.Event()
                self.calls = 0

            def deliver(self, *, payload: bytes, envelope_sha256: str, channel_id: str):
                del channel_id
                self.calls += 1
                self.entered.set()
                self.release.wait(timeout=5)
                return type("Confirmation", (), {
                    "envelope_sha256": envelope_sha256,
                    "delivered_bytes": len(payload),
                })()

        kernel = DeliveryKernel()
        prepared = kernel.prepare(self._request())
        adapter = BlockingAdapter()
        outcome: list[object] = []

        def first_handoff() -> None:
            outcome.append(kernel.handoff(prepared, adapter))

        writer = threading.Thread(target=first_handoff)
        writer.start()
        self.assertTrue(adapter.entered.wait(timeout=5))
        with self.assertRaisesRegex(w2b1.AgentContextError, "another runtime writer") as competing:
            kernel.handoff(prepared, FakeTransportAdapter())
        self.assertEqual(exit_code(competing.exception), ExitCode.E_CONCURRENCY)
        adapter.release.set()
        writer.join(timeout=5)
        self.assertFalse(writer.is_alive())
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(len(outcome), 1)
        self.assertEqual(outcome[0].session["state"], "HANDED_OFF")

    def test_runtime_collision_and_terminal_receipt_rewrite_fail_closed(self) -> None:
        kernel = DeliveryKernel()
        with patch("agent_context.delivery_kernel.secrets.token_hex", return_value="fixed"):
            first = kernel.prepare(self._request())
            with self.assertRaisesRegex(w2b1.AgentContextError, "unique runtime session") as collision:
                kernel.prepare(self._request())
        self.assertEqual(exit_code(collision.exception), ExitCode.E_CONCURRENCY)
        kernel.handoff(first, FakeTransportAdapter())
        with self.assertRaisesRegex(w2b1.AgentContextError, "current PREPARED generation") as duplicate:
            kernel.handoff(first, FakeTransportAdapter())
        self.assertEqual(exit_code(duplicate.exception), ExitCode.E_RECEIPT)
        session = w2b1.parse_strict_json((first.runtime_dir / "session.json").read_bytes())
        self.assertEqual(session["state"], "HANDED_OFF")

    def test_runtime_substitution_and_permissions_fail_before_handoff(self) -> None:
        kernel = DeliveryKernel()
        prepared = kernel.prepare(self._request())
        if os.name == "posix":
            os.chmod(prepared.runtime_dir, 0o755)
            with self.assertRaisesRegex(w2b1.AgentContextError, "owner-only") as permissions:
                kernel.handoff(prepared, FakeTransportAdapter())
            self.assertEqual(exit_code(permissions.exception), ExitCode.E_RUNTIME)
            os.chmod(prepared.runtime_dir, 0o700)

        replaced = kernel.prepare(self._request())
        session = replaced.runtime_dir / "session.json"
        session.unlink()
        session.symlink_to(self.root / "policy.md")
        with self.assertRaisesRegex(w2b1.AgentContextError, "unsafe") as substitution:
            kernel.handoff(replaced, FakeTransportAdapter())
        self.assertEqual(exit_code(substitution.exception), ExitCode.E_RUNTIME)

    def test_cleanup_handles_interruption_and_rejects_unsafe_children(self) -> None:
        kernel = DeliveryKernel()
        prepared = kernel.prepare(self._request())
        kernel.cleanup(prepared.runtime_dir, self.root)
        self.assertFalse(prepared.runtime_dir.exists())

        interrupted = kernel._new_runtime_dir(self.root)
        kernel.cleanup(interrupted, self.root)
        self.assertFalse(interrupted.exists())

        unsafe = kernel.prepare(self._request())
        (unsafe.runtime_dir / "outside").symlink_to(self.root / "policy.md")
        with self.assertRaisesRegex(w2b1.AgentContextError, "unexpected entry") as cleanup_failure:
            kernel.cleanup(unsafe.runtime_dir, self.root)
        self.assertEqual(exit_code(cleanup_failure.exception), ExitCode.E_RUNTIME)
        self.assertTrue(unsafe.runtime_dir.exists())

    def test_retention_removes_only_validated_old_direct_sessions(self) -> None:
        kernel = DeliveryKernel()
        sessions = [kernel.prepare(self._request()).runtime_dir for _ in range(3)]
        for index, session in enumerate(sessions):
            os.utime(session, (index + 1, index + 1))
        self.assertEqual(kernel.cleanup_retained(self.root, max_sessions=1), 2)
        self.assertFalse(sessions[0].exists())
        self.assertFalse(sessions[1].exists())
        self.assertTrue(sessions[2].exists())


if __name__ == "__main__":
    unittest.main()
