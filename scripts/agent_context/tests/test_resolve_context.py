from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.resolve_context import ResolutionRequest, resolve_context


SHA = "a" * 64


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _capability() -> dict[str, object]:
    return {
        "agent": "codex",
        "platform": "devcontainer",
        "mode": "non-interactive",
        "status": "REQUIRED",
        "inspection_mechanism": "codex-debug-prompt-input",
        "channel_id": "cli-config-developer-instructions",
        "verified_channel_limit": 32768,
        "client_context_allowance": 65536,
        "reserved_margin": 32768,
        "start_supported": True,
        "resume_supported": True,
        "clear_supported": True,
        "compact_supported": False,
        "launcher_identity_available": True,
        "client_session_identity_available": True,
        "blocks_closeout": True,
    }


def _unit(
    policy_id: str, path: str, repository_id: str, prefix: str, tier: str = "workspace"
) -> dict[str, object]:
    return {
        "id": policy_id,
        "path": path,
        "authority_tier": tier,
        "scope": {"repository_id": repository_id, "prefix": prefix},
        "invariant_ids": ["OWNERSHIP"],
        "conflicts_with": [],
        "may_override": [],
        "required": policy_id == "workspace.root",
        "capabilities_granted": ["read"],
    }


class ScopedResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "AGENTS.md").write_bytes(b"root\r\n")
        for repository in ("repo-a", "repo-b"):
            directory = self.root / repository
            directory.mkdir()
            (directory / "CONTEXT.md").write_bytes(f"{repository}\n".encode())
        self.capability = _capability()
        self.registry = {
            "schema_version": 2,
            "repositories": [
                {
                    "id": "repo-a",
                    "path": "repo-a",
                    "kind": "python",
                    "layer": "platform",
                    "facets": ["a"],
                },
                {
                    "id": "repo-b",
                    "path": "repo-b",
                    "kind": "python",
                    "layer": "platform",
                    "facets": ["b"],
                },
            ],
        }
        self.units = [
            _unit("workspace.root", "AGENTS.md", "$workspace", "."),
            _unit("repo.a", "repo-a/CONTEXT.md", "repo-a", "repo-a", "repository"),
            _unit("repo.b", "repo-b/CONTEXT.md", "repo-b", "repo-b", "repository"),
        ]
        self.index = {
            "schema_version": 2,
            "mode": "faceted",
            "budgets": {"preferred_bytes": 24576, "hard_bytes": 32768},
            "always": ["workspace.root"],
            "facet_ids": ["a", "b"],
            "facets": {"a": ["repo.a"], "b": ["repo.b"]},
            "tasks": {
                "cross.a": {
                    "policies": ["workspace.root"],
                    "authorization": "cross-repository",
                },
                "cross.b": {
                    "policies": ["workspace.root"],
                    "authorization": "cross-repository",
                },
            },
            "exclusions": {"remove-a": ["repo.a"], "remove-root": ["workspace.root"]},
        }

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _request(
        self,
        repositories: tuple[str, ...] = ("repo-a", "repo-b"),
        tasks: tuple[str, ...] = ("cross.a", "cross.b"),
    ) -> ResolutionRequest:
        root_raw = (self.root / "AGENTS.md").read_bytes()
        native = {
            "native_evidence_id": SHA,
            "agent": "codex",
            "platform": "devcontainer",
            "mode": "non-interactive",
            "client_identity": "codex",
            "client_version": "0.144.6",
            "config_sha256": SHA,
            "capability_evidence_id": w2b1.canonical_sha256(self.capability),
            "trust_state": "trusted",
            "inspection_mechanism": "codex-debug-prompt-input",
            "captured_at": "2026-07-19T00:00:00Z",
            "sources": [{"path": "AGENTS.md", "sha256": _digest(root_raw)}],
        }
        native["native_evidence_id"] = w2b1.canonical_sha256(
            {key: value for key, value in native.items() if key != "native_evidence_id"}
        )
        inject = {
            "generation": 0,
            "native_discovery_disabled": True,
            "exact_once_handoff_proven": True,
            "sources": [
                {
                    "path": "repo-a/CONTEXT.md",
                    "sha256": _digest((self.root / "repo-a/CONTEXT.md").read_bytes()),
                },
                {
                    "path": "repo-b/CONTEXT.md",
                    "sha256": _digest((self.root / "repo-b/CONTEXT.md").read_bytes()),
                },
            ],
        }
        authorization = {
            "authorization_id": "human.cross",
            "kind": "explicit-user-message",
            "authorized_by": "owner",
            "source_ref": "conversation:42",
            "source_sha256": SHA,
            "repositories": ["repo-a", "repo-b"],
            "operations": ["analyze"],
            "issued_at": "2026-07-19T00:00:00Z",
        }
        return ResolutionRequest(
            root=self.root,
            registry=self.registry,
            policy_index=self.index,
            policy_metadata={
                "units": self.units,
                "invariants": ["OWNERSHIP"],
                "capabilities": ["read"],
            },
            capability_row=self.capability,
            reviewed_tree={"algorithm": "git-sha1", "value": "b" * 40},
            agent="codex",
            platform="devcontainer",
            mode="non-interactive",
            repositories=repositories,
            tasks=tasks,
            operations=("analyze",),
            authorizations=(authorization,),
            native_evidence=native,
            injection_evidence=inject,
        )

    def test_reordered_scope_inputs_have_identical_manifest_and_envelope(self) -> None:
        left = resolve_context(self._request())
        right = resolve_context(
            self._request(("repo-b", "repo-a"), ("cross.b", "cross.a"))
        )
        self.assertEqual(left.manifest, right.manifest)
        self.assertEqual(left.envelope_bytes, right.envelope_bytes)
        accounting = left.manifest["accounting"]
        self.assertEqual(
            accounting["model_visible_total"],
            accounting["native_model_visible_bytes"]
            + accounting["serialized_injected_envelope_bytes"],
        )
        self.assertEqual(
            accounting["serialization_overhead_bytes"],
            accounting["serialized_injected_envelope_bytes"]
            - accounting["raw_injected_source_bytes"],
        )
        self.assertEqual(
            [entry["delivery"] for entry in left.manifest["entries"]],
            ["native", "inject", "inject"],
        )

    def test_required_exclusion_and_cross_repository_authorization_fail_closed(
        self,
    ) -> None:
        request = self._request()
        forbidden = ResolutionRequest(
            **{**request.__dict__, "exclusions": ("remove-root",)}
        )
        with self.assertRaisesRegex(w2b1.AgentContextError, "required policy"):
            resolve_context(forbidden)
        without_authorization = ResolutionRequest(
            **{**request.__dict__, "authorizations": ()}
        )
        with self.assertRaisesRegex(
            w2b1.AgentContextError, "requires explicit human authorization"
        ):
            resolve_context(without_authorization)

    def test_mismatched_duplicate_path_and_stale_native_evidence_fail(self) -> None:
        request = self._request()
        duplicate = _unit(
            "repo.duplicate", "repo-a/CONTEXT.md", "repo-a", "repo-a", "repository"
        )
        duplicate_request = ResolutionRequest(
            **{
                **request.__dict__,
                "policy_metadata": {
                    "units": [*self.units, duplicate],
                    "invariants": ["OWNERSHIP"],
                    "capabilities": ["read"],
                },
                "policy_index": {
                    **self.index,
                    "facets": {"a": ["repo.a", "repo.duplicate"], "b": ["repo.b"]},
                },
            }
        )
        with self.assertRaisesRegex(w2b1.AgentContextError, "mismatched metadata"):
            resolve_context(duplicate_request)
        stale_native = dict(request.native_evidence or {})
        stale_native["sources"] = [{"path": "AGENTS.md", "sha256": SHA}]
        stale_native["native_evidence_id"] = w2b1.canonical_sha256(
            {
                key: value
                for key, value in stale_native.items()
                if key != "native_evidence_id"
            }
        )
        stale_request = ResolutionRequest(
            **{**request.__dict__, "native_evidence": stale_native}
        )
        with self.assertRaisesRegex(w2b1.AgentContextError, "neither verified native"):
            resolve_context(stale_request)

    def test_same_tier_conflict_and_lower_override_are_rejected(self) -> None:
        request = self._request(("repo-a",), ())
        first = dict(self.units[1])
        second = _unit(
            "repo.conflict", "repo-a/CONTEXT.md", "repo-a", "repo-a", "repository"
        )
        first["conflicts_with"] = ["repo.conflict"]
        conflict_request = ResolutionRequest(
            **{
                **request.__dict__,
                "policy_metadata": {
                    "units": [self.units[0], first, second],
                    "invariants": ["OWNERSHIP"],
                    "capabilities": ["read"],
                },
                "policy_index": {
                    **self.index,
                    "facets": {"a": ["repo.a", "repo.conflict"], "b": ["repo.b"]},
                },
                "authorizations": (),
                "operations": (),
            }
        )
        with self.assertRaisesRegex(w2b1.AgentContextError, "unresolved same-tier"):
            resolve_context(conflict_request)
        lower = dict(self.units[1])
        lower["may_override"] = ["workspace.root"]
        lower_request = ResolutionRequest(
            **{
                **request.__dict__,
                "policy_metadata": {
                    "units": [self.units[0], lower, self.units[2]],
                    "invariants": ["OWNERSHIP"],
                    "capabilities": ["read"],
                },
                "authorizations": (),
                "operations": (),
            }
        )
        with self.assertRaisesRegex(w2b1.AgentContextError, "lower authority"):
            resolve_context(lower_request)

    def test_capability_and_authorization_provenance_invalidation_table(self) -> None:
        request = self._request()
        stale_capability = dict(self.capability)
        stale_capability["channel_id"] = "different-channel"
        bad_scope = dict(request.authorizations[0])
        bad_scope["repositories"] = ["repo-a"]
        fixtures = (
            (
                "limited-mode",
                ResolutionRequest(**{**request.__dict__, "capability_row": {**self.capability, "status": "LIMITED"}}),
                "E_UNSUPPORTED_MODE",
            ),
            (
                "capability-evidence-drift",
                ResolutionRequest(**{**request.__dict__, "capability_row": stale_capability}),
                "E_NATIVE_EVIDENCE",
            ),
            (
                "authorization-scope-drift",
                ResolutionRequest(**{**request.__dict__, "authorizations": (bad_scope,)}),
                "E_AUTHORIZATION",
            ),
        )
        for name, fixture, code in fixtures:
            with self.subTest(name=name):
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    resolve_context(fixture)
                self.assertEqual(failure.exception.code, code)

    def test_platform_capability_matrix_is_not_inferred_from_devcontainer(self) -> None:
        request = self._request()
        fixtures = (("windows", "windows"), ("host-posix", "posix"))
        for name, platform in fixtures:
            with self.subTest(name=name):
                capability = {**self.capability, "platform": platform, "status": "UNSUPPORTED"}
                unsupported = ResolutionRequest(
                    **{**request.__dict__, "platform": platform, "capability_row": capability}
                )
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    resolve_context(unsupported)
                self.assertEqual(failure.exception.code, "E_UNSUPPORTED_MODE")

    def test_exact_accounting_keeps_raw_injected_bytes_diagnostic_only(self) -> None:
        resolved = resolve_context(self._request())
        accounting = resolved.manifest["accounting"]
        self.assertGreater(accounting["raw_injected_source_bytes"], 0)
        self.assertEqual(
            accounting["model_visible_total"],
            accounting["native_model_visible_bytes"]
            + accounting["serialized_injected_envelope_bytes"],
        )
        self.assertNotEqual(
            accounting["model_visible_total"],
            accounting["native_model_visible_bytes"]
            + accounting["serialized_injected_envelope_bytes"]
            + accounting["raw_injected_source_bytes"],
        )


if __name__ == "__main__":
    unittest.main()
