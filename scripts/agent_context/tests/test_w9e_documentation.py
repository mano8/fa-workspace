"""W9e documentation/status consistency fixtures."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DOCS = (
    ROOT / ".workspace/README.md",
    ROOT / "AGENTS.md",
    ROOT / "CLAUDE.md",
    ROOT / "scripts/agent_context/README.md",
)
EVIDENCE = ROOT / "scripts/agent_context/fixtures/evidence/w9e-documentation-evidence.json"


class W9eDocumentationTests(unittest.TestCase):
    def _docs(self) -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in DOCS)

    def test_active_inactive_and_canonical_limited_claims_are_consistent(self) -> None:
        docs = self._docs()
        self.assertIn("Codex devcontainer non-interactive", docs)
        self.assertIn("`REQUIRED`", docs)
        self.assertIn("current Claude capability evidence is limited", docs)
        self.assertIn("`EXECUTION_AMBIGUOUS`", docs)
        self.assertNotIn("canonical launch remains\ndisabled", docs)
        self.assertNotIn("exact-once `HANDED_OFF`", docs)

    def test_current_historical_and_parent_final_tree_claims_are_consistent(self) -> None:
        docs = self._docs()
        evidence = (ROOT / "scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md").read_text(encoding="utf-8")
        self.assertIn("Post-remediation", evidence)
        self.assertIn("historical", docs)
        self.assertIn("workspace root", docs)
        self.assertIn("selected child", docs)
        self.assertIn("`COMPLETED`", docs)
        self.assertIn("model retention", docs)

    def test_documented_commands_and_links_validate(self) -> None:
        for path in DOCS:
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), path)
            self.assertNotIn(b"\r", raw, path)
            self.assertTrue(raw.endswith(b"\n"), path)
        for relative in (
            "scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md",
            "scripts/agent_context/fixtures/evidence/w9c-submission-state-evidence.json",
            "scripts/agent_context/fixtures/evidence/w9d1-multi-repository-evidence.json",
            "scripts/agent_context/fixtures/evidence/w9d2-bootstrap-reproducibility-evidence.json",
            "scripts/agent_context/fixtures/evidence/w9d3-capability-authority-evidence.json",
            "scripts/agent_context/fixtures/evidence/w9d3-lifecycle-evidence.json",
            "scripts/agent_context/fixtures/evidence/w9d3-shared-validation-evidence.json",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["status"], "CURRENT_POST_REMEDIATION")
        for relative, expected in evidence["sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected, relative)


if __name__ == "__main__":
    unittest.main()
