"""Phase 4.6 context measurement for the active faceted workspace policies.

The report deliberately separates verified client-native bootstrap bytes from
the JCS envelope used for injected policy units.  It never adds raw injected
source bytes to the model-visible total a second time and it never writes raw
model input or policy content to the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context import w2b1
from agent_context.resolve_context import ResolutionRequest, resolve_context


CAPABILITY_ROW = {
    "agent": "codex",
    "platform": "devcontainer",
    "mode": "non-interactive",
    "status": "REQUIRED",
    "inspection_mechanism": "codex debug prompt-input",
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
CAPABILITY_EVIDENCE = (
    ".workspace/status/fa-workspace/"
    "agent-configuration-token-efficiency-capability-evidence-2026-07-19.md"
)
BASELINE_EVIDENCE = (
    ".workspace/status/fa-workspace/"
    "agent-configuration-token-efficiency-capability-evidence-2026-07-18.md"
)
FIXTURE_CATALOG = (
    ".workspace/status/fa-workspace/"
    "agent-configuration-token-efficiency-budgets-and-fixtures-2026-07-18.json"
)
NATIVE_EVIDENCE = (
    ".workspace/status/fa-workspace/"
    "agent-configuration-token-efficiency-w4-native-evidence-2026-07-19.json"
)
SOURCE_SHA = "a" * 64


def _load_json(path: Path) -> dict[str, Any]:
    value = w2b1.parse_strict_json(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_set(root: Path, metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"path": unit["path"], "sha256": _sha256(root / unit["path"])}
        for unit in sorted(metadata["units"], key=lambda item: item["path"])
    ]


def _replacement_gates(root: Path) -> dict[str, dict[str, int | str]]:
    """Derive gates from the reproducible Step 0.6 baseline, never W0 history."""
    text = (root / BASELINE_EVIDENCE).read_text(encoding="utf-8")
    values: dict[str, int] = {}
    for repository in ("auth-sdk-m8", "astro-auth-m8"):
        match = re.search(
            rf"\| `{re.escape(repository)}:implementation` \| ([0-9,]+) \|",
            text,
        )
        if match is None:
            raise ValueError(f"Step 0.6 baseline is missing {repository}")
        values[repository] = int(match.group(1).replace(",", ""))
    return {
        "auth-sdk-implementation-target": {
            "baseline_fixture": "auth-sdk-m8:implementation",
            "baseline_bytes": values["auth-sdk-m8"],
            "maximum_bytes": values["auth-sdk-m8"] * 65 // 100,
            "derivation": "floor(reproduced Step 0.6 baseline * 0.65)",
        },
        "astro-plugin-implementation-target": {
            "baseline_fixture": "astro-auth-m8:implementation",
            "baseline_bytes": values["astro-auth-m8"],
            "maximum_bytes": values["astro-auth-m8"] * 65 // 100,
            "derivation": "floor(reproduced Step 0.6 baseline * 0.65)",
        },
    }


def _native_bootstrap(root: Path) -> dict[str, Any]:
    evidence = _load_json(root / NATIVE_EVIDENCE)
    source = evidence.get("source")
    if evidence.get("status") != "VERIFIED_CURRENT" or not isinstance(source, dict):
        raise ValueError("current native evidence is not verified")
    path = source.get("path")
    if not isinstance(path, str) or _sha256(root / path) != source.get("source_sha256"):
        raise ValueError("native source hash no longer matches current evidence")
    if len((root / path).read_bytes()) != source.get("source_bytes"):
        raise ValueError("native source byte count no longer matches current evidence")
    if source.get("exact_source_substring_occurrences") != 1:
        raise ValueError("native evidence must show one exact source occurrence")
    return {
        "path": path,
        "bytes": source["source_bytes"],
        "sha256": source["source_sha256"],
        "evidence_path": NATIVE_EVIDENCE,
        "evidence_sha256": _sha256(root / NATIVE_EVIDENCE),
        "inspection_mechanism": evidence["inspection_mechanism"],
    }


def _task_request(fixture: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    task = fixture["task"]
    if task in {"implementation", "environment"}:
        return (() if task == "implementation" else (task,), ())
    return ((task,), (task,))


def _unmeasured(fixture: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "fixture_id": fixture["fixture_id"],
        "agent": "codex",
        "capability_status": "REQUIRED",
        "result": "NOT_MEASURED",
        "reason": reason,
        "baseline_native_evidence": None,
        "manifest_visibility": None,
        "raw_injected_content": None,
        "serialized_injected_envelope_bytes": None,
        "serialization_overhead_bytes": None,
        "other_model_visible_bootstrap_bytes": None,
        "model_visible_total": None,
        "estimated_tokens": None,
        "excluded_receipts_session_global_layers": [
            "receipts", "session state", "global client instructions"
        ],
        "hashes": None,
        "policy_ceiling": 32768,
        "preferred_ceiling": 24576,
        "channel_client_allowance": None,
        "verified_channel_limit": None,
        "reserved_margin": None,
        "effective_hard_limit": None,
        "gate": None,
    }


def _measured(
    *, root: Path, fixture: Mapping[str, Any], registry: Mapping[str, Any],
    index: Mapping[str, Any], metadata: Mapping[str, Any], native: Mapping[str, Any],
    gates: Mapping[str, Mapping[str, int | str]], source_set: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    tasks, operations = _task_request(fixture)
    repository = fixture["owner_repository"]
    resolved = resolve_context(
        ResolutionRequest(
            root=root,
            registry=registry,
            policy_index=index,
            policy_metadata=metadata,
            capability_row=CAPABILITY_ROW,
            reviewed_tree={"algorithm": "git-sha1", "value": "b" * 40},
            agent="codex",
            platform="devcontainer",
            mode="non-interactive",
            repositories=(repository,),
            tasks=tasks,
            operations=operations,
            injection_evidence={
                "generation": 0,
                "native_discovery_disabled": True,
                "exact_once_handoff_proven": True,
                "sources": list(source_set),
            },
        )
    )
    accounting = resolved.manifest["accounting"]
    total = native["bytes"] + accounting["serialized_injected_envelope_bytes"]
    gate = gates.get(fixture.get("budget_id"))
    gate_result = None
    if gate is not None:
        gate_result = {
            "maximum_bytes": gate["maximum_bytes"],
            "within_gate": total <= gate["maximum_bytes"],
            "reduction_percent": round(
                (1 - total / gate["baseline_bytes"]) * 100, 2
            ),
            "derivation": gate["derivation"],
        }
    result = "PASS"
    if total > accounting["effective_hard_limit"]:
        result = "FAIL_HARD_LIMIT"
    elif total > index["budgets"]["preferred_bytes"]:
        result = "PASS_PREFERRED_WARNING"
    return {
        "fixture_id": fixture["fixture_id"],
        "agent": "codex",
        "capability_status": "REQUIRED",
        "result": result,
        "semantic_pass": True,
        "baseline_native_evidence": native,
        "manifest_visibility": {
            "entries": [
                {"policy_id": entry["policy_id"], "path": entry["path"], "delivery": entry["delivery"]}
                for entry in resolved.manifest["entries"]
            ],
            "manifest_sha256": resolved.manifest["manifest_id"],
            "envelope_sha256": resolved.envelope_sha256,
        },
        "raw_injected_content": {
            "bytes": accounting["raw_injected_source_bytes"],
            "source_hashes": [
                {"path": entry["path"], "sha256": entry["source_sha256"], "bytes": entry["source_bytes"]}
                for entry in resolved.manifest["entries"]
                if entry["delivery"] == "inject"
            ],
            "not_added_to_model_visible_total": True,
        },
        "serialized_injected_envelope_bytes": accounting["serialized_injected_envelope_bytes"],
        "serialization_overhead_bytes": accounting["serialization_overhead_bytes"],
        "other_model_visible_bootstrap_bytes": 0,
        "model_visible_total": total,
        "estimated_tokens": (total + 3) // 4,
        "excluded_receipts_session_global_layers": [
            "receipts", "session state", "global client instructions"
        ],
        "hashes": {
            "native_source_sha256": native["sha256"],
            "manifest_sha256": resolved.manifest["manifest_id"],
            "envelope_sha256": resolved.envelope_sha256,
        },
        "policy_ceiling": index["budgets"]["hard_bytes"],
        "preferred_ceiling": index["budgets"]["preferred_bytes"],
        "channel_client_allowance": CAPABILITY_ROW["client_context_allowance"],
        "verified_channel_limit": CAPABILITY_ROW["verified_channel_limit"],
        "reserved_margin": CAPABILITY_ROW["reserved_margin"],
        "effective_hard_limit": accounting["effective_hard_limit"],
        "gate": gate_result,
    }


def build_report(root: Path, captured_at: str) -> dict[str, Any]:
    registry = _load_json(root / ".workspace/repo-types.json")
    index = _load_json(root / ".workspace/policy.index.json")
    metadata = _load_json(root / ".workspace/policy.metadata.json")
    catalog = _load_json(root / FIXTURE_CATALOG)
    native = _native_bootstrap(root)
    gates = _replacement_gates(root)
    source_set = _source_set(root, metadata)
    records: list[dict[str, Any]] = []
    for fixture in catalog["fixtures"]:
        if fixture["mode"] == "standalone":
            records.append(_unmeasured(fixture, "child-owned standalone context is outside workspace-controlled measurement"))
        elif fixture["lifecycle"] != "present":
            records.append(_unmeasured(fixture, "fixture is not an active registered direct-child repository"))
        elif fixture["task"] in {"commit", "release", "cross-repository"}:
            records.append(_unmeasured(fixture, "no explicit human authorization exists to select this mutating or cross-repository overlay"))
        else:
            records.append(_measured(root=root, fixture=fixture, registry=registry, index=index, metadata=metadata, native=native, gates=gates, source_set=source_set))
    claude_records = []
    for fixture in catalog["fixtures"]:
        record = _unmeasured(
            fixture,
            "Claude is authenticated but has no verified native-inspection or exact full-content channel row",
        )
        record["agent"] = "claude"
        record["capability_status"] = "LIMITED"
        claude_records.append(record)
    return {
        "schema_version": 1,
        "phase": "4.6",
        "captured_at": captured_at,
        "status": "PASS_WITH_NONBLOCKING_UNMEASURED_FIXTURES",
        "measurement_formula": "verified_native_bytes + serialized_injected_envelope_bytes + other_model_visible_bootstrap_bytes; raw injected bytes are diagnostic only",
        "capability_evidence": {"path": CAPABILITY_EVIDENCE, "sha256": _sha256(root / CAPABILITY_EVIDENCE)},
        "baseline_evidence": {"path": BASELINE_EVIDENCE, "sha256": _sha256(root / BASELINE_EVIDENCE)},
        "replacement_gates": gates,
        "excluded_layers": ["receipts", "session state", "global client instructions"],
        "codex_records": records,
        "claude_records": claude_records,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure Phase 4.6 workspace-controlled context.")
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--captured-at", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build_report(args.workspace.resolve(), args.captured_at), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
