"""Frozen M-2 parity fixtures for the one offline/live strict validator."""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.delivery_kernel import DeliveryKernel
from agent_context.resolve_context import ResolvedContext
from agent_context.shared_validation import validate_persisted, validate_resolved
from agent_context.tests.test_delivery_kernel import DeliveryKernelTests


class W9d3SharedValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = DeliveryKernelTests()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def _resolved(self, manifest: dict) -> ResolvedContext:
        entries = self.fixture.resolved.envelope["entries"]
        manifest["manifest_id"] = w2b1.canonical_sha256(
            {key: value for key, value in manifest.items() if key != "manifest_id"}
        )
        envelope, raw, digest = w2b1.build_envelope(
            manifest_id=manifest["manifest_id"], generation=0, entries=entries
        )
        return ResolvedContext(manifest, envelope, raw, digest)

    def _live_code(self, resolved: ResolvedContext, **changes: object) -> str:
        request = type(self.fixture._request())(**{**self.fixture._request().__dict__, "resolved": resolved, **changes})
        with self.assertRaises(w2b1.AgentContextError) as failure:
            DeliveryKernel().prepare(request)
        return failure.exception.code

    def test_authorization_lifecycle_and_receipt_defects_match(self) -> None:
        result = DeliveryKernel().handoff(DeliveryKernel().prepare(self.fixture._request()), type("Exact", (), {"deliver": lambda _self, **kwargs: type("C", (), {"envelope_sha256": kwargs["envelope_sha256"], "delivered_bytes": len(kwargs["payload"])})()})())
        receipt = deepcopy(result.receipt)
        receipt["authorization_ids"] = ["wrong"]
        with self.assertRaises(w2b1.AgentContextError) as offline:
            validate_persisted(workspace=self.fixture.root, manifest=self.fixture.resolved.manifest,
                envelope=self.fixture.resolved.envelope, envelope_bytes=self.fixture.resolved.envelope_bytes,
                session=result.session, receipt=receipt)
        self.assertEqual(offline.exception.code, "E_SCHEMA")
        manifest = deepcopy(self.fixture.resolved.manifest)
        manifest["authorization_ids"] = ["wrong"]
        self.assertEqual(self._live_code(self._resolved(manifest)), offline.exception.code)

    def test_native_and_trust_defects_match(self) -> None:
        source = self.fixture.root / "policy.md"
        original = source.read_bytes()
        source.write_bytes(b"drift\n")
        with self.assertRaises(w2b1.AgentContextError) as offline:
            validate_resolved(workspace=self.fixture.root, manifest=self.fixture.resolved.manifest,
                envelope=self.fixture.resolved.envelope, envelope_bytes=self.fixture.resolved.envelope_bytes)
        self.assertEqual(self._live_code(self.fixture.resolved), offline.exception.code)
        self.assertEqual(offline.exception.code, "E_SOURCE")
        source.write_bytes(original)

        identity = {"trust_identity_sha256": "a" * 64}
        trust_kwargs: dict[str, object] = {}
        drift = w2b1.AgentContextError("E_TRUST", "reviewed trust identity drifted")
        with mock.patch(
            "agent_context.shared_validation.verify_trust_identity", side_effect=drift,
        ):
            with self.assertRaises(w2b1.AgentContextError) as offline_trust:
                validate_resolved(
                    workspace=self.fixture.root, manifest=self.fixture.resolved.manifest,
                    envelope=self.fixture.resolved.envelope,
                    envelope_bytes=self.fixture.resolved.envelope_bytes,
                    trust_identity_sha256="a" * 64, trust_identity=identity,
                    trust_identity_kwargs=trust_kwargs,
                )
            live_code = self._live_code(
                self.fixture.resolved, trust_identity_sha256="a" * 64,
                trust_identity=identity, trust_identity_kwargs=trust_kwargs,
            )
        self.assertEqual(offline_trust.exception.code, "E_TRUST")
        self.assertEqual(live_code, offline_trust.exception.code)

    def test_source_entry_and_accounting_defects_match(self) -> None:
        manifest = deepcopy(self.fixture.resolved.manifest)
        manifest["accounting"]["estimated_tokens"] += 1
        broken = self._resolved(manifest)
        with self.assertRaises(w2b1.AgentContextError) as offline:
            validate_resolved(workspace=self.fixture.root, manifest=broken.manifest,
                envelope=broken.envelope, envelope_bytes=broken.envelope_bytes)
        self.assertEqual(offline.exception.code, "E_BUDGET")
        self.assertEqual(self._live_code(broken), offline.exception.code)

    def test_valid_live_delivery_recomputes_exactly(self) -> None:
        result = DeliveryKernel().handoff(DeliveryKernel().prepare(self.fixture._request()), type("Exact", (), {"deliver": lambda _self, **kwargs: type("C", (), {"envelope_sha256": kwargs["envelope_sha256"], "delivered_bytes": len(kwargs["payload"])})()})())
        validate_persisted(workspace=self.fixture.root, manifest=self.fixture.resolved.manifest,
            envelope=self.fixture.resolved.envelope, envelope_bytes=self.fixture.resolved.envelope_bytes,
            session=result.session, receipt=result.receipt)
        self.assertEqual(result.receipt["delivered_bytes"], len(self.fixture.resolved.envelope_bytes))


if __name__ == "__main__":
    unittest.main()
