"""Phase 10.7 M-1 capability-authority regression fixtures."""

from __future__ import annotations

import hashlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.codex_adapter import CodexDeliveryAdapter
from agent_context.tests.test_w6_codex_adapter import W6CodexAdapterTests


class W9d3CapabilityAuthorityTests(unittest.TestCase):
    """Only the tracked canonical artifact may grant frozen capability authority."""

    def setUp(self) -> None:
        self.fixture = W6CodexAdapterTests()
        self.fixture.setUp()
        self.canonical = self.fixture.root / (
            "scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md"
        )
        self.canonical.parent.mkdir(parents=True)
        self.canonical.write_text("frozen tracked capability evidence\n", encoding="utf-8")
        self.canonical_sha256 = hashlib.sha256(self.canonical.read_bytes()).hexdigest()
        self.binary = self.fixture.root / "fixture-codex"
        self.binary.write_bytes(b"fixture Codex executable")

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def _patches(self):
        return patch.multiple(
            "agent_context.codex_adapter",
            CAPABILITY_EVIDENCE_SHA256=self.canonical_sha256,
            EXPECTED_CODEX_VERSION="codex-cli fixture",
            EXPECTED_CODEX_SHA256=hashlib.sha256(self.binary.read_bytes()).hexdigest(),
            shutil_which=lambda _command: self.binary,
        )

    def _preflight(self) -> None:
        with self._patches(), patch.dict(os.environ, {"CODEX_HOME": str(self.fixture.home)}):
            CodexDeliveryAdapter(
                runner=self.fixture._runner, codex_command="fixture-codex"
            ).preflight(workspace_root=self.fixture.root, repository_id="repo-a")

    def test_clean_checkout_has_documented_capability_path(self) -> None:
        self.assertFalse((self.fixture.root / ".workspace/status").exists())
        self._preflight()

    def test_deleted_ignored_status_does_not_change_authority(self) -> None:
        ignored = self.fixture.root / ".workspace/status/fa-workspace/legacy.md"
        ignored.parent.mkdir(parents=True)
        ignored.write_text("historical only\n", encoding="utf-8")
        ignored.unlink()
        self._preflight()

    def test_substituted_ignored_status_does_not_change_authority(self) -> None:
        ignored = self.fixture.root / ".workspace/status/fa-workspace/legacy.md"
        ignored.parent.mkdir(parents=True)
        ignored.write_text("substituted historical status\n", encoding="utf-8")
        self._preflight()

    def test_tracked_capability_drift_fails(self) -> None:
        self.canonical.write_text("substituted tracked capability evidence\n", encoding="utf-8")
        with self.assertRaisesRegex(w2b1.AgentContextError, "capability evidence changed") as failure:
            self._preflight()
        self.assertEqual(failure.exception.code, "E_CAPABILITY")


if __name__ == "__main__":
    unittest.main()
