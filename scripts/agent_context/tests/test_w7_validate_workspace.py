from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.validate_workspace import WorkspaceValidationError, validate_workspace


WORKSPACE = Path(__file__).resolve().parents[3]


class WorkspaceValidatorTests(unittest.TestCase):
    """The validator has no checkout, child-test, or client-runtime dependency."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "workspace"
        self.root.mkdir()
        for name in ("AGENTS.md", "CLAUDE.md", ".gitignore", ".m8-workspace-root"):
            shutil.copy2(WORKSPACE / name, self.root / name)
        shutil.copytree(WORKSPACE / ".workspace", self.root / ".workspace", ignore=shutil.ignore_patterns(".runtime"))
        shutil.copytree(WORKSPACE / ".claude", self.root / ".claude", ignore=shutil.ignore_patterns("*.local.json", "memory", "agent-memory"))
        (self.root / ".codex").mkdir()
        shutil.copy2(WORKSPACE / ".codex" / "config.toml", self.root / ".codex" / "config.toml")
        shutil.copytree(WORKSPACE / ".githooks", self.root / ".githooks")
        (self.root / "scripts").mkdir()
        for name in ("codex-repo.sh", "codex-repo.ps1"):
            shutil.copy2(WORKSPACE / "scripts" / name, self.root / "scripts" / name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_strict_root_validation_passes_without_any_child_clone(self) -> None:
        report = validate_workspace(self.root)
        self.assertEqual(report.repository_count, 16)
        self.assertEqual(report.policy_count, 28)
        self.assertEqual(len(report.child_diagnostics), 16)
        self.assertFalse(report.artifact_validated)

    def test_policy_encoding_or_source_drift_fails_before_any_child_is_needed(self) -> None:
        policy = self.root / ".workspace/policies/always/security.md"
        policy.write_bytes(policy.read_bytes() + b"\r\n")
        with self.assertRaisesRegex(WorkspaceValidationError, "policy source"):
            validate_workspace(self.root)

    def test_contract_capability_identity_drift_fails_closed(self) -> None:
        contract = self.root / ".workspace/contracts/agent-context-w2a.contract.md"
        contract.write_text(
            contract.read_text(encoding="utf-8").replace("3fce2371", "0fce2371", 1),
            encoding="utf-8", newline="\n",
        )
        with self.assertRaisesRegex(WorkspaceValidationError, "capability-evidence hash"):
            validate_workspace(self.root)

    def test_child_rollout_contract_drift_fails_without_child_execution(self) -> None:
        contract = self.root / ".workspace/contracts/child-repository-rollout-v1.boundaries.json"
        contract.write_text(
            contract.read_text(encoding="utf-8").replace(
                '"REPOSITORY_CONTEXT.md"]', '"REPOSITORY_CONTEXT.md", "pyproject.toml"]', 1
            ),
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaisesRegex(WorkspaceValidationError, "three-path allowlist"):
            validate_workspace(self.root)

    def test_partial_runtime_artifacts_are_never_accepted_as_canonical_parity(self) -> None:
        artifact = self.root / "manifest.json"
        artifact.write_text("{}\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(WorkspaceValidationError, "must be supplied together"):
            validate_workspace(self.root, manifest_path=artifact)

    def test_exact_runtime_artifact_parity_is_validated_without_a_client(self) -> None:
        raw = (self.root / ".workspace/policies/always/security.md").read_bytes()
        source_hash = hashlib.sha256(raw).hexdigest()
        envelope_entry = w2b1.source_entry_from_bytes(raw, {
            "policy_id": "always.security", "repository_id": "$workspace", "scope_prefix": ".",
            "path": ".workspace/policies/always/security.md", "authority_tier": "security",
        })
        manifest = {
            "schema_version": 2, "manifest_id": "0" * 64,
            "reviewed_tree": {"algorithm": "git-sha1", "value": "a" * 40},
            "agent": "codex", "platform": "devcontainer", "mode": "non-interactive",
            "capability_evidence_id": "b" * 64, "repositories": [], "tasks": [], "operations": [],
            "authorization_ids": [], "authorization_provenance": [],
            "entries": [{
                "policy_id": "always.security", "repository_id": "$workspace", "scope_prefix": ".",
                "path": ".workspace/policies/always/security.md", "delivery": "inject",
                "source_sha256": source_hash, "source_bytes": len(raw), "metadata_sha256": "c" * 64,
                "native_evidence_id": None,
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
        manifest["manifest_id"] = w2b1.canonical_sha256({key: value for key, value in manifest.items() if key != "manifest_id"})
        envelope, envelope_raw, envelope_hash = w2b1.build_envelope(manifest_id=manifest["manifest_id"], generation=0, entries=[envelope_entry])
        accounting = manifest["accounting"]
        accounting.update(serialized_injected_envelope_bytes=len(envelope_raw), model_visible_total=len(envelope_raw), serialization_overhead_bytes=len(envelope_raw) - len(raw), estimated_tokens=(len(envelope_raw) + 3) // 4)
        manifest["manifest_id"] = w2b1.canonical_sha256({key: value for key, value in manifest.items() if key != "manifest_id"})
        envelope, envelope_raw, envelope_hash = w2b1.build_envelope(manifest_id=manifest["manifest_id"], generation=0, entries=[envelope_entry])
        session = {
            "schema_version": 2, "launch_id": "launch.fixture", "client_session_id": "client.fixture",
            "generation": 0, "state": "HANDED_OFF", "manifest_id": manifest["manifest_id"], "envelope_sha256": envelope_hash,
            "capability_evidence_id": "b" * 64, "native_evidence_ids": [], "repositories": [], "tasks": [], "operations": [],
            "authorization_ids": [], "authorization_provenance": [], "created_at": "2026-07-20T00:00:00Z",
            "updated_at": "2026-07-20T00:00:00Z", "previous_receipt_sha256": "d" * 64,
        }
        receipt = {
            "schema_version": 2, "receipt_id": "0" * 64, "launch_id": session["launch_id"], "client_session_id": session["client_session_id"],
            "generation": 0, "manifest_id": manifest["manifest_id"], "envelope_sha256": envelope_hash, "capability_evidence_id": "b" * 64,
            "native_evidence_ids": [], "repositories": [], "tasks": [], "operations": [], "authorization_ids": [], "authorization_provenance": [],
            "previous_state": "PREPARED", "state": "HANDED_OFF", "channel_id": "fixture-channel", "delivered_bytes": len(envelope_raw),
            "failure_code": "OK", "recorded_at": "2026-07-20T00:00:00Z",
        }
        receipt["receipt_id"] = w2b1.canonical_sha256({key: value for key, value in receipt.items() if key != "receipt_id"})
        runtime = self.root / ".workspace/.runtime/session-fixture"
        runtime.mkdir(parents=True)
        os.chmod(runtime, 0o700)
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        paths = {
            "manifest": artifacts / "manifest.json", "envelope": artifacts / "envelope.json",
            "session": runtime / "session.json", "receipt": runtime / "receipt.json",
        }
        for name, value in (("manifest", manifest), ("envelope", envelope), ("session", session), ("receipt", receipt)):
            paths[name].write_bytes(envelope_raw if name == "envelope" else w2b1.canonical_bytes(value))
            os.chmod(paths[name], 0o600)
        report = validate_workspace(self.root, manifest_path=paths["manifest"], envelope_path=paths["envelope"], session_path=paths["session"], receipt_path=paths["receipt"])
        self.assertTrue(report.artifact_validated)


if __name__ == "__main__":
    unittest.main()
