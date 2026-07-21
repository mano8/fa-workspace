from __future__ import annotations

import os
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import codex_repo_launcher, w2b1
from agent_context.delivery_kernel import DeliveryKernel, FakeTransportAdapter
from agent_context.resolve_context import ResolvedContext
from agent_context.tests.test_delivery_kernel import DeliveryKernelTests


class W9d3LifecycleTests(unittest.TestCase):
    """Frozen H-3 production lifecycle and retention safety fixtures."""

    def setUp(self) -> None:
        self.fixture = DeliveryKernelTests()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def _next_request(self, **changes: object):
        envelope, raw, digest = w2b1.build_envelope(
            manifest_id=self.fixture.resolved.manifest["manifest_id"], generation=1,
            entries=self.fixture.resolved.envelope["entries"],
        )
        resolved = ResolvedContext(self.fixture.resolved.manifest, envelope, raw, digest)
        return type(self.fixture._request())(**{
            **self.fixture._request().__dict__, "resolved": resolved, **changes,
        })

    def test_ambiguous_generation_cannot_resume(self) -> None:
        prepared = DeliveryKernel().prepare(self.fixture._request())
        with self.assertRaises(w2b1.AgentContextError):
            DeliveryKernel().handoff(prepared, type("Fault", (), {"deliver": lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError())})())
        with self.assertRaisesRegex(w2b1.AgentContextError, "completed generation") as failure:
            DeliveryKernel().resume(prepared.runtime_dir, self._next_request())
        self.assertEqual(failure.exception.code, "E_LIFECYCLE")

    def test_concurrent_and_substituted_runtime_paths_fail(self) -> None:
        kernel = DeliveryKernel()
        prepared = kernel.prepare(self.fixture._request())
        (prepared.runtime_dir / "receipt.json").unlink()
        (prepared.runtime_dir / "receipt.json").symlink_to(self.fixture.root / "policy.md")
        with self.assertRaisesRegex(w2b1.AgentContextError, "unsafe") as failure:
            kernel.cleanup(prepared.runtime_dir, self.fixture.root)
        self.assertEqual(failure.exception.code, "E_RUNTIME")

    def test_fresh_invalidates_prior_reuse(self) -> None:
        kernel = DeliveryKernel()
        prior = kernel.handoff(kernel.prepare(self.fixture._request()), FakeTransportAdapter())
        fresh = kernel.fresh(prior.runtime_dir, self.fixture._request())
        self.assertFalse(prior.runtime_dir.exists())
        self.assertEqual(fresh.session["generation"], 0)
        with self.assertRaises(w2b1.AgentContextError):
            kernel.resume(prior.runtime_dir, self._next_request())

        adapter = mock.Mock()
        adapter.fresh_and_handoff_repositories.return_value = mock.Mock(
            receipt={"receipt_id": "a" * 64}
        )
        launcher_kernel = mock.Mock()
        prior_path = self.fixture.root / ".workspace/.runtime/session-prior"
        with (
            mock.patch.object(codex_repo_launcher, "find_workspace_root", return_value=self.fixture.root),
            mock.patch.object(codex_repo_launcher, "DeliveryKernel", return_value=launcher_kernel),
            mock.patch.object(codex_repo_launcher, "CodexDeliveryAdapter", return_value=adapter),
            redirect_stdout(StringIO()),
        ):
            exit_status = codex_repo_launcher.main([
                "--repository", "repo-a", "--fresh", str(prior_path), "fresh task",
            ])
        self.assertEqual(exit_status, 0)
        launcher_kernel._validate_runtime_dir.assert_called_once_with(prior_path, self.fixture.root)
        adapter.fresh_and_handoff_repositories.assert_called_once()
        self.assertEqual(
            adapter.fresh_and_handoff_repositories.call_args.kwargs["prior_runtime_dir"],
            prior_path,
        )

    def test_interrupted_retention_and_startup_cleanup_are_safe(self) -> None:
        kernel = DeliveryKernel()
        old = kernel.prepare(self.fixture._request()).runtime_dir
        newer = kernel.prepare(self.fixture._request()).runtime_dir
        os.utime(old, (1, 1))
        os.utime(newer, (2, 2))
        self.assertEqual(kernel.cleanup_retained(self.fixture.root, max_sessions=1), 1)
        self.assertFalse(old.exists())
        self.assertTrue(newer.exists())

    def test_resume_revalidates_source_and_trust_identity(self) -> None:
        kernel = DeliveryKernel()
        completed = kernel.handoff(kernel.prepare(self.fixture._request()), FakeTransportAdapter())
        with self.assertRaisesRegex(w2b1.AgentContextError, "linkage") as failure:
            kernel.resume(completed.runtime_dir, self._next_request(trust_identity_sha256="a" * 64))
        self.assertEqual(failure.exception.code, "E_RECEIPT")

    def test_unsupported_compact_fails(self) -> None:
        prepared = DeliveryKernel().prepare(self.fixture._request())
        with self.assertRaisesRegex(w2b1.AgentContextError, "compaction") as failure:
            DeliveryKernel().compact(prepared)
        self.assertEqual(failure.exception.code, "E_LIFECYCLE")


if __name__ == "__main__":
    unittest.main()
