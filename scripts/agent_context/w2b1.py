"""Strict W2b1 schemas and RFC 8785-style canonical JSON serialization.

This module deliberately has no filesystem discovery, resolver, transport, or
runtime-store behavior.  It validates data supplied by callers and serializes
only the v2 injected-envelope shape frozen by the W2a contract.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, NoReturn


MAX_BYTE_COUNT = 2_147_483_647
MAX_SAFE_INTEGER = 9_007_199_254_740_991
IDENTIFIER_RE = re.compile(r"^[a-z0-9._$-]{1,128}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
GIT_TREE_RE = {
    "git-sha1": re.compile(r"^[0-9a-f]{40}$"),
    "git-sha256": re.compile(r"^[0-9a-f]{64}$"),
}
STATES = frozenset({"RESOLVED", "PREPARED", "HANDED_OFF", "FAILED"})
AUTHORIZATION = frozenset({"none", "mutating", "cross-repository"})
AUTHORITY_TIERS = frozenset({"security", "workspace", "task", "repository"})


@dataclass
class AgentContextError(ValueError):
    """A stable W2a error class for schema or source serialization failures."""

    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _fail(message: str, *, code: str = "E_SCHEMA") -> NoReturn:
    raise AgentContextError(code, message)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _byte_count(value: Any, field: str) -> None:
    if not _is_int(value) or not 0 <= value <= MAX_BYTE_COUNT:
        _fail(f"{field} must be an integer from 0 through {MAX_BYTE_COUNT}")


def _identifier(value: Any, field: str) -> None:
    if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
        _fail(f"{field} must be a 1-128 byte lowercase identifier")


def _sha256(value: Any, field: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        _fail(f"{field} must be a lowercase SHA-256 hexadecimal digest")


def _timestamp(value: Any, field: str) -> None:
    if not isinstance(value, str) or not TIMESTAMP_RE.fullmatch(value):
        _fail(f"{field} must be a whole-second UTC RFC 3339 timestamp")


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{field} must be an object")
    return value


def _closed(value: Any, fields: set[str], name: str) -> dict[str, Any]:
    obj = _object(value, name)
    actual = set(obj)
    missing = fields - actual
    unknown = actual - fields
    if missing:
        _fail(f"{name} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        _fail(f"{name} has unknown fields: {', '.join(sorted(unknown))}")
    return obj


def _canonical_path(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value:
        _fail(f"{field} must be a non-empty canonical workspace-relative path")
    if "\\" in value or "\x00" in value or "%" in value or value.startswith("/"):
        _fail(f"{field} is not a canonical path")
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        _fail(f"{field} is not a canonical path")


def _scope_prefix(value: Any, field: str) -> None:
    if value == ".":
        return
    _canonical_path(value, field)


def _ordered_ids(value: Any, field: str) -> None:
    if not isinstance(value, list):
        _fail(f"{field} must be an array")
    for index, item in enumerate(value):
        _identifier(item, f"{field}[{index}]")
    if len(value) != len(set(value)):
        _fail(f"{field} must not contain duplicate identifiers")


def _canonical_set(value: Any, field: str) -> None:
    _ordered_ids(value, field)
    if value != sorted(value):
        _fail(f"{field} must be sorted by Unicode code point")


def _canonical_sha256_set(value: Any, field: str) -> None:
    if not isinstance(value, list):
        _fail(f"{field} must be an array")
    for index, item in enumerate(value):
        _sha256(item, f"{field}[{index}]")
    if len(value) != len(set(value)):
        _fail(f"{field} must not contain duplicate digests")
    if value != sorted(value):
        _fail(f"{field} must be sorted by Unicode code point")


def _ordered_paths(value: Any, field: str) -> None:
    if not isinstance(value, list) or not value:
        _fail(f"{field} must be a non-empty array of canonical paths")
    for index, item in enumerate(value):
        _canonical_path(item, f"{field}[{index}]")
    if len(value) != len(set(value)):
        _fail(f"{field} must not contain duplicate paths")


def _strict_unicode(value: str, field: str) -> None:
    for index, codepoint in enumerate(map(ord, value)):
        if 0xD800 <= codepoint <= 0xDFFF:
            _fail(f"{field} contains a lone UTF-16 surrogate", code="E_SOURCE")


def canonical_json(value: Any) -> str:
    """Return JCS-compatible compact JSON for the contract's integer-only data.

    RFC 8785 delegates primitive string serialization to ECMAScript. Python's
    compact JSON encoder has the same escaping for valid Unicode strings; keys
    are explicitly sorted by UTF-16 code units as required by JCS. Floats,
    non-finite values, non-string keys, and lone surrogates are rejected.
    """

    def encode(item: Any, field: str) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if _is_int(item):
            if not -MAX_SAFE_INTEGER <= item <= MAX_SAFE_INTEGER:
                _fail(f"{field} is outside the JCS-safe integer range")
            return str(item)
        if isinstance(item, float):
            _fail(f"{field} must not contain floating-point values")
        if isinstance(item, str):
            _strict_unicode(item, field)
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if isinstance(item, list):
            return "[" + ",".join(encode(child, f"{field}[{index}]") for index, child in enumerate(item)) + "]"
        if isinstance(item, dict):
            for key in item:
                if not isinstance(key, str):
                    _fail(f"{field} has a non-string object key")
                _strict_unicode(key, f"{field} key")
            keys = sorted(item, key=lambda key: key.encode("utf-16-be"))
            return "{" + ",".join(
                f"{encode(key, f'{field} key')}:{encode(item[key], f'{field}.{key}')}" for key in keys
            ) + "}"
        _fail(f"{field} contains unsupported JSON data")

    return encode(value, "$")


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8", "strict")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _identified_digest(value: dict[str, Any], identifier_field: str) -> str:
    if identifier_field not in value:
        _fail(f"record is missing {identifier_field}")
    without_identifier = {key: item for key, item in value.items() if key != identifier_field}
    return canonical_sha256(without_identifier)


def validate_registry_v1(value: Any) -> None:
    registry = _object(value, "registry v1")
    if not registry:
        _fail("registry v1 must not be empty")
    for repository_id, bundle in registry.items():
        _identifier(repository_id, "registry v1 repository id")
        _identifier(bundle, f"registry v1 bundle for {repository_id}")


def validate_policy_index_v1(value: Any) -> None:
    index = _object(value, "policy index v1")
    if not index:
        _fail("policy index v1 must not be empty")
    for bundle, paths in index.items():
        _identifier(bundle, "policy index v1 bundle id")
        _ordered_paths(paths, f"policy index v1 bundle {bundle}")


def validate_registry_v2(value: Any, *, index_mode: str | None = None) -> None:
    registry = _closed(value, {"schema_version", "repositories"}, "registry v2")
    if registry["schema_version"] != 2:
        _fail("registry v2 schema_version must be 2")
    repositories = registry["repositories"]
    if not isinstance(repositories, list):
        _fail("registry v2 repositories must be an array")
    ids: list[str] = []
    paths: list[str] = []
    for index, repository in enumerate(repositories):
        repo = _closed(repository, {"id", "path", "kind", "layer", "facets", "migration"} if index_mode == "transitional-v1-bundles" else {"id", "path", "kind", "layer", "facets"}, f"registry v2 repositories[{index}]")
        _identifier(repo["id"], f"registry v2 repositories[{index}].id")
        _canonical_path(repo["path"], f"registry v2 repositories[{index}].path")
        if "/" in repo["path"]:
            _fail("registry v2 repository path must be a direct-child path")
        _identifier(repo["kind"], f"registry v2 repositories[{index}].kind")
        if repo["layer"] not in {"platform", "service", "client", "shared"}:
            _fail(f"registry v2 repositories[{index}].layer is invalid")
        _ordered_ids(repo["facets"], f"registry v2 repositories[{index}].facets")
        if index_mode == "transitional-v1-bundles":
            migration = _closed(repo["migration"], {"v1_bundle"}, f"registry v2 repositories[{index}].migration")
            _identifier(migration["v1_bundle"], f"registry v2 repositories[{index}].migration.v1_bundle")
        ids.append(repo["id"])
        paths.append(repo["path"])
    if ids != sorted(ids):
        _fail("registry v2 repositories must be sorted by id")
    if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
        _fail("registry v2 repository ids and paths must be unique")


def _id_to_ordered_ids_map(value: Any, field: str, *, paths: bool = False) -> None:
    mapping = _object(value, field)
    if list(mapping) != sorted(mapping):
        _fail(f"{field} keys must be sorted by Unicode code point")
    for key, items in mapping.items():
        _identifier(key, f"{field} key")
        if paths:
            _ordered_paths(items, f"{field}.{key}")
        else:
            _ordered_ids(items, f"{field}.{key}")


def validate_policy_index_v2(value: Any, *, v1_policy_index: Any | None = None) -> None:
    index = _object(value, "policy index v2")
    base_fields = {"schema_version", "mode", "budgets", "always", "facets", "tasks", "exclusions"}
    mode = index.get("mode")
    if mode == "transitional-v1-bundles":
        expected = base_fields | {"compatibility_bundles"}
    elif mode == "faceted":
        expected = base_fields
    else:
        _fail("policy index v2 mode must be transitional-v1-bundles or faceted")
    _closed(index, expected, "policy index v2")
    if index["schema_version"] != 2:
        _fail("policy index v2 schema_version must be 2")
    budgets = _closed(index["budgets"], {"preferred_bytes", "hard_bytes"}, "policy index v2 budgets")
    if budgets["preferred_bytes"] != 24_576 or budgets["hard_bytes"] != 32_768:
        _fail("policy index v2 budgets must be the frozen 24576/32768 values")
    _ordered_ids(index["always"], "policy index v2 always")
    _id_to_ordered_ids_map(index["facets"], "policy index v2 facets")
    tasks = _object(index["tasks"], "policy index v2 tasks")
    if list(tasks) != sorted(tasks):
        _fail("policy index v2 tasks keys must be sorted by Unicode code point")
    for task_id, task in tasks.items():
        _identifier(task_id, "policy index v2 task id")
        task_object = _closed(task, {"policies", "authorization"}, f"policy index v2 tasks.{task_id}")
        _ordered_ids(task_object["policies"], f"policy index v2 tasks.{task_id}.policies")
        if task_object["authorization"] not in AUTHORIZATION:
            _fail(f"policy index v2 tasks.{task_id}.authorization is invalid")
    _id_to_ordered_ids_map(index["exclusions"], "policy index v2 exclusions")
    if mode == "transitional-v1-bundles":
        if any(index[field] for field in ("always", "facets", "tasks", "exclusions")):
            _fail("transitional-v1-bundles policy fields must be empty")
        _id_to_ordered_ids_map(index["compatibility_bundles"], "policy index v2 compatibility_bundles", paths=True)
        if v1_policy_index is not None:
            validate_policy_index_v1(v1_policy_index)
            if index["compatibility_bundles"] != v1_policy_index:
                _fail("compatibility_bundles must exactly mirror the supplied v1 policy index")


def validate_workspace_configuration_v2(registry_value: Any, index_value: Any) -> None:
    """Validate the coupled active v2 registry and policy-index configuration.

    W3 keeps the legacy policy bundles only as data inside the transitional v2
    index.  This cross-file check is the migration boundary: each repository
    selector must resolve to one of those embedded bundles, and selectors are
    forbidden once the faceted index is active.
    """
    index = _object(index_value, "policy index v2")
    mode = index.get("mode")
    validate_policy_index_v2(index)
    validate_registry_v2(registry_value, index_mode=mode)
    if mode != "transitional-v1-bundles":
        return
    bundles = index["compatibility_bundles"]
    for repository in registry_value["repositories"]:
        bundle = repository["migration"]["v1_bundle"]
        if bundle not in bundles:
            _fail(
                f"registry v2 migration selector has no compatibility bundle: {repository['id']}",
                code="E_UNKNOWN_ID",
            )


def project_transitional_v1_configuration(
    registry_value: Any, index_value: Any
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return the reversible W3 v1 projection without changing authoritative files."""
    validate_workspace_configuration_v2(registry_value, index_value)
    if index_value["mode"] != "transitional-v1-bundles":
        _fail("only a transitional v2 configuration has a v1 compatibility projection")
    registry = {
        repository["id"]: repository["migration"]["v1_bundle"]
        for repository in registry_value["repositories"]
    }
    bundles = {
        bundle: list(paths)
        for bundle, paths in index_value["compatibility_bundles"].items()
    }
    validate_registry_v1(registry)
    validate_policy_index_v1(bundles)
    return registry, bundles


def validate_policy_unit(value: Any) -> None:
    unit = _closed(value, {"id", "path", "authority_tier", "scope", "invariant_ids", "conflicts_with", "may_override", "required", "capabilities_granted"}, "policy unit")
    _identifier(unit["id"], "policy unit id")
    _canonical_path(unit["path"], "policy unit path")
    if unit["authority_tier"] not in AUTHORITY_TIERS:
        _fail("policy unit authority_tier is invalid")
    scope = _closed(unit["scope"], {"repository_id", "prefix"}, "policy unit scope")
    _identifier(scope["repository_id"], "policy unit scope.repository_id")
    _scope_prefix(scope["prefix"], "policy unit scope.prefix")
    for field in ("invariant_ids", "conflicts_with", "may_override", "capabilities_granted"):
        _canonical_set(unit[field], f"policy unit {field}")
    if not isinstance(unit["required"], bool):
        _fail("policy unit required must be boolean")


ENVELOPE_ENTRY_FIELDS = {
    "policy_id", "repository_id", "scope_prefix", "path", "authority_tier",
    "source_sha256", "source_bytes", "leading_bom_bytes",
    "serialized_content_bytes", "content",
}


def validate_envelope_entry(value: Any) -> None:
    entry = _closed(value, ENVELOPE_ENTRY_FIELDS, "envelope entry")
    _identifier(entry["policy_id"], "envelope entry policy_id")
    _identifier(entry["repository_id"], "envelope entry repository_id")
    _scope_prefix(entry["scope_prefix"], "envelope entry scope_prefix")
    _canonical_path(entry["path"], "envelope entry path")
    if entry["authority_tier"] not in AUTHORITY_TIERS:
        _fail("envelope entry authority_tier is invalid")
    _sha256(entry["source_sha256"], "envelope entry source_sha256")
    _byte_count(entry["source_bytes"], "envelope entry source_bytes")
    if entry["leading_bom_bytes"] not in {0, 3}:
        _fail("envelope entry leading_bom_bytes must be 0 or 3")
    _byte_count(entry["serialized_content_bytes"], "envelope entry serialized_content_bytes")
    if not isinstance(entry["content"], str):
        _fail("envelope entry content must be a string")
    _strict_unicode(entry["content"], "envelope entry content")
    if "\x00" in entry["content"]:
        _fail("envelope entry content must not contain NUL", code="E_SOURCE")
    if entry["content"].startswith("\ufeff"):
        _fail("envelope entry content must not retain a leading BOM", code="E_SOURCE")
    encoded_length = len(entry["content"].encode("utf-8", "strict"))
    if entry["serialized_content_bytes"] != encoded_length:
        _fail("envelope entry serialized_content_bytes does not match UTF-8 content", code="E_SOURCE")
    if entry["source_bytes"] != encoded_length + entry["leading_bom_bytes"]:
        _fail("envelope entry source_bytes does not match original source bytes", code="E_SOURCE")


def source_entry_from_bytes(raw: bytes, metadata: Mapping[str, Any], *, allow_legacy_leading_bom: bool = False) -> dict[str, Any]:
    """Create one validated envelope entry from exact original source bytes."""
    if not isinstance(raw, bytes):
        _fail("raw source must be bytes", code="E_SOURCE")
    if b"\x00" in raw:
        _fail("source must not contain NUL", code="E_SOURCE")
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    if has_bom and not allow_legacy_leading_bom:
        _fail("a new or migrated source must not have a leading BOM", code="E_SOURCE")
    source_content = raw[3:] if has_bom else raw
    try:
        content = source_content.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        _fail(f"source is not strict UTF-8: {error}", code="E_SOURCE")
    entry = dict(metadata)
    entry.update({
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw),
        "leading_bom_bytes": 3 if has_bom else 0,
        "serialized_content_bytes": len(source_content),
        "content": content,
    })
    validate_envelope_entry(entry)
    return entry


def build_envelope(*, manifest_id: str, generation: int, entries: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], bytes, str]:
    """Validate, exact-deduplicate, and JCS-serialize the injected envelope."""
    _sha256(manifest_id, "manifest_id")
    _byte_count(generation, "generation")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes, bytearray)):
        _fail("entries must be an array")
    unique: list[dict[str, Any]] = []
    by_path: dict[str, dict[str, Any]] = {}
    for index, supplied in enumerate(entries):
        if not isinstance(supplied, Mapping):
            _fail(f"entries[{index}] must be an object")
        entry = dict(supplied)
        validate_envelope_entry(entry)
        prior = by_path.get(entry["path"])
        if prior is None:
            by_path[entry["path"]] = entry
            unique.append(entry)
        elif prior != entry:
            _fail(f"duplicate canonical path has mismatched metadata: {entry['path']}", code="E_SOURCE")
        # Identical entries are deliberately emitted once, retaining resolver order.
    envelope = {"schema_version": 2, "manifest_id": manifest_id, "generation": generation, "entries": unique}
    serialized = canonical_bytes(envelope)
    return envelope, serialized, hashlib.sha256(serialized).hexdigest()


def _reviewed_tree(value: Any) -> None:
    tree = _closed(value, {"algorithm", "value"}, "reviewed_tree")
    algorithm = tree["algorithm"]
    if algorithm not in GIT_TREE_RE or not isinstance(tree["value"], str) or not GIT_TREE_RE[algorithm].fullmatch(tree["value"]):
        _fail("reviewed_tree is invalid")


def _manifest_entry(value: Any) -> None:
    entry = _closed(value, {"policy_id", "repository_id", "scope_prefix", "path", "delivery", "source_sha256", "source_bytes", "metadata_sha256", "native_evidence_id"}, "manifest entry")
    _identifier(entry["policy_id"], "manifest entry policy_id")
    _identifier(entry["repository_id"], "manifest entry repository_id")
    _scope_prefix(entry["scope_prefix"], "manifest entry scope_prefix")
    _canonical_path(entry["path"], "manifest entry path")
    if entry["delivery"] not in {"native", "inject"}:
        _fail("manifest entry delivery is invalid")
    _sha256(entry["source_sha256"], "manifest entry source_sha256")
    _byte_count(entry["source_bytes"], "manifest entry source_bytes")
    _sha256(entry["metadata_sha256"], "manifest entry metadata_sha256")
    if entry["native_evidence_id"] is not None:
        _sha256(entry["native_evidence_id"], "manifest entry native_evidence_id")


ACCOUNTING_FIELDS = {
    "policy_hard_limit", "verified_channel_limit", "client_context_allowance", "reserved_margin", "effective_hard_limit",
    "native_model_visible_bytes", "serialized_injected_envelope_bytes", "other_model_visible_bootstrap_bytes",
    "model_visible_total", "raw_injected_source_bytes", "serialization_overhead_bytes", "estimated_tokens", "excluded_external_layers",
}


def validate_manifest(value: Any, *, verify_identifier: bool = True) -> None:
    fields = {"schema_version", "manifest_id", "reviewed_tree", "agent", "platform", "mode", "capability_evidence_id", "repositories", "tasks", "authorization_ids", "entries", "accounting"}
    manifest = _closed(value, fields, "manifest")
    if manifest["schema_version"] != 2:
        _fail("manifest schema_version must be 2")
    _sha256(manifest["manifest_id"], "manifest_id")
    _reviewed_tree(manifest["reviewed_tree"])
    if manifest["agent"] not in {"codex", "claude"} or manifest["platform"] not in {"windows", "posix", "devcontainer"} or manifest["mode"] not in {"interactive", "non-interactive"}:
        _fail("manifest agent/platform/mode is invalid")
    _sha256(manifest["capability_evidence_id"], "manifest capability_evidence_id")
    for field in ("repositories", "tasks", "authorization_ids"):
        _canonical_set(manifest[field], f"manifest {field}")
    if not isinstance(manifest["entries"], list):
        _fail("manifest entries must be an array")
    for entry in manifest["entries"]:
        _manifest_entry(entry)
    accounting = _closed(manifest["accounting"], ACCOUNTING_FIELDS, "manifest accounting")
    for field in ACCOUNTING_FIELDS - {"excluded_external_layers"}:
        _byte_count(accounting[field], f"manifest accounting {field}")
    _canonical_set(accounting["excluded_external_layers"], "manifest accounting excluded_external_layers")
    if verify_identifier and manifest["manifest_id"] != _identified_digest(manifest, "manifest_id"):
        _fail("manifest_id does not match JCS content", code="E_SOURCE")


SESSION_FIELDS = {
    "schema_version", "launch_id", "client_session_id", "generation", "state", "manifest_id", "envelope_sha256",
    "capability_evidence_id", "native_evidence_ids", "authorization_ids", "created_at", "updated_at", "previous_receipt_sha256",
}


def validate_session(value: Any) -> None:
    session = _closed(value, SESSION_FIELDS, "session")
    if session["schema_version"] != 2:
        _fail("session schema_version must be 2")
    _identifier(session["launch_id"], "session launch_id")
    _identifier(session["client_session_id"], "session client_session_id")
    _byte_count(session["generation"], "session generation")
    if session["state"] not in STATES:
        _fail("session state is invalid")
    for field in ("manifest_id", "envelope_sha256", "capability_evidence_id", "previous_receipt_sha256"):
        _sha256(session[field], f"session {field}")
    _canonical_sha256_set(session["native_evidence_ids"], "session native_evidence_ids")
    _canonical_set(session["authorization_ids"], "session authorization_ids")
    _timestamp(session["created_at"], "session created_at")
    _timestamp(session["updated_at"], "session updated_at")


RECEIPT_FIELDS = {
    "schema_version", "receipt_id", "launch_id", "client_session_id", "generation", "manifest_id", "envelope_sha256",
    "capability_evidence_id", "native_evidence_ids", "authorization_ids", "previous_state", "state", "channel_id",
    "delivered_bytes", "failure_code", "recorded_at",
}


def validate_receipt(value: Any, *, verify_identifier: bool = True) -> None:
    receipt = _closed(value, RECEIPT_FIELDS, "receipt")
    if receipt["schema_version"] != 2:
        _fail("receipt schema_version must be 2")
    _sha256(receipt["receipt_id"], "receipt_id")
    _identifier(receipt["launch_id"], "receipt launch_id")
    _identifier(receipt["client_session_id"], "receipt client_session_id")
    _byte_count(receipt["generation"], "receipt generation")
    for field in ("manifest_id", "envelope_sha256", "capability_evidence_id"):
        _sha256(receipt[field], f"receipt {field}")
    _canonical_sha256_set(receipt["native_evidence_ids"], "receipt native_evidence_ids")
    _canonical_set(receipt["authorization_ids"], "receipt authorization_ids")
    if receipt["previous_state"] not in STATES or receipt["state"] not in STATES:
        _fail("receipt state is invalid")
    _identifier(receipt["channel_id"], "receipt channel_id")
    _byte_count(receipt["delivered_bytes"], "receipt delivered_bytes")
    if receipt["failure_code"] != "OK" and not (isinstance(receipt["failure_code"], str) and re.fullmatch(r"E_[A-Z_]+", receipt["failure_code"])):
        _fail("receipt failure_code must be OK or a stable E_* code")
    _timestamp(receipt["recorded_at"], "receipt recorded_at")
    if verify_identifier and receipt["receipt_id"] != _identified_digest(receipt, "receipt_id"):
        _fail("receipt_id does not match JCS content", code="E_SOURCE")


def parse_strict_json(raw: bytes) -> Any:
    """Decode JSON without duplicate keys, floats, invalid UTF-8, or trailing data."""
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        _fail(f"JSON input is not strict UTF-8: {error}", code="E_SOURCE")

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                _fail(f"JSON object contains duplicate key: {key}")
            result[key] = item
        return result

    def no_float(_: str) -> Any:
        _fail("JSON input must not contain floating-point values")

    try:
        return json.loads(text, object_pairs_hook=no_duplicates, parse_float=no_float, parse_constant=no_float)
    except AgentContextError:
        raise
    except json.JSONDecodeError as error:
        _fail(f"JSON input is malformed: {error}")
