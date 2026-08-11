"""Unit tests for the reparto declared-contract vs served-surface leg.

The discrimination that matters is the ``S2-08``/``S2-09`` case: a synthetic
workspace whose plugin declares ``DELETE`` on an item path the service serves
only as ``PATCH`` + ``POST …/retire`` must fail here. Two tests below build
exactly that state.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.conformance import ConformanceError
from scripts.conformance.reparto_contract_surface import (
    PLUGIN_CONTRACT_SOURCE,
    SERVED_SURFACE_ARTIFACT,
    parse_declared_contract,
    run_reparto_contract_surface,
    workspace_root,
)

ACTIVITY_ITEM = "/assignment-processes/{process_id}/teaching-activities/{activity_id}"
CELL_ITEM = "/assignment-processes/{process_id}/group-subjects/{group_subject_id}"


def contract_source(entries: str, version: str = "reparto-docente-m8@2.0.0") -> str:
    """Return a minimal ``compatibility.ts`` carrying *entries*."""
    return (
        f'export const REPARTO_CONTRACT_VERSION = "{version}";\n\n'
        "export type RepartoContractOperation = {\n"
        "  readonly method: RepartoContractMethod;\n"
        "  readonly path: string;\n"
        "};\n\n"
        "export const REPARTO_CONTRACT_OPERATIONS = {\n"
        f"{entries}"
        "} as const satisfies Record<string, RepartoContractOperation>;\n"
    )


def entry(name: str, method: str, path: str) -> str:
    return (
        f'  "{name}": {{\n'
        f'    method: "{method}",\n'
        f'    path: "{path}",\n'
        f'    response: "Whatever"\n'
        "  },\n"
    )


class SyntheticWorkspace:
    """A workspace-shaped tree holding only the two files the leg reads."""

    def __init__(self, contract_text: str, served_operations: list[str]) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        plugin = self.root / PLUGIN_CONTRACT_SOURCE
        plugin.parent.mkdir(parents=True, exist_ok=True)
        plugin.write_text(contract_text, encoding="utf-8")
        surface = self.root / SERVED_SURFACE_ARTIFACT
        surface.parent.mkdir(parents=True, exist_ok=True)
        surface.write_text(
            json.dumps(
                {
                    "contract": "reparto-docente-m8@2.0.0",
                    "api_prefix": "/reparto",
                    "operations": sorted(served_operations),
                }
            ),
            encoding="utf-8",
        )

    def cleanup(self) -> None:
        self._tmp.cleanup()


SERVED_RETIRE_ONLY = [
    f"GET /reparto{ACTIVITY_ITEM}",
    f"PATCH /reparto{ACTIVITY_ITEM}",
    f"POST /reparto{ACTIVITY_ITEM}/retire",
    f"GET /reparto{CELL_ITEM}",
    f"PATCH /reparto{CELL_ITEM}",
    f"POST /reparto{CELL_ITEM}/retire",
]


class ParseDeclaredContractTests(unittest.TestCase):
    def test_reads_version_and_entries(self) -> None:
        text = contract_source(
            entry("teachingActivities.get", "GET", ACTIVITY_ITEM)
            + entry("teachingActivities.retire", "POST", f"{ACTIVITY_ITEM}/retire")
        )
        version, operations = parse_declared_contract(text)
        self.assertEqual(version, "reparto-docente-m8@2.0.0")
        self.assertEqual(
            operations,
            {
                "teachingActivities.get": ("GET", ACTIVITY_ITEM),
                "teachingActivities.retire": ("POST", f"{ACTIVITY_ITEM}/retire"),
            },
        )

    def test_joins_a_path_split_across_string_literals(self) -> None:
        """Prettier wraps long paths; the parser must still see the whole path."""
        text = contract_source(
            '  "groupSubjects.retire": {\n'
            '    method: "POST",\n'
            "    path:\n"
            f'      "{CELL_ITEM}/retire",\n'
            '    response: "GroupSubjectPublic"\n'
            "  },\n"
        )
        _, operations = parse_declared_contract(text)
        self.assertEqual(
            operations["groupSubjects.retire"], ("POST", f"{CELL_ITEM}/retire")
        )

    def test_missing_version_fails_closed(self) -> None:
        with self.assertRaises(ConformanceError):
            parse_declared_contract("export const NOTHING = 1;\n")

    def test_an_entry_the_parser_cannot_read_fails_closed(self) -> None:
        """A silently shrinking swept set is the failure mode to avoid."""
        text = contract_source(
            entry("teachingActivities.get", "GET", ACTIVITY_ITEM)
            + '  "teachingActivities.weird": {\n'
            '    method: "POST",\n'
            "    path: buildPath(),\n"
            "  },\n"
        )
        with self.assertRaises(ConformanceError):
            parse_declared_contract(text)


class RunAgainstSyntheticWorkspaceTests(unittest.TestCase):
    def run_leg(self, contract_text: str, served: list[str]) -> dict[str, bool]:
        workspace = SyntheticWorkspace(contract_text, served)
        self.addCleanup(workspace.cleanup)
        return {r.name: r.passed for r in run_reparto_contract_surface(workspace.root)}

    def test_declared_retire_against_served_retire_passes(self) -> None:
        outcome = self.run_leg(
            contract_source(
                entry("teachingActivities.retire", "POST", f"{ACTIVITY_ITEM}/retire")
                + entry("groupSubjects.retire", "POST", f"{CELL_ITEM}/retire")
            ),
            SERVED_RETIRE_ONLY,
        )
        self.assertTrue(all(outcome.values()), outcome)

    def test_the_s2_08_defect_fails(self) -> None:
        """The plugin state that shipped green: ``DELETE`` on the activity item."""
        outcome = self.run_leg(
            contract_source(
                entry("teachingActivities.remove", "DELETE", ACTIVITY_ITEM)
            ),
            SERVED_RETIRE_ONLY,
        )
        self.assertFalse(outcome["reparto.every_declared_operation_is_served"])
        self.assertFalse(outcome["reparto.withdrawn_delete_absent_from_both_sides"])

    def test_the_s2_09_defect_fails(self) -> None:
        """The latent half: ``DELETE`` on the group-subject cell item."""
        outcome = self.run_leg(
            contract_source(entry("groupSubjects.remove", "DELETE", CELL_ITEM)),
            SERVED_RETIRE_ONLY,
        )
        self.assertFalse(outcome["reparto.every_declared_operation_is_served"])
        self.assertFalse(outcome["reparto.withdrawn_delete_absent_from_both_sides"])

    def test_a_path_typo_fails_even_when_the_verb_is_right(self) -> None:
        outcome = self.run_leg(
            contract_source(
                entry("teachingActivities.retire", "POST", f"{ACTIVITY_ITEM}/retired")
            ),
            SERVED_RETIRE_ONLY,
        )
        self.assertFalse(outcome["reparto.every_declared_operation_is_served"])

    def test_a_contract_version_split_fails(self) -> None:
        outcome = self.run_leg(
            contract_source(
                entry("teachingActivities.retire", "POST", f"{ACTIVITY_ITEM}/retire"),
                version="reparto-docente-m8@1.0.0",
            ),
            SERVED_RETIRE_ONLY,
        )
        self.assertFalse(outcome["reparto.contract_version_matches_service"])

    def test_a_missing_retire_on_the_served_side_fails(self) -> None:
        outcome = self.run_leg(
            contract_source(
                entry("teachingActivities.retire", "POST", f"{ACTIVITY_ITEM}/retire")
            ),
            [f"POST /reparto{ACTIVITY_ITEM}/retire"],
        )
        self.assertFalse(outcome["reparto.retire_actions_served"])

    def test_a_missing_plugin_checkout_fails_closed(self) -> None:
        with (
            tempfile.TemporaryDirectory() as empty,
            self.assertRaises(ConformanceError),
        ):
            run_reparto_contract_surface(Path(empty))

    def test_a_missing_served_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / PLUGIN_CONTRACT_SOURCE
            plugin.parent.mkdir(parents=True, exist_ok=True)
            plugin.write_text(
                contract_source(entry("x.get", "GET", "/x")), encoding="utf-8"
            )
            with self.assertRaises(ConformanceError):
                run_reparto_contract_surface(root)


class RunAgainstTheWorkspaceTests(unittest.TestCase):
    """The real seam, when both children are checked out beside the root."""

    def setUp(self) -> None:
        root = workspace_root()
        for required in (PLUGIN_CONTRACT_SOURCE, SERVED_SURFACE_ARTIFACT):
            if not (root / required).exists():
                self.skipTest(f"{required.as_posix()} is not checked out")
        self.results = run_reparto_contract_surface(root)

    def test_all_checks_pass(self) -> None:
        failures = [f"{r.name}: {r.detail}" for r in self.results if not r.passed]
        self.assertEqual(failures, [], f"reparto contract-surface failures: {failures}")

    def test_expected_named_checks_present(self) -> None:
        names = {r.name for r in self.results}
        for required in (
            "reparto.contract_version_matches_service",
            "reparto.declared_operations_parsed",
            "reparto.every_declared_operation_is_served",
            "reparto.withdrawn_delete_absent_from_both_sides",
            "reparto.retire_actions_served",
        ):
            self.assertIn(required, names)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
