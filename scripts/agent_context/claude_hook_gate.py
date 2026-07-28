"""Step 12.4 single pre-task injection authority for the Claude hook channel.

Step 12.1 measured that the client's ``UserPromptSubmit`` hook carries an exact
``additionalContext`` value up to 10,000 bytes and silently substitutes a
``<persisted-output>`` preview plus a temporary-file pointer above it, and that
``SessionStart`` carries the same value with the same boundary — so registering
both events would deliver two copies.  Step 12.3 built the fail-closed adapter
but left the hook row ineligible because no byte-exact round trip was frozen.

This module is the hook side of that channel.  It is invoked by the launcher's
own settings file, reads the client's hook JSON on stdin, and returns the exact
serialized envelope the launcher armed for that generation.  Everything it does
is deliberately narrow:

* it answers only ``UserPromptSubmit``; a second ``additionalContext`` event
  reaching this gate is a configuration failure, not a second delivery;
* it serves only the launcher-owned client session recorded in the armed
  channel state, so no other session — interactive or otherwise — can redeem
  another launch's envelope;
* it re-verifies the armed payload against its recorded hash, byte count, and
  the row's verified channel limit, so a drifted or oversize payload is never
  offered to the client;
* it claims each generation exactly once through atomic no-replace creation, so
  a repeated prompt in the same generation is answered without a second copy
  rather than by injecting again; and
* every failure exits non-zero with no claim, which blocks the prompt and makes
  the launcher's own post-run claim check fail closed.

The gate never reads a policy source, never resolves context, and never writes
outside the owner-only runtime session directory the kernel already owns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context import w2b1
from agent_context.delivery_kernel import DeliveryKernel, exit_code


HOOK_EVENT = "UserPromptSubmit"
CHANNEL_ID = "claude-hook-additional-context"
CHANNEL_STATE_ARTIFACT = "channel-state.json"
CHANNEL_ENVELOPE_ARTIFACT = "channel-envelope.bin"
CHANNEL_SETTINGS_ARTIFACT = "channel-settings.json"
# Blocking exit code for a pre-task hook: the client refuses the prompt and
# shows the reason instead of proceeding with unverified context.
BLOCKING_EXIT_CODE = 2
CHANNEL_STATE_FIELDS = frozenset({
    "schema_version", "channel_id", "launch_id", "client_session_id", "generation",
    "manifest_id", "envelope_sha256", "envelope_bytes", "verified_channel_limit",
    "effective_hard_limit", "model_visible_total", "round_trip_evidence_id",
    "capability_evidence_id", "launch_scope",
})


def _fail(code: str, message: str) -> NoReturn:
    raise w2b1.AgentContextError(code, message)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def claim_artifact(generation: int) -> str:
    """Return the exactly-once claim name for one launcher-controlled generation."""
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        _fail("E_USAGE", "the launcher generation must be a non-negative integer")
    return f"channel-claim-{generation:06d}.json"


def _positive(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _fail("E_CHANNEL", f"armed channel state has an invalid {field}")
    return value


def load_channel_state(kernel: DeliveryKernel, runtime_dir: Path) -> dict[str, Any]:
    """Read and fully validate the armed channel state; a partial one is fatal."""
    raw = kernel.read_channel_artifact(runtime_dir, CHANNEL_STATE_ARTIFACT)
    try:
        state = w2b1.parse_strict_json(raw)
    except w2b1.AgentContextError as error:
        _fail("E_CHANNEL", f"armed channel state is invalid: {error.message}")
    if not isinstance(state, dict) or set(state) != CHANNEL_STATE_FIELDS:
        _fail("E_CHANNEL", "armed channel state does not have its closed shape")
    if state["schema_version"] != 1 or state["channel_id"] != CHANNEL_ID:
        _fail("E_CHANNEL", "armed channel state is not this verified hook channel")
    for field in ("launch_id", "client_session_id", "manifest_id", "round_trip_evidence_id"):
        try:
            w2b1._identifier(state[field], field)
        except w2b1.AgentContextError:
            _fail("E_CHANNEL", f"armed channel state has an invalid {field}")
    try:
        w2b1._sha256(state["envelope_sha256"], "envelope_sha256")
    except w2b1.AgentContextError:
        _fail("E_CHANNEL", "armed channel state has an invalid envelope hash")
    for field in (
        "generation", "envelope_bytes", "verified_channel_limit", "effective_hard_limit",
        "model_visible_total",
    ):
        _positive(state[field], field)
    if state["model_visible_total"] > state["effective_hard_limit"]:
        _fail("E_BUDGET", "the armed generation exceeds its effective hard limit")
    return state


def armed_envelope(kernel: DeliveryKernel, runtime_dir: Path, state: Mapping[str, Any]) -> str:
    """Return the exact armed envelope text, or fail before offering anything.

    A truncated, drifted, or oversize payload is never delivered: the contract
    accepts only the complete serialized envelope the launcher resolved.
    """
    raw = kernel.read_channel_artifact(runtime_dir, CHANNEL_ENVELOPE_ARTIFACT)
    if len(raw) != state["envelope_bytes"]:
        _fail("E_CHANNEL", "the armed envelope byte count drifted after resolution")
    if hashlib.sha256(raw).hexdigest() != state["envelope_sha256"]:
        _fail("E_CHANNEL", "the armed envelope hash drifted after resolution")
    if len(raw) > state["verified_channel_limit"]:
        _fail("E_CHANNEL", "the armed envelope exceeds the verified channel limit")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail("E_SOURCE", "the armed envelope is not strict UTF-8")


def _hook_payload(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        _fail("E_CHANNEL", f"the client hook payload is not JSON: {error}")
    if not isinstance(payload, dict):
        _fail("E_CHANNEL", "the client hook payload is not a JSON object")
    return payload


def gate(
    *, runtime_dir: Path, payload: Mapping[str, Any], kernel: DeliveryKernel | None = None,
) -> dict[str, Any]:
    """Answer one pre-task gate invocation for one launcher-controlled generation."""
    delivery_kernel = kernel or DeliveryKernel()
    state = load_channel_state(delivery_kernel, runtime_dir)
    event = payload.get("hook_event_name")
    if event != HOOK_EVENT:
        # SessionStart carries the same value with the same boundary, so a
        # second registered event is rejected here rather than delivering twice.
        _fail("E_CHANNEL", f"only {HOOK_EVENT} is the pre-task injection authority")
    if payload.get("session_id") != state["client_session_id"]:
        _fail("E_LIFECYCLE", "this session does not own the armed Claude generation")
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd and str(Path(cwd).resolve()) != state["launch_scope"]:
        _fail("E_SCOPE_UNAVAILABLE", "the client launch scope differs from the armed scope")
    content = armed_envelope(delivery_kernel, runtime_dir, state)
    claim = {
        "schema_version": 1,
        "channel_id": CHANNEL_ID,
        "launch_id": state["launch_id"],
        "client_session_id": state["client_session_id"],
        "generation": state["generation"],
        "manifest_id": state["manifest_id"],
        "envelope_sha256": state["envelope_sha256"],
        "delivered_bytes": state["envelope_bytes"],
        "round_trip_evidence_id": state["round_trip_evidence_id"],
        "claimed_at": _now(),
    }
    try:
        delivery_kernel.write_channel_artifact(
            runtime_dir, claim_artifact(state["generation"]),
            w2b1.canonical_bytes(claim), replace=False,
        )
    except w2b1.AgentContextError as error:
        if error.code != "E_CONCURRENCY":
            raise
        # This generation was already delivered exactly once.  A later prompt in
        # the same session proceeds with no second copy of the same envelope.
        return {"hookSpecificOutput": {"hookEventName": HOOK_EVENT}}
    return {
        "hookSpecificOutput": {"hookEventName": HOOK_EVENT, "additionalContext": content}
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Return the launcher-armed Claude envelope for one pre-task gate.",
    )
    parser.add_argument(
        "--runtime-dir", type=Path, required=True,
        help="the owner-only runtime session directory that armed this generation",
    )
    arguments = parser.parse_args(argv)
    try:
        output = gate(
            runtime_dir=arguments.runtime_dir, payload=_hook_payload(sys.stdin.buffer.read()),
        )
    except w2b1.AgentContextError as error:
        # No claim is written on any failure, so the launcher's own post-run
        # check also fails closed rather than trusting this exit status alone.
        print(f"{error.code}: {error.message}", file=sys.stderr)
        return BLOCKING_EXIT_CODE
    sys.stdout.write(json.dumps(output))
    return 0


__all__ = [
    "BLOCKING_EXIT_CODE",
    "CHANNEL_ENVELOPE_ARTIFACT",
    "CHANNEL_ID",
    "CHANNEL_SETTINGS_ARTIFACT",
    "CHANNEL_STATE_ARTIFACT",
    "HOOK_EVENT",
    "claim_artifact",
    "exit_code",
    "gate",
]


if __name__ == "__main__":
    raise SystemExit(main())
