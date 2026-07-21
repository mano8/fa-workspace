from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.delivery_kernel import DeliveryKernel, FakeTransportAdapter
from agent_context.tests.test_delivery_kernel import DeliveryKernelTests


class W9cSubmissionStateTests(unittest.TestCase):
    """Crash/kill fixtures for the conservative C-2 submission boundary."""

    def setUp(self) -> None:
        self.fixture = DeliveryKernelTests()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def _prepared(self):
        return DeliveryKernel().prepare(self.fixture._request())

    @staticmethod
    def _fault(boundary: str):
        def fail(current: str) -> None:
            if current == boundary:
                raise RuntimeError(boundary)
        return fail

    def test_fault_before_transport_is_failed(self) -> None:
        prepared = self._prepared()
        with self.assertRaises(w2b1.AgentContextError):
            DeliveryKernel(fault_hook=self._fault("before-submission-journal")).handoff(
                prepared, FakeTransportAdapter()
            )
        state = w2b1.parse_strict_json((prepared.runtime_dir / "session.json").read_bytes())
        self.assertEqual(state["state"], "FAILED")

    def test_fault_after_submission_is_ambiguous(self) -> None:
        prepared = self._prepared()
        with self.assertRaises(w2b1.AgentContextError):
            DeliveryKernel(fault_hook=self._fault("after-submission-journal")).handoff(
                prepared, FakeTransportAdapter()
            )
        state = w2b1.parse_strict_json((prepared.runtime_dir / "session.json").read_bytes())
        self.assertEqual(state["state"], "EXECUTION_AMBIGUOUS")

    def test_fault_after_context_and_before_prompt_is_ambiguous(self) -> None:
        class ContextThenPromptFault:
            def deliver(self, **_: object):
                # The real CLI combines these in one exec call; this fixture
                # models a process death after the developer context reaches
                # the client but before prompt execution is knowable.
                raise RuntimeError("after-context-before-prompt")

        prepared = self._prepared()
        with self.assertRaises(w2b1.AgentContextError):
            DeliveryKernel().handoff(prepared, ContextThenPromptFault())
        state = w2b1.parse_strict_json((prepared.runtime_dir / "session.json").read_bytes())
        self.assertEqual(state["state"], "EXECUTION_AMBIGUOUS")

    def test_fault_after_side_effect_never_retries(self) -> None:
        calls = 0

        class SideEffectThenFault:
            def deliver(self, **_: object):
                nonlocal calls
                calls += 1
                raise RuntimeError("side-effect-completed")

        prepared = self._prepared()
        kernel = DeliveryKernel()
        with self.assertRaises(w2b1.AgentContextError):
            kernel.handoff(prepared, SideEffectThenFault())
        with self.assertRaises(w2b1.AgentContextError):
            kernel.handoff(prepared, FakeTransportAdapter())
        self.assertEqual(calls, 1)

    def test_journal_and_derived_view_crash_matrix_fails_closed(self) -> None:
        for boundary in ("receipt-view-before-write", "receipt-view-after-write", "session-view-before-write", "session-view-after-write"):
            with self.subTest(boundary=boundary):
                prepared = self._prepared()
                kernel = DeliveryKernel(fault_hook=self._fault(boundary))
                with self.assertRaises(Exception):
                    kernel.handoff(prepared, FakeTransportAdapter())
                # The immutable journal records that submission started even
                # when a derived view write is torn; a new attempt fails closed.
                with self.assertRaises(w2b1.AgentContextError):
                    DeliveryKernel().handoff(prepared, FakeTransportAdapter())

    def test_kill_during_cleanup_preserves_terminal_disposition(self) -> None:
        prepared = self._prepared()
        result = DeliveryKernel().handoff(prepared, FakeTransportAdapter())
        with self.assertRaises(RuntimeError):
            DeliveryKernel(fault_hook=self._fault("cleanup-before-remove")).cleanup(
                result.runtime_dir, self.fixture.root
            )
        self.assertEqual(
            DeliveryKernel()._latest_journal(result.runtime_dir)["receipt"]["state"],
            "COMPLETED",
        )


if __name__ == "__main__":
    unittest.main()
