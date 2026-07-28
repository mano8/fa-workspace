"""Step 12.4 byte-exact Claude hook-channel round-trip probe.

Step 12.1 measured the ``additionalContext`` boundary with a hook registered in
a project settings file.  Step 12.4 delivers through a *launcher-owned*
registration instead — one ``--settings`` file per launch, naming the tracked
``claude_hook_gate`` — so the boundary alone is not evidence for this channel.
This probe measures the wiring that actually delivers:

* the complete serialized JCS envelope the launcher armed appears **byte-exact**
  in the model input the client built, through the real gate;
* the same generation, prompted again, receives **no second copy**, because the
  gate's atomic claim is the exactly-once authority;
* a ``--settings`` hook **merges** with the project layer rather than replacing
  it, which is why a foreign ``additionalContext`` event must make every row
  ineligible;
* a session that does not own the armed generation, a non-``UserPromptSubmit``
  event, and an oversize payload are all refused with no claim and no delivery;
  and
* the client's own 10,000/10,001 boundary still holds through this registration
  path, and above it the client substitutes a preview plus a temporary-file
  pointer, which is never delivery.

Method.  Exactly as Steps 12.1 and 12.2: every invocation points
``ANTHROPIC_BASE_URL`` at a loopback recorder this probe starts, with a dummy
``ANTHROPIC_API_KEY``, so the vendor API is never contacted and no real
credential leaves the machine.  Request *bodies* only are stored, in a
temporary directory removed before the probe returns.  The probe creates its own
project and its own runtime root outside the workspace and writes no workspace
or child repository file; the only workspace file it reads is the tracked gate
it registers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context import claude_hook_gate as gate
from agent_context import w2b1
from agent_context.claude_native_evidence import client_identity
from agent_context.delivery_kernel import DeliveryKernel
from agent_context.probe_claude_capabilities import DUMMY_KEY, Capture, build_fixture


PROBE_ID = "w12-claude-hook-channel-probe"
PROBE_MODEL = "claude-haiku-4-5-20251001"
MECHANISM = "claude-loopback-model-input-capture"
DELIVERY_MECHANISM = "launcher-owned --settings UserPromptSubmit gate"
CHANNEL_ID = gate.CHANNEL_ID
# The hook row Step 12.1 froze; the round trip is evidence only for that row.
HOOK_ROW_ID = "claude-devcontainer-non-interactive-hook-additional-context"
CAPABILITY_EVIDENCE = (
    "scripts/agent_context/fixtures/evidence/w12-claude-capability-evidence-2026-07-27.json"
)
FOREIGN_MARKER = "W12_FOREIGN_AUTHORITY_MARKER_1c8f"
INHERITED_CLIENT_VARIABLES = (
    "ANTHROPIC_AUTH_TOKEN", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_SSE_PORT", "CLAUDE_CODE_SESSION_ID",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build_probe_envelope(target_bytes: int) -> tuple[bytes, str]:
    """Return a real JCS envelope of approximately ``target_bytes`` bytes.

    The channel carries opaque bytes, but measuring it with the exact artifact
    type it must carry — including the escaping, CRLF, and non-ASCII content a
    policy source can hold — is stronger evidence than a flat fixture.
    """
    manifest_id = _digest(b"w12-4-probe-manifest")
    entry = w2b1.source_entry_from_bytes(
        build_fixture(max(target_bytes // 2, 64), "mixed"),
        {
            "policy_id": "probe.round.trip", "repository_id": "$workspace",
            "scope_prefix": ".", "path": ".workspace/policies/probe-round-trip.md",
            "authority_tier": "workspace",
        },
    )
    envelope, serialized, digest = w2b1.build_envelope(
        manifest_id=manifest_id, generation=0, entries=[entry],
    )
    del envelope
    return serialized, digest


def client_environment(capture: Capture) -> dict[str, str]:
    environment = dict(os.environ)
    environment["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{capture.port}"
    environment["ANTHROPIC_API_KEY"] = DUMMY_KEY
    for name in INHERITED_CLIENT_VARIABLES:
        environment.pop(name, None)
    return environment


def new_session_id() -> str:
    """Every measured launch owns its own identity; a reused one collides."""
    return str(uuid.uuid4())


def run_client(
    project: Path, capture: Capture, extra: Sequence[str], *, prompt: str = "SAY PROBE",
    session_id: str | None = None, resume: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        "claude", "-p", prompt, "--model", PROBE_MODEL, "--tools", "",
        "--output-format", "json", *extra,
    ]
    if session_id is not None:
        command += ["--session-id", session_id]
    if resume is not None:
        command += ["--resume", resume]
    return subprocess.run(
        command, cwd=str(project), env=client_environment(capture), capture_output=True,
        text=True, timeout=300, check=False,
    )


class ArmedGeneration:
    """One launcher-owned runtime session armed exactly as the adapter arms it."""

    def __init__(self, base: Path, *, generation: int = 0) -> None:
        self.workspace_root = base / "runtime-root"
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.kernel = DeliveryKernel()
        self.runtime_dir = self.kernel._new_runtime_dir(self.workspace_root)
        self.generation = generation

    def arm(
        self, payload: bytes, *, launch_scope: Path, client_session_id: str,
        capability_evidence_id: str, round_trip_evidence_id: str,
        verified_channel_limit: int = 10000,
    ) -> Path:
        state = {
            "schema_version": 1, "channel_id": CHANNEL_ID,
            "launch_id": "launch-" + "0" * 32, "client_session_id": client_session_id,
            "generation": self.generation, "manifest_id": _digest(b"w12-4-probe-manifest"),
            "envelope_sha256": _digest(payload), "envelope_bytes": len(payload),
            "verified_channel_limit": verified_channel_limit,
            "effective_hard_limit": 10000,
            "model_visible_total": len(payload),
            "round_trip_evidence_id": round_trip_evidence_id,
            "capability_evidence_id": capability_evidence_id,
            "launch_scope": str(launch_scope),
        }
        command = " ".join(
            shlex.quote(item)
            for item in (
                sys.executable, str(Path(__file__).resolve().parent / "claude_hook_gate.py"),
                "--runtime-dir", str(self.runtime_dir),
            )
        )
        settings = {
            "hooks": {
                gate.HOOK_EVENT: [{"hooks": [{"type": "command", "command": command}]}]
            }
        }
        self.kernel.write_channel_artifact(
            self.runtime_dir, gate.CHANNEL_ENVELOPE_ARTIFACT, payload,
        )
        self.kernel.write_channel_artifact(
            self.runtime_dir, gate.CHANNEL_STATE_ARTIFACT, w2b1.canonical_bytes(state),
        )
        return self.kernel.write_channel_artifact(
            self.runtime_dir, gate.CHANNEL_SETTINGS_ARTIFACT, w2b1.canonical_bytes(settings),
        )

    def claims(self) -> list[str]:
        return sorted(
            child.name for child in self.runtime_dir.iterdir()
            if child.name.startswith("channel-claim-")
        )

    def claim(self) -> dict[str, Any] | None:
        try:
            raw = self.kernel.read_channel_artifact(
                self.runtime_dir, gate.claim_artifact(self.generation)
            )
        except w2b1.AgentContextError:
            return None
        return w2b1.parse_strict_json(raw)


def probe_round_trip(base: Path, project: Path, capability_evidence_id: str) -> dict[str, Any]:
    """Deliver one real armed envelope and prove the exact bytes reach the model."""
    payload, digest = build_probe_envelope(6144)
    session = new_session_id()
    armed = ArmedGeneration(base / "round-trip")
    settings = armed.arm(
        payload, launch_scope=project, client_session_id=session,
        capability_evidence_id=capability_evidence_id,
        round_trip_evidence_id=_digest(b"w12-4-pending"),
    )
    capture = Capture(base / "capture-round-trip")
    try:
        first = run_client(
            project, capture, ["--settings", str(settings)], session_id=session,
        )
        exact = capture.contains(payload)
        occurrences = "\n".join(capture.texts()).count(payload.decode("utf-8"))
        claim = armed.claim()
    finally:
        capture.close()
    # The same generation, prompted again in the same session: the gate must
    # answer without a second copy of the envelope it already delivered.
    capture = Capture(base / "capture-exact-once")
    try:
        second = run_client(
            project, capture, ["--settings", str(settings)], prompt="SECOND PROMPT",
            resume=session,
        )
        # A resumed session replays its own transcript, so the envelope is
        # legitimately visible once more.  A *second injection* would make it
        # visible twice; the count, not the presence, is the evidence.
        repeated = "\n".join(capture.texts()).count(payload.decode("utf-8"))
    finally:
        capture.close()
    return {
        "envelope_sha256": digest,
        "envelope_bytes": len(payload),
        "envelope_is_jcs": w2b1.canonical_bytes(json.loads(payload.decode("utf-8"))) == payload,
        "client_exit_code": first.returncode,
        "exact_model_input": exact,
        "model_visible_occurrences": occurrences,
        "claim_recorded": claim is not None,
        "claim": claim,
        "second_prompt_exit_code": second.returncode,
        "second_prompt_model_visible_occurrences": repeated,
        "claims_after_second_prompt": armed.claims(),
    }


def probe_gate_refusals(base: Path, project: Path, capability_evidence_id: str) -> list[dict[str, Any]]:
    """Every refusal must block with no claim and no model-visible payload."""
    observations: list[dict[str, Any]] = []
    payload, _ = build_probe_envelope(2048)

    # 1. A session that does not own the armed generation.
    armed = ArmedGeneration(base / "refuse-session")
    settings = armed.arm(
        payload, launch_scope=project, client_session_id=new_session_id(),
        capability_evidence_id=capability_evidence_id,
        round_trip_evidence_id=_digest(b"w12-4-pending"),
    )
    capture = Capture(base / "capture-refuse-session")
    try:
        result = run_client(
            project, capture, ["--settings", str(settings)], session_id=new_session_id(),
        )
        observations.append({
            "case": "unowned-session", "expected_code": "E_LIFECYCLE",
            "client_exit_code": result.returncode, "delivered": capture.contains(payload),
            "claims": armed.claims(), "model_input_requests": len(capture.bodies()),
            "client_stderr_excerpt": result.stderr.strip()[:200] or None,
        })
    finally:
        capture.close()

    # 2. An oversize payload never reaches the client at all.
    oversize = build_fixture(10001, "ascii")
    session = new_session_id()
    armed = ArmedGeneration(base / "refuse-oversize")
    settings = armed.arm(
        oversize, launch_scope=project, client_session_id=session,
        capability_evidence_id=capability_evidence_id,
        round_trip_evidence_id=_digest(b"w12-4-pending"), verified_channel_limit=10000,
    )
    capture = Capture(base / "capture-refuse-oversize")
    try:
        result = run_client(
            project, capture, ["--settings", str(settings)], session_id=session,
        )
        observations.append({
            "case": "oversize-payload", "expected_code": "E_CHANNEL",
            "client_exit_code": result.returncode, "delivered": capture.contains(oversize),
            "claims": armed.claims(), "model_input_requests": len(capture.bodies()),
            "client_stderr_excerpt": result.stderr.strip()[:200] or None,
        })
    finally:
        capture.close()

    # 3. A drifted armed envelope.
    session = new_session_id()
    armed = ArmedGeneration(base / "refuse-drift")
    settings = armed.arm(
        payload, launch_scope=project, client_session_id=session,
        capability_evidence_id=capability_evidence_id,
        round_trip_evidence_id=_digest(b"w12-4-pending"),
    )
    armed.kernel.write_channel_artifact(
        armed.runtime_dir, gate.CHANNEL_ENVELOPE_ARTIFACT, payload + b"drift", replace=True,
    )
    capture = Capture(base / "capture-refuse-drift")
    try:
        result = run_client(
            project, capture, ["--settings", str(settings)], session_id=session,
        )
        observations.append({
            "case": "drifted-envelope", "expected_code": "E_CHANNEL",
            "client_exit_code": result.returncode,
            "delivered": capture.contains(payload + b"drift"), "claims": armed.claims(),
            "model_input_requests": len(capture.bodies()),
            "client_stderr_excerpt": result.stderr.strip()[:200] or None,
        })
    finally:
        capture.close()

    # 4. The gate registered on the other additionalContext event.  Even a
    # misconfigured launcher cannot turn this gate into a second authority.
    session = new_session_id()
    armed = ArmedGeneration(base / "refuse-event")
    settings_path = armed.arm(
        payload, launch_scope=project, client_session_id=session,
        capability_evidence_id=capability_evidence_id,
        round_trip_evidence_id=_digest(b"w12-4-pending"),
    )
    registration = w2b1.parse_strict_json(settings_path.read_bytes())
    command = registration["hooks"][gate.HOOK_EVENT]
    settings_path.write_text(
        json.dumps({"hooks": {"SessionStart": command}}), encoding="utf-8",
    )
    capture = Capture(base / "capture-refuse-event")
    try:
        result = run_client(
            project, capture, ["--settings", str(settings_path)], session_id=session,
        )
        observations.append({
            "case": "session-start-event", "expected_code": "E_CHANNEL",
            "client_exit_code": result.returncode, "delivered": capture.contains(payload),
            "claims": armed.claims(), "model_input_requests": len(capture.bodies()),
            "client_stderr_excerpt": result.stderr.strip()[:200] or None,
        })
    finally:
        capture.close()
    return observations


def probe_foreign_authority(base: Path, project: Path, capability_evidence_id: str) -> dict[str, Any]:
    """Prove that a --settings hook merges with, and never replaces, the project layer."""
    emitter = base / "foreign_hook.py"
    emitter.write_text(
        "import json, os, sys\n"
        "sys.stdin.read()\n"
        "sys.stdout.write(json.dumps({'hookSpecificOutput': {\n"
        "    'hookEventName': 'UserPromptSubmit',\n"
        f"    'additionalContext': {FOREIGN_MARKER!r},\n"
        "}}))\n",
        encoding="utf-8",
    )
    (project / ".claude").mkdir(exist_ok=True)
    (project / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"UserPromptSubmit": [
            {"hooks": [{"type": "command", "command": f"{sys.executable} {emitter}"}]}
        ]}}),
        encoding="utf-8",
    )
    payload, _ = build_probe_envelope(2048)
    session = new_session_id()
    armed = ArmedGeneration(base / "foreign")
    settings = armed.arm(
        payload, launch_scope=project, client_session_id=session,
        capability_evidence_id=capability_evidence_id,
        round_trip_evidence_id=_digest(b"w12-4-pending"),
    )
    capture = Capture(base / "capture-foreign")
    try:
        result = run_client(
            project, capture, ["--settings", str(settings)], session_id=session,
        )
        text = "\n".join(capture.texts())
        observation = {
            "client_exit_code": result.returncode,
            "launcher_envelope_delivered": capture.contains(payload),
            "foreign_marker_occurrences": text.count(FOREIGN_MARKER),
            "settings_hooks_merge": capture.contains(payload) and FOREIGN_MARKER in text,
        }
    finally:
        capture.close()
        (project / ".claude" / "settings.json").unlink()
    return observation


def probe_setting_sources(base: Path, project: Path, capability_evidence_id: str) -> dict[str, Any]:
    """Measure why the launcher must not narrow ``--setting-sources``.

    Suppressing the project settings source would also suppress the project
    memory the Step 12.2 native evidence enumerated, so the launch would no
    longer be the identically configured launch that evidence describes.
    """
    payload, _ = build_probe_envelope(2048)
    memory = (project / "CLAUDE.md").read_text(encoding="utf-8")
    observations: dict[str, Any] = {}
    for label, extra in (("default", []), ("user-only", ["--setting-sources", "user"])):
        session = new_session_id()
        armed = ArmedGeneration(base / f"sources-{label}")
        settings = armed.arm(
            payload, launch_scope=project, client_session_id=session,
            capability_evidence_id=capability_evidence_id,
            round_trip_evidence_id=_digest(b"w12-4-pending"),
        )
        capture = Capture(base / f"capture-sources-{label}")
        try:
            result = run_client(
                project, capture, ["--settings", str(settings), *extra], session_id=session,
            )
            observations[label] = {
                "client_exit_code": result.returncode,
                "envelope_delivered": capture.contains(payload),
                "native_project_memory_present": memory in "\n".join(capture.texts()),
            }
        finally:
            capture.close()
    return observations


def probe_boundary(base: Path, project: Path) -> list[dict[str, Any]]:
    """Reconfirm the client's own exact boundary through this registration path."""
    emitter = base / "boundary_hook.py"
    emitter.write_text(
        "import json, os, sys\n"
        f"sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})\n"
        "from probe_claude_capabilities import build_fixture\n"
        "sys.stdin.read()\n"
        "payload = build_fixture(int(os.environ['W12_SIZE']), 'ascii')\n"
        "sys.stdout.write(json.dumps({'hookSpecificOutput': {\n"
        "    'hookEventName': 'UserPromptSubmit',\n"
        "    'additionalContext': payload.decode('utf-8'),\n"
        "}}))\n",
        encoding="utf-8",
    )
    observations = []
    for size in (10000, 10001):
        fixture = build_fixture(size, "ascii")
        settings = base / f"boundary-settings-{size}.json"
        settings.write_text(
            json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [{
                "type": "command",
                "command": f"W12_SIZE={size} {sys.executable} {emitter}",
            }]}]}}),
            encoding="utf-8",
        )
        capture = Capture(base / f"capture-boundary-{size}")
        try:
            result = run_client(project, capture, ["--settings", str(settings)])
            text = "\n".join(capture.texts())
            observations.append({
                "fixture_bytes": size,
                "fixture_sha256": _digest(fixture),
                "exact_model_input": capture.contains(fixture),
                "persisted_output_substituted": "<persisted-output>" in text,
                "client_exit_code": result.returncode,
            })
        finally:
            capture.close()
    return observations


def _capability_evidence_id(workspace_root: Path) -> tuple[str, int]:
    artifact = json.loads(
        (workspace_root / CAPABILITY_EVIDENCE).read_text(encoding="utf-8")
    )
    row = next(item for item in artifact["rows"] if item["row_id"] == HOOK_ROW_ID)
    return row["capability_evidence_id"], row["capability_row"]["verified_channel_limit"]


def run_probe(workspace_root: Path) -> dict[str, Any]:
    identity, version, binary_sha256 = client_identity("claude")
    capability_evidence_id, verified_channel_limit = _capability_evidence_id(workspace_root)
    with tempfile.TemporaryDirectory(prefix="w12-claude-hook-") as temporary:
        base = Path(temporary).resolve()
        project = base / "project"
        project.mkdir()
        (project / "CLAUDE.md").write_text(
            "# probe project memory\n\nThis file exists only to keep a native"
            " instruction source present.\n",
            encoding="utf-8", newline="\n",
        )
        round_trip = probe_round_trip(base, project, capability_evidence_id)
        refusals = probe_gate_refusals(base, project, capability_evidence_id)
        foreign = probe_foreign_authority(base, project, capability_evidence_id)
        setting_sources = probe_setting_sources(base, project, capability_evidence_id)
        boundary = probe_boundary(base, project)
    return {
        "probe_id": PROBE_ID,
        "probe_source_sha256": _digest(Path(__file__).resolve().read_bytes()),
        "gate_source_sha256": _digest(
            (workspace_root / "scripts/agent_context/claude_hook_gate.py").read_bytes()
        ),
        "captured_at": _now(),
        "client": {"identity": identity, "version": version, "sha256": binary_sha256},
        "capability_evidence_id": capability_evidence_id,
        "verified_channel_limit": verified_channel_limit,
        "mechanism": MECHANISM,
        "delivery_mechanism": DELIVERY_MECHANISM,
        "vendor_api_contacted": False,
        "workspace_files_written": 0,
        "round_trip": round_trip,
        "gate_refusals": refusals,
        "foreign_authority": foreign,
        "setting_sources": setting_sources,
        "boundary": boundary,
    }


def frozen_round_trip(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return the closed record the adapter pins and recomputes."""
    trip = report["round_trip"]
    record = {
        "round_trip_evidence_id": "0" * 64,
        "channel_id": CHANNEL_ID,
        "hook_event": gate.HOOK_EVENT,
        "mechanism": report["mechanism"],
        "delivery_mechanism": report["delivery_mechanism"],
        "capability_evidence_id": report["capability_evidence_id"],
        "verified_channel_limit": report["verified_channel_limit"],
        "client_identity": report["client"]["identity"],
        "client_version": report["client"]["version"],
        "client_sha256": report["client"]["sha256"],
        "gate_source_sha256": report["gate_source_sha256"],
        "captured_at": report["captured_at"],
        "envelope_sha256": trip["envelope_sha256"],
        "envelope_bytes": trip["envelope_bytes"],
        "exact_model_input": trip["exact_model_input"],
        "model_visible_occurrences": trip["model_visible_occurrences"],
        "second_prompt_model_visible_occurrences": trip["second_prompt_model_visible_occurrences"],
        "claims_after_second_prompt": len(trip["claims_after_second_prompt"]),
        "claim_recorded": trip["claim_recorded"],
    }
    record["round_trip_evidence_id"] = w2b1.canonical_sha256(
        {key: value for key, value in record.items() if key != "round_trip_evidence_id"}
    )
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure the Claude hook-channel round trip.")
    parser.add_argument("--workspace-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True, help="raw observation path")
    arguments = parser.parse_args(argv)
    report = run_probe(arguments.workspace_root.resolve(strict=True))
    report["round_trip_record"] = frozen_round_trip(report)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
