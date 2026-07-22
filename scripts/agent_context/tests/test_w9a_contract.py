from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.validate_w9a_contract import (
    W9aContractError,
    validate_w9a_contract,
)


WORKSPACE = Path(__file__).resolve().parents[3]
REGISTER = Path(".workspace/contracts/agent-context-w9a-findings.json")
CONTRACT = Path(".workspace/contracts/agent-context-w9a-remediation.contract.md")
W2A = Path(".workspace/contracts/agent-context-w2a.contract.md")
CAPABILITY = Path(
    "scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md"
)
AUDIT_EN = Path(
    ".workspace/plans/fa-workspace/feedback/phase-9-5-critical-sign-off-audit-en.md"
)


class W9aContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "workspace"
        for relative in (REGISTER, CONTRACT, W2A, CAPABILITY):
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(WORKSPACE / relative, destination)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _register(self) -> dict[str, object]:
        return json.loads((self.root / REGISTER).read_text(encoding="utf-8"))

    def _write_register(self, value: dict[str, object]) -> None:
        (self.root / REGISTER).write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def test_current_register_freezes_all_audit_dispositions(self) -> None:
        report = validate_w9a_contract(WORKSPACE)
        self.assertEqual(report.finding_count, 11)
        self.assertEqual(report.blocking_count, 5)
        self.assertEqual(report.limitation_count, 1)
        self.assertEqual(report.named_negative_test_count, 52)
        self.assertEqual(report.named_closure_artifact_count, 53)

    def test_clean_checkout_does_not_require_ignored_audit_files(self) -> None:
        report = validate_w9a_contract(self.root)
        self.assertEqual(report.finding_count, 11)
        self.assertEqual(report.blocking_count, 5)

    def test_present_external_audit_must_match_frozen_hash(self) -> None:
        audit = self.root / AUDIT_EN
        audit.parent.mkdir(parents=True, exist_ok=True)
        audit.write_text("substituted audit\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(W9aContractError, "source input hash changed"):
            validate_w9a_contract(self.root)

    def test_unknown_register_field_fails_closed(self) -> None:
        value = self._register()
        value["compatibility"] = True
        self._write_register(value)
        with self.assertRaisesRegex(W9aContractError, "unknown fields"):
            validate_w9a_contract(self.root)

    def test_missing_finding_or_changed_disposition_mapping_fails(self) -> None:
        value = self._register()
        findings = value["findings"]
        assert isinstance(findings, list)
        findings.pop()
        self._write_register(value)
        with self.assertRaisesRegex(W9aContractError, "exactly the eleven"):
            validate_w9a_contract(self.root)

        shutil.copy2(WORKSPACE / REGISTER, self.root / REGISTER)
        value = self._register()
        findings = value["findings"]
        assert isinstance(findings, list) and isinstance(findings[0], dict)
        findings[0]["remediation_step"] = "10.3"
        self._write_register(value)
        with self.assertRaisesRegex(W9aContractError, "mapping changed"):
            validate_w9a_contract(self.root)

    def test_capability_ceiling_cannot_expand(self) -> None:
        value = self._register()
        ceiling = value["capability_ceiling"]
        assert isinstance(ceiling, dict) and isinstance(ceiling["required_rows"], list)
        ceiling["required_rows"].append("codex:devcontainer:interactive")
        self._write_register(value)
        with self.assertRaisesRegex(W9aContractError, "capability ceiling"):
            validate_w9a_contract(self.root)

    def test_named_test_module_and_contract_markers_are_required(self) -> None:
        value = self._register()
        findings = value["findings"]
        assert isinstance(findings, list) and isinstance(findings[0], dict)
        artifacts = findings[0]["closure_artifacts"]
        assert isinstance(artifacts, list)
        artifacts.remove("scripts/agent_context/tests/test_w9b_authorization.py")
        self._write_register(value)
        with self.assertRaisesRegex(W9aContractError, "does not name the module"):
            validate_w9a_contract(self.root)

        shutil.copy2(WORKSPACE / REGISTER, self.root / REGISTER)
        contract = self.root / CONTRACT
        contract.write_text(
            contract.read_text(encoding="utf-8").replace("Ed25519", "another algorithm"),
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaisesRegex(W9aContractError, "missing frozen markers"):
            validate_w9a_contract(self.root)


if __name__ == "__main__":
    unittest.main()
