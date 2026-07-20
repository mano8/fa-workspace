"""Inactive W2b2 scoped context resolver for the active faceted v2 schema.

The resolver reads explicit fixture inputs and produces deterministic manifests
plus injected envelopes. It does not activate a client transport or write
runtime state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from agent_context import w2b1


CAPABILITY_FIELDS = {
    "agent",
    "platform",
    "mode",
    "status",
    "inspection_mechanism",
    "channel_id",
    "verified_channel_limit",
    "client_context_allowance",
    "reserved_margin",
    "start_supported",
    "resume_supported",
    "clear_supported",
    "compact_supported",
    "launcher_identity_available",
    "client_session_identity_available",
    "blocks_closeout",
}
NATIVE_EVIDENCE_FIELDS = {
    "native_evidence_id",
    "agent",
    "platform",
    "mode",
    "client_identity",
    "client_version",
    "config_sha256",
    "capability_evidence_id",
    "trust_state",
    "inspection_mechanism",
    "captured_at",
    "sources",
}
AUTHORIZATION_FIELDS = {
    "authorization_id",
    "kind",
    "authorized_by",
    "source_ref",
    "source_sha256",
    "repositories",
    "operations",
    "issued_at",
}
INJECTION_EVIDENCE_FIELDS = {
    "generation",
    "native_discovery_disabled",
    "exact_once_handoff_proven",
    "sources",
}
TIER_ORDER = {"security": 0, "workspace": 1, "task": 2, "repository": 3}


@dataclass(frozen=True)
class ResolutionRequest:
    """Explicit inputs for one non-activating W2b2 resolution."""

    root: Path
    registry: Mapping[str, Any]
    policy_index: Mapping[str, Any]
    policy_metadata: Mapping[str, Any]
    capability_row: Mapping[str, Any]
    reviewed_tree: Mapping[str, Any]
    agent: str
    platform: str
    mode: str
    repositories: tuple[str, ...] = ()
    tasks: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    authorizations: tuple[Mapping[str, Any], ...] = ()
    native_evidence: Mapping[str, Any] | None = None
    injection_evidence: Mapping[str, Any] | None = None
    other_model_visible_bootstrap_bytes: int = 0
    generation: int = 0


@dataclass(frozen=True)
class ResolvedContext:
    """Canonical resolver outputs, held in memory by this inactive step."""

    manifest: dict[str, Any]
    envelope: dict[str, Any]
    envelope_bytes: bytes
    envelope_sha256: str


def _fail(message: str, code: str) -> NoReturn:
    raise w2b1.AgentContextError(code, message)


def _closed(
    value: Any, fields: set[str], name: str, code: str = "E_SCHEMA"
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{name} must be an object", code)
    actual = set(value)
    if actual != fields:
        _fail(f"{name} fields do not match the frozen shape", code)
    return value


def _identifier(value: Any, field: str, code: str = "E_SCHEMA") -> str:
    try:
        w2b1._identifier(value, field)
    except w2b1.AgentContextError as error:
        _fail(error.message, code)
    return value


def _sha256(value: Any, field: str, code: str = "E_SCHEMA") -> str:
    try:
        w2b1._sha256(value, field)
    except w2b1.AgentContextError as error:
        _fail(error.message, code)
    return value


def _canonical_set(values: Any, field: str, code: str = "E_SCHEMA") -> tuple[str, ...]:
    try:
        w2b1._canonical_set(values, field)
    except w2b1.AgentContextError as error:
        _fail(error.message, code)
    return tuple(values)


def _canonical_input(values: Sequence[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        _fail(f"{field} must be a sequence of identifiers", "E_USAGE")
    result = tuple(sorted(set(values)))
    for value in result:
        _identifier(value, field, "E_USAGE")
    return result


def _read_source(root: Path, path: str) -> bytes:
    try:
        w2b1._canonical_path(path, "policy path")
    except w2b1.AgentContextError as error:
        _fail(error.message, "E_SCOPE_UNAVAILABLE")
    candidate = root.joinpath(*path.split("/"))
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as error:
        _fail(
            f"policy path is missing or escapes root: {path} ({error})",
            "E_SCOPE_UNAVAILABLE",
        )
    if not resolved.is_file():
        _fail(f"policy path is not a regular file: {path}", "E_SOURCE")
    try:
        return resolved.read_bytes()
    except OSError as error:
        _fail(f"could not read policy source {path}: {error}", "E_SOURCE")


def _metadata_catalog(
    value: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], set[str], set[str]]:
    catalog = _closed(value, {"units", "invariants", "capabilities"}, "policy metadata")
    try:
        w2b1._canonical_invariant_set(
            catalog["invariants"], "policy metadata invariants"
        )
    except w2b1.AgentContextError as error:
        _fail(error.message, error.code)
    invariants = set(catalog["invariants"])
    capabilities = set(
        _canonical_set(catalog["capabilities"], "policy metadata capabilities")
    )
    if not isinstance(catalog["units"], list):
        _fail("policy metadata units must be an array", "E_SCHEMA")
    units: dict[str, dict[str, Any]] = {}
    for supplied in catalog["units"]:
        try:
            w2b1.validate_policy_unit(supplied)
        except w2b1.AgentContextError as error:
            _fail(error.message, error.code)
        unit = dict(supplied)
        policy_id = unit["id"]
        if policy_id in units:
            _fail(f"duplicate policy metadata id: {policy_id}", "E_SCHEMA")
        units[policy_id] = unit
    for unit in units.values():
        for invariant in unit["invariant_ids"]:
            if invariant not in invariants:
                _fail(f"unknown invariant target: {invariant}", "E_UNKNOWN_ID")
        for capability in unit["capabilities_granted"]:
            if capability not in capabilities:
                _fail(f"unknown capability target: {capability}", "E_UNKNOWN_ID")
        for field in ("conflicts_with", "may_override"):
            for target in unit[field]:
                if target not in units:
                    _fail(f"unknown {field} target: {target}", "E_UNKNOWN_ID")
    return units, invariants, capabilities


def _validate_registry_scope(
    registry: Mapping[str, Any], units: Mapping[str, Mapping[str, Any]]
) -> dict[str, str]:
    try:
        w2b1.validate_registry_v2(registry)
    except w2b1.AgentContextError as error:
        _fail(error.message, error.code)
    paths = {item["id"]: item["path"] for item in registry["repositories"]}
    for unit in units.values():
        scope = unit["scope"]
        repository_id = scope["repository_id"]
        prefix = scope["prefix"]
        path = unit["path"]
        if repository_id == "$workspace":
            if prefix != ".":
                _fail(
                    "workspace policy scope must use the . prefix",
                    "E_SCOPE_UNAVAILABLE",
                )
            continue
        expected = paths.get(repository_id)
        if expected is None:
            _fail(
                f"policy scope has unknown repository: {repository_id}", "E_UNKNOWN_ID"
            )
        if prefix != expected or not path.startswith(f"{expected}/"):
            _fail(
                f"policy path is outside its repository scope: {unit['id']}",
                "E_SCOPE_UNAVAILABLE",
            )
    return paths


def _validate_capability(row: Mapping[str, Any], request: ResolutionRequest) -> None:
    capability = _closed(row, CAPABILITY_FIELDS, "capability row", "E_CAPABILITY")
    if (
        capability["agent"] != request.agent
        or capability["platform"] != request.platform
    ):
        _fail("capability row does not match requested agent/platform", "E_CAPABILITY")
    if capability["mode"] != request.mode:
        _fail("capability row does not match requested mode", "E_CAPABILITY")
    if capability["status"] != "REQUIRED":
        _fail("selected mode is not a required canonical mode", "E_UNSUPPORTED_MODE")
    if any(
        not isinstance(capability[field], bool)
        for field in CAPABILITY_FIELDS
        if field.endswith("supported")
        or field.endswith("available")
        or field == "blocks_closeout"
    ):
        _fail(
            "capability lifecycle and identity fields must be boolean", "E_CAPABILITY"
        )
    for field in (
        "verified_channel_limit",
        "client_context_allowance",
        "reserved_margin",
    ):
        if (
            not isinstance(capability[field], int)
            or isinstance(capability[field], bool)
            or capability[field] < 0
        ):
            _fail(f"capability {field} must be a non-negative integer", "E_CAPABILITY")
    if not all(
        capability[field]
        for field in (
            "start_supported",
            "resume_supported",
            "clear_supported",
            "launcher_identity_available",
            "client_session_identity_available",
            "blocks_closeout",
        )
    ):
        _fail(
            "required capability row lacks a required lifecycle or identity",
            "E_CAPABILITY",
        )
    if (
        not isinstance(capability["inspection_mechanism"], str)
        or not capability["inspection_mechanism"]
    ):
        _fail("required capability row lacks inspection mechanism", "E_CAPABILITY")
    if not isinstance(capability["channel_id"], str) or not capability["channel_id"]:
        _fail("required capability row lacks channel id", "E_CAPABILITY")


def _validate_native_evidence(
    value: Mapping[str, Any], request: ResolutionRequest
) -> dict[str, str]:
    evidence = _closed(
        value, NATIVE_EVIDENCE_FIELDS, "native evidence", "E_NATIVE_EVIDENCE"
    )
    for field in ("native_evidence_id", "config_sha256", "capability_evidence_id"):
        _sha256(evidence[field], f"native evidence {field}", "E_NATIVE_EVIDENCE")
    if evidence["native_evidence_id"] != w2b1.canonical_sha256(
        {key: item for key, item in evidence.items() if key != "native_evidence_id"}
    ):
        _fail("native evidence id does not match JCS content", "E_NATIVE_EVIDENCE")
    if any(
        evidence[field] != getattr(request, field)
        for field in ("agent", "platform", "mode")
    ):
        _fail("native evidence does not match requested mode", "E_NATIVE_EVIDENCE")
    if evidence["capability_evidence_id"] != _capability_evidence_id(
        request.capability_row
    ):
        _fail("native evidence capability identity is stale", "E_NATIVE_EVIDENCE")
    if evidence["trust_state"] != "trusted" or not isinstance(
        evidence["inspection_mechanism"], str
    ):
        _fail("native evidence lacks trusted inspection", "E_NATIVE_EVIDENCE")
    for field in ("client_identity", "client_version", "inspection_mechanism"):
        if not isinstance(evidence[field], str) or not evidence[field]:
            _fail(f"native evidence {field} is required", "E_NATIVE_EVIDENCE")
    try:
        w2b1._timestamp(evidence["captured_at"], "native evidence captured_at")
    except w2b1.AgentContextError as error:
        _fail(error.message, "E_NATIVE_EVIDENCE")
    if not isinstance(evidence["sources"], list):
        _fail("native evidence sources must be an array", "E_NATIVE_EVIDENCE")
    sources: dict[str, str] = {}
    for source in evidence["sources"]:
        item = _closed(
            source, {"path", "sha256"}, "native evidence source", "E_NATIVE_EVIDENCE"
        )
        path = item["path"]
        try:
            w2b1._canonical_path(path, "native evidence source path")
        except w2b1.AgentContextError as error:
            _fail(error.message, "E_NATIVE_EVIDENCE")
        digest = _sha256(
            item["sha256"], "native evidence source sha256", "E_NATIVE_EVIDENCE"
        )
        if path in sources:
            _fail(f"duplicate native evidence source: {path}", "E_NATIVE_EVIDENCE")
        sources[path] = digest
    if list(sources) != sorted(sources):
        _fail(
            "native evidence sources must be sorted by canonical path",
            "E_NATIVE_EVIDENCE",
        )
    return sources


def _validate_injection_evidence(
    value: Mapping[str, Any], generation: int
) -> dict[str, str]:
    evidence = _closed(
        value, INJECTION_EVIDENCE_FIELDS, "injection evidence", "E_NATIVE_EVIDENCE"
    )
    if evidence["generation"] != generation:
        _fail(
            "injection evidence generation does not match resolver generation",
            "E_NATIVE_EVIDENCE",
        )
    if (
        evidence["native_discovery_disabled"] is not True
        or evidence["exact_once_handoff_proven"] is not True
    ):
        _fail(
            "injection evidence does not prove disabled native discovery and exact-once handoff",
            "E_NATIVE_EVIDENCE",
        )
    if not isinstance(evidence["sources"], list):
        _fail("injection evidence sources must be an array", "E_NATIVE_EVIDENCE")
    sources: dict[str, str] = {}
    for source in evidence["sources"]:
        item = _closed(
            source, {"path", "sha256"}, "injection evidence source", "E_NATIVE_EVIDENCE"
        )
        path = item["path"]
        try:
            w2b1._canonical_path(path, "injection evidence source path")
        except w2b1.AgentContextError as error:
            _fail(error.message, "E_NATIVE_EVIDENCE")
        if path in sources:
            _fail(f"duplicate injection evidence source: {path}", "E_NATIVE_EVIDENCE")
        sources[path] = _sha256(
            item["sha256"], "injection evidence source sha256", "E_NATIVE_EVIDENCE"
        )
    if list(sources) != sorted(sources):
        _fail(
            "injection evidence sources must be sorted by canonical path",
            "E_NATIVE_EVIDENCE",
        )
    return sources


def _capability_evidence_id(row: Mapping[str, Any]) -> str:
    """Derive the frozen evidence identity from the exact capability-row JCS bytes."""
    return w2b1.canonical_sha256(row)


def _selected_policy_ids(
    request: ResolutionRequest,
    registry: Mapping[str, Any],
    units: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    index = request.policy_index
    try:
        w2b1.validate_policy_index_v2(index)
    except w2b1.AgentContextError as error:
        _fail(error.message, error.code)
    if index["mode"] != "faceted":
        _fail(
            "W2b2 resolver requires an explicit faceted v2 policy index",
            "E_SCOPE_UNAVAILABLE",
        )
    selected: list[str] = list(index["always"])
    repositories = _canonical_input(request.repositories, "repository")
    tasks = _canonical_input(request.tasks, "task")
    for repository in repositories:
        matches = [
            item for item in registry["repositories"] if item["id"] == repository
        ]
        if not matches:
            _fail(f"unknown repository: {repository}", "E_UNKNOWN_ID")
        for facet in matches[0]["facets"]:
            if facet not in index["facet_ids"]:
                _fail(f"unknown facet: {facet}", "E_UNKNOWN_ID")
            # A known, evidenced facet may have no shared policy slice.  It is
            # deliberately a no-op rather than an empty policy slice.
            selected.extend(index["facets"].get(facet, ()))
    for task in tasks:
        if task not in index["tasks"]:
            _fail(f"unknown task: {task}", "E_UNKNOWN_ID")
        selected.extend(index["tasks"][task]["policies"])
    for policy_id in selected:
        if policy_id not in units:
            _fail(f"unknown policy unit: {policy_id}", "E_UNKNOWN_ID")
    exclusions = _canonical_input(request.exclusions, "exclusion")
    excluded: set[str] = set()
    for exclusion in exclusions:
        if exclusion not in index["exclusions"]:
            _fail(f"unknown exclusion: {exclusion}", "E_UNKNOWN_ID")
        excluded.update(index["exclusions"][exclusion])
    for policy_id in excluded:
        if policy_id not in units:
            _fail(f"unknown excluded policy unit: {policy_id}", "E_UNKNOWN_ID")
        if units[policy_id]["required"]:
            _fail(
                f"exclusion attempts to remove required policy: {policy_id}",
                "E_AUTHORITY",
            )
    resolved: list[str] = []
    seen: set[str] = set()
    for policy_id in selected:
        if policy_id not in excluded and policy_id not in seen:
            resolved.append(policy_id)
            seen.add(policy_id)
    return tuple(resolved)


def _validate_authority(
    selected: Sequence[str], units: Mapping[str, Mapping[str, Any]]
) -> None:
    selected_set = set(selected)
    for policy_id in selected:
        unit = units[policy_id]
        for target in unit["may_override"]:
            if (
                TIER_ORDER[unit["authority_tier"]]
                > TIER_ORDER[units[target]["authority_tier"]]
            ):
                _fail(f"lower authority cannot override {target}", "E_AUTHORITY")
        for target in unit["conflicts_with"]:
            if target not in selected_set:
                continue
            other = units[target]
            same_tier = unit["authority_tier"] == other["authority_tier"]
            resolved = (
                target in unit["may_override"] or policy_id in other["may_override"]
            )
            if same_tier and not resolved:
                _fail(
                    f"unresolved same-tier policy conflict: {policy_id}/{target}",
                    "E_AUTHORITY",
                )


def _validate_selected_scope(
    selected: Sequence[str],
    units: Mapping[str, Mapping[str, Any]],
    repositories: tuple[str, ...],
) -> None:
    allowed = set(repositories)
    for policy_id in selected:
        repository_id = units[policy_id]["scope"]["repository_id"]
        if repository_id != "$workspace" and repository_id not in allowed:
            _fail(
                f"policy is outside selected repository scope: {policy_id}",
                "E_SCOPE_UNAVAILABLE",
            )


def _validate_authorizations(
    request: ResolutionRequest, tasks: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[dict[str, str], ...]]:
    task_definitions = request.policy_index["tasks"]
    requires_authorization = any(
        task_definitions[task]["authorization"] != "none" for task in tasks
    )
    cross_repository = len(_canonical_input(request.repositories, "repository")) > 1
    if cross_repository and not any(
        task_definitions[task]["authorization"] == "cross-repository" for task in tasks
    ):
        _fail(
            "multiple repositories require a selected cross-repository task",
            "E_AUTHORIZATION",
        )
    if not requires_authorization and not cross_repository:
        if request.authorizations:
            _fail(
                "authorization records require an authorized selected task",
                "E_AUTHORIZATION",
            )
        if request.operations:
            _fail(
                "operation scope requires an authorized selected task",
                "E_AUTHORIZATION",
            )
        return (), ()
    repositories = _canonical_input(request.repositories, "repository")
    operations = _canonical_input(request.operations, "operation")
    mutating_operations = {
        task
        for task in tasks
        if task_definitions[task]["authorization"] == "mutating"
    }
    if not operations:
        _fail(
            "authorized selected tasks require a non-empty operation scope",
            "E_AUTHORIZATION",
        )
    if not mutating_operations.issubset(operations):
        _fail(
            "mutating task operations do not match the selected task set",
            "E_AUTHORIZATION",
        )
    valid_records: dict[str, dict[str, str]] = {}
    for supplied in request.authorizations:
        record = _closed(
            supplied, AUTHORIZATION_FIELDS, "authorization", "E_AUTHORIZATION"
        )
        authorization_id = _identifier(
            record["authorization_id"], "authorization id", "E_AUTHORIZATION"
        )
        if record["kind"] not in {"explicit-user-message", "named-owner-decision"}:
            _fail("authorization kind is invalid", "E_AUTHORIZATION")
        if not isinstance(record["authorized_by"], str) or not record["authorized_by"]:
            _fail("authorization authorized_by is required", "E_AUTHORIZATION")
        if not isinstance(record["source_ref"], str) or not record["source_ref"]:
            _fail("authorization source_ref is required", "E_AUTHORIZATION")
        _sha256(
            record["source_sha256"], "authorization source_sha256", "E_AUTHORIZATION"
        )
        try:
            w2b1._timestamp(record["issued_at"], "authorization issued_at")
        except w2b1.AgentContextError as error:
            _fail(error.message, "E_AUTHORIZATION")
        if (
            _canonical_set(
                record["repositories"], "authorization repositories", "E_AUTHORIZATION"
            )
            != repositories
        ):
            _fail(
                "authorization repository scope does not exactly match",
                "E_AUTHORIZATION",
            )
        if (
            _canonical_set(
                record["operations"], "authorization operations", "E_AUTHORIZATION"
            )
            != operations
        ):
            _fail(
                "authorization operation scope does not exactly match",
                "E_AUTHORIZATION",
            )
        if authorization_id in valid_records:
            _fail(f"duplicate authorization id: {authorization_id}", "E_AUTHORIZATION")
        valid_records[authorization_id] = {
            "authorization_id": authorization_id,
            "authorization_sha256": w2b1.canonical_sha256(record),
            "source_sha256": record["source_sha256"],
        }
    if not valid_records:
        _fail("selected task requires explicit human authorization", "E_AUTHORIZATION")
    ordered_ids = tuple(sorted(valid_records))
    return ordered_ids, tuple(valid_records[item] for item in ordered_ids)


def _manifest_entries(
    request: ResolutionRequest,
    selected: Sequence[str],
    units: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    native_sources = (
        _validate_native_evidence(request.native_evidence, request)
        if request.native_evidence
        else {}
    )
    injection_sources = (
        _validate_injection_evidence(request.injection_evidence, request.generation)
        if request.injection_evidence
        else {}
    )
    native_id = (
        request.native_evidence["native_evidence_id"]
        if request.native_evidence
        else None
    )
    manifest_entries: list[dict[str, Any]] = []
    envelope_entries: list[dict[str, Any]] = []
    native_bytes = 0
    raw_injected_bytes = 0
    for policy_id in selected:
        unit = units[policy_id]
        raw = _read_source(request.root, unit["path"])
        digest = hashlib.sha256(raw).hexdigest()
        native_match = native_sources.get(unit["path"]) == digest
        inject_match = injection_sources.get(unit["path"]) == digest
        if native_match:
            delivery = "native"
            native_evidence_id: str | None = native_id
            native_bytes += len(raw)
        elif inject_match:
            delivery = "inject"
            native_evidence_id = None
            raw_injected_bytes += len(raw)
        else:
            _fail(
                f"source has neither verified native nor exact-once inject evidence: {unit['path']}",
                "E_NATIVE_EVIDENCE",
            )
        manifest_entries.append(
            {
                "policy_id": policy_id,
                "repository_id": unit["scope"]["repository_id"],
                "scope_prefix": unit["scope"]["prefix"],
                "path": unit["path"],
                "delivery": delivery,
                "source_sha256": digest,
                "source_bytes": len(raw),
                "metadata_sha256": w2b1.canonical_sha256(unit),
                "native_evidence_id": native_evidence_id,
            }
        )
        if delivery == "inject":
            envelope_entries.append(
                w2b1.source_entry_from_bytes(
                    raw,
                    {
                        "policy_id": policy_id,
                        "repository_id": unit["scope"]["repository_id"],
                        "scope_prefix": unit["scope"]["prefix"],
                        "path": unit["path"],
                        "authority_tier": unit["authority_tier"],
                    },
                )
            )
    return manifest_entries, envelope_entries, native_bytes, raw_injected_bytes


def resolve_context(request: ResolutionRequest) -> ResolvedContext:
    """Resolve scoped policies deterministically without activating delivery."""
    _validate_capability(request.capability_row, request)
    try:
        w2b1._reviewed_tree(request.reviewed_tree)
    except w2b1.AgentContextError as error:
        _fail(error.message, "E_TRUST")
    units, _, _ = _metadata_catalog(request.policy_metadata)
    _validate_registry_scope(request.registry, units)
    repositories = _canonical_input(request.repositories, "repository")
    tasks = _canonical_input(request.tasks, "task")
    selected = _selected_policy_ids(request, request.registry, units)
    _validate_authority(selected, units)
    _validate_selected_scope(selected, units, repositories)
    authorization_ids, authorization_provenance = _validate_authorizations(
        request, tasks
    )
    operations = _canonical_input(request.operations, "operation")
    entries, injected_entries, native_bytes, raw_injected_bytes = _manifest_entries(
        request, selected, units
    )
    policy_hard_limit = request.policy_index["budgets"]["hard_bytes"]
    row = request.capability_row
    effective_limit = min(
        policy_hard_limit,
        row["verified_channel_limit"],
        row["client_context_allowance"] - row["reserved_margin"],
    )
    if effective_limit < 0:
        _fail("capability allowance is smaller than reserved margin", "E_BUDGET")
    if (
        not isinstance(request.other_model_visible_bootstrap_bytes, int)
        or request.other_model_visible_bootstrap_bytes < 0
    ):
        _fail(
            "other model-visible bootstrap bytes must be a non-negative integer",
            "E_USAGE",
        )
    blank_manifest_id = "0" * 64
    _, provisional_envelope, _ = w2b1.build_envelope(
        manifest_id=blank_manifest_id,
        generation=request.generation,
        entries=injected_entries,
    )
    serialized_envelope_bytes = len(provisional_envelope)
    manifest = {
        "schema_version": 2,
        "manifest_id": blank_manifest_id,
        "reviewed_tree": dict(request.reviewed_tree),
        "agent": request.agent,
        "platform": request.platform,
        "mode": request.mode,
        "capability_evidence_id": _capability_evidence_id(request.capability_row),
        "repositories": list(repositories),
        "tasks": list(tasks),
        "operations": list(operations),
        "authorization_ids": list(authorization_ids),
        "authorization_provenance": list(authorization_provenance),
        "entries": entries,
        "accounting": {
            "policy_hard_limit": policy_hard_limit,
            "verified_channel_limit": row["verified_channel_limit"],
            "client_context_allowance": row["client_context_allowance"],
            "reserved_margin": row["reserved_margin"],
            "effective_hard_limit": effective_limit,
            "native_model_visible_bytes": native_bytes,
            "serialized_injected_envelope_bytes": serialized_envelope_bytes,
            "other_model_visible_bootstrap_bytes": request.other_model_visible_bootstrap_bytes,
            "model_visible_total": native_bytes
            + serialized_envelope_bytes
            + request.other_model_visible_bootstrap_bytes,
            "raw_injected_source_bytes": raw_injected_bytes,
            "serialization_overhead_bytes": serialized_envelope_bytes
            - raw_injected_bytes,
            "estimated_tokens": (
                native_bytes
                + serialized_envelope_bytes
                + request.other_model_visible_bootstrap_bytes
                + 3
            )
            // 4,
            "excluded_external_layers": [],
        },
    }
    manifest_id = w2b1.canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_id"}
    )
    manifest["manifest_id"] = manifest_id
    try:
        w2b1.validate_manifest(manifest)
    except w2b1.AgentContextError as error:
        _fail(error.message, error.code)
    envelope, envelope_bytes, envelope_sha256 = w2b1.build_envelope(
        manifest_id=manifest_id,
        generation=request.generation,
        entries=injected_entries,
    )
    if len(envelope_bytes) != serialized_envelope_bytes:
        _fail(
            "fixed-width manifest id changed serialized envelope length", "E_INTERNAL"
        )
    return ResolvedContext(manifest, envelope, envelope_bytes, envelope_sha256)


def _load_json(path: str) -> Mapping[str, Any]:
    raw = Path(path).read_bytes()
    parsed = w2b1.parse_strict_json(raw)
    if not isinstance(parsed, dict):
        _fail(f"JSON input must be an object: {path}", "E_SCHEMA")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve inactive W2b2 faceted agent context.")
    parser.add_argument("--root")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--policy-index", required=True)
    parser.add_argument("--policy-metadata")
    parser.add_argument("--capability-row")
    parser.add_argument("--reviewed-tree")
    parser.add_argument("--agent", choices=("codex", "claude"))
    parser.add_argument(
        "--platform", choices=("windows", "posix", "devcontainer")
    )
    parser.add_argument(
        "--mode", choices=("interactive", "non-interactive")
    )
    parser.add_argument("--repository", action="append", default=[])
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--operation", action="append", default=[])
    parser.add_argument("--authorization", action="append", default=[])
    parser.add_argument("--native-evidence")
    parser.add_argument("--injection-evidence")
    parser.add_argument("--generation", type=int, default=0)
    parser.add_argument("--other-visible-bootstrap-bytes", type=int, default=0)
    parser.add_argument(
        "--format", choices=("manifest", "envelope", "resolution"), default="resolution"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one resolve-only request and write canonical JSON to stdout."""
    args = _parser().parse_args(argv)
    try:
        registry = _load_json(args.registry)
        policy_index = _load_json(args.policy_index)
        required = {
            "--root": args.root,
            "--policy-metadata": args.policy_metadata,
            "--capability-row": args.capability_row,
            "--reviewed-tree": args.reviewed_tree,
            "--agent": args.agent,
            "--platform": args.platform,
            "--mode": args.mode,
        }
        missing = [option for option, value in required.items() if value is None]
        if missing:
            _fail(f"{', '.join(missing)} is required for faceted resolution", "E_USAGE")
        request = ResolutionRequest(
            root=Path(args.root),
            registry=registry,
            policy_index=policy_index,
            policy_metadata=_load_json(args.policy_metadata),
            capability_row=_load_json(args.capability_row),
            reviewed_tree=_load_json(args.reviewed_tree),
            agent=args.agent,
            platform=args.platform,
            mode=args.mode,
            repositories=tuple(args.repository),
            tasks=tuple(args.task),
            exclusions=tuple(args.exclude),
            operations=tuple(args.operation),
            authorizations=tuple(_load_json(path) for path in args.authorization),
            native_evidence=_load_json(args.native_evidence)
            if args.native_evidence
            else None,
            injection_evidence=_load_json(args.injection_evidence)
            if args.injection_evidence
            else None,
            other_model_visible_bootstrap_bytes=args.other_visible_bootstrap_bytes,
            generation=args.generation,
        )
        result = resolve_context(request)
        if args.format == "manifest":
            output: Any = result.manifest
        elif args.format == "envelope":
            sys.stdout.buffer.write(result.envelope_bytes)
            return 0
        else:
            output = {
                "manifest": result.manifest,
                "envelope": result.envelope,
                "envelope_sha256": result.envelope_sha256,
            }
        sys.stdout.buffer.write(w2b1.canonical_bytes(output))
        return 0
    except w2b1.AgentContextError as error:
        print(
            json.dumps(
                {"code": error.code, "message": error.message}, separators=(",", ":")
            ),
            file=sys.stderr,
        )
        return {
            "E_USAGE": 2,
            "E_SCHEMA": 3,
            "E_UNKNOWN_ID": 4,
            "E_SCOPE_UNAVAILABLE": 5,
            "E_AUTHORITY": 6,
            "E_AUTHORIZATION": 7,
            "E_SOURCE": 8,
            "E_NATIVE_EVIDENCE": 9,
            "E_TRUST": 10,
            "E_BUDGET": 14,
            "E_UNSUPPORTED_MODE": 18,
            "E_INTERNAL": 19,
        }.get(error.code, 19)


if __name__ == "__main__":
    raise SystemExit(main())
