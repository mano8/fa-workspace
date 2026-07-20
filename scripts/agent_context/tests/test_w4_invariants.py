from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.validate_invariants import (
    InvariantValidationError,
    validate_workspace_invariants,
)
from agent_context.w2b1 import parse_strict_json


WORKSPACE = Path(__file__).resolve().parents[3]
EXPECTED_IDS = {
    "ARCH-LAYER-DIRECTION",
    "ARCH-NO-CROSS-SERVICE-DATA",
    "CFG-LOCAL-PROFILES-UNTRACKED",
    "CFG-SINGLE-WORKSPACE-OWNER",
    "PORTABLE-NO-WORKSPACE-PATHS",
    "SEC-NO-SECRET-DISCLOSURE",
    "SEC-NO-TRACKED-SECRETS",
    "SEC-VALIDATE-UNTRUSTED-INPUT",
    "STANDALONE-CHILD-USABILITY",
}


class W4InvariantTests(unittest.TestCase):
    def _copy_policy_tree(self, destination: Path) -> None:
        shared = destination / ".workspace"
        shared.mkdir(parents=True)
        for name in ("architecture.md", "invariants.json"):
            shutil.copy2(WORKSPACE / ".workspace" / name, shared / name)

    def test_current_workspace_has_one_definition_per_step_4_1_candidate(self) -> None:
        report = validate_workspace_invariants(WORKSPACE)
        catalog = parse_strict_json(
            (WORKSPACE / ".workspace/invariants.json").read_bytes()
        )
        self.assertEqual({item["id"] for item in catalog["invariants"]}, EXPECTED_IDS)
        self.assertEqual(report.invariant_count, 9)
        self.assertEqual(report.definition_count, 9)
        # Astro's retained compatibility core now omits task procedures and
        # their duplicate invariant links; the active task metadata carries
        # task-specific invariant relationships instead.
        self.assertGreaterEqual(report.reference_count, 6)
        self.assertEqual(report.tracked_tool_copy_count, 0)

    def test_duplicate_definition_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_policy_tree(root)
            source = root / ".workspace/architecture.md"
            source.write_text(
                source.read_text(encoding="utf-8")
                + "\n### `SEC-NO-TRACKED-SECRETS`\n\nDuplicate.\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(InvariantValidationError, "exactly one definition"):
                validate_workspace_invariants(root, tracked_paths=())

    def test_unresolved_reference_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_policy_tree(root)
            source = root / ".workspace/architecture.md"
            source.write_text(
                source.read_text(encoding="utf-8")
                + "\n[`SEC-UNKNOWN-INVARIANT`](../architecture.md#sec-unknown-invariant).\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(InvariantValidationError, "unresolved invariant"):
                validate_workspace_invariants(root, tracked_paths=())

    def test_tracked_tool_specific_shared_copy_fails(self) -> None:
        with self.assertRaisesRegex(InvariantValidationError, "tool-specific"):
            validate_workspace_invariants(
                WORKSPACE, tracked_paths=(".codex/architecture.md",)
            )


if __name__ == "__main__":
    unittest.main()
