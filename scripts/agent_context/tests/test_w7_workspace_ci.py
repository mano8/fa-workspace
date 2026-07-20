from __future__ import annotations

import json
import unittest
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
WORKFLOW = WORKSPACE / ".github/workflows/workspace-policy-lint.yml"


class WorkspacePolicyLintWorkflowTests(unittest.TestCase):
    def test_workflow_runs_root_validation_and_root_tests_only(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workspace-policy-lint", text)
        self.assertIn("validate_workspace.py --workspace .", text)
        self.assertIn("validate_migration_guards.py --workspace .", text)
        self.assertIn("validate_w9a_contract.py --workspace .", text)
        self.assertIn("budget_promotion.py --workspace . --enforce-preferred", text)
        self.assertIn("unittest discover -s scripts/agent_context/tests -v", text)
        self.assertIn("python -m ruff check scripts/agent_context", text)
        self.assertIn("tomllib", text)
        self.assertNotIn("working-directory", text)
        self.assertIn("submodules: false", text)
        registry = json.loads((WORKSPACE / ".workspace/repo-types.json").read_text(encoding="utf-8"))
        for repository in registry["repositories"]:
            self.assertNotIn(repository["path"], text)


if __name__ == "__main__":
    unittest.main()
