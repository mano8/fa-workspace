from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1
from agent_context.resolve_context import ResolutionRequest, resolve_context


WORKSPACE = Path(__file__).resolve().parents[3]


def _capability() -> dict[str, object]:
    return {
        "agent": "codex",
        "platform": "devcontainer",
        "mode": "non-interactive",
        "status": "REQUIRED",
        "inspection_mechanism": "fixture",
        "channel_id": "fixture",
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


class W4FacetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = w2b1.parse_strict_json(
            (WORKSPACE / ".workspace/repo-types.json").read_bytes()
        )
        cls.index = w2b1.parse_strict_json(
            (WORKSPACE / ".workspace/policy.index.json").read_bytes()
        )
        cls.metadata = w2b1.parse_strict_json(
            (WORKSPACE / ".workspace/policy.metadata.json").read_bytes()
        )

    def _resolve(self, repository: str):
        sources = [
            {
                "path": unit["path"],
                "sha256": hashlib.sha256(
                    (WORKSPACE / unit["path"]).read_bytes()
                ).hexdigest(),
            }
            for unit in sorted(self.metadata["units"], key=lambda item: item["path"])
        ]
        capability = _capability()
        return resolve_context(
            ResolutionRequest(
                root=WORKSPACE,
                registry=self.registry,
                policy_index=self.index,
                policy_metadata=self.metadata,
                capability_row=capability,
                reviewed_tree={"algorithm": "git-sha1", "value": "b" * 40},
                agent="codex",
                platform="devcontainer",
                mode="non-interactive",
                repositories=(repository,),
                injection_evidence={
                    "generation": 0,
                    "native_discovery_disabled": True,
                    "exact_once_handoff_proven": True,
                    "sources": sources,
                },
            )
        )

    def test_active_configuration_has_complete_evidenced_catalog_without_empty_slices(self) -> None:
        w2b1.validate_workspace_configuration_v2(self.registry, self.index)
        self.assertEqual(self.index["mode"], "faceted")
        self.assertEqual(
            set(self.index["facet_ids"]),
            {facet for repository in self.registry["repositories"] for facet in repository["facets"]},
        )
        units = {unit["id"]: unit for unit in self.metadata["units"]}
        for facet, policy_ids in self.index["facets"].items():
            self.assertIn(facet, self.index["facet_ids"])
            self.assertTrue(policy_ids)
            for policy_id in policy_ids:
                source = WORKSPACE / units[policy_id]["path"]
                self.assertTrue(source.is_file())
                self.assertTrue(source.read_text(encoding="utf-8").strip())
        astro_tasks = {
            "astro-auth-adapter": ["task.astro-auth-adapter"],
            "astro-host": ["task.astro-host"],
            "astro-plugin-testing": ["task.astro-plugin-testing"],
            "astro-registry-scaffolding": ["task.astro-registry-scaffolding"],
        }
        for task, policies in astro_tasks.items():
            self.assertEqual(self.index["tasks"][task]["policies"], policies)

    def test_representative_selections_preserve_scope_and_sdk_neutrality(self) -> None:
        expected = {
            "auth-sdk-m8": {"always.security", "always.workspace", "facet.language.python", "facet.domain.auth-security"},
            "fa-auth-m8": {"always.security", "always.workspace", "facet.language.python", "facet.kind.api-service", "facet.layer.service", "facet.framework.fastapi", "facet.domain.auth-security"},
            "astro-auth-m8": {"always.security", "always.workspace", "facet.language.typescript", "facet.layer.client", "facet.kind.astro-plugin", "facet.framework.astro", "facet.domain.auth-client"},
            "fa-ui-m8": {"always.security", "always.workspace", "facet.language.typescript", "facet.layer.client", "facet.framework.astro", "facet.domain.shared-ui"},
            "astro-ui-m8": {"always.security", "always.workspace", "facet.language.typescript", "facet.kind.ui-library", "facet.domain.shared-ui"},
        }
        for repository, selected in expected.items():
            with self.subTest(repository=repository):
                result = self._resolve(repository)
                self.assertEqual(
                    {entry["policy_id"] for entry in result.manifest["entries"]}, selected
                )
        sdk = self._resolve("auth-sdk-m8")
        self.assertNotIn("facet.kind.api-service", {entry["policy_id"] for entry in sdk.manifest["entries"]})

    def test_facet_slices_retain_the_classified_semantics_before_compression(self) -> None:
        required_text = {
            "language-python.md": ("strict typing", "Use f-strings", "Build iteratively"),
            "language-typescript.md": ("strict mode", "untyped `any`"),
            "layer-client.md": ("contract-bound client boundary", "stateless"),
            "kind-api-service.md": ("business logic from the transport layer", "fails fast"),
            "kind-astro-plugin.md": ("HTTP contract", "never imports another optional plugin", "headless"),
            "kind-ui-library.md": ("shared shadcn registry", "not an Astro\nintegration"),
            "framework-astro.md": ("React 18/19 islands", "confirmation panels"),
            "domain-auth-client.md": ("authentication foundation", "HTTP contract only"),
            "domain-media-client.md": ("media-service-m8", "contract only"),
            "domain-prompt-client.md": ("prompt-engine-m8", "contract only"),
            "domain-teaching-assignment-client.md": ("reparto-docente-m8", "contract only"),
            "domain-shared-ui.md": ("Extend a missing capability", "Do not fork"),
        }
        for filename, fragments in required_text.items():
            content = (WORKSPACE / ".workspace/policies/facets" / filename).read_text(
                encoding="utf-8"
            )
            for fragment in fragments:
                with self.subTest(filename=filename, fragment=fragment):
                    self.assertIn(fragment, content)


if __name__ == "__main__":
    unittest.main()
