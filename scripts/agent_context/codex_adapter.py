"""Phase 6.3 Codex non-interactive delivery boundary.

Only the frozen devcontainer/non-interactive capability row is implemented.
The adapter discovers a workspace solely through ``.m8-workspace-root``,
admits one or more registered direct children, proves the active root/child
``AGENTS.md`` bytes with ``codex debug prompt-input``, and sends the resolver's
exact JCS envelope through the evidence-backed ``developer_instructions``
override.  Inputs are identifiers, never paths; multi-repository authorization
is delegated to the frozen resolver contract.

The shared kernel remains the owner of source-drift checks, immutable journal
state, and conservative submission semantics. This module neither serializes
envelopes nor treats model output as context acceptance or exactly-once proof.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_context import w2b1
from agent_context.delivery_kernel import (
    DeliveryKernel,
    DeliveryRequest,
    DeliveryResult,
    TransportAdapter,
    TransportConfirmation,
)
from agent_context.resolve_context import ResolutionRequest, ResolvedContext, resolve_context
from agent_context.shared_validation import validate_trust
from agent_context.trust_identity import build_trust_identity


MARKER_NAME = ".m8-workspace-root"
MARKER_VALUE = "m8-workspace-v2\n"
CAPABILITY_EVIDENCE_PATH = (
    "scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md"
)
CAPABILITY_EVIDENCE_SHA256 = "d921bcdbc26cb4e65ffc6f0ab642d191d543987594df5291cc904a01a4562e7b"
EXPECTED_CODEX_VERSION = "codex-cli 0.144.6"
EXPECTED_CODEX_SHA256 = "134063e133f0b4244fa3b251acf973d4fe4b4aeeacbdc135211bf480f59f1477"

CURRENT_CODEX_CAPABILITY: dict[str, object] = {
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


def _fail(code: str, message: str) -> None:
    raise w2b1.AgentContextError(code, message)


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        _fail("E_SOURCE", f"cannot hash required source: {error}")


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _unique_identifiers(values: Sequence[str], field: str) -> tuple[str, ...]:
    """Return a canonical non-empty repository/task/operation argument set."""
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
class CommandResult:
    """Captured process data; raw data is held only in memory."""

    returncode: int
    stdout: bytes
    stderr: bytes = b""


CommandRunner = Callable[[Sequence[str], Path], CommandResult]


def subprocess_runner(command: Sequence[str], cwd: Path) -> CommandResult:
    completed = subprocess.run(
        list(command), cwd=cwd, check=False, capture_output=True,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


@dataclass(frozen=True)
class CodexNativeInspection:
    """In-memory result of the evidence-backed native-source inspection."""

    client_identity: str
    client_version: str
    config_sha256: str
    source_sha256: Mapping[str, str]
    active_source_sha256: Mapping[str, str]
    # Transient preflight data only; it never reaches persistent runtime state.
    visible_text: str
    # Complete reviewed-tree/environment identity captured before resolution.
    trust_identity: Mapping[str, Any]


def find_workspace_root(start: Path) -> Path:
    """Find only the nearest exact marker; .git and environment fallbacks are forbidden."""
    try:
        current = start.resolve(strict=True)
    except OSError as error:
        _fail("E_SCOPE_UNAVAILABLE", f"launcher start path is unavailable: {error}")
    if current.is_file():
        current = current.parent
    while True:
        marker = current / MARKER_NAME
        try:
            if marker.is_file() and not marker.is_symlink() and marker.read_bytes() == MARKER_VALUE.encode():
                return current
        except OSError as error:
            _fail("E_SCOPE_UNAVAILABLE", f"workspace marker cannot be inspected: {error}")
        if current.parent == current:
            _fail("E_SCOPE_UNAVAILABLE", "no canonical .m8-workspace-root ancestor exists")
        current = current.parent


class CodexDeliveryAdapter:
    """Codex-specific preflight/resolution boundary for direct children."""

    def __init__(
        self, *, runner: CommandRunner = subprocess_runner, codex_command: str = "codex",
        strict_trust_identity: bool = False,
    ) -> None:
        self.runner = runner
        self.codex_command = codex_command
        # The production wrapper opts in.  This keeps W2b resolver fixtures
        # independent of a host Git/configuration environment while ensuring
        # the only public canonical launcher cannot bypass W9d2 preflight.
        self.strict_trust_identity = strict_trust_identity

    def resolve_single_repository(
        self, *, workspace_root: Path, repository_id: str,
    ) -> tuple[Path, ResolvedContext, CodexNativeInspection]:
        repositories, resolved, inspection = self.resolve_repositories(
            workspace_root=workspace_root, repository_ids=(repository_id,),
        )
        return repositories[0], resolved, inspection

    def resolve_repositories(
        self, *, workspace_root: Path, repository_ids: Sequence[str],
        tasks: Sequence[str] = (), operations: Sequence[str] = (),
        authorizations: Sequence[Mapping[str, Any]] = (),
        verified_authorization_provenance: Sequence[Mapping[str, Any]] = (),
        authorization_trust_store: Path | None = None,
        generation: int = 0,
    ) -> tuple[tuple[Path, ...], ResolvedContext, CodexNativeInspection]:
        """Resolve a canonical direct-child set without starting a user task.

        Repeated identifiers are deliberately rejected at the launcher
        boundary.  Canonical ordering is applied only after that check, so
        reordered equivalent invocations resolve to the same manifest while a
        duplicate cannot silently alter a requested scope.
        """
        canonical_repositories = _unique_identifiers(repository_ids, "repository")
        canonical_tasks = _unique_identifiers(tasks, "task")
        canonical_operations = _unique_identifiers(operations, "operation")
        if self.strict_trust_identity and authorizations and not verified_authorization_provenance:
            _fail("E_AUTHORIZATION", "canonical launch requires externally verified authorization provenance")
        root = find_workspace_root(workspace_root)
        if root != workspace_root.resolve(strict=True):
            _fail("E_SCOPE_UNAVAILABLE", "canonical launcher root differs from its marker root")
        repositories, inspection = self._preflight_repositories(
            root=root, repository_ids=canonical_repositories,
            authorization_trust_store=authorization_trust_store,
        )
        root = workspace_root.resolve(strict=True)
        metadata = _load_json(root / ".workspace" / "policy.metadata.json")
        injection_evidence = self._injection_evidence(
            root, metadata, inspection.visible_text, repositories, generation,
        )
        native_evidence = self._native_evidence(inspection)
        request = ResolutionRequest(
            root=root, registry=_load_json(root / ".workspace" / "repo-types.json"),
            policy_index=_load_json(root / ".workspace" / "policy.index.json"),
            policy_metadata=metadata, capability_row=CURRENT_CODEX_CAPABILITY,
            reviewed_tree=_reviewed_tree(root), agent="codex", platform="devcontainer",
            mode="non-interactive", repositories=canonical_repositories,
            tasks=canonical_tasks, operations=canonical_operations,
            authorizations=tuple(authorizations),
            verified_authorization_provenance=tuple(verified_authorization_provenance),
            native_evidence=native_evidence, injection_evidence=injection_evidence,
            instruction_sources=self._instruction_sources(root, canonical_repositories, repositories),
            other_model_visible_bootstrap_bytes=sum(
                (root / source).stat().st_size for source in inspection.active_source_sha256
            ),
            generation=generation,
        )
        return repositories, resolve_context(request), inspection

    def prepare_and_handoff(
        self, *, workspace_root: Path, repository_id: str, prompt: str,
        kernel: DeliveryKernel | None = None,
    ) -> DeliveryResult:
        if not isinstance(prompt, str) or not prompt:
            _fail("E_USAGE", "a non-empty Codex user prompt is required")
        return self.prepare_and_handoff_repositories(
            workspace_root=workspace_root, repository_ids=(repository_id,), prompt=prompt,
            kernel=kernel,
        )

    def prepare_and_handoff_repositories(
        self, *, workspace_root: Path, repository_ids: Sequence[str], prompt: str,
        tasks: Sequence[str] = (), operations: Sequence[str] = (),
        authorizations: Sequence[Mapping[str, Any]] = (),
        verified_authorization_provenance: Sequence[Mapping[str, Any]] = (),
        authorization_trust_store: Path | None = None,
        launch_id: str | None = None,
        fresh_runtime_dir: Path | None = None,
        kernel: DeliveryKernel | None = None,
    ) -> DeliveryResult:
        """Perform exactly one full-content handoff for a resolved generation."""
        if not isinstance(prompt, str) or not prompt:
            _fail("E_USAGE", "a non-empty Codex user prompt is required")
        repositories, resolved, inspection = self.resolve_repositories(
            workspace_root=workspace_root, repository_ids=repository_ids,
            tasks=tasks, operations=operations, authorizations=authorizations,
            verified_authorization_provenance=verified_authorization_provenance,
            authorization_trust_store=authorization_trust_store,
        )
        root = workspace_root.resolve(strict=True)
        trust_kwargs = (
            self._trust_identity_kwargs(root, repositories, inspection, authorization_trust_store)
            if self.strict_trust_identity else None
        )
        request = DeliveryRequest(
            workspace_root=root, resolved=resolved,
            capability_row=CURRENT_CODEX_CAPABILITY, trusted=True,
            reviewed_tree=resolved.manifest["reviewed_tree"],
            capability_evidence_id=w2b1.canonical_sha256(CURRENT_CODEX_CAPABILITY),
            # The actual client identity is learned from thread.started by the
            # transport and replaces this launch-owned pending value atomically.
            client_session_id="codex.pending", channel_id="cli-config-developer-instructions",
            trust_identity_sha256=inspection.trust_identity.get("trust_identity_sha256", "0" * 64),
            launch_id=launch_id,
            trust_identity=inspection.trust_identity if self.strict_trust_identity else None,
            trust_identity_kwargs=trust_kwargs,
        )
        transport = CodexExecTransport(
            runner=self.runner, codex_command=self.codex_command, repository=root,
            workspace_root=root, prompt=prompt, expected_native_sources=inspection.active_source_sha256,
            expected_config_sha256=inspection.config_sha256,
            integrity_check=lambda: self._verify_live_integration(
                root, inspection, authorization_trust_store=authorization_trust_store,
            ),
        )
        delivery_kernel = kernel or DeliveryKernel()
        prepared = (
            delivery_kernel.fresh(fresh_runtime_dir, request)
            if fresh_runtime_dir is not None
            else delivery_kernel.prepare(request)
        )
        return delivery_kernel.handoff(prepared, transport)

    def fresh_and_handoff_repositories(
        self, *, workspace_root: Path, prior_runtime_dir: Path,
        repository_ids: Sequence[str], prompt: str,
        tasks: Sequence[str] = (), operations: Sequence[str] = (),
        authorizations: Sequence[Mapping[str, Any]] = (),
        verified_authorization_provenance: Sequence[Mapping[str, Any]] = (),
        authorization_trust_store: Path | None = None,
        launch_id: str | None = None,
        kernel: DeliveryKernel | None = None,
    ) -> DeliveryResult:
        """Invalidate one validated prior runtime and hand off generation zero."""
        return self.prepare_and_handoff_repositories(
            workspace_root=workspace_root, repository_ids=repository_ids,
            prompt=prompt, tasks=tasks, operations=operations,
            authorizations=authorizations,
            verified_authorization_provenance=verified_authorization_provenance,
            authorization_trust_store=authorization_trust_store,
            launch_id=launch_id, fresh_runtime_dir=prior_runtime_dir, kernel=kernel,
        )

    def resume_and_handoff_repositories(
        self, *, workspace_root: Path, runtime_dir: Path, repository_ids: Sequence[str], prompt: str,
        tasks: Sequence[str] = (), operations: Sequence[str] = (),
        authorizations: Sequence[Mapping[str, Any]] = (),
        verified_authorization_provenance: Sequence[Mapping[str, Any]] = (),
        authorization_trust_store: Path | None = None,
        launch_id: str | None = None,
        kernel: DeliveryKernel | None = None,
    ) -> DeliveryResult:
        """Resume only a completed, identity-matched Codex thread once.

        The generation is derived from the authoritative journal-backed session;
        source and trust state are freshly resolved before the kernel permits a
        resume.  Ambiguous/failed sessions therefore cannot reach transport.
        """
        if not isinstance(prompt, str) or not prompt:
            _fail("E_USAGE", "a non-empty Codex user prompt is required")
        delivery_kernel = kernel or DeliveryKernel()
        prior = delivery_kernel._authoritative_session(runtime_dir)
        if prior["state"] != "COMPLETED":
            _fail("E_LIFECYCLE", "only a completed generation may resume")
        repositories, resolved, inspection = self.resolve_repositories(
            workspace_root=workspace_root, repository_ids=repository_ids, tasks=tasks,
            operations=operations, authorizations=authorizations,
            verified_authorization_provenance=verified_authorization_provenance,
            authorization_trust_store=authorization_trust_store,
            generation=prior["generation"] + 1,
        )
        root = workspace_root.resolve(strict=True)
        trust_kwargs = (
            self._trust_identity_kwargs(root, repositories, inspection, authorization_trust_store)
            if self.strict_trust_identity else None
        )
        request = DeliveryRequest(
            workspace_root=root, resolved=resolved, capability_row=CURRENT_CODEX_CAPABILITY,
            trusted=True, reviewed_tree=resolved.manifest["reviewed_tree"],
            capability_evidence_id=w2b1.canonical_sha256(CURRENT_CODEX_CAPABILITY),
            client_session_id=prior["client_session_id"], channel_id="cli-config-developer-instructions",
            trust_identity_sha256=inspection.trust_identity.get("trust_identity_sha256", "0" * 64),
            launch_id=launch_id,
            trust_identity=inspection.trust_identity if self.strict_trust_identity else None,
            trust_identity_kwargs=trust_kwargs,
        )
        prepared = delivery_kernel.resume(runtime_dir, request)
        transport = CodexExecTransport(
            runner=self.runner, codex_command=self.codex_command, repository=root,
            workspace_root=root, prompt=prompt, expected_native_sources=inspection.active_source_sha256,
            expected_config_sha256=inspection.config_sha256,
            integrity_check=lambda: self._verify_live_integration(
                root, inspection, authorization_trust_store=authorization_trust_store,
            ),
            resume_session_id=prior["client_session_id"],
        )
        return delivery_kernel.handoff(prepared, transport)

    def _preflight_repositories(
        self, *, root: Path, repository_ids: tuple[str, ...],
        authorization_trust_store: Path | None = None,
    ) -> tuple[tuple[Path, ...], CodexNativeInspection]:
        if not Path("/.dockerenv").is_file():
            _fail("E_UNSUPPORTED_MODE", "only the evidence-backed devcontainer mode is canonical")
        evidence = root / CAPABILITY_EVIDENCE_PATH
        if _sha256(evidence) != CAPABILITY_EVIDENCE_SHA256:
            _fail("E_CAPABILITY", "Codex capability evidence changed and must be refreshed")
        config = root / ".codex" / "config.toml"
        self._verify_project_config(config)
        repositories = tuple(self._repository_path(root, repository_id) for repository_id in repository_ids)
        binary = self._verify_client_identity()
        self._verify_project_trust(root)
        inspection = self._inspect_native_sources(root, repositories, config)
        trust_identity: Mapping[str, Any] = {}
        if self.strict_trust_identity:
            trust_identity = build_trust_identity(
                workspace_root=root, selected_repositories=repositories,
                capability_path=CAPABILITY_EVIDENCE_PATH, codex_binary=binary,
                codex_version=inspection.client_version,
                authorization_trust_store=authorization_trust_store,
            )
        return repositories, CodexNativeInspection(
            client_identity=inspection.client_identity,
            client_version=inspection.client_version,
            config_sha256=inspection.config_sha256,
            source_sha256=inspection.source_sha256,
            active_source_sha256=inspection.active_source_sha256,
            visible_text=inspection.visible_text,
            trust_identity=trust_identity,
        )

    @staticmethod
    def _verify_project_config(config: Path) -> None:
        try:
            parsed_config = tomllib.loads(config.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            _fail("E_TRUST", f"Codex project configuration cannot be verified: {error}")
        if parsed_config != {
            "approval_policy": "on-request", "sandbox_mode": "workspace-write",
            "web_search": "cached", "windows": {"sandbox": "unelevated"},
        }:
            _fail("E_TRUST", "Codex project configuration differs from frozen least-privilege settings")

    def _verify_live_integration(
        self, root: Path, inspection: CodexNativeInspection,
        *, authorization_trust_store: Path | None = None,
    ) -> None:
        """Reject drift between native inspection and the actual exec boundary."""
        config = root / ".codex" / "config.toml"
        self._verify_project_config(config)
        if _sha256(config) != inspection.config_sha256:
            _fail("E_TRUST", "Codex project configuration changed after preflight")
        binary = self._verify_client_identity()
        self._verify_project_trust(root)
        for path, digest in inspection.source_sha256.items():
            if _sha256(root / path) != digest:
                _fail("E_NATIVE_EVIDENCE", "native instruction source changed after inspection")
        if self.strict_trust_identity:
            selected = tuple(
                root.joinpath(*entry["path"].split("/"))
                for entry in inspection.trust_identity["children"]
            )
            validate_trust(
                trust_identity_sha256=inspection.trust_identity["trust_identity_sha256"],
                trust_identity=inspection.trust_identity,
                trust_identity_kwargs=self._trust_identity_kwargs(
                    root, selected, inspection, authorization_trust_store,
                    codex_binary=binary,
                ),
            )

    @staticmethod
    def _trust_identity_kwargs(
        root: Path, repositories: Sequence[Path], inspection: CodexNativeInspection,
        authorization_trust_store: Path | None, *, codex_binary: Path | None = None,
    ) -> dict[str, Any]:
        return {
            "workspace_root": root,
            "selected_repositories": tuple(repositories),
            "capability_path": CAPABILITY_EVIDENCE_PATH,
            "codex_binary": codex_binary or Path(inspection.client_identity).resolve(strict=True),
            "codex_version": inspection.client_version,
            "authorization_trust_store": authorization_trust_store,
        }

    def preflight(self, *, workspace_root: Path, repository_id: str) -> tuple[Path, CodexNativeInspection]:
        """Backward-compatible single-repository preflight entry point."""
        root = find_workspace_root(workspace_root)
        if root != workspace_root.resolve(strict=True):
            _fail("E_SCOPE_UNAVAILABLE", "canonical launcher root differs from its marker root")
        repositories, inspection = self._preflight_repositories(
            root=root, repository_ids=_unique_identifiers((repository_id,), "repository"),
        )
        return repositories[0], inspection

    def _repository_path(self, root: Path, repository_id: str) -> Path:
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
            agents_info = (candidate / "AGENTS.md").lstat()
        except OSError as error:
            _fail("E_NATIVE_EVIDENCE", f"selected repository lacks a regular native AGENTS.md: {error}")
        if stat.S_ISLNK(agents_info.st_mode) or not stat.S_ISREG(agents_info.st_mode):
            _fail("E_NATIVE_EVIDENCE", "selected repository lacks a regular native AGENTS.md")
        return candidate

    def _verify_client_identity(self) -> Path:
        command_path = shutil_which(self.codex_command)
        if command_path is None or _sha256(command_path) != EXPECTED_CODEX_SHA256:
            _fail("E_CAPABILITY", "installed Codex binary identity changed")
        version = self.runner((self.codex_command, "--version"), Path.cwd())
        if version.returncode != 0 or version.stdout.decode("utf-8", "replace").strip() != EXPECTED_CODEX_VERSION:
            _fail("E_CAPABILITY", "installed Codex version changed")
        return command_path

    def _verify_project_trust(self, root: Path) -> None:
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        config = codex_home / "config.toml"
        try:
            projects = tomllib.loads(config.read_text(encoding="utf-8")).get("projects", {})
            project = projects.get(str(root)) if isinstance(projects, dict) else None
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            _fail("E_TRUST", f"Codex trusted-project record cannot be inspected: {error}")
        if not isinstance(project, dict) or project.get("trust_level") != "trusted":
            _fail("E_TRUST", "Codex project is not explicitly trusted")

    def _inspect_native_sources(
        self, root: Path, repositories: Sequence[Path], config: Path,
    ) -> CodexNativeInspection:
        source_paths = ("AGENTS.md", *[f"{repository.name}/AGENTS.md" for repository in repositories])
        source_sha256 = {path: _sha256(root / path) for path in source_paths}
        marker = "M8_CODEX_PREFLIGHT_20260720"
        override = f"developer_instructions={json.dumps(marker)}"
        result = self.runner(
            # Root is the one reviewed execution directory.  Inspecting a
            # child here would make its AGENTS.md native and invalidate W9d1.
            (self.codex_command, "-c", override, "debug", "prompt-input", marker), root,
        )
        if result.returncode != 0:
            _fail("E_NATIVE_EVIDENCE", "Codex native prompt inspection did not complete")
        try:
            messages = json.loads(result.stdout)
            texts = [part["text"] for message in messages for part in message.get("content", [])
                     if part.get("type") == "input_text" and isinstance(part.get("text"), str)]
        except (TypeError, ValueError, KeyError) as error:
            _fail("E_NATIVE_EVIDENCE", f"Codex native inspection output is invalid: {error}")
        if marker not in texts:
            _fail("E_CHANNEL", "Codex inspection did not preserve the direct full-content channel")
        try:
            root_text = (root / "AGENTS.md").read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            _fail("E_SOURCE", "root AGENTS.md is not strict UTF-8")
        if sum(text.count(root_text) for text in texts) != 1:
            _fail("E_NATIVE_EVIDENCE", "Codex did not prove exactly one active root instruction source")
        return CodexNativeInspection(
            client_identity=str(shutil_which(self.codex_command)), client_version=EXPECTED_CODEX_VERSION,
            config_sha256=_sha256(config), source_sha256=source_sha256,
            active_source_sha256={"AGENTS.md": source_sha256["AGENTS.md"]},
            visible_text="\n".join(texts),
            trust_identity={},
        )

    def _native_evidence(self, inspection: CodexNativeInspection) -> dict[str, Any]:
        evidence: dict[str, Any] = {
            "native_evidence_id": "0" * 64, "agent": "codex", "platform": "devcontainer",
            "mode": "non-interactive", "client_identity": inspection.client_identity,
            "client_version": inspection.client_version, "config_sha256": inspection.config_sha256,
            "capability_evidence_id": w2b1.canonical_sha256(CURRENT_CODEX_CAPABILITY),
            "trust_state": "trusted", "inspection_mechanism": "codex debug prompt-input",
            "captured_at": _timestamp(),
            "sources": [{"path": path, "sha256": digest} for path, digest in sorted(inspection.active_source_sha256.items())],
        }
        evidence["native_evidence_id"] = w2b1.canonical_sha256(
            {key: value for key, value in evidence.items() if key != "native_evidence_id"}
        )
        return evidence

    def _injection_evidence(
        self, root: Path, metadata: Mapping[str, Any], native_visible_text: str,
        repositories: Sequence[Path], generation: int,
    ) -> dict[str, Any]:
        units = metadata.get("units")
        if not isinstance(units, list):
            _fail("E_SCHEMA", "policy metadata units are missing")
        sources: dict[str, str] = {}
        for unit in units:
            path = unit.get("path") if isinstance(unit, dict) else None
            if not isinstance(path, str):
                _fail("E_SCHEMA", "policy metadata path is invalid")
            policy = root / path
            raw = policy.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                _fail("E_SOURCE", "injected policy source is not strict UTF-8")
            if text and text in native_visible_text:
                _fail("E_NATIVE_EVIDENCE", "policy source was unexpectedly active in Codex native discovery")
            sources[path] = hashlib.sha256(raw).hexdigest()
        for repository in repositories:
            path = f"{repository.name}/AGENTS.md"
            raw = (root / path).read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                _fail("E_SOURCE", "selected child AGENTS.md is not strict UTF-8")
            if text and text in native_visible_text:
                _fail("E_NATIVE_EVIDENCE", "selected child instruction was unexpectedly native")
            sources[path] = hashlib.sha256(raw).hexdigest()
        return {
            "generation": generation, "native_discovery_disabled": True,
            "exact_once_handoff_proven": True,
            "sources": [{"path": path, "sha256": digest} for path, digest in sorted(sources.items())],
        }

    @staticmethod
    def _instruction_sources(
        root: Path, repository_ids: Sequence[str], repositories: Sequence[Path],
    ) -> tuple[dict[str, str], ...]:
        children = sorted(
            zip(repository_ids, repositories, strict=True),
            key=lambda item: item[1].relative_to(root).as_posix(),
        )
        return tuple([
            {"policy_id": "instruction.root.agents", "repository_id": "$workspace",
             "scope_prefix": ".", "path": "AGENTS.md", "authority_tier": "workspace"},
            *[
                {"policy_id": f"instruction.{repository_id}.agents", "repository_id": repository_id,
                 "scope_prefix": repository.relative_to(root).as_posix(),
                 "path": f"{repository.relative_to(root).as_posix()}/AGENTS.md", "authority_tier": "repository"}
                for repository_id, repository in children
            ],
        ])


@dataclass
class CodexExecTransport(TransportAdapter):
    """Run one real Codex pre-task gate and return metadata-only confirmation."""

    runner: CommandRunner
    codex_command: str
    repository: Path
    workspace_root: Path
    prompt: str
    expected_native_sources: Mapping[str, str]
    expected_config_sha256: str
    integrity_check: Callable[[], None]
    resume_session_id: str | None = None
    output: bytes = b""

    def deliver(self, *, payload: bytes, envelope_sha256: str, channel_id: str) -> TransportConfirmation:
        if channel_id != "cli-config-developer-instructions":
            _fail("E_CHANNEL", "Codex transport received an unverified channel")
        try:
            content = payload.decode("utf-8")
        except UnicodeDecodeError:
            _fail("E_SOURCE", "serialized envelope must be UTF-8")
        self.integrity_check()
        config = self.workspace_root / ".codex" / "config.toml"
        if _sha256(config) != self.expected_config_sha256:
            _fail("E_TRUST", "Codex configuration changed before transport")
        for path, digest in self.expected_native_sources.items():
            if _sha256(self.workspace_root / path) != digest:
                _fail("E_NATIVE_EVIDENCE", "native instruction source changed before transport")
        override = f"developer_instructions={json.dumps(content, ensure_ascii=False)}"
        command: tuple[str, ...] = (
            self.codex_command, "-c", override, "exec", "--strict-config", "--json",
            "-C", str(self.repository), self.prompt,
        )
        if self.resume_session_id is not None:
            command = (
                self.codex_command, "-c", override, "exec", "resume", self.resume_session_id,
                "--strict-config", "--json", "-C", str(self.repository), self.prompt,
            )
        result = self.runner(command, self.repository)
        self.output = result.stdout
        if result.returncode != 0:
            _fail("E_CHANNEL", "Codex execution did not confirm the pre-task handoff")
        session_id = _thread_started_id(result.stdout)
        return TransportConfirmation(envelope_sha256, len(payload), session_id)


def _thread_started_id(raw: bytes) -> str:
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "thread.started":
            value = event.get("thread_id")
            try:
                w2b1._identifier(value, "Codex thread.started thread_id")
            except w2b1.AgentContextError:
                _fail("E_LIFECYCLE", "Codex thread.started has no valid session identity")
            return value
    _fail("E_LIFECYCLE", "Codex JSONL did not expose thread.started before completion")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = w2b1.parse_strict_json(path.read_bytes())
    except OSError as error:
        _fail("E_SOURCE", f"required workspace metadata is missing: {error}")
    if not isinstance(value, dict):
        _fail("E_SCHEMA", "workspace metadata must be a JSON object")
    return value


def _reviewed_tree(root: Path) -> dict[str, str]:
    result = subprocess_runner(("git", "rev-parse", "HEAD^{tree}"), root)
    if result.returncode != 0:
        _fail("E_TRUST", "reviewed workspace Git tree cannot be determined")
    value = result.stdout.decode("ascii", "strict").strip()
    if len(value) == 40:
        return {"algorithm": "git-sha1", "value": value}
    if len(value) == 64:
        return {"algorithm": "git-sha256", "value": value}
    _fail("E_TRUST", "reviewed Git tree identifier has an unsupported format")


def shutil_which(command: str) -> Path | None:
    """Resolve a command without accepting a caller-supplied path traversal."""
    import shutil

    found = shutil.which(command)
    return Path(found).resolve() if found else None
