"""Step 12.1 installed-Claude canonical-delivery capability probe.

The probe answers exactly the questions the resolved-context delivery and
native-load evidence contracts require for a Claude row: which hook events run,
which channels carry an exact model-visible payload and up to how many bytes,
whether project trust gates that behavior, which lifecycle identities exist, and
whether any supported inspection reports the active project instruction sources.

Method.  Every measured invocation points ``ANTHROPIC_BASE_URL`` at a loopback
recorder started by this probe and supplies a dummy ``ANTHROPIC_API_KEY``, so
the vendor API is never contacted and no real credential leaves the machine.
The recorder stores request *bodies* only; headers are never written or logged.
A captured body is the exact model input the client constructed, which is the
strongest available byte-exact evidence of model-visible content.  It proves
client-side construction, not vendor acceptance or model retention.

Scope.  The probe creates its own temporary project outside the workspace,
never reads or writes a workspace or child repository file, and purges the
temporary project's client state when it exits.  Its output is evidence for a
capability matrix; it freezes nothing by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterable, Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

PROBE_ID = "w12-claude-capability-probe"
PROBE_MODEL = "claude-haiku-4-5-20251001"
DUMMY_KEY = "probe-dummy-key-not-a-credential"
NATIVE_MARKER = "W12_NATIVE_MARKER_ALPHA_7f3c"
HOOK_EVENTS = (
    "SessionStart", "SessionEnd", "UserPromptSubmit", "PreCompact", "PostCompact",
    "PreToolUse", "PostToolUse", "Notification", "SubagentStop",
)
HOOK_CHANNEL_SIZES = (8192, 10000, 10001, 10240, 12288, 16384, 32768)
WRAPPER_SIZES = (32768, 65536, 131000, 262144, 1048576)
FIXTURE_HEAD = "W12HEAD:"
FIXTURE_TAIL = ":W12TAIL"
FIXTURE_UNITS = {
    # Backslashes, quotes, CRLF, tab, and non-ASCII exercise every escaping and
    # newline path a JCS envelope can contain.
    "mixed": '{"k":"\\\\\\"é—\r\n\t~`|"}',
    "ascii": '{"k":"\\\\\\"\r\n\t~`|"}',
}


def build_fixture(total_bytes: int, mode: str) -> bytes:
    """Return exactly ``total_bytes`` deterministic UTF-8 fixture bytes."""
    unit = FIXTURE_UNITS[mode]
    head = FIXTURE_HEAD.encode("utf-8")
    tail = FIXTURE_TAIL.encode("utf-8")
    target = total_bytes - len(head) - len(tail)
    if target < 16:
        raise ValueError("fixture is too small to carry its markers")
    chunks: list[bytes] = []
    length = 0
    counter = 0
    while length < target:
        seed = hashlib.sha256(f"w12-{counter}".encode()).hexdigest()[:16]
        raw = f"{counter:08d}|{seed}|{unit}".encode()
        if length + len(raw) > target:
            raw = raw[: target - length]
            while raw:
                try:
                    raw.decode("utf-8")
                    break
                except UnicodeDecodeError:
                    raw = raw[:-1]
            raw = raw + b"." * (target - length - len(raw))
        chunks.append(raw)
        length += len(raw)
        counter += 1
    return head + b"".join(chunks) + tail


class _Recorder(BaseHTTPRequestHandler):
    """Record request bodies only; headers are read and immediately discarded."""

    protocol_version = "HTTP/1.1"
    directory: Path
    lock: ClassVar[threading.Lock] = threading.Lock()
    counter: ClassVar[list[int]] = [0]

    def log_message(self, *_args: object) -> None:
        return

    def _reply(self, payload: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:  # BaseHTTPRequestHandler naming contract
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length) if length else b""
        with _Recorder.lock:
            _Recorder.counter[0] += 1
            index = _Recorder.counter[0]
        (type(self).directory / f"request-{index:04d}.json").write_bytes(body)
        try:
            streaming = bool(json.loads(body.decode("utf-8")).get("stream"))
        except (ValueError, UnicodeDecodeError):
            streaming = False
        if streaming:
            self._reply(_SSE.encode("utf-8"), "text/event-stream")
        else:
            self._reply(json.dumps(_MESSAGE).encode("utf-8"), "application/json")

    def do_GET(self) -> None:  # BaseHTTPRequestHandler naming contract
        self._reply(b'{"ok":true}', "application/json")


_MESSAGE = {
    "id": "msg_probe", "type": "message", "role": "assistant", "model": "probe",
    "content": [{"type": "text", "text": "PROBE_OK"}], "stop_reason": "end_turn",
    "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
}
_SSE = (
    'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_probe",'
    '"type":"message","role":"assistant","model":"probe","content":[],"stop_reason":null,'
    '"stop_sequence":null,"usage":{"input_tokens":1,"output_tokens":1}}}\n\n'
    'event: content_block_start\ndata: {"type":"content_block_start","index":0,'
    '"content_block":{"type":"text","text":""}}\n\n'
    'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,'
    '"delta":{"type":"text_delta","text":"PROBE_OK"}}\n\n'
    'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n'
    'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn",'
    '"stop_sequence":null},"usage":{"output_tokens":1}}\n\n'
    'event: message_stop\ndata: {"type":"message_stop"}\n\n'
)


class Capture:
    """One loopback model-input recorder bound to an ephemeral port."""

    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        handler = type("BoundRecorder", (_Recorder,), {"directory": directory})
        self.directory = directory
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def bodies(self) -> list[dict[str, Any]]:
        payloads = []
        for path in sorted(self.directory.glob("request-*.json")):
            try:
                payloads.append(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, UnicodeDecodeError):
                continue
        return payloads

    def texts(self) -> list[str]:
        blocks: list[str] = []
        for body in self.bodies():
            for entry in body.get("system") or []:
                if isinstance(entry, Mapping) and entry.get("type") == "text":
                    blocks.append(entry.get("text", ""))
            for message in body.get("messages") or []:
                content = message.get("content")
                if isinstance(content, str):
                    blocks.append(content)
                    continue
                for entry in content or []:
                    if isinstance(entry, Mapping) and entry.get("type") == "text":
                        blocks.append(entry.get("text", ""))
        return blocks

    def contains(self, payload: bytes) -> bool:
        wanted = payload.decode("utf-8")
        return any(wanted in block for block in self.texts())


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(command: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command), capture_output=True, text=True, check=False, timeout=300, **kwargs
    )


class ProbeProject:
    """A disposable Claude project outside the workspace."""

    def __init__(self, base: Path) -> None:
        self.root = base / "project"
        (self.root / ".claude").mkdir(parents=True)
        self.memory = self.root / "CLAUDE.md"
        self.memory.write_text(
            f"{NATIVE_MARKER}\n\nThis probe project memory file exists only to test"
            " native discovery.\n",
            encoding="utf-8", newline="\n",
        )
        self.settings = self.root / ".claude/settings.json"
        self.base = base

    def write_hook(self, event: str, command: str) -> None:
        self.settings.write_text(
            json.dumps({"hooks": {event: [{"hooks": [{"type": "command", "command": command}]}]}}),
            encoding="utf-8",
        )

    def clear_hooks(self) -> None:
        if self.settings.exists():
            self.settings.unlink()

    def purge(self) -> None:
        _run(["claude", "project", "purge", str(self.root), "--yes"])


def _client_environment(capture: Capture) -> dict[str, str]:
    environment = dict(os.environ)
    environment["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{capture.port}"
    environment["ANTHROPIC_API_KEY"] = DUMMY_KEY
    environment.pop("ANTHROPIC_AUTH_TOKEN", None)
    return environment


def _print_run(
    project: ProbeProject, capture: Capture, extra: Sequence[str] = (), prompt: str | None = "SAY PROBE",
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = ["claude", "-p"]
    if prompt is not None:
        command.append(prompt)
    command += [
        "--model", PROBE_MODEL, "--tools", "", "--output-format", "json",
        "--no-session-persistence", *extra,
    ]
    return _run(command, cwd=str(project.root), env=_client_environment(capture), input=stdin)


def probe_identity() -> dict[str, Any]:
    """Record the exact resolved client, runtime, and platform identities."""
    resolved = shutil.which("claude")
    real = Path(resolved).resolve() if resolved else None
    doctor = _run(["claude", "doctor"]).stdout
    installations = [
        line.strip("- ").strip() for line in doctor.splitlines() if line.strip().startswith("- ")
    ]
    return {
        "claude_command": resolved,
        "claude_resolved_path": str(real) if real else None,
        "claude_sha256": _sha256(real.read_bytes()) if real and real.is_file() else None,
        "claude_version": _run(["claude", "--version"]).stdout.strip(),
        "doctor_commit": next(
            (line.split(":", 1)[1].strip() for line in doctor.splitlines() if line.startswith("Commit:")),
            None,
        ),
        "doctor_platform": next(
            (line.split(":", 1)[1].strip() for line in doctor.splitlines() if line.startswith("Platform:")),
            None,
        ),
        "doctor_reported_installations": installations,
        "node_version": _run(["node", "--version"]).stdout.strip(),
        "python_version": sys.version.split()[0],
        "os_release": next(
            (
                line.split("=", 1)[1].strip().strip('"')
                for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines()
                if line.startswith("PRETTY_NAME=")
            ),
            None,
        ),
        "kernel": os.uname().release,
        "machine": os.uname().machine,
    }


def probe_authentication() -> dict[str, Any]:
    """Record only non-identifying authentication facts."""
    result = _run(["claude", "auth", "status", "--json"])
    try:
        status = json.loads(result.stdout)
    except ValueError:
        return {"available": False, "logged_in": None, "auth_method": None, "subscription": None}
    return {
        "available": result.returncode == 0,
        "logged_in": status.get("loggedIn"),
        "auth_method": status.get("authMethod"),
        "api_provider": status.get("apiProvider"),
        "subscription": status.get("subscriptionType"),
    }


def probe_hook_events(identity: Mapping[str, Any]) -> dict[str, Any]:
    """Report which hook event names the installed executable contains."""
    path = identity.get("claude_resolved_path")
    if not path or not Path(path).is_file():
        return {"mechanism": "unavailable", "events": {}}
    result = _run(["strings", "-n", "6", path])
    present = set(result.stdout.splitlines())
    return {
        "mechanism": "strings(1) over the installed executable",
        "events": {event: event in present for event in HOOK_EVENTS},
    }


def _hook_command(runner: Path, event: str, size: int, mode: str) -> str:
    return (
        f"W12_EVENT={event} W12_SIZE={size} W12_MODE={mode} "
        f"{sys.executable} {runner}"
    )


def _write_hook_runner(base: Path) -> Path:
    runner = base / "hook_runner.py"
    runner.write_text(
        "import json, os, sys\n"
        "sys.path.insert(0, os.environ['W12_PROBE_DIR'])\n"
        "from probe_claude_capabilities import build_fixture\n"
        "sys.stdin.read()\n"
        "payload = build_fixture(int(os.environ['W12_SIZE']), os.environ['W12_MODE'])\n"
        "sys.stdout.write(json.dumps({'hookSpecificOutput': {\n"
        "    'hookEventName': os.environ['W12_EVENT'],\n"
        "    'additionalContext': payload.decode('utf-8'),\n"
        "}}))\n",
        encoding="utf-8",
    )
    return runner


def probe_hook_channel(project: ProbeProject, runner: Path, event: str) -> list[dict[str, Any]]:
    """Bisect the exact ``additionalContext`` limit for one hook event."""
    observations = []
    for size in HOOK_CHANNEL_SIZES:
        for mode in ("ascii", "mixed"):
            fixture = build_fixture(size, mode)
            capture = Capture(project.base / f"capture-{event}-{mode}-{size}")
            project.write_hook(event, _hook_command(runner, event, size, mode))
            try:
                self_test = _print_run(project, capture)
                observations.append({
                    "event": event,
                    "mode": mode,
                    "fixture_bytes": size,
                    "fixture_characters": len(fixture.decode("utf-8")),
                    "fixture_sha256": _sha256(fixture),
                    "exact_model_input": capture.contains(fixture),
                    "client_exit_code": self_test.returncode,
                })
            finally:
                capture.close()
                project.clear_hooks()
    return observations


def probe_wrapper_channels(project: ProbeProject) -> list[dict[str, Any]]:
    """Measure the launcher-controlled full-content channels."""
    observations = []
    for channel in ("append-system-prompt", "stdin-prompt"):
        for size in WRAPPER_SIZES:
            fixture = build_fixture(size, "mixed")
            text = fixture.decode("utf-8")
            capture = Capture(project.base / f"capture-{channel}-{size}")
            observation: dict[str, Any] = {
                "channel": channel,
                "fixture_bytes": size,
                "fixture_sha256": _sha256(fixture),
            }
            try:
                if channel == "append-system-prompt":
                    result = _print_run(project, capture, extra=["--append-system-prompt", text])
                else:
                    result = _print_run(
                        project, capture, prompt=None, stdin=f"{text}\nSAY PROBE",
                    )
            except OSError as error:
                # A single argument above the operating system's per-argument
                # limit never reaches the client; that boundary belongs to the
                # channel record, not to client behavior.
                observation.update({
                    "exact_model_input": False,
                    "client_exit_code": None,
                    "invocation_error": f"{type(error).__name__}: {error.strerror or error}",
                })
            else:
                observation.update({
                    "exact_model_input": capture.contains(fixture),
                    "client_exit_code": result.returncode,
                    "client_stderr_excerpt": result.stderr.strip()[:200] or None,
                    "invocation_error": None,
                })
            finally:
                capture.close()
            observations.append(observation)
    return observations


def probe_native_discovery(project: ProbeProject) -> dict[str, Any]:
    """Compare the delivered project-memory content with its exact source."""
    capture = Capture(project.base / "capture-native")
    try:
        _print_run(project, capture)
        source = project.memory.read_bytes()
        blocks = capture.texts()
        joined = "\n".join(blocks)
        return {
            "source_path": "CLAUDE.md",
            "source_bytes": len(source),
            "source_sha256": _sha256(source),
            "exact_content_in_model_input": source.decode("utf-8") in joined,
            "absolute_path_labelled": str(project.memory) in joined,
            "marker_present": NATIVE_MARKER in joined,
        }
    finally:
        capture.close()


def probe_trust_and_project_settings(project: ProbeProject, runner: Path) -> dict[str, Any]:
    """Record whether untrusted project settings still execute in print mode."""
    config = Path(os.path.expanduser("~/.claude.json"))
    trusted_before = None
    if config.is_file():
        try:
            projects = json.loads(config.read_text(encoding="utf-8")).get("projects", {})
            trusted_before = projects.get(str(project.root), {}).get("hasTrustDialogAccepted")
        except (ValueError, UnicodeDecodeError):
            trusted_before = None
    capture = Capture(project.base / "capture-trust")
    project.write_hook("UserPromptSubmit", _hook_command(runner, "UserPromptSubmit", 8192, "ascii"))
    try:
        result = _print_run(project, capture)
        return {
            "trust_record_before_run": trusted_before,
            "trust_record_mechanism": "~/.claude.json projects[<path>].hasTrustDialogAccepted",
            "project_settings_hook_executed_without_trust_record": capture.contains(
                build_fixture(8192, "ascii")
            ),
            "client_exit_code": result.returncode,
        }
    finally:
        capture.close()
        project.clear_hooks()


def probe_lifecycle(project: ProbeProject) -> dict[str, Any]:
    """Record the session identities a launcher can bind before invocation."""
    capture = Capture(project.base / "capture-lifecycle")
    requested = "22222222-2222-4222-8222-222222222222"

    def _session(extra: Sequence[str], prompt: str) -> str | None:
        command = [
            "claude", "-p", prompt, "--model", PROBE_MODEL, "--tools", "",
            "--output-format", "json", *extra,
        ]
        result = _run(command, cwd=str(project.root), env=_client_environment(capture))
        try:
            return json.loads(result.stdout).get("session_id")
        except ValueError:
            return None

    try:
        start = _session(["--session-id", requested], "one")
        resumed = _session(["-r", requested], "two")
        forked = _session(["-r", requested, "--fork-session"], "three")
        fresh = _session([], "four")
        return {
            "requested_session_id": requested,
            "start_session_id": start,
            "resume_session_id": resumed,
            "fork_session_id": forked,
            "fresh_session_id": fresh,
            "launcher_owned_identity_before_invocation": start == requested,
            "resume_preserves_identity": resumed == requested,
            "fork_creates_new_identity": bool(forked) and forked != requested,
            "fresh_start_creates_new_identity": bool(fresh) and fresh != requested,
            "compaction_transition_captured": False,
        }
    finally:
        capture.close()


def probe_debug_exposure(project: ProbeProject) -> dict[str, Any]:
    """Check whether the client's own debug output reveals the model input."""
    capture = Capture(project.base / "capture-debug")
    log = project.base / "debug.log"
    try:
        _print_run(project, capture, extra=["-d", "api,hooks", "--debug-file", str(log)])
        text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        return {
            "mechanism": "claude -p -d api,hooks --debug-file",
            "debug_bytes": len(text.encode("utf-8")),
            "logs_api_request_lines": "[API REQUEST]" in text,
            "exposes_model_input_body": NATIVE_MARKER in text,
        }
    finally:
        capture.close()


def _pty_session(project: ProbeProject, capture: Capture, arguments: Sequence[str], log: Path) -> None:
    """Drive one bounded interactive session over a pty."""
    import pty
    import select

    pid, descriptor = pty.fork()
    if pid == 0:
        os.chdir(str(project.root))
        environment = _client_environment(capture)
        environment["TERM"] = "xterm-256color"
        os.execvpe("claude", ["claude", *arguments], environment)
    keystrokes = [
        (6.0, b"\r"), (9.0, b"2"), (11.0, b"\r"), (16.0, b"SAY PROBE"), (19.0, b"\r"),
        (45.0, b"\x03"), (47.0, b"\x04"), (49.0, b"\x04"),
    ]
    captured = bytearray()
    started = time.time()
    index = 0
    while time.time() - started < 70:
        elapsed = time.time() - started
        while index < len(keystrokes) and elapsed >= keystrokes[index][0]:
            try:
                os.write(descriptor, keystrokes[index][1])
            except OSError:
                pass
            index += 1
        ready, _, _ = select.select([descriptor], [], [], 0.4)
        if ready:
            try:
                chunk = os.read(descriptor, 65536)
            except OSError:
                break
            if not chunk:
                break
            captured.extend(chunk)
        if index >= len(keystrokes) and elapsed > 55:
            break
    log.write_bytes(bytes(captured))
    try:
        os.kill(pid, 9)
    except OSError:
        pass


def probe_interactive(project: ProbeProject, runner: Path) -> dict[str, Any]:
    """Measure the interactive row: startup gating, hook channel, and wrapper."""
    observations: dict[str, Any] = {"attempted": True}
    session = "35353535-3535-4535-8535-353535353535"
    for size in (10000, 10001):
        fixture = build_fixture(size, "ascii")
        capture = Capture(project.base / f"capture-interactive-hook-{size}")
        project.write_hook("UserPromptSubmit", _hook_command(runner, "UserPromptSubmit", size, "ascii"))
        try:
            _pty_session(
                project, capture,
                ["--model", PROBE_MODEL, "--tools", "", "--session-id", session],
                project.base / f"interactive-{size}.log",
            )
            observations[f"hook_additional_context_{size}_exact"] = capture.contains(fixture)
        finally:
            capture.close()
            project.clear_hooks()
    fixture = build_fixture(32768, "mixed")
    capture = Capture(project.base / "capture-interactive-wrapper")
    try:
        _pty_session(
            project, capture,
            [
                "--model", PROBE_MODEL, "--tools", "", "--session-id", session,
                "--append-system-prompt", fixture.decode("utf-8"),
            ],
            project.base / "interactive-wrapper.log",
        )
        observations["append_system_prompt_32768_exact"] = capture.contains(fixture)
        observations["model_input_requests_captured"] = len(capture.bodies())
    finally:
        capture.close()
    return observations


def _summarise_hook_limit(observations: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    exact = [row for row in observations if row["exact_model_input"]]
    rejected = [row for row in observations if not row["exact_model_input"]]
    return {
        "max_exact_characters": max((row["fixture_characters"] for row in exact), default=None),
        "min_rejected_characters": min((row["fixture_characters"] for row in rejected), default=None),
        "max_exact_bytes": max((row["fixture_bytes"] for row in exact), default=None),
    }


def run_probe(*, interactive: bool) -> dict[str, Any]:
    identity = probe_identity()
    with tempfile.TemporaryDirectory(prefix="w12-claude-probe-") as temporary:
        base = Path(temporary)
        project = ProbeProject(base)
        runner = _write_hook_runner(base)
        os.environ["W12_PROBE_DIR"] = str(Path(__file__).resolve().parent)
        try:
            hook_rows = probe_hook_channel(project, runner, "UserPromptSubmit")
            session_start_rows = probe_hook_channel(project, runner, "SessionStart")
            report = {
                "probe_id": PROBE_ID,
                "probe_source_sha256": _sha256(Path(__file__).resolve().read_bytes()),
                "identity": identity,
                "authentication": probe_authentication(),
                "hook_events_present": probe_hook_events(identity),
                "hook_channel": {
                    "UserPromptSubmit": hook_rows,
                    "SessionStart": session_start_rows,
                    "user_prompt_submit_limit": _summarise_hook_limit(hook_rows),
                    "session_start_limit": _summarise_hook_limit(session_start_rows),
                },
                "wrapper_channels": probe_wrapper_channels(project),
                "native_discovery": probe_native_discovery(project),
                "trust": probe_trust_and_project_settings(project, runner),
                "lifecycle": probe_lifecycle(project),
                "debug_exposure": probe_debug_exposure(project),
            }
            report["interactive"] = (
                probe_interactive(project, runner) if interactive else {"attempted": False}
            )
            return report
        finally:
            project.purge()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="machine-readable observation path")
    parser.add_argument(
        "--interactive", action="store_true",
        help="also drive one bounded interactive pty session (requires settled startup dialogs)",
    )
    arguments = parser.parse_args(argv)
    report = run_probe(interactive=arguments.interactive)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
