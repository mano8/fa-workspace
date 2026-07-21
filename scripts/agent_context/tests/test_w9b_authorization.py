from __future__ import annotations

import base64
import json
import os
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agent_context import authorization, w2b1
from agent_context.codex_repo_launcher import _verified_authorizations


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class W9bAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.external = root / "external-authority"
        self.external.mkdir(mode=0o700)
        self.replay = self.external / "replay"
        self.replay.mkdir(mode=0o700)
        self.trust = self.external / "trust.json"
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.trust.write_bytes(w2b1.canonical_bytes({
            "schema_version": 1,
            "keys": [{"issuer": "owner", "key_id": "ed25519.primary", "algorithm": "ed25519", "public_key": _b64url(public), "status": "active"}],
        }))
        self._owner_only(self.external, self.replay, self.trust)
        self.request = authorization.create_request(
            repositories=("repo-a", "repo-b"), tasks=("cross-repository",),
            operations=("push",), user_task="push the validated changes",
            launch_id="launch-fixture", nonce="nonce-fixture",
        )
        self.now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _owner_only(*paths: Path) -> None:
        if os.name == "posix":
            for path in paths:
                path.chmod(0o700 if path.is_dir() else 0o600)

    def _capability(self, **changes: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": 1, "authorization_id": "approval.fixture", "issuer": "owner",
            "key_id": "ed25519.primary", "nonce": self.request.nonce,
            "issued_at": "2026-07-20T11:55:00Z", "expires_at": "2026-07-20T12:05:00Z",
            **self.request.payload_binding(),
        }
        payload.update(changes)
        payload_bytes = w2b1.canonical_bytes(payload)
        return {"schema_version": 1, "payload_jcs": payload_bytes.decode("utf-8"), "signature": _b64url(self.private.sign(payload_bytes))}

    def _redeem(self, capability: dict[str, object], request: authorization.AuthorizationRequest | None = None):
        return authorization.verify_and_redeem(
            capability, request=request or self.request, workspace_root=self.workspace,
            external_root=self.external,
            trust_store=self.trust, replay_store=self.replay, now=self.now,
        )

    def test_agent_created_workspace_json_cannot_authorize(self) -> None:
        fake = self.workspace / "agent-created.json"
        fake.write_text(json.dumps({"schema_version": 1, "payload_jcs": "{}", "signature": "A"}), encoding="utf-8")
        with self.assertRaisesRegex(w2b1.AgentContextError, "closed required shape|payload") as failure:
            self._redeem(w2b1.parse_strict_json(fake.read_bytes()))
        self.assertEqual(failure.exception.code, "E_AUTHORIZATION")
        unsigned = self._capability()
        unsigned["signature"] = _b64url(b"x" * 64)
        with self.assertRaisesRegex(w2b1.AgentContextError, "signature is invalid"):
            self._redeem(unsigned)
        workspace_authority = self.workspace / "authority"
        workspace_authority.mkdir(mode=0o700)
        workspace_replay = workspace_authority / "replay"
        workspace_replay.mkdir(mode=0o700)
        workspace_trust = workspace_authority / "trust.json"
        workspace_trust.write_bytes(self.trust.read_bytes())
        self._owner_only(workspace_authority, workspace_replay, workspace_trust)
        with self.assertRaisesRegex(w2b1.AgentContextError, "outside the workspace"):
            authorization.verify_and_redeem(
                self._capability(), request=self.request, workspace_root=self.workspace,
                external_root=workspace_authority, trust_store=workspace_trust,
                replay_store=workspace_replay, now=self.now,
            )
        with self.assertRaisesRegex(w2b1.AgentContextError, "must not contain"):
            authorization.verify_and_redeem(
                self._capability(), request=self.request, workspace_root=self.workspace,
                external_root=self.workspace.parent, trust_store=workspace_trust,
                replay_store=workspace_replay, now=self.now,
            )

    def test_expired_future_or_overlong_capability_fails(self) -> None:
        cases = (
            {"expires_at": "2026-07-20T11:59:59Z"},
            {"issued_at": "2026-07-20T12:00:01Z", "expires_at": "2026-07-20T12:05:00Z"},
            {"expires_at": "2026-07-20T12:10:01Z"},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    self._redeem(self._capability(**changes))
                self.assertEqual(failure.exception.code, "E_AUTHORIZATION")

    def test_forged_or_modified_signature_fails(self) -> None:
        forged = self._capability()
        forged["signature"] = _b64url(b"y" * 64)
        with self.assertRaisesRegex(w2b1.AgentContextError, "signature is invalid"):
            self._redeem(forged)
        modified = self._capability()
        modified["payload_jcs"] = modified["payload_jcs"].replace("approval.fixture", "approval.changed")
        with self.assertRaisesRegex(w2b1.AgentContextError, "signature is invalid"):
            self._redeem(modified)

    def test_launch_repository_task_operation_or_prompt_mismatch_fails(self) -> None:
        for field, expected in (
            ("launch_id", "launch-other"), ("repositories", ("repo-a",)),
            ("tasks", ("push",)), ("operations", ("analyze",)),
        ):
            with self.subTest(field=field):
                changed = authorization.create_request(
                    repositories=self.request.repositories, tasks=self.request.tasks,
                    operations=self.request.operations, user_task="push the validated changes",
                    launch_id=expected if field == "launch_id" else self.request.launch_id,
                    nonce=self.request.nonce,
                )
                if field in {"repositories", "tasks", "operations"}:
                    changed = authorization.AuthorizationRequest(
                        launch_id=changed.launch_id, nonce=changed.nonce,
                        repositories=expected if field == "repositories" else changed.repositories,
                        tasks=expected if field == "tasks" else changed.tasks,
                        operations=expected if field == "operations" else changed.operations,
                        user_task_sha256=changed.user_task_sha256,
                    )
                with self.assertRaisesRegex(w2b1.AgentContextError, "does not match"):
                    self._redeem(self._capability(), changed)
        prompt_changed = authorization.create_request(
            repositories=self.request.repositories, tasks=self.request.tasks,
            operations=self.request.operations, user_task="a different user task",
            launch_id=self.request.launch_id, nonce=self.request.nonce,
        )
        with self.assertRaisesRegex(w2b1.AgentContextError, "does not match"):
            self._redeem(self._capability(), prompt_changed)

    def test_replay_and_ambiguous_redemption_fail(self) -> None:
        result = self._redeem(self._capability())
        provenance = result.provenance.as_dict()
        self.assertEqual(set(provenance), authorization.PROVENANCE_FIELDS)
        self.assertNotIn(self._capability()["signature"], json.dumps(provenance))
        self.assertNotIn("push the validated changes", json.dumps(provenance))
        with self.assertRaisesRegex(w2b1.AgentContextError, "already or ambiguously redeemed") as failure:
            self._redeem(self._capability())
        self.assertEqual(failure.exception.code, "E_AUTHORIZATION")
        self.assertEqual(len(list(self.replay.glob("redeemed-*.json"))), 1)
        if os.name == "posix":
            info = next(self.replay.iterdir()).stat()
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)

    def test_canonical_launcher_redeems_before_adapter_and_preserves_provenance(self) -> None:
        capability = self._capability()
        real_verify = authorization.verify_and_redeem

        def verify_with_frozen_clock(value, **kwargs):
            return real_verify(value, now=self.now, **kwargs)

        with patch(
            "agent_context.codex_repo_launcher.authorization.verify_and_redeem",
            side_effect=verify_with_frozen_clock,
        ):
            records, provenance, launch_id, trust_store = _verified_authorizations(
                root=self.workspace, capabilities=(capability,),
                repositories=["repo-a", "repo-b"], tasks=["cross-repository"],
                operations=["push"], prompt="push the validated changes",
                external_root=self.external, trust_store=self.trust,
                replay_store=self.replay,
            )
        self.assertEqual(launch_id, "launch-fixture")
        self.assertEqual(trust_store, self.trust)
        self.assertEqual(records[0]["authorization_id"], "approval.fixture")
        self.assertEqual(records[0]["source_sha256"], provenance[0]["signed_payload_sha256"])
        self.assertEqual(provenance[0]["issuer"], "owner")
        self.assertNotIn(capability["signature"], json.dumps(provenance))
        self.assertEqual(len(list(self.replay.glob("redeemed-*.json"))), 1)
