"""Verify the reviewed, reproducible Phase 7.5 preferred-budget baseline."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context.measure_w4_context import build_report


BASELINE_PATH = Path("scripts/agent_context/fixtures/w7-preferred-budget-baseline.json")
PROMOTION_FIXTURE_IDS = (
    "sdk-implementation",
    "worker-environment",
    "astro-host-implementation",
    "astro-plugin-implementation",
)


class BudgetPromotionError(ValueError):
    """Raised when the promotion evidence is missing, stale, or over budget."""


def _fail(message: str) -> None:
    raise BudgetPromotionError(message)


def _record_snapshot(record: Mapping[str, Any]) -> dict[str, Any]:
    native = record.get("baseline_native_evidence")
    visibility = record.get("manifest_visibility")
    raw = record.get("raw_injected_content")
    hashes = record.get("hashes")
    if not all(isinstance(value, Mapping) for value in (native, visibility, raw, hashes)):
        _fail(f"promotion fixture {record.get('fixture_id')!r} lacks exact accounting evidence")
    entries = visibility.get("entries")
    source_hashes = raw.get("source_hashes")
    if not isinstance(entries, list) or not isinstance(source_hashes, list):
        _fail(f"promotion fixture {record['fixture_id']} has malformed source evidence")
    return {
        "fixture_id": record["fixture_id"],
        "native": {
            "path": native["path"], "bytes": native["bytes"], "sha256": native["sha256"],
        },
        "policy_paths": [entry["path"] for entry in entries],
        "source_hashes": [
            {"path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"]}
            for item in source_hashes
        ],
        "manifest_sha256": hashes["manifest_sha256"],
        "envelope_sha256": hashes["envelope_sha256"],
        "raw_injected_source_bytes": raw["bytes"],
        "serialized_injected_envelope_bytes": record["serialized_injected_envelope_bytes"],
        "model_visible_total": record["model_visible_total"],
        "preferred_ceiling": record["preferred_ceiling"],
        "effective_hard_limit": record["effective_hard_limit"],
    }


def report_snapshot(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return the complete reproducibility identity, excluding capture time."""
    records = {item.get("fixture_id"): item for item in report.get("codex_records", [])}
    if set(PROMOTION_FIXTURE_IDS) - set(records):
        _fail("promotion fixture set is incomplete")
    selected = [records[fixture_id] for fixture_id in PROMOTION_FIXTURE_IDS]
    return {
        "schema_version": 1,
        "measurement_formula": report["measurement_formula"],
        "capability_evidence": report["capability_evidence"],
        "baseline_evidence": report["baseline_evidence"],
        "fixtures": [_record_snapshot(record) for record in selected],
    }


def _validate_limits(snapshot: Mapping[str, Any], *, enforce_preferred: bool) -> None:
    fixtures = snapshot.get("fixtures")
    if not isinstance(fixtures, list) or [item.get("fixture_id") for item in fixtures] != list(PROMOTION_FIXTURE_IDS):
        _fail("promotion baseline fixture order or identity is invalid")
    for fixture in fixtures:
        total = fixture.get("model_visible_total")
        preferred = fixture.get("preferred_ceiling")
        hard = fixture.get("effective_hard_limit")
        if not all(isinstance(value, int) for value in (total, preferred, hard)):
            _fail(f"promotion fixture {fixture.get('fixture_id')!r} has non-integer limits")
        if total > hard:
            _fail(f"hard context budget overflow in {fixture['fixture_id']}")
        if enforce_preferred and total > preferred:
            _fail(f"preferred context budget overflow in {fixture['fixture_id']}")


def _validate_report_results(report: Mapping[str, Any]) -> None:
    records = {item.get("fixture_id"): item for item in report.get("codex_records", [])}
    for fixture_id in PROMOTION_FIXTURE_IDS:
        record = records.get(fixture_id)
        if not isinstance(record, Mapping) or record.get("result") != "PASS":
            _fail(f"promotion fixture {fixture_id} did not pass")


def load_baseline(root: Path) -> dict[str, Any]:
    path = root / BASELINE_PATH
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(f"cannot read reviewed preferred-budget baseline: {error}")
    if not isinstance(value, dict):
        _fail("reviewed preferred-budget baseline must be a JSON object")
    return value


def verify(root: Path, *, enforce_preferred: bool) -> dict[str, Any]:
    """Perform two independent deterministic runs and compare reviewed evidence."""
    first_report = build_report(root, "1970-01-01T00:00:00Z")
    second_report = build_report(root, "1970-01-02T00:00:00Z")
    _validate_report_results(first_report)
    _validate_report_results(second_report)
    first = report_snapshot(first_report)
    second = report_snapshot(second_report)
    if first != second:
        _fail("independent rerun changed fixture paths, hashes, or byte accounting")
    baseline = load_baseline(root)
    if baseline != first:
        _fail("current clean-checkout measurement does not match the reviewed baseline")
    _validate_limits(first, enforce_preferred=enforce_preferred)
    return first


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the Phase 7.5 preferred-budget promotion gate.")
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--enforce-preferred", action="store_true")
    args = parser.parse_args(argv)
    try:
        snapshot = verify(args.workspace.resolve(), enforce_preferred=args.enforce_preferred)
    except BudgetPromotionError as error:
        print(f"preferred-budget promotion failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(snapshot, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
