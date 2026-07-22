"""W9e L-2 deterministic root-tooling SBOM fixtures."""

from __future__ import annotations

import json
import sys
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_context.generate_root_sbom import (  # noqa: E402
    SOURCE_PATHS,
    SbomError,
    build_sbom,
    canonical_bytes,
    validate_sbom,
)


class W9eSbomTests(unittest.TestCase):
    def test_sbom_covers_frozen_root_tooling_inputs(self) -> None:
        sbom = build_sbom(ROOT)
        components = {component["bom-ref"] for component in sbom["components"]}
        self.assertTrue(all(property["name"].removeprefix("m8:source-sha256:") in {
            path.as_posix() for path in SOURCE_PATHS
        } for property in sbom["metadata"]["properties"] if property["name"].startswith("m8:source-sha256:")))
        for expected in (
            "application:@openai/codex@0.144.6",
            "application:@anthropic-ai/claude-code@2.1.217",
            "application:node@24.16.0",
            "application:python@3.12.13",
            "application:headroom-ai[mcp,proxy,code]@0.32.1",
            "container:ghcr.io/chopratejas/headroom@code-nonroot",
            "container:ghcr.io/devcontainers/features/node:2@2.0.0",
            "container:docker.io/library/python@3.12.13-slim-bookworm",
            "application:actions/checkout@v4.2.2",
            "application:actions/setup-python@v5.6.0",
            "library:ruff@0.15.22",
            "library:cryptography@49.0.0",
            "library:cffi@2.1.0",
            "library:pycparser@3.0",
        ):
            self.assertIn(expected, components)
        by_reference = {component["bom-ref"]: component for component in sbom["components"]}
        self.assertEqual(
            by_reference["container:ghcr.io/chopratejas/headroom@code-nonroot"]["hashes"][0]["content"],
            "71f3a36be1ca232c96714fbff679fb3b5c7e6970a81b52acb3f0a45328bd2c41",
        )
        self.assertEqual(
            next(
                property["value"]
                for property in by_reference["application:actions/checkout@v4.2.2"]["properties"]
                if property["name"] == "m8:resolved"
            ),
            "11bd71901bbe5b1630ceea73d27597364c9af683",
        )
        for reference in (
            "library:ruff@0.15.22", "library:cryptography@49.0.0",
            "library:cffi@2.1.0", "library:pycparser@3.0",
        ):
            self.assertEqual(
                sum(
                    property == {
                        "name": "m8:source",
                        "value": ".github/workflows/root-tooling.requirements.lock",
                    }
                    for property in by_reference[reference]["properties"]
                ),
                1,
            )

    def test_sbom_is_deterministic_and_schema_valid(self) -> None:
        first = canonical_bytes(ROOT)
        self.assertEqual(first, canonical_bytes(ROOT))
        parsed = json.loads(first)
        self.assertEqual(parsed["bomFormat"], "CycloneDX")
        self.assertEqual(parsed["specVersion"], "1.6")
        self.assertNotIn("timestamp", parsed["metadata"])
        validate_sbom(ROOT)

    def test_sbom_staleness_fails(self) -> None:
        with mock.patch("agent_context.generate_root_sbom.canonical_bytes", return_value=b"drift\n"):
            with self.assertRaisesRegex(SbomError, "stale"):
                validate_sbom(ROOT)


if __name__ == "__main__":
    unittest.main()
