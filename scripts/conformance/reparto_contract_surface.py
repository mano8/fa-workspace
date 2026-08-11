"""Declared consumer contract vs served route surface (``reparto`` seam).

Realises check (b) of the *"Close the gate gap that let ``S2-01``…``S2-09`` ship
green"* bullet in
``.workspace/plans/docentes/todo/2026-07-14-three-stage-adaptation.md`` §13.2a:

    every ``compatibility.ts`` entry's method and path is asserted against the
    served ``openapi.json`` in the conformance harness — this alone catches
    ``S2-08`` and ``S2-09``.

``astro-reparto-m8/src/runtime/compatibility.ts`` is the plugin's own statement
of the backend contract. Nothing compared it with the backend, so the plugin
declared — and called — ``DELETE`` on two endpoints the service had already
replaced with the §20.12 guarded ``retire`` action, while a conformance harness
that only compared *versions* reported the seam as aligned.

Both sides are read as **files**, never imported: the plugin is a TypeScript
package and ``reparto-docente-m8`` is a service, so importing it would breach
``ARCH-LAYER-DIRECTION`` and the no-cross-service-source-import rule in
``policies/tasks/cross-repository.md``. This mirrors how
:mod:`scripts.conformance.local_package_matrix` treats the issuer.

The served side is
``reparto-docente-m8/docs/served-api-surface.json``: the service's own tracked
artifact, generated from ``app.openapi()`` and kept honest inside that
repository by ``tests/test_served_api_surface.py``, which regenerates it on
every run and fails on drift. A snapshot is what makes the comparison possible
at all — a document that only exists on a running instance cannot gate a
consumer's pull request — and the service, not this harness, owns keeping it
true.

Direction of the assertion: every operation the **plugin declares** must be
served. The reverse is deliberately not required — a service may serve more than
any one consumer uses, and demanding full coverage would turn every new backend
route into a plugin failure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.conformance import CheckResult, ConformanceError

#: Consumer-side declaration, relative to the workspace root.
PLUGIN_CONTRACT_SOURCE = (
    Path("astro-reparto-m8") / "src" / "runtime" / "compatibility.ts"
)

#: Service-side served surface, relative to the workspace root.
SERVED_SURFACE_ARTIFACT = (
    Path("reparto-docente-m8") / "docs" / "served-api-surface.json"
)

#: The pair that motivated this check (``S2-08``/``S2-09``). Named explicitly so
#: the regression has a check of its own rather than only being covered by the
#: sweep, and so the failure message says what was withdrawn and what replaced
#: it.
WITHDRAWN_DELETE_ITEM_PATHS = (
    "/assignment-processes/{process_id}/teaching-activities/{activity_id}",
    "/assignment-processes/{process_id}/group-subjects/{group_subject_id}",
)

_VERSION_PATTERN = re.compile(
    r"REPARTO_CONTRACT_VERSION\s*=\s*[\"']([^\"']+)[\"']",
)

#: One ``"name": { method: "M", path: "…" }`` entry. The path is matched as one
#: or more adjacent string literals because prettier wraps a long path onto its
#: own line and may split it; joining the literals is exactly what TypeScript
#: does.
_OPERATION_PATTERN = re.compile(
    r"[\"']([A-Za-z0-9_.]+)[\"']\s*:\s*\{\s*"
    r"method\s*:\s*[\"']([A-Z]+)[\"']\s*,\s*"
    r"path\s*:\s*((?:[\"'][^\"']*[\"']\s*\+?\s*)+),",
)

#: Structural entry marker used to prove the parse above is complete.
_ENTRY_MARKER = re.compile(r"^\s{4}method\s*:\s*[\"'][A-Z]+[\"']\s*,", re.MULTILINE)

_STRING_LITERAL = re.compile(r"[\"']([^\"']*)[\"']")


def workspace_root() -> Path:
    """Return the workspace root (three levels up from this module)."""
    return Path(__file__).resolve().parents[2]


def parse_declared_contract(text: str) -> tuple[str, dict[str, tuple[str, str]]]:
    """Return ``(contract_version, {operation: (method, path)})`` from the source.

    Raises:
        ConformanceError: if the contract version is absent, or if the number of
            parsed entries disagrees with the number of entry markers in the
            file. The second case is the important one: a formatting change this
            parser does not understand would otherwise silently shrink the swept
            set and report green on an unchecked contract.
    """
    version_match = _VERSION_PATTERN.search(text)
    if not version_match:
        raise ConformanceError(
            f"no REPARTO_CONTRACT_VERSION in {PLUGIN_CONTRACT_SOURCE.as_posix()}"
        )

    operations: dict[str, tuple[str, str]] = {}
    for name, method, path_expression in _OPERATION_PATTERN.findall(text):
        operations[name] = (method, "".join(_STRING_LITERAL.findall(path_expression)))

    declared_entries = len(_ENTRY_MARKER.findall(text))
    if len(operations) != declared_entries:
        raise ConformanceError(
            f"parsed {len(operations)} operations from "
            f"{PLUGIN_CONTRACT_SOURCE.as_posix()} but the file declares "
            f"{declared_entries}; the contract table's formatting changed and "
            "this parser no longer sees all of it"
        )
    return version_match.group(1), operations


def load_served_surface(path: Path) -> dict[str, object]:
    """Load the service's tracked served-surface artifact.

    Raises:
        ConformanceError: if the artifact is missing or lacks a required key.
    """
    if not path.exists():
        raise ConformanceError(
            f"{path} is missing; reparto-docente-m8 publishes it from "
            "app.openapi() (tests/test_served_api_surface.py)"
        )
    surface = json.loads(path.read_text(encoding="utf-8"))
    for key in ("contract", "api_prefix", "operations"):
        if key not in surface:
            raise ConformanceError(f"{path} has no {key!r} key")
    return surface


def run_reparto_contract_surface(root: Path | None = None) -> list[CheckResult]:
    """Assert the plugin's declared contract against the served surface.

    Returns one :class:`CheckResult` per assertion. Raises
    :class:`ConformanceError` only on a structural problem (a missing or
    unparseable source of truth); ordinary expectation failures are reported as
    failed results so the whole seam is always visible in one run.
    """
    root = root or workspace_root()
    contract_source = root / PLUGIN_CONTRACT_SOURCE
    if not contract_source.exists():
        raise ConformanceError(
            f"{contract_source} is missing; the plugin checkout is required "
            "for the reparto contract-surface leg"
        )

    declared_version, declared = parse_declared_contract(
        contract_source.read_text(encoding="utf-8")
    )
    surface = load_served_surface(root / SERVED_SURFACE_ARTIFACT)
    served_contract = str(surface["contract"])
    prefix = str(surface["api_prefix"])
    served: set[str] = set(surface["operations"])  # type: ignore[arg-type]

    results = [
        CheckResult(
            "reparto.contract_version_matches_service",
            declared_version == served_contract,
            f"plugin declares {declared_version}; service serves {served_contract}",
        ),
        CheckResult(
            "reparto.declared_operations_parsed",
            bool(declared),
            f"{len(declared)} operations declared in "
            f"{PLUGIN_CONTRACT_SOURCE.as_posix()}",
        ),
    ]

    unserved = sorted(
        f"{name} ({method} {prefix}{path})"
        for name, (method, path) in declared.items()
        if f"{method} {prefix}{path}" not in served
    )
    results.append(
        CheckResult(
            "reparto.every_declared_operation_is_served",
            not unserved,
            (f"all {len(declared)} declared operations are served under {prefix}")
            if not unserved
            else f"declared but not served: {', '.join(unserved)}",
        )
    )

    # S2-08 / S2-09 as a named regression: the withdrawn verb must be gone from
    # both sides, and the action that replaced it present on both.
    declared_pairs = {(method, path) for method, path in declared.values()}
    withdrawn = sorted(
        f"DELETE {prefix}{item}"
        for item in WITHDRAWN_DELETE_ITEM_PATHS
        if ("DELETE", item) in declared_pairs or f"DELETE {prefix}{item}" in served
    )
    results.append(
        CheckResult(
            "reparto.withdrawn_delete_absent_from_both_sides",
            not withdrawn,
            "neither side exposes the withdrawn item DELETE (§20.12)"
            if not withdrawn
            else f"withdrawn DELETE still present: {', '.join(withdrawn)}",
        )
    )
    missing_retire = sorted(
        f"POST {prefix}{item}/retire"
        for item in WITHDRAWN_DELETE_ITEM_PATHS
        if f"POST {prefix}{item}/retire" not in served
    )
    results.append(
        CheckResult(
            "reparto.retire_actions_served",
            not missing_retire,
            "both §20.12 retire actions are served"
            if not missing_retire
            else f"not served: {', '.join(missing_retire)}",
        )
    )
    return results
