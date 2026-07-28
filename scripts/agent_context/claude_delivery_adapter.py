"""Step 12.3 fail-closed canonical Claude launcher-adapter.

Step 12.1 froze the installed-client capability matrix and Step 12.2 established
the out-of-band ``claude-loopback-model-input-capture`` native-load evidence
mechanism.  This module is the launcher-adapter those two steps gate.  For one
launch it performs the complete preflight, resolves the faceted v2 context for
agent ``claude``, classifies every selected source ``native`` or ``inject``
against real client evidence, selects a channel by ``model_visible_total``, and
hands the resolver's exact JCS envelope to the shared W2b3 delivery kernel.

Nothing here is optimistic.  Every stage has one fail-closed answer:

* the launch must run in the evidenced devcontainer, against the pinned Step
  12.1 capability artifact and the exact installed client it froze;
* the project must be recorded ``trusted`` by the client's own trust record —
  print mode does not grant trust and a launcher must never self-grant it;
* the project settings layer must still satisfy the reviewed Phase 5.5 contract,
  and a settings/hook change between preflight and transport invalidates it;
* ``native`` is only what the Step 12.2 capture proved active, ``inject`` is
  only what the same capture proved absent, and the manifest is compared with
  that evidence in both directions before an injected entry is omitted;
* a row may deliver only when the shared validator accepts its complete
  accounting, so an over-budget row is rejected rather than truncated; and
* the kernel owns runtime storage, source-drift rehashing, the immutable
  journal, and the ``RESOLVED``/``PREPARED``/``SUBMISSION_STARTED``/
  ``COMPLETED``/``EXECUTION_AMBIGUOUS``/``FAILED`` lifecycle.

The resolver, kernel, authorization boundary, shared validator, and trust
identity are reused unchanged; this module adds only the Claude-specific
preflight, classification, and transport.

Step 12.4 wired the second channel.  The hook row is now eligible, bound to the
frozen byte-exact round-trip artifact, and delivered by the launcher's own
``--settings`` registration of exactly one ``UserPromptSubmit`` gate per
launcher-controlled generation.  Because a settings-registered
``additionalContext`` hook merges with the launcher's own, any such event
already registered in the project, local, or user layer is a second injection
authority this launcher does not own and makes *both* rows ineligible.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import shlex
import stat
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from agent_context import claude_hook_gate as gate
from agent_context import claude_native_evidence as native
from agent_context import w2b1

# Workspace-marker discovery, the process-runner seam, the reviewed-tree reader,
# and the strict JSON loader are client-neutral and frozen by Phase 6.  They are
# reused rather than forked so both canonical launchers share one behavior.
from agent_context.codex_adapter import (
    CommandResult,
    CommandRunner,
    _load_json,
    _reviewed_tree,
    find_workspace_root,
    subprocess_runner,
)
from agent_context.delivery_kernel import (
    DeliveryKernel,
    DeliveryRequest,
    DeliveryResult,
    TransportAdapter,
    TransportConfirmation,
)
from agent_context.resolve_context import ResolutionRequest, ResolvedContext, resolve_context
from agent_context.shared_validation import validate_resolved, validate_trust
from agent_context.trust_identity import build_trust_identity
from agent_context.validate_claude_settings import (
    ClaudeSettingsValidationError,
    validate_claude_settings,
)


# Only the devcontainer rows were measured; every other platform row is frozen
# ``UNSUPPORTED`` and nothing is inferred from this one.
CONTAINER_MARKER = Path("/.dockerenv")

CAPABILITY_EVIDENCE_PATH = (
    "scripts/agent_context/fixtures/evidence/w12-claude-capability-evidence-2026-07-27.json"
)
CAPABILITY_EVIDENCE_SHA256 = "f3539f7f66135a6726253e97c5bab0b3858860e904b9148ec26d112d82c7c6f8"
NATIVE_LOAD_EVIDENCE_PATH = (
    "scripts/agent_context/fixtures/evidence/w12-claude-native-load-evidence-2026-07-28.json"
)
NATIVE_LOAD_EVIDENCE_SHA256 = "705d1b9d30a8b617d2c4b683b12d57d85e76ab29d206447951434201a0825634"
HOOK_CHANNEL_EVIDENCE_PATH = (
    "scripts/agent_context/fixtures/evidence/w12-claude-hook-channel-evidence-2026-07-28.json"
)
HOOK_CHANNEL_EVIDENCE_SHA256 = "db329b43cd2205838e619037e1a8051ce2c53e943d5e2ec19baefacb00463d5e"

HOOK_CHANNEL_ID = "claude-hook-additional-context"
FULL_CONTENT_CHANNEL_ID = "claude-cli-append-system-prompt"
# Preference order: the cheapest verified channel that fits is tried first.
REQUIRED_ROW_IDS = (
    "claude-devcontainer-non-interactive-hook-additional-context",
    "claude-devcontainer-non-interactive-append-system-prompt",
)
INJECTION_AUTHORITY_EVENT = gate.HOOK_EVENT
GATE_MODULE_PATH = "scripts/agent_context/claude_hook_gate.py"
# Step 12.4's frozen byte-exact round trip.  It is the identity of the tracked
# hook-channel artifact and is bound into every armed generation; the hook row
# stays ineligible whenever it is absent.
HOOK_ROUND_TRIP_EVIDENCE: str | None = (
    "c9fe9601915491ca1b6085373f6c32ba76506b75985579a3a288be4f7135b922"
)
REPOSITORY_INSTRUCTION_FILES = ("CLAUDE.md", "REPOSITORY_CONTEXT.md")
# The client frames native memory itself and that framing is client-owned, not
# workspace-controlled.  Every workspace-owned native byte is already counted
# exactly once through its own manifest entry, so this term stays zero and the
# measurement boundary is not inflated by counting a source twice.
OTHER_MODEL_VISIBLE_BOOTSTRAP_BYTES = 0


def _fail(code: str, message: str) -> NoReturn:
    raise w2b1.AgentContextError(code, message)


def _sha256(path: Path, *, code: str = "E_SOURCE") -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        _fail(code, f"cannot hash required source: {error}")


def _unique_identifiers(values: Sequence[str], field: str) -> tuple[str, ...]:
    """Return a canonical argument set; a duplicate never silently changes scope."""
    if isinstance(values, (str, bytes, bytearray)):
        _fail("E_USAGE", f"{field} arguments must be repeatable identifiers")
    items = tuple(values)
    if field == "repository" and not items:
        _fail("E_USAGE", "at least one repository is required")
    for value in items:
        try:
            w2b1._identifier(value, f"{field} argument")
        except w2b1.AgentContextError:
            _fail("E_USAGE", f"{field} argument is not a canonical identifier")
    if len(items) != len(set(items)):
        _fail("E_USAGE", f"duplicate {field} arguments are forbidden")
    return tuple(sorted(items))


@dataclass(frozen=True)
class ClaudeCapabilityRow:
    """One frozen Step 12.1 row and the identities the resolver recomputes."""

    row_id: str
    row: Mapping[str, Any]
    capability_evidence_id: str
    effective_hard_limit: int


@dataclass(frozen=True)
class ClaudePreflight:
    """Everything one launch proved before any context was resolved."""

    workspace_root: Path
    launch_scope: Path
    project: str
    repositories: tuple[Path, ...]
    repository_ids: tuple[str, ...]
    client_identity: str
    client_version: str
    client_sha256: str
    settings: Mapping[str, Any]
    config_sha256: str
    trust_state: str
    load: native.ClaudeNativeLoad
    # Complete reviewed-tree/environment identity; empty unless strict.
    trust_identity: Mapping[str, Any]

    @property
    def native_source_sha256(self) -> Mapping[str, str]:
        return self.load.source_sha256


@dataclass(frozen=True)
class ClaudeResolution:
    """One resolved generation bound to the channel that may carry it."""

    capability: ClaudeCapabilityRow
    channel_id: str
    resolved: ResolvedContext
    native_evidence: Mapping[str, Any]
    injection_evidence: Mapping[str, Any]
    # Metadata-only selection trace: why each earlier row could not deliver.
    rejected_rows: tuple[Mapping[str, str], ...]
    # The frozen Step 12.4 round trip, present only when the hook row delivers.
    round_trip_evidence_id: str | None = None


def _capability_artifact(root: Path) -> dict[str, Any]:
    """Load the pinned Step 12.1 artifact; a changed matrix fails closed."""
    path = root.joinpath(*CAPABILITY_EVIDENCE_PATH.split("/"))
    if _sha256(path, code="E_CAPABILITY") != CAPABILITY_EVIDENCE_SHA256:
        _fail("E_CAPABILITY", "Claude capability evidence changed and must be refreshed")
    evidence = root.joinpath(*NATIVE_LOAD_EVIDENCE_PATH.split("/"))
    if _sha256(evidence, code="E_NATIVE_EVIDENCE") != NATIVE_LOAD_EVIDENCE_SHA256:
        _fail("E_NATIVE_EVIDENCE", "Claude native-load evidence changed and must be refrozen")
    hook_channel = root.joinpath(*HOOK_CHANNEL_EVIDENCE_PATH.split("/"))
    if _sha256(hook_channel, code="E_CHANNEL") != HOOK_CHANNEL_EVIDENCE_SHA256:
        _fail("E_CHANNEL", "Claude hook round-trip evidence changed and must be refrozen")
    try:
        artifact = w2b1.parse_strict_json(path.read_bytes())
    except (OSError, w2b1.AgentContextError) as error:
        _fail("E_CAPABILITY", f"Claude capability evidence is invalid: {error}")
    if not isinstance(artifact, dict) or not isinstance(artifact.get("rows"), list):
        _fail("E_CAPABILITY", "Claude capability evidence has no frozen row list")
    return artifact


def _hook_channel_evidence(root: Path, rows: Mapping[str, ClaudeCapabilityRow]) -> Mapping[str, Any]:
    """Load the frozen Step 12.4 round trip and prove it still describes this row.

    A round trip is evidence only while it names the same client, the same hook
    event, the same channel, and the same verified limit as the capability row
    it unlocks; any drift makes the hook row ineligible rather than optimistic.
    """
    path = root.joinpath(*HOOK_CHANNEL_EVIDENCE_PATH.split("/"))
    try:
        artifact = w2b1.parse_strict_json(path.read_bytes())
    except (OSError, w2b1.AgentContextError) as error:
        _fail("E_CHANNEL", f"Claude hook round-trip evidence is invalid: {error}")
    record = artifact.get("round_trip") if isinstance(artifact, dict) else None
    if not isinstance(record, dict):
        _fail("E_CHANNEL", "Claude hook round-trip evidence has no frozen record")
    identity = record.get("round_trip_evidence_id")
    if w2b1.canonical_sha256(
        {key: value for key, value in record.items() if key != "round_trip_evidence_id"}
    ) != identity:
        _fail("E_CHANNEL", "the frozen hook round-trip identity does not recompute")
    if identity != HOOK_ROUND_TRIP_EVIDENCE:
        _fail("E_CHANNEL", "the frozen hook round-trip identity differs from the adapter")
    row = rows[REQUIRED_ROW_IDS[0]]
    if (
        record.get("channel_id") != HOOK_CHANNEL_ID
        or record.get("hook_event") != INJECTION_AUTHORITY_EVENT
        or record.get("capability_evidence_id") != row.capability_evidence_id
        or record.get("verified_channel_limit") != row.row["verified_channel_limit"]
    ):
        _fail("E_CHANNEL", "the frozen hook round trip does not describe the required hook row")
    if record.get("exact_model_input") is not True or record.get("delivery_mechanism") != (
        "launcher-owned --settings UserPromptSubmit gate"
    ):
        _fail("E_CHANNEL", "the frozen hook round trip does not prove exact model-visible delivery")
    if record.get("model_visible_occurrences") != 1 or record.get("claims_after_second_prompt") != 1:
        _fail("E_CHANNEL", "the frozen hook round trip does not prove exactly-once delivery")
    # The gate is the injection authority the round trip measured; a changed
    # gate is unmeasured wiring, so the row becomes ineligible rather than
    # inheriting another file's evidence.
    if _sha256(
        root.joinpath(*GATE_MODULE_PATH.split("/")), code="E_CHANNEL"
    ) != record.get("gate_source_sha256"):
        _fail("E_CHANNEL", "the Claude hook gate changed since its round-trip evidence")
    return record


def _capability_rows(artifact: Mapping[str, Any]) -> dict[str, ClaudeCapabilityRow]:
    """Return the required rows, each recomputing its own frozen identity."""
    rows: dict[str, ClaudeCapabilityRow] = {}
    for item in artifact["rows"]:
        row_id = item.get("row_id") if isinstance(item, dict) else None
        if row_id not in REQUIRED_ROW_IDS:
            continue
        row = item.get("capability_row")
        if not isinstance(row, dict) or row.get("agent") != "claude" or row.get("status") != "REQUIRED":
            _fail("E_CAPABILITY", f"frozen row is not a required Claude row: {row_id}")
        if w2b1.canonical_sha256(row) != item.get("capability_evidence_id"):
            _fail("E_CAPABILITY", f"frozen row identity does not recompute: {row_id}")
        if row.get("inspection_mechanism") != native.MECHANISM:
            _fail("E_CAPABILITY", f"frozen row does not carry the evidenced mechanism: {row_id}")
        limit = item.get("effective_hard_limit")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            _fail("E_CAPABILITY", f"frozen row has no effective hard limit: {row_id}")
        rows[row_id] = ClaudeCapabilityRow(row_id, row, item["capability_evidence_id"], limit)
    if set(rows) != set(REQUIRED_ROW_IDS):
        _fail("E_CAPABILITY", "the frozen Claude matrix no longer contains both required rows")
    return rows


def _registered_repository(root: Path, repository_id: str) -> Path:
    """Resolve one registered direct child that owns a regular native CLAUDE.md."""
    registry = _load_json(root / ".workspace" / "repo-types.json")
    repositories = registry.get("repositories")
    if not isinstance(repositories, list):
        _fail("E_SCHEMA", "repository registry has no v2 repository list")
    match = [item for item in repositories if item.get("id") == repository_id]
    if len(match) != 1 or not isinstance(match[0].get("path"), str):
        _fail("E_UNKNOWN_ID", "launcher target is not one registered repository")
    path = match[0]["path"]
    try:
        w2b1._canonical_path(path, "registered repository path")
        candidate = root.joinpath(*path.split("/"))
        candidate_info = candidate.lstat()
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError, w2b1.AgentContextError) as error:
        _fail("E_SCOPE_UNAVAILABLE", f"registered repository path is unsafe: {error}")
    if (
        candidate != resolved
        or candidate.parent != root
        or stat.S_ISLNK(candidate_info.st_mode)
        or not stat.S_ISDIR(candidate_info.st_mode)
    ):
        _fail("E_SCOPE_UNAVAILABLE", "canonical launcher requires one direct child Git repository")
    try:
        git_info = (candidate / ".git").lstat()
    except OSError as error:
        _fail("E_SCOPE_UNAVAILABLE", f"selected repository lacks direct child .git presence: {error}")
    if stat.S_ISLNK(git_info.st_mode) or not (
        stat.S_ISDIR(git_info.st_mode) or stat.S_ISREG(git_info.st_mode)
    ):
        _fail("E_SCOPE_UNAVAILABLE", "canonical launcher requires direct child .git presence")
    try:
        instruction_info = (candidate / "CLAUDE.md").lstat()
    except OSError as error:
        _fail("E_NATIVE_EVIDENCE", f"selected repository lacks a regular native CLAUDE.md: {error}")
    if stat.S_ISLNK(instruction_info.st_mode) or not stat.S_ISREG(instruction_info.st_mode):
        _fail("E_NATIVE_EVIDENCE", "selected repository lacks a regular native CLAUDE.md")
    return candidate


def _instruction_paths(root: Path, repository: Path) -> tuple[str, ...]:
    """Return the child instruction files this launch must account for."""
    prefix = repository.relative_to(root).as_posix()
    paths: list[str] = []
    for name in REPOSITORY_INSTRUCTION_FILES:
        candidate = repository / name
        try:
            info = candidate.lstat()
        except OSError:
            if name == "CLAUDE.md":
                _fail("E_NATIVE_EVIDENCE", f"selected repository lacks {name}: {prefix}")
            continue
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            _fail("E_NATIVE_EVIDENCE", f"child instruction source is not a regular file: {prefix}/{name}")
        paths.append(f"{prefix}/{name}")
    return tuple(paths)


class ClaudeLauncherAdapter:
    """Claude-specific preflight, classification, and delivery boundary."""

    def __init__(
        self, *, runner: CommandRunner = subprocess_runner, client_command: str = "claude",
        strict_trust_identity: bool = False,
        inspector: Callable[..., native.ClaudeNativeLoad] = native.inspect_native_load,
    ) -> None:
        self.runner = runner
        self.client_command = client_command
        # The production wrapper opts in.  Offline fixtures keep the resolver
        # and kernel independent of a host Git/configuration environment while
        # the only public canonical launcher cannot bypass W9d2 preflight.
        self.strict_trust_identity = strict_trust_identity
        # The native-load inspection is a separate real client launch.  Tests
        # supply a recorded capture through this seam; it is never a substitute
        # for evidence in a canonical launch.
        self.inspector = inspector

    # ---------------------------------------------------------------- preflight

    def preflight(
        self, *, workspace_root: Path, repository_ids: Sequence[str], project: str | None = None,
        authorization_trust_store: Path | None = None,
    ) -> ClaudePreflight:
        """Prove client, trust, configuration, scope, and native load, in order."""
        if not CONTAINER_MARKER.is_file():
            _fail("E_UNSUPPORTED_MODE", "only the evidenced devcontainer Claude rows are canonical")
        root = find_workspace_root(workspace_root)
        if root != workspace_root.resolve(strict=True):
            _fail("E_SCOPE_UNAVAILABLE", "canonical launcher root differs from its marker root")
        artifact = _capability_artifact(root)
        identity, version, binary_sha256 = native.client_identity(self.client_command)
        self._verify_client(artifact, identity, version, binary_sha256)
        try:
            validate_claude_settings(root)
        except ClaudeSettingsValidationError as error:
            _fail("E_TRUST", f"project Claude settings are not the reviewed layer: {error}")
        settings = native.settings_identity(root)
        repositories = tuple(_registered_repository(root, item) for item in repository_ids)
        scope = self._launch_scope(root, project, repositories)
        state = native.trust_state(scope)
        if state != "trusted":
            # Trust is a recorded human action.  A launcher that granted its own
            # would defeat the gate, so an unrecorded scope blocks the task.
            _fail("E_TRUST", f"the Claude launch scope is {state}, not trusted")
        load = self.inspector(
            workspace_root=root, project=scope, client_command=self.client_command,
        )
        if load.config_sha256 != w2b1.canonical_sha256(settings):
            _fail("E_TRUST", "the Claude settings layer changed during native-load inspection")
        if load.client_sha256 != binary_sha256 or load.trust_state != state:
            _fail("E_CAPABILITY", "the Claude client or trust state changed during inspection")
        trust_identity: Mapping[str, Any] = {}
        if self.strict_trust_identity:
            trust_identity = build_trust_identity(
                workspace_root=root, selected_repositories=repositories,
                capability_path=CAPABILITY_EVIDENCE_PATH, agent="claude",
                claude_binary=Path(identity), claude_version=version,
                project_trust_scope=scope,
                authorization_trust_store=authorization_trust_store,
            )
        return ClaudePreflight(
            workspace_root=root, launch_scope=scope,
            project="." if scope == root else scope.relative_to(root).as_posix(),
            repositories=repositories, repository_ids=tuple(repository_ids),
            client_identity=identity, client_version=version, client_sha256=binary_sha256,
            settings=settings, config_sha256=load.config_sha256, trust_state=state,
            load=load, trust_identity=trust_identity,
        )

    @staticmethod
    def _verify_client(
        artifact: Mapping[str, Any], identity: str, version: str, binary_sha256: str,
    ) -> None:
        client = artifact.get("client")
        if not isinstance(client, dict):
            _fail("E_CAPABILITY", "Claude capability evidence has no frozen client identity")
        if binary_sha256 != client.get("sha256"):
            _fail("E_CAPABILITY", "the installed Claude client changed since its capability evidence")
        if identity != client.get("resolved_path"):
            _fail("E_CAPABILITY", "the installed Claude client path differs from its capability evidence")
        frozen_version = client.get("version")
        if not isinstance(frozen_version, str) or not version.startswith(frozen_version):
            _fail("E_CAPABILITY", "the installed Claude client version differs from its capability evidence")

    @staticmethod
    def _launch_scope(root: Path, project: str | None, repositories: Sequence[Path]) -> Path:
        """Return the launch directory; a child scope must be a selected child."""
        if project is None:
            return root
        try:
            w2b1._identifier(project, "project argument")
        except w2b1.AgentContextError:
            _fail("E_USAGE", "project argument is not a canonical identifier")
        selected = {repository.name: repository for repository in repositories}
        if project not in selected:
            _fail("E_SCOPE_UNAVAILABLE", "the launch scope must be one selected registered repository")
        return selected[project]

    # --------------------------------------------------------------- resolution

    def resolve_repositories(
        self, *, workspace_root: Path, repository_ids: Sequence[str], tasks: Sequence[str] = (),
        operations: Sequence[str] = (), authorizations: Sequence[Mapping[str, Any]] = (),
        verified_authorization_provenance: Sequence[Mapping[str, Any]] = (),
        authorization_trust_store: Path | None = None, project: str | None = None,
        generation: int = 0, preflight: ClaudePreflight | None = None,
    ) -> tuple[ClaudeResolution, ClaudePreflight]:
        """Resolve, classify, and select a channel without starting a user task."""
        canonical_repositories = _unique_identifiers(repository_ids, "repository")
        canonical_tasks = _unique_identifiers(tasks, "task")
        canonical_operations = _unique_identifiers(operations, "operation")
        if self.strict_trust_identity and authorizations and not verified_authorization_provenance:
            _fail("E_AUTHORIZATION", "canonical launch requires externally verified authorization provenance")
        if preflight is None:
            preflight = self.preflight(
                workspace_root=workspace_root, repository_ids=canonical_repositories,
                project=project, authorization_trust_store=authorization_trust_store,
            )
        root = preflight.workspace_root
        rows = _capability_rows(_capability_artifact(root))
        round_trip = (
            _hook_channel_evidence(root, rows) if HOOK_ROUND_TRIP_EVIDENCE is not None else None
        )
        metadata = _load_json(root / ".workspace" / "policy.metadata.json")
        instruction_sources, injected_instructions = self._classified_instructions(preflight)
        injection_evidence = native.build_injection_evidence(
            preflight.load, generation=generation,
            paths=self._injection_candidates(root, metadata, injected_instructions),
        )
        rejected: list[Mapping[str, str]] = []
        for row_id in REQUIRED_ROW_IDS:
            capability = rows[row_id]
            native_evidence = native.build_native_evidence(
                preflight.load, capability_row=capability.row,
                expected_client_sha256=preflight.client_sha256,
            )
            resolved = resolve_context(ResolutionRequest(
                root=root, registry=_load_json(root / ".workspace" / "repo-types.json"),
                policy_index=_load_json(root / ".workspace" / "policy.index.json"),
                policy_metadata=metadata, capability_row=capability.row,
                reviewed_tree=_reviewed_tree(root), agent="claude",
                platform=capability.row["platform"], mode=capability.row["mode"],
                repositories=canonical_repositories, tasks=canonical_tasks,
                operations=canonical_operations, authorizations=tuple(authorizations),
                verified_authorization_provenance=tuple(verified_authorization_provenance),
                native_evidence=native_evidence, injection_evidence=injection_evidence,
                instruction_sources=instruction_sources,
                other_model_visible_bootstrap_bytes=OTHER_MODEL_VISIBLE_BOOTSTRAP_BYTES,
                generation=generation,
            ))
            # The contract omits an injected entry only after the manifest and
            # the client-proven active set agree in both directions.
            native.verify_manifest_native_binding(resolved.manifest, native_evidence)
            if resolved.manifest["accounting"]["effective_hard_limit"] != capability.effective_hard_limit:
                _fail("E_CAPABILITY", f"resolved effective limit differs from frozen evidence: {row_id}")
            reasons = self._ineligible_reasons(capability, preflight, resolved)
            if not reasons:
                channel = capability.row["channel_id"]
                return ClaudeResolution(
                    capability=capability, channel_id=channel,
                    resolved=resolved, native_evidence=native_evidence,
                    injection_evidence=injection_evidence, rejected_rows=tuple(rejected),
                    round_trip_evidence_id=(
                        round_trip["round_trip_evidence_id"]
                        if channel == HOOK_CHANNEL_ID and round_trip is not None else None
                    ),
                ), preflight
            rejected.append({"row_id": row_id, "reason": "; ".join(reasons)})
        # Every row over budget is a budget failure; a row that fits but is not
        # wired is a channel failure.  Either way no task may begin.
        over_budget = all("E_BUDGET:" in item["reason"] for item in rejected)
        _fail(
            "E_BUDGET" if over_budget else "E_CHANNEL",
            "no verified Claude channel can carry this generation: "
            + "; ".join(f"{item['row_id']}: {item['reason']}" for item in rejected),
        )

    def _classified_instructions(
        self, preflight: ClaudePreflight,
    ) -> tuple[tuple[dict[str, str], ...], tuple[str, ...]]:
        """Split the launch's instruction inventory into native and injected."""
        proven = set(preflight.native_source_sha256)
        injected: list[str] = []
        for repository in preflight.repositories:
            for path in _instruction_paths(preflight.workspace_root, repository):
                if path not in proven:
                    injected.append(path)
        sources = native.instruction_sources(
            preflight.load, repositories=preflight.repository_ids,
            injected_paths=tuple(sorted(injected)),
        )
        return sources, tuple(sorted(injected))

    @staticmethod
    def _injection_candidates(
        root: Path, metadata: Mapping[str, Any], injected_instructions: Sequence[str],
    ) -> tuple[str, ...]:
        """Return every source whose absence from native discovery must be proved."""
        units = metadata.get("units")
        if not isinstance(units, list):
            _fail("E_SCHEMA", "policy metadata units are missing")
        candidates: set[str] = set(injected_instructions)
        for unit in units:
            path = unit.get("path") if isinstance(unit, dict) else None
            if not isinstance(path, str):
                _fail("E_SCHEMA", "policy metadata path is invalid")
            candidates.add(path)
        return tuple(sorted(candidates))

    def _ineligible_reasons(
        self, capability: ClaudeCapabilityRow, preflight: ClaudePreflight, resolved: ResolvedContext,
    ) -> tuple[str, ...]:
        """Return every reason this row cannot deliver; empty means it may.

        The shared validator is the budget oracle, so ``model_visible_total`` —
        not envelope size — decides whether a row fits, exactly as Step 12.1's
        correction and Step 12.2's refinement require.

        Step 12.4 makes the injection authority launcher-owned: the hook is
        registered for one launch through the launcher's own ``--settings``
        file, never in the workspace.  A ``--settings`` hook *merges* with the
        project, local, and user layers rather than replacing them, so any
        ``additionalContext`` event already registered there is a foreign
        second authority and makes every row ineligible.
        """
        registered = set(preflight.settings.get("registered_hook_events") or ())
        foreign = registered.intersection(native.DUPLICATE_INJECTION_EVENTS)
        if len(foreign) > 1:
            # Step 12.1 measured that SessionStart carries additionalContext
            # exactly as UserPromptSubmit does; both would deliver two copies.
            _fail("E_CHANNEL", "SessionStart and UserPromptSubmit would both inject additionalContext")
        channel = capability.row["channel_id"]
        reasons: list[str] = []
        try:
            validate_resolved(
                workspace=preflight.workspace_root, manifest=resolved.manifest,
                envelope=resolved.envelope, envelope_bytes=resolved.envelope_bytes,
                capability_row=capability.row, reviewed_tree=resolved.manifest["reviewed_tree"],
                capability_evidence_id=capability.capability_evidence_id, channel_id=channel,
            )
        except w2b1.AgentContextError as error:
            if error.code != "E_BUDGET":
                raise
            reasons.append(f"E_BUDGET: {error.message}")
        if channel == HOOK_CHANNEL_ID:
            if HOOK_ROUND_TRIP_EVIDENCE is None:
                reasons.append("E_CHANNEL: no byte-exact hook round-trip evidence is frozen (Step 12.4)")
            elif foreign:
                reasons.append(
                    "E_CHANNEL: a settings-registered additionalContext hook is a second "
                    "injection authority this launcher does not own"
                )
        elif channel == FULL_CONTENT_CHANNEL_ID:
            if foreign:
                reasons.append("E_CHANNEL: a registered additionalContext hook would inject a second copy")
        else:
            _fail("E_CHANNEL", f"frozen row has no implemented Claude channel: {capability.row_id}")
        return tuple(reasons)

    # ----------------------------------------------------------------- delivery

    def prepare_and_handoff_repositories(
        self, *, workspace_root: Path, repository_ids: Sequence[str], prompt: str,
        tasks: Sequence[str] = (), operations: Sequence[str] = (),
        authorizations: Sequence[Mapping[str, Any]] = (),
        verified_authorization_provenance: Sequence[Mapping[str, Any]] = (),
        authorization_trust_store: Path | None = None, project: str | None = None,
        launch_id: str | None = None, fresh_runtime_dir: Path | None = None,
        kernel: DeliveryKernel | None = None,
    ) -> DeliveryResult:
        """Perform exactly one full-content handoff for a resolved generation."""
        if not isinstance(prompt, str) or not prompt:
            _fail("E_USAGE", "a non-empty Claude user prompt is required")
        resolution, preflight = self.resolve_repositories(
            workspace_root=workspace_root, repository_ids=repository_ids, tasks=tasks,
            operations=operations, authorizations=authorizations,
            verified_authorization_provenance=verified_authorization_provenance,
            authorization_trust_store=authorization_trust_store, project=project,
        )
        # The client honors --session-id, so the launcher owns the session
        # identity before invocation and the transport only confirms it.
        client_session_id = str(uuid.uuid4())
        request = self._delivery_request(
            preflight, resolution, client_session_id=client_session_id,
            launch_id=launch_id or f"launch-{secrets.token_hex(16)}",
            authorization_trust_store=authorization_trust_store,
        )
        delivery_kernel = kernel or DeliveryKernel()
        prepared = (
            delivery_kernel.fresh(fresh_runtime_dir, request)
            if fresh_runtime_dir is not None
            else delivery_kernel.prepare(request)
        )
        transport = self._transport(
            preflight, resolution, prompt, client_session_id, authorization_trust_store,
            kernel=delivery_kernel, runtime_dir=prepared.runtime_dir,
            launch_id=prepared.session["launch_id"],
        )
        return delivery_kernel.handoff(prepared, transport)

    def fresh_and_handoff_repositories(
        self, *, workspace_root: Path, prior_runtime_dir: Path, repository_ids: Sequence[str],
        prompt: str, **kwargs: Any,
    ) -> DeliveryResult:
        """Invalidate one validated prior runtime and hand off generation zero."""
        return self.prepare_and_handoff_repositories(
            workspace_root=workspace_root, repository_ids=repository_ids, prompt=prompt,
            fresh_runtime_dir=prior_runtime_dir, **kwargs,
        )

    def resume_and_handoff_repositories(
        self, *, workspace_root: Path, runtime_dir: Path, repository_ids: Sequence[str], prompt: str,
        tasks: Sequence[str] = (), operations: Sequence[str] = (),
        authorizations: Sequence[Mapping[str, Any]] = (),
        verified_authorization_provenance: Sequence[Mapping[str, Any]] = (),
        authorization_trust_store: Path | None = None, project: str | None = None,
        launch_id: str | None = None, kernel: DeliveryKernel | None = None,
    ) -> DeliveryResult:
        """Resume only a completed, identity-matched Claude session once."""
        if not isinstance(prompt, str) or not prompt:
            _fail("E_USAGE", "a non-empty Claude user prompt is required")
        delivery_kernel = kernel or DeliveryKernel()
        prior = delivery_kernel._authoritative_session(runtime_dir)
        if prior["state"] != "COMPLETED":
            _fail("E_LIFECYCLE", "only a completed generation may resume")
        resolution, preflight = self.resolve_repositories(
            workspace_root=workspace_root, repository_ids=repository_ids, tasks=tasks,
            operations=operations, authorizations=authorizations,
            verified_authorization_provenance=verified_authorization_provenance,
            authorization_trust_store=authorization_trust_store, project=project,
            generation=prior["generation"] + 1,
        )
        request = self._delivery_request(
            preflight, resolution, client_session_id=prior["client_session_id"],
            launch_id=launch_id or prior["launch_id"],
            authorization_trust_store=authorization_trust_store,
        )
        prepared = delivery_kernel.resume(runtime_dir, request)
        transport = self._transport(
            preflight, resolution, prompt, prior["client_session_id"],
            authorization_trust_store, resume=True, kernel=delivery_kernel,
            runtime_dir=prepared.runtime_dir, launch_id=prepared.session["launch_id"],
        )
        return delivery_kernel.handoff(prepared, transport)

    def _delivery_request(
        self, preflight: ClaudePreflight, resolution: ClaudeResolution, *, client_session_id: str,
        launch_id: str, authorization_trust_store: Path | None,
    ) -> DeliveryRequest:
        return DeliveryRequest(
            workspace_root=preflight.workspace_root, resolved=resolution.resolved,
            capability_row=resolution.capability.row, trusted=True,
            reviewed_tree=resolution.resolved.manifest["reviewed_tree"],
            capability_evidence_id=resolution.capability.capability_evidence_id,
            client_session_id=client_session_id, channel_id=resolution.channel_id,
            trust_identity_sha256=preflight.trust_identity.get("trust_identity_sha256", "0" * 64),
            launch_id=launch_id,
            trust_identity=preflight.trust_identity if self.strict_trust_identity else None,
            trust_identity_kwargs=(
                self._trust_identity_kwargs(preflight, authorization_trust_store)
                if self.strict_trust_identity else None
            ),
        )

    def _transport(
        self, preflight: ClaudePreflight, resolution: ClaudeResolution, prompt: str,
        client_session_id: str, authorization_trust_store: Path | None, *, resume: bool = False,
        kernel: DeliveryKernel | None = None, runtime_dir: Path | None = None,
        launch_id: str | None = None,
    ) -> ClaudeCliTransport:
        accounting = resolution.resolved.manifest["accounting"]
        return ClaudeCliTransport(
            runner=self.runner, client_command=self.client_command,
            workspace_root=preflight.workspace_root, launch_scope=preflight.launch_scope,
            prompt=prompt, client_session_id=client_session_id,
            expected_native_sources=dict(preflight.native_source_sha256),
            expected_config_sha256=preflight.config_sha256,
            integrity_check=lambda: self._verify_live_integration(
                preflight, authorization_trust_store=authorization_trust_store,
            ),
            resume=resume,
            # The hook channel arms a separate process, so it needs the runtime
            # session the kernel owns and the exact generation identity.
            kernel=kernel, runtime_dir=runtime_dir, launch_id=launch_id,
            generation=resolution.resolved.envelope["generation"],
            manifest_id=resolution.resolved.manifest["manifest_id"],
            capability_evidence_id=resolution.capability.capability_evidence_id,
            verified_channel_limit=resolution.capability.row["verified_channel_limit"],
            effective_hard_limit=accounting["effective_hard_limit"],
            model_visible_total=accounting["model_visible_total"],
            round_trip_evidence_id=resolution.round_trip_evidence_id,
        )

    def _verify_live_integration(
        self, preflight: ClaudePreflight, *, authorization_trust_store: Path | None = None,
    ) -> None:
        """Reject any drift between preflight and the actual delivery boundary."""
        root = preflight.workspace_root
        try:
            validate_claude_settings(root)
        except ClaudeSettingsValidationError as error:
            _fail("E_TRUST", f"project Claude settings changed after preflight: {error}")
        if w2b1.canonical_sha256(native.settings_identity(root)) != preflight.config_sha256:
            _fail("E_TRUST", "the Claude settings or hook layer changed after preflight")
        identity, version, binary_sha256 = native.client_identity(self.client_command)
        if (identity, version, binary_sha256) != (
            preflight.client_identity, preflight.client_version, preflight.client_sha256
        ):
            _fail("E_CAPABILITY", "the installed Claude client changed after preflight")
        if native.trust_state(preflight.launch_scope) != preflight.trust_state:
            _fail("E_TRUST", "the Claude project trust state changed after preflight")
        for path, digest in preflight.native_source_sha256.items():
            if _sha256(root / path, code="E_NATIVE_EVIDENCE") != digest:
                _fail("E_NATIVE_EVIDENCE", "a proven native instruction source changed after inspection")
        if self.strict_trust_identity:
            validate_trust(
                trust_identity_sha256=preflight.trust_identity["trust_identity_sha256"],
                trust_identity=preflight.trust_identity,
                trust_identity_kwargs=self._trust_identity_kwargs(
                    preflight, authorization_trust_store,
                ),
            )

    @staticmethod
    def _trust_identity_kwargs(
        preflight: ClaudePreflight, authorization_trust_store: Path | None,
    ) -> dict[str, Any]:
        return {
            "workspace_root": preflight.workspace_root,
            "selected_repositories": tuple(preflight.repositories),
            "capability_path": CAPABILITY_EVIDENCE_PATH,
            "agent": "claude",
            "claude_binary": Path(preflight.client_identity),
            "claude_version": preflight.client_version,
            "project_trust_scope": preflight.launch_scope,
            "authorization_trust_store": authorization_trust_store,
        }


@dataclass
class ClaudeCliTransport(TransportAdapter):
    """Run one real Claude pre-task gate and return metadata-only confirmation.

    Both wired channels deliver the identical serialized envelope and differ
    only in transport: the full-content row passes it as one
    ``--append-system-prompt`` argument, and the hook row arms the launcher's
    own ``UserPromptSubmit`` gate, which returns it as ``additionalContext``
    exactly once per launcher-controlled generation.
    """

    runner: CommandRunner
    client_command: str
    workspace_root: Path
    launch_scope: Path
    prompt: str
    client_session_id: str
    expected_native_sources: Mapping[str, str]
    expected_config_sha256: str
    integrity_check: Callable[[], None]
    resume: bool = False
    output: bytes = b""
    # Hook-channel state; the full-content channel needs none of it.
    kernel: DeliveryKernel | None = None
    runtime_dir: Path | None = None
    launch_id: str | None = None
    generation: int = 0
    manifest_id: str = ""
    capability_evidence_id: str = ""
    verified_channel_limit: int = 0
    effective_hard_limit: int = 0
    model_visible_total: int = 0
    round_trip_evidence_id: str | None = None

    def deliver(self, *, payload: bytes, envelope_sha256: str, channel_id: str) -> TransportConfirmation:
        if channel_id not in (FULL_CONTENT_CHANNEL_ID, HOOK_CHANNEL_ID):
            # Only the two rows Step 12.1 measured and Steps 12.3/12.4 wired may
            # ever reach a client invocation.
            _fail("E_CHANNEL", "Claude transport received an unwired or unverified channel")
        try:
            content = payload.decode("utf-8")
        except UnicodeDecodeError:
            _fail("E_SOURCE", "serialized envelope must be UTF-8")
        self.integrity_check()
        for path, digest in self.expected_native_sources.items():
            if _sha256(self.workspace_root / path, code="E_NATIVE_EVIDENCE") != digest:
                _fail("E_NATIVE_EVIDENCE", "native instruction source changed before transport")
        session_argument = ("--resume", self.client_session_id) if self.resume else (
            "--session-id", self.client_session_id
        )
        if channel_id == HOOK_CHANNEL_ID:
            settings = self._arm_hook_channel(payload, envelope_sha256)
            command = (
                self.client_command, "-p", "--output-format", "json",
                *session_argument, "--settings", str(settings), self.prompt,
            )
        else:
            command = (
                self.client_command, "-p", "--output-format", "json",
                *session_argument, "--append-system-prompt", content, self.prompt,
            )
        result = self.runner(command, self.launch_scope)
        self.output = result.stdout
        if result.returncode != 0:
            _fail("E_CHANNEL", "Claude execution did not confirm the pre-task handoff")
        if channel_id == HOOK_CHANNEL_ID:
            self._verify_injection_claim(envelope_sha256, len(payload))
        session_id = _reported_session_id(result.stdout)
        if session_id != self.client_session_id:
            _fail("E_LIFECYCLE", "Claude reported a different session identity than the launcher owned")
        return TransportConfirmation(envelope_sha256, len(payload), session_id)

    # ------------------------------------------------------------- hook channel

    def _hook_runtime(self) -> tuple[DeliveryKernel, Path]:
        if self.kernel is None or self.runtime_dir is None or self.launch_id is None:
            _fail("E_CHANNEL", "the Claude hook channel requires a prepared runtime generation")
        return self.kernel, self.runtime_dir

    def _gate_command(self, runtime_dir: Path) -> str:
        """Build the one shell command the launcher's own settings registers."""
        gate = self.workspace_root / GATE_MODULE_PATH
        try:
            info = gate.lstat()
            gate.resolve(strict=True).relative_to(self.workspace_root)
        except (OSError, ValueError) as error:
            _fail("E_CHANNEL", f"the reviewed Claude hook gate is unavailable: {error}")
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            _fail("E_CHANNEL", "the reviewed Claude hook gate is not a regular file")
        return " ".join(
            shlex.quote(item)
            for item in (sys.executable, str(gate), "--runtime-dir", str(runtime_dir))
        )

    def _arm_hook_channel(self, payload: bytes, envelope_sha256: str) -> Path:
        """Persist the exact envelope and the one-launch hook registration.

        The gate runs as a separate process, so the payload cannot be handed to
        it in memory.  Both artifacts are created no-replace inside the kernel's
        owner-only runtime session, which keeps containment, permissions, and
        cleanup under a single policy.
        """
        kernel, runtime_dir = self._hook_runtime()
        if self.round_trip_evidence_id is None:
            _fail("E_CHANNEL", "the Claude hook channel requires frozen round-trip evidence")
        if len(payload) > self.verified_channel_limit:
            # The client silently substitutes a preview plus a file pointer
            # above the measured boundary, which is never delivery.
            _fail("E_CHANNEL", "the envelope exceeds the verified hook channel limit")
        state = {
            "schema_version": 1,
            "channel_id": HOOK_CHANNEL_ID,
            "launch_id": self.launch_id,
            "client_session_id": self.client_session_id,
            "generation": self.generation,
            "manifest_id": self.manifest_id,
            "envelope_sha256": envelope_sha256,
            "envelope_bytes": len(payload),
            "verified_channel_limit": self.verified_channel_limit,
            "effective_hard_limit": self.effective_hard_limit,
            "model_visible_total": self.model_visible_total,
            "round_trip_evidence_id": self.round_trip_evidence_id,
            "capability_evidence_id": self.capability_evidence_id,
            "launch_scope": str(self.launch_scope),
        }
        settings = {
            "hooks": {
                gate.HOOK_EVENT: [
                    {"hooks": [{"type": "command", "command": self._gate_command(runtime_dir)}]}
                ]
            }
        }
        # A resumed session arms its next generation in the same session
        # directory, so the armed payload is replaced while the per-generation
        # claim — the exactly-once authority — stays no-replace.
        kernel.write_channel_artifact(
            runtime_dir, gate.CHANNEL_ENVELOPE_ARTIFACT, payload, replace=True,
        )
        kernel.write_channel_artifact(
            runtime_dir, gate.CHANNEL_STATE_ARTIFACT, w2b1.canonical_bytes(state), replace=True,
        )
        return kernel.write_channel_artifact(
            runtime_dir, gate.CHANNEL_SETTINGS_ARTIFACT, w2b1.canonical_bytes(settings),
            replace=True,
        )

    def _verify_injection_claim(self, envelope_sha256: str, delivered_bytes: int) -> None:
        """Prove the launcher's own gate delivered this generation exactly once."""
        kernel, runtime_dir = self._hook_runtime()
        try:
            raw = kernel.read_channel_artifact(
                runtime_dir, gate.claim_artifact(self.generation)
            )
            claim = w2b1.parse_strict_json(raw)
        except w2b1.AgentContextError as error:
            _fail(
                "E_CHANNEL",
                f"the pre-task injection authority did not deliver this generation: {error.message}",
            )
        expected = {
            "schema_version": 1, "channel_id": HOOK_CHANNEL_ID, "launch_id": self.launch_id,
            "client_session_id": self.client_session_id, "generation": self.generation,
            "manifest_id": self.manifest_id, "envelope_sha256": envelope_sha256,
            "delivered_bytes": delivered_bytes,
            "round_trip_evidence_id": self.round_trip_evidence_id,
        }
        if not isinstance(claim, dict) or set(claim) != set(expected) | {"claimed_at"}:
            _fail("E_CHANNEL", "the injection claim does not have its closed shape")
        if any(claim[key] != value for key, value in expected.items()):
            _fail("E_CHANNEL", "the injection claim does not match the armed generation exactly")


def _reported_session_id(raw: bytes) -> str:
    """Read the client's own session identity from its JSON result."""
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        _fail("E_LIFECYCLE", f"Claude did not return a JSON result: {error}")
    value = result.get("session_id") if isinstance(result, dict) else None
    try:
        w2b1._identifier(value, "Claude session_id")
    except w2b1.AgentContextError:
        _fail("E_LIFECYCLE", "Claude did not expose a valid session identity")
    return value


__all__ = [
    "CAPABILITY_EVIDENCE_PATH",
    "CAPABILITY_EVIDENCE_SHA256",
    "FULL_CONTENT_CHANNEL_ID",
    "GATE_MODULE_PATH",
    "HOOK_CHANNEL_EVIDENCE_PATH",
    "HOOK_CHANNEL_EVIDENCE_SHA256",
    "HOOK_CHANNEL_ID",
    "HOOK_ROUND_TRIP_EVIDENCE",
    "REQUIRED_ROW_IDS",
    "ClaudeCapabilityRow",
    "ClaudeCliTransport",
    "ClaudeLauncherAdapter",
    "ClaudePreflight",
    "ClaudeResolution",
    "CommandResult",
    "find_workspace_root",
]
