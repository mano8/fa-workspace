from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import w2b1


SHA = "a" * 64


def metadata() -> dict[str, object]:
    return {
        "policy_id": "workspace.env",
        "repository_id": "$workspace",
        "scope_prefix": ".",
        "path": "context/env.md",
        "authority_tier": "workspace",
    }


class CanonicalSerializationTests(unittest.TestCase):
    def test_jcs_orders_utf16_keys_and_preserves_crlf_unicode(self) -> None:
        value = {"\U0001f600": "z", "\ufffd": "é\r\n}"}
        self.assertEqual(w2b1.canonical_json(value), '{"😀":"z","�":"é\\r\\n}"}')

    def test_source_bytes_strip_only_explicit_legacy_bom(self) -> None:
        entry = w2b1.source_entry_from_bytes(b"\xef\xbb\xbfline\r\n\xe2\x98\x83", metadata(), allow_legacy_leading_bom=True)
        self.assertEqual(entry["leading_bom_bytes"], 3)
        self.assertEqual(entry["content"], "line\r\n☃")
        self.assertEqual(entry["source_sha256"], hashlib.sha256(b"\xef\xbb\xbfline\r\n\xe2\x98\x83").hexdigest())

    def test_rejects_nul_bom_invalid_utf8_and_float(self) -> None:
        with self.assertRaisesRegex(w2b1.AgentContextError, "NUL"):
            w2b1.source_entry_from_bytes(b"bad\x00", metadata())
        with self.assertRaisesRegex(w2b1.AgentContextError, "leading BOM"):
            w2b1.source_entry_from_bytes(b"\xef\xbb\xbfnew", metadata())
        with self.assertRaisesRegex(w2b1.AgentContextError, "strict UTF-8"):
            w2b1.source_entry_from_bytes(b"\xff", metadata())
        with self.assertRaisesRegex(w2b1.AgentContextError, "floating-point"):
            w2b1.canonical_json({"number": 1.5})

    def test_identical_duplicate_is_deduplicated_mismatch_fails(self) -> None:
        entry = w2b1.source_entry_from_bytes(b"alpha", metadata())
        envelope, _, _ = w2b1.build_envelope(manifest_id=SHA, generation=0, entries=[entry, entry])
        self.assertEqual(len(envelope["entries"]), 1)
        changed = dict(entry)
        changed["authority_tier"] = "task"
        with self.assertRaisesRegex(w2b1.AgentContextError, "mismatched metadata"):
            w2b1.build_envelope(manifest_id=SHA, generation=0, entries=[entry, changed])

    def test_framing_attack_payloads_are_exact_content_not_structure(self) -> None:
        fixtures = {
            "delimiter": b"---context---\n",
            "closing-json": b"}\n]}\n",
            "fake-header": b"Content-Length: 1\r\n\r\n",
            "unicode-crlf": "snowman=☃\r\nemoji=😀\r\n".encode(),
            "embedded-bom": b"alpha\xef\xbb\xbfbeta\n",
        }
        for name, raw in fixtures.items():
            with self.subTest(name=name):
                entry = w2b1.source_entry_from_bytes(raw, metadata())
                envelope, serialized, digest = w2b1.build_envelope(
                    manifest_id=SHA, generation=0, entries=[entry]
                )
                self.assertEqual(entry["content"].encode("utf-8"), raw)
                self.assertEqual(envelope["entries"][0]["content"], entry["content"])
                self.assertEqual(digest, hashlib.sha256(serialized).hexdigest())
                self.assertEqual(serialized, w2b1.canonical_bytes(envelope))

    def test_bom_nul_and_duplicate_metadata_attack_table_fails_closed(self) -> None:
        entry = w2b1.source_entry_from_bytes(b"alpha", metadata())
        changed = dict(entry)
        changed["repository_id"] = "repo-a"
        fixtures = (
            ("new-leading-bom", lambda: w2b1.source_entry_from_bytes(b"\xef\xbb\xbfbeta", metadata())),
            ("nul", lambda: w2b1.source_entry_from_bytes(b"alpha\x00", metadata())),
            ("duplicate-metadata", lambda: w2b1.build_envelope(manifest_id=SHA, generation=0, entries=[entry, changed])),
        )
        for name, operation in fixtures:
            with self.subTest(name=name):
                with self.assertRaises(w2b1.AgentContextError):
                    operation()


class SchemaTests(unittest.TestCase):
    def test_registry_rejects_internal_paths_and_unknown_fields(self) -> None:
        registry = {
            "schema_version": 2,
            "repositories": [{
                "id": "fa-ui-m8", "path": "fa-ui-m8/app", "kind": "typescript",
                "layer": "client", "facets": [],
            }],
        }
        with self.assertRaisesRegex(w2b1.AgentContextError, "direct-child"):
            w2b1.validate_registry_v2(registry)
        registry["unknown"] = True
        with self.assertRaisesRegex(w2b1.AgentContextError, "unknown fields"):
            w2b1.validate_registry_v2(registry)

    def test_final_schemas_reject_compatibility_and_migration_fields(self) -> None:
        registry = {
            "schema_version": 2,
            "repositories": [{
                "id": "fa-ui-m8", "path": "fa-ui-m8", "kind": "typescript",
                "layer": "client", "facets": [], "migration": {"v1_bundle": "typescript"},
            }],
        }
        with self.assertRaisesRegex(w2b1.AgentContextError, "unknown fields"):
            w2b1.validate_registry_v2(registry)
        index = {
            "schema_version": 2,
            "mode": "transitional-v1-bundles",
            "budgets": {"preferred_bytes": 24576, "hard_bytes": 32768},
            "always": [], "facet_ids": [], "facets": {}, "tasks": {}, "exclusions": {}
        }
        with self.assertRaisesRegex(w2b1.AgentContextError, "mode must be faceted"):
            w2b1.validate_policy_index_v2(index)
        index["mode"] = "faceted"
        index["compatibility_bundles"] = {}
        with self.assertRaisesRegex(w2b1.AgentContextError, "unknown fields"):
            w2b1.validate_policy_index_v2(index)

    def test_strict_parser_rejects_duplicate_keys_and_floats(self) -> None:
        with self.assertRaisesRegex(w2b1.AgentContextError, "duplicate key"):
            w2b1.parse_strict_json(b'{"a":1,"a":2}')
        with self.assertRaisesRegex(w2b1.AgentContextError, "floating-point"):
            w2b1.parse_strict_json(b'{"a":1.2}')

    def test_manifest_identifier_is_jcs_digest(self) -> None:
        manifest = {
            "schema_version": 2, "manifest_id": SHA,
            "reviewed_tree": {"algorithm": "git-sha1", "value": "b" * 40},
            "agent": "codex", "platform": "devcontainer", "mode": "non-interactive",
            "capability_evidence_id": SHA, "repositories": [], "tasks": [],
            "operations": [], "authorization_ids": [],
            "authorization_provenance": [], "entries": [],
            "accounting": {
                "policy_hard_limit": 32768, "verified_channel_limit": 32768,
                "client_context_allowance": 65536, "reserved_margin": 32768,
                "effective_hard_limit": 32768, "native_model_visible_bytes": 0,
                "serialized_injected_envelope_bytes": 0, "other_model_visible_bootstrap_bytes": 0,
                "model_visible_total": 0, "raw_injected_source_bytes": 0,
                "serialization_overhead_bytes": 0, "estimated_tokens": 0,
                "excluded_external_layers": [],
            },
        }
        manifest["manifest_id"] = w2b1.canonical_sha256({key: value for key, value in manifest.items() if key != "manifest_id"})
        w2b1.validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
