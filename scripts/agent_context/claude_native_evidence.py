"""Step 12.2 Claude native-load evidence mechanism.

Step 12.1 proved that the installed client has *no* in-band inspection of its
own active project memory: ``-d api,hooks --debug-file`` logs ``[API REQUEST]``
lines and never the body.  The frozen mechanism is therefore the out-of-band
``claude-loopback-model-input-capture``: one separate, identically configured
launch whose ``ANTHROPIC_BASE_URL`` points at a loopback recorder started by the
caller, so the captured request body is the exact model input the client built.

This module turns that mechanism into the fail-closed evidence the native-load
evidence contract requires:

* it enumerates every active model-visible instruction source from the client's
  own ``# claudeMd`` labels rather than from any assumption about discovery;
* it proves each labelled workspace source byte-exact — the file's decoded
  bytes must follow its own label and appear exactly once in the whole captured
  model input — and rejects a labelled source outside the workspace, because a
  manifest cannot carry what the workspace does not own;
* it proves the complementary *absence* of every source the resolver may treat
  as ``inject``, which is the only classification the contract accepts when
  native discovery cannot be disabled;
* it binds client identity, project trust, settings/hook identity, and the
  capability row into a closed record whose ``native_evidence_id`` the resolver
  recomputes and the kernel copies into the receipt.

Model acknowledgement is never evidence here; nothing in this module reads the
client's reply.  The capture holds full model input in a temporary directory it
deletes on exit, and the evidence records hashes and byte counts only.  Because
the capture replaces the API endpoint, it cannot run inside the canonical launch
itself: any client, settings, hook, trust, or channel change invalidates it and
requires a rerun.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from agent_context import w2b1
from agent_context.probe_claude_capabilities import DUMMY_KEY, Capture


MECHANISM = "claude-loopback-model-input-capture"
MEMORY_SECTION_HEADING = "# claudeMd"
PROJECT_MEMORY_LABEL = "project instructions, checked into the codebase"
LABEL_RE = re.compile(r"^Contents of (?P<path>.+?) \((?P<label>[^)\n]*)\):$", re.MULTILINE)
LABEL_CONTENT_SEPARATOR = "\n\n"
CAPTURE_MODEL = "claude-haiku-4-5-20251001"
CAPTURE_PROMPT = "W12 NATIVE LOAD EVIDENCE CAPTURE"
CAPTURE_TIMEOUT_SECONDS = 300
# A nested client must not inherit the parent session's transport or entrypoint
# state, or the capture would measure something other than a clean launch.
INHERITED_CLIENT_VARIABLES = (
    "ANTHROPIC_AUTH_TOKEN", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_SSE_PORT", "CLAUDE_CODE_SESSION_ID",
)
SETTINGS_FILES = (".claude/settings.json", ".claude/settings.local.json")
USER_SETTINGS = ".claude/settings.json"
TRUST_RECORD = ".claude.json"
# Registering both events would deliver two copies of the same envelope; Step
# 12.1 measured that SessionStart carries additionalContext exactly as
# UserPromptSubmit does.
DUPLICATE_INJECTION_EVENTS = ("SessionStart", "UserPromptSubmit")
NATIVE_INSTRUCTION_TIERS = {
    "CLAUDE.md": ("instruction.root.claude", "workspace"),
}
REPOSITORY_INSTRUCTION_TIERS = {
    "CLAUDE.md": ("claude", "repository"),
    "REPOSITORY_CONTEXT.md": ("repository-context", "repository"),
}


def _fail(code: str, message: str) -> NoReturn:
    raise w2b1.AgentContextError(code, message)


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_source(workspace_root: Path, path: str) -> bytes:
    """Read one contained, regular, non-symlinked workspace source."""
    try:
        w2b1._canonical_path(path, "native source path")
        candidate = workspace_root.joinpath(*path.split("/"))
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(workspace_root)
        if candidate.is_symlink() or not resolved.is_file():
            _fail("E_NATIVE_EVIDENCE", f"native source is not a contained regular file: {path}")
        return resolved.read_bytes()
    except (OSError, ValueError, w2b1.AgentContextError) as error:
        _fail("E_NATIVE_EVIDENCE", f"native source cannot be inspected: {error}")


@dataclass(frozen=True)
class NativeSource:
    """One model-visible instruction source proven active by the client itself."""

    path: str
    source_bytes: int
    source_sha256: str
    label: str


@dataclass(frozen=True)
class ClaudeNativeLoad:
    """One complete, fail-closed native-load inspection for a single project."""

    mechanism: str
    workspace_root: Path
    project: str
    client_identity: str
    client_version: str
    client_sha256: str
    trust_state: str
    settings: Mapping[str, Any]
    config_sha256: str
    captured_at: str
    sources: tuple[NativeSource, ...]
    external_labels: tuple[str, ...]
    request_count: int
    model_input_sha256: str
    model_input_bytes: int
    # Transient preflight data; it is never serialized into evidence, receipts,
    # or logs, because it is the complete model input of the capture launch.
    visible_text: str

    @property
    def source_sha256(self) -> dict[str, str]:
        return {source.path: source.source_sha256 for source in self.sources}

    def observation(self) -> dict[str, Any]:
        """Return the metadata-only record of this inspection."""
        return {
            "mechanism": self.mechanism,
            "project": self.project,
            "client_identity": self.client_identity,
            "client_version": self.client_version,
            "client_sha256": self.client_sha256,
            "trust_state": self.trust_state,
            "settings": dict(self.settings),
            "config_sha256": self.config_sha256,
            "captured_at": self.captured_at,
            "request_count": self.request_count,
            "model_input_sha256": self.model_input_sha256,
            "model_input_bytes": self.model_input_bytes,
            "native_sources": [
                {
                    "path": source.path, "source_bytes": source.source_bytes,
                    "source_sha256": source.source_sha256, "label": source.label,
                }
                for source in self.sources
            ],
            "native_model_visible_bytes": sum(source.source_bytes for source in self.sources),
            "external_labels": list(self.external_labels),
        }


def capture_environment(capture: Capture) -> dict[str, str]:
    """Point one client launch at the loopback recorder with a dummy key."""
    environment = dict(os.environ)
    environment["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{capture.port}"
    environment["ANTHROPIC_API_KEY"] = DUMMY_KEY
    for name in INHERITED_CLIENT_VARIABLES:
        environment.pop(name, None)
    return environment


def capture_model_input(
    *, project: Path, client_command: str = "claude", model: str = CAPTURE_MODEL,
    timeout: int = CAPTURE_TIMEOUT_SECONDS,
) -> tuple[list[str], int]:
    """Return the exact model-input text blocks one clean client launch built.

    The recorder stores request bodies only, in a temporary directory removed
    before this function returns; headers are never read into evidence.
    """
    with tempfile.TemporaryDirectory(prefix="w12-claude-native-") as temporary:
        capture = Capture(Path(temporary) / "capture")
        try:
            result = subprocess.run(
                [
                    client_command, "-p", CAPTURE_PROMPT, "--model", model, "--tools", "",
                    "--output-format", "json", "--no-session-persistence",
                ],
                cwd=str(project), env=capture_environment(capture), capture_output=True,
                text=True, timeout=timeout, check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            _fail("E_NATIVE_EVIDENCE", f"the native-load capture launch failed: {error}")
        else:
            texts = capture.texts()
            request_count = len(capture.bodies())
        finally:
            capture.close()
    if result.returncode != 0:
        _fail("E_NATIVE_EVIDENCE", "the native-load capture launch did not complete")
    if request_count < 1 or not texts:
        _fail("E_NATIVE_EVIDENCE", "the native-load capture recorded no model input")
    return texts, request_count


def parse_active_sources(
    texts: Sequence[str], workspace_root: Path,
) -> tuple[tuple[NativeSource, ...], tuple[str, ...]]:
    """Enumerate the client's own active project-memory labels, byte-exact.

    Returns the contained workspace sources in canonical path order and every
    labelled source outside the workspace.  A label whose exact file content
    does not immediately follow it, or does not appear exactly once in the whole
    captured model input, fails closed.
    """
    if not isinstance(texts, Sequence) or isinstance(texts, (str, bytes)):
        _fail("E_NATIVE_EVIDENCE", "captured model input must be a sequence of text blocks")
    sections = [text for text in texts if MEMORY_SECTION_HEADING in text]
    if not sections:
        _fail("E_NATIVE_EVIDENCE", "captured model input contains no project-memory section")
    if len(sections) > 1:
        _fail("E_NATIVE_EVIDENCE", "project memory appears in more than one model-visible block")
    section = sections[0]
    joined = "\n".join(texts)
    root = workspace_root.resolve(strict=True)
    sources: list[NativeSource] = []
    external: list[str] = []
    seen: set[str] = set()
    for match in LABEL_RE.finditer(section):
        label_path = match.group("path")
        if label_path in seen:
            _fail("E_NATIVE_EVIDENCE", f"duplicate active instruction label: {label_path}")
        seen.add(label_path)
        try:
            absolute = Path(label_path).resolve()
            relative = absolute.relative_to(root).as_posix()
        except (OSError, ValueError):
            external.append(label_path)
            continue
        raw = _read_source(root, relative)
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            _fail("E_NATIVE_EVIDENCE", f"active instruction source is not strict UTF-8: {relative}")
        # The client frames each source as its label line, one blank line, then
        # the file's exact bytes; the label match stops before its own newline.
        if not section.startswith(LABEL_CONTENT_SEPARATOR + content, match.end()):
            _fail(
                "E_NATIVE_EVIDENCE",
                f"active instruction source does not follow its own label byte-exactly: {relative}",
            )
        if joined.count(content) != 1:
            _fail(
                "E_NATIVE_EVIDENCE",
                f"active instruction source is not model-visible exactly once: {relative}",
            )
        sources.append(NativeSource(relative, len(raw), _digest(raw), match.group("label")))
    if not sources:
        _fail("E_NATIVE_EVIDENCE", "no workspace instruction source was proved active")
    ordered = tuple(sorted(sources, key=lambda source: source.path))
    return ordered, tuple(sorted(external))


def verify_absent(texts: Sequence[str], workspace_root: Path, paths: Sequence[str]) -> dict[str, str]:
    """Prove that every candidate ``inject`` source is absent from native discovery."""
    joined = "\n".join(texts)
    root = workspace_root.resolve(strict=True)
    absent: dict[str, str] = {}
    for path in paths:
        raw = _read_source(root, path)
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            _fail("E_NATIVE_EVIDENCE", f"candidate injected source is not strict UTF-8: {path}")
        if content and content in joined:
            _fail(
                "E_NATIVE_EVIDENCE",
                f"candidate injected source is already active in native discovery: {path}",
            )
        absent[path] = _digest(raw)
    return absent


def trust_state(project: Path, *, home: Path | None = None) -> str:
    """Read the client's own project trust record; never write or infer it."""
    record = (home or Path.home()) / TRUST_RECORD
    try:
        projects = json.loads(record.read_text(encoding="utf-8")).get("projects")
    except (OSError, UnicodeDecodeError, ValueError) as error:
        _fail("E_TRUST", f"the Claude trust record cannot be inspected: {error}")
    if not isinstance(projects, dict):
        _fail("E_TRUST", "the Claude trust record has no project table")
    entry = projects.get(str(project.resolve(strict=True)))
    if not isinstance(entry, dict):
        return "unrecorded"
    return "trusted" if entry.get("hasTrustDialogAccepted") is True else "untrusted"


def settings_identity(workspace_root: Path, *, home: Path | None = None) -> dict[str, Any]:
    """Freeze the settings and hook layer whose change invalidates this evidence."""
    identity: dict[str, Any] = {"project": {}, "user": None, "registered_hook_events": []}
    events: set[str] = set()

    def _hooks(raw: bytes, name: str) -> None:
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            _fail("E_TRUST", f"Claude settings are not valid JSON: {name}: {error}")
        hooks = parsed.get("hooks") if isinstance(parsed, dict) else None
        if isinstance(hooks, dict):
            events.update(str(event) for event in hooks)

    for relative in SETTINGS_FILES:
        path = workspace_root / relative
        if not path.is_file() or path.is_symlink():
            identity["project"][relative] = None
            continue
        raw = path.read_bytes()
        identity["project"][relative] = _digest(raw)
        _hooks(raw, relative)
    user = (home or Path.home()) / USER_SETTINGS
    if user.is_file() and not user.is_symlink():
        raw = user.read_bytes()
        identity["user"] = _digest(raw)
        _hooks(raw, USER_SETTINGS)
    identity["registered_hook_events"] = sorted(events)
    return identity


def client_identity(client_command: str = "claude") -> tuple[str, str, str]:
    """Resolve the exact installed client path, version, and content hash."""
    found = shutil.which(client_command)
    if found is None:
        _fail("E_CAPABILITY", "the Claude client is not installed on this PATH")
    resolved = Path(found).resolve()
    try:
        raw = resolved.read_bytes()
    except OSError as error:
        _fail("E_CAPABILITY", f"the Claude client cannot be hashed: {error}")
    try:
        version = subprocess.run(
            [client_command, "--version"], capture_output=True, text=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        _fail("E_CAPABILITY", f"the Claude client version cannot be read: {error}")
    if version.returncode != 0 or not version.stdout.strip():
        _fail("E_CAPABILITY", "the Claude client did not report a version")
    return str(resolved), version.stdout.strip(), _digest(raw)


def inspect_native_load(
    *, workspace_root: Path, project: Path, client_command: str = "claude",
    model: str = CAPTURE_MODEL, home: Path | None = None,
) -> ClaudeNativeLoad:
    """Run one complete out-of-band native-load inspection for a project scope."""
    root = workspace_root.resolve(strict=True)
    scope = project.resolve(strict=True)
    try:
        relative = scope.relative_to(root).as_posix()
    except ValueError:
        _fail("E_SCOPE_UNAVAILABLE", "the inspected project is outside the workspace root")
    identity, version, binary_sha256 = client_identity(client_command)
    settings = settings_identity(root, home=home)
    state = trust_state(scope, home=home)
    texts, request_count = capture_model_input(
        project=scope, client_command=client_command, model=model,
    )
    sources, external = parse_active_sources(texts, root)
    joined = "\n".join(texts)
    return ClaudeNativeLoad(
        mechanism=MECHANISM,
        workspace_root=root,
        project="." if relative == "." else relative,
        client_identity=identity,
        client_version=version,
        client_sha256=binary_sha256,
        trust_state=state,
        settings=settings,
        config_sha256=w2b1.canonical_sha256(settings),
        captured_at=_timestamp(),
        sources=sources,
        external_labels=external,
        request_count=request_count,
        model_input_sha256=_digest(joined.encode("utf-8")),
        model_input_bytes=len(joined.encode("utf-8")),
        visible_text=joined,
    )


def build_native_evidence(
    load: ClaudeNativeLoad, *, capability_row: Mapping[str, Any],
    expected_client_sha256: str | None = None,
) -> dict[str, Any]:
    """Return the closed record the resolver validates and the receipt binds.

    It fails closed rather than describe an unusable state: an untrusted or
    unrecorded project, an active source the workspace does not own, or a
    capability row whose frozen inspection mechanism is not this one.
    """
    row = dict(capability_row)
    if row.get("agent") != "claude":
        _fail("E_CAPABILITY", "Claude native evidence requires a Claude capability row")
    if row.get("inspection_mechanism") != MECHANISM:
        _fail("E_CAPABILITY", "the capability row does not freeze this inspection mechanism")
    if load.mechanism != MECHANISM:
        _fail("E_NATIVE_EVIDENCE", "the inspection did not use the frozen mechanism")
    if expected_client_sha256 is not None and load.client_sha256 != expected_client_sha256:
        _fail("E_CAPABILITY", "the installed Claude client changed since its capability evidence")
    if load.trust_state != "trusted":
        _fail("E_TRUST", f"the inspected Claude project is {load.trust_state}, not trusted")
    if load.external_labels:
        _fail(
            "E_NATIVE_EVIDENCE",
            "an active instruction source outside the workspace cannot be covered by a manifest",
        )
    evidence: dict[str, Any] = {
        "native_evidence_id": "0" * 64,
        "agent": "claude",
        "platform": row["platform"],
        "mode": row["mode"],
        "client_identity": load.client_identity,
        "client_version": load.client_version,
        "config_sha256": load.config_sha256,
        "capability_evidence_id": w2b1.canonical_sha256(row),
        "trust_state": "trusted",
        "inspection_mechanism": MECHANISM,
        "captured_at": load.captured_at,
        "sources": [
            {"path": source.path, "sha256": source.source_sha256} for source in load.sources
        ],
    }
    evidence["native_evidence_id"] = w2b1.canonical_sha256(
        {key: value for key, value in evidence.items() if key != "native_evidence_id"}
    )
    return evidence


def build_injection_evidence(
    load: ClaudeNativeLoad, *, generation: int, paths: Sequence[str],
) -> dict[str, Any]:
    """Return exact-once inject evidence for provably non-native sources.

    Claude cannot disable its own project-memory discovery, so the contract's
    alternative applies: every injected source is proved absent from the exact
    model input of an identically configured launch.  Exactly-once handoff is
    the kernel's launcher-controlled generation state, so a second registered
    additionalContext event is rejected here rather than discovered at delivery.
    """
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        _fail("E_USAGE", "the launcher generation must be a non-negative integer")
    registered = set(load.settings.get("registered_hook_events") or ())
    if len(registered.intersection(DUPLICATE_INJECTION_EVENTS)) > 1:
        _fail(
            "E_CHANNEL",
            "SessionStart and UserPromptSubmit would both inject additionalContext",
        )
    native = set(load.source_sha256)
    for path in paths:
        if path in native:
            _fail("E_NATIVE_EVIDENCE", f"a proven native source cannot be injected: {path}")
    absent = verify_absent([load.visible_text], load.workspace_root, paths)
    return {
        "generation": generation,
        "native_discovery_disabled": True,
        "exact_once_handoff_proven": True,
        "sources": [{"path": path, "sha256": absent[path]} for path in sorted(absent)],
    }


def verify_manifest_native_binding(
    manifest: Mapping[str, Any], evidence: Mapping[str, Any],
) -> dict[str, str]:
    """Compare the client-proven active sources with the manifest, both ways.

    The contract omits an ``inject`` entry only after this comparison, so a
    manifest that claims an unproven native source, misses a proven one, or
    carries a different evidence identity fails closed here.
    """
    try:
        proven = {source["path"]: source["sha256"] for source in evidence["sources"]}
        identity = evidence["native_evidence_id"]
        entries = manifest["entries"]
    except (KeyError, TypeError) as error:
        _fail("E_NATIVE_EVIDENCE", f"native evidence or manifest is malformed: {error}")
    claimed: dict[str, str] = {}
    for entry in entries:
        if entry["delivery"] != "native":
            if entry["native_evidence_id"] is not None:
                _fail("E_NATIVE_EVIDENCE", f"an injected entry claims native evidence: {entry['path']}")
            if entry["path"] in proven:
                _fail("E_NATIVE_EVIDENCE", f"a proven native source is injected: {entry['path']}")
            continue
        if entry["native_evidence_id"] != identity:
            _fail("E_NATIVE_EVIDENCE", f"native entry binds another evidence record: {entry['path']}")
        if proven.get(entry["path"]) != entry["source_sha256"]:
            _fail("E_NATIVE_EVIDENCE", f"native entry is not proven active byte-exactly: {entry['path']}")
        claimed[entry["path"]] = entry["source_sha256"]
    missing = set(proven) - set(claimed)
    if missing:
        _fail(
            "E_NATIVE_EVIDENCE",
            f"the manifest omits proven model-visible sources: {', '.join(sorted(missing))}",
        )
    return claimed


def _instruction_entry(path: str, selected: Sequence[str]) -> dict[str, str]:
    """Map one canonical instruction path onto its resolver entry."""
    parts = path.split("/")
    if len(parts) == 1:
        if path not in NATIVE_INSTRUCTION_TIERS:
            _fail("E_NATIVE_EVIDENCE", f"unexpected workspace instruction source: {path}")
        policy_id, tier = NATIVE_INSTRUCTION_TIERS[path]
        return {
            "policy_id": policy_id, "repository_id": "$workspace", "scope_prefix": ".",
            "path": path, "authority_tier": tier,
        }
    repository_id, name = parts[0], parts[-1]
    if len(parts) != 2 or name not in REPOSITORY_INSTRUCTION_TIERS:
        _fail("E_NATIVE_EVIDENCE", f"unexpected repository instruction source: {path}")
    if repository_id not in set(selected):
        _fail("E_SCOPE_UNAVAILABLE", f"an instruction source is outside the selected scope: {path}")
    suffix, tier = REPOSITORY_INSTRUCTION_TIERS[name]
    return {
        "policy_id": f"instruction.{repository_id}.{suffix}", "repository_id": repository_id,
        "scope_prefix": repository_id, "path": path, "authority_tier": tier,
    }


def instruction_sources(
    load: ClaudeNativeLoad, *, repositories: Sequence[str], injected_paths: Sequence[str] = (),
) -> tuple[dict[str, str], ...]:
    """Map proven-active and proven-absent instruction files onto resolver entries.

    ``injected_paths`` carries the sibling instruction files a launch scope does
    not load natively.  They may only be declared once the same capture has
    proved their absence, so a file can never be both native and injected.
    """
    native = set(load.source_sha256)
    entries = [_instruction_entry(source.path, repositories) for source in load.sources]
    for path in injected_paths:
        if path in native:
            _fail("E_NATIVE_EVIDENCE", f"a proven native source cannot be injected: {path}")
        entries.append(_instruction_entry(path, repositories))
    if len({entry["path"] for entry in entries}) != len(entries):
        _fail("E_NATIVE_EVIDENCE", "duplicate instruction source path")
    return tuple(sorted(entries, key=lambda item: item["path"]))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture Claude native-load evidence for one project scope.")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument(
        "--project", type=Path, default=None,
        help="the launch directory; defaults to the workspace root",
    )
    parser.add_argument("--client-command", default="claude")
    parser.add_argument("--model", default=CAPTURE_MODEL)
    parser.add_argument("--absent", action="append", default=[], help="candidate injected source path")
    parser.add_argument("--output", type=Path, required=True, help="metadata-only observation path")
    arguments = parser.parse_args(argv)
    load = inspect_native_load(
        workspace_root=arguments.workspace_root,
        project=arguments.project or arguments.workspace_root,
        client_command=arguments.client_command,
        model=arguments.model,
    )
    observation = load.observation()
    if arguments.absent:
        observation["proved_absent"] = [
            {"path": path, "sha256": digest}
            for path, digest in sorted(
                verify_absent([load.visible_text], load.workspace_root, arguments.absent).items()
            )
        ]
    arguments.output.write_text(
        json.dumps(observation, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
