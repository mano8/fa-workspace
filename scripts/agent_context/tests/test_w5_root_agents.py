from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.validate_root_agents import (
    MAX_BOOTSTRAP_BYTES,
    RootAgentsValidationError,
    validate_root_agents,
)


WORKSPACE = Path(__file__).resolve().parents[3]


class W5RootAgentsTests(unittest.TestCase):
    def _copy_root_agents(self, destination: Path) -> Path:
        shutil.copy2(WORKSPACE / "AGENTS.md", destination / "AGENTS.md")
        return destination / "AGENTS.md"

    def test_current_bootstrap_is_compact_and_resolver_driven(self) -> None:
        report = validate_root_agents(WORKSPACE)
        self.assertLessEqual(report.byte_count, MAX_BOOTSTRAP_BYTES)
        self.assertEqual(report.reference_count, 7)

    def test_noncanonical_reference_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._copy_root_agents(root)
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    ".workspace/policy.index.json", ".codex/policy.index.json"
                ),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(RootAgentsValidationError, "canonical references"):
                validate_root_agents(root)

    def test_scope_and_delivery_claims_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._copy_root_agents(root)
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "This bootstrap does not invoke the resolver or\nhand off context. ", ""
                ),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(RootAgentsValidationError, "scope, task, or delivery"):
                validate_root_agents(root)

    def test_stale_or_host_specific_content_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._copy_root_agents(root)
            path.write_text(
                path.read_text(encoding="utf-8") + "\nUse /workspace directly.\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(RootAgentsValidationError, "forbidden"):
                validate_root_agents(root)


if __name__ == "__main__":
    unittest.main()
