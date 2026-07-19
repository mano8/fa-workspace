"""Phase 5 Claude delivery boundary.

The current Claude Code capability evidence is ``LIMITED``.  In particular it
does not prove trusted project-hook activation, byte-exact native-source
inspection, or either a bounded ``additionalContext`` channel or a larger
full-content channel.  This module deliberately does *not* invoke ``claude``
or activate a project hook while that remains true.

It provides the narrow adapter seam for a future, independently evidenced
Claude mode.  The shared W2b3 kernel still owns runtime storage, source-drift
rehashing, lifecycle, and receipt transitions.  Test-only transports may use
the seam to prove the kernel contract; they are not client evidence.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from agent_context import w2b1
from agent_context.delivery_kernel import (
    DeliveryKernel,
    DeliveryRequest,
    DeliveryResult,
    PreparedDelivery,
    TransportAdapter,
)


CURRENT_CLAUDE_MODES = {
    "interactive": "LIMITED",
    "non-interactive": "LIMITED",
}


def _fail(code: str, message: str) -> None:
    raise w2b1.AgentContextError(code, message)


@dataclass(frozen=True)
class ClaudeNativeInspection:
    """A future client-produced active-source inspection record.

    The adapter verifies the supplied hashes against the filesystem but does
    not manufacture this record.  A future Claude capability refresh must
    provide a real inspection mechanism before this can enable delivery.
    """

    mechanism: str
    trusted_project: bool
    active_hook: bool
    source_sha256: Mapping[str, str]


@dataclass(frozen=True)
class ClaudeChannelEvidence:
    """Verified channel limits for one future Claude capability row.

    ``additional_context_limit`` is the direct hook-channel maximum.  Payloads
    over that boundary require a separately tested full-content channel; a
    preview, file pointer, or truncation is never selected.
    """

    additional_context_limit: int | None
    full_content_channel_id: str | None
    full_content_limit: int | None

    def select(self, payload_bytes: int) -> str:
        if not isinstance(payload_bytes, int) or isinstance(payload_bytes, bool) or payload_bytes < 0:
            _fail("E_CHANNEL", "payload byte count is invalid")
        direct = self.additional_context_limit
        if isinstance(direct, int) and not isinstance(direct, bool) and direct >= 0:
            if payload_bytes <= direct:
                # Receipt channel identifiers follow the frozen lowercase
                # identifier grammar; the underlying Claude hook field is
                # named ``additionalContext``.
                return "claude-hook-additional-context"
        if (
            isinstance(self.full_content_channel_id, str)
            and self.full_content_channel_id
            and isinstance(self.full_content_limit, int)
            and not isinstance(self.full_content_limit, bool)
            and self.full_content_limit >= 0
            and payload_bytes <= self.full_content_limit
        ):
            return self.full_content_channel_id
        _fail("E_CHANNEL", "no verified Claude full-content channel fits this payload")


@dataclass(frozen=True)
class ClaudeAdapterConfiguration:
    """Claude-only activation inputs; current project activation is disabled."""

    capability_row: Mapping[str, object]
    channels: ClaudeChannelEvidence
    project_hook_configured: bool = False


CURRENT_CLAUDE_CONFIGURATION = ClaudeAdapterConfiguration(
    capability_row={
        "agent": "claude",
        "platform": "devcontainer",
        "mode": "non-interactive",
        "status": "LIMITED",
    },
    channels=ClaudeChannelEvidence(None, None, None),
    project_hook_configured=False,
)


class ClaudeDeliveryAdapter:
    """Preflight and channel selection around the shared delivery kernel.

    This class accepts a transport supplied by the client-specific integration.
    It never substitutes a shell invocation, temporary-file reference, or
    partial payload for an exact transport confirmation.
    """

    def __init__(self, configuration: ClaudeAdapterConfiguration) -> None:
        self.configuration = configuration

    def preflight(
        self,
        *,
        workspace_root: Path,
        expected_native_paths: tuple[str, ...],
        inspection: ClaudeNativeInspection,
    ) -> None:
        row = self.configuration.capability_row
        if row.get("agent") != "claude" or row.get("status") != "REQUIRED":
            _fail("E_UNSUPPORTED_MODE", "Claude canonical delivery is not supported by current capability evidence")
        if not self.configuration.project_hook_configured:
            _fail("E_TRUST", "the verified Claude project hook is not active")
        if not inspection.trusted_project or not inspection.active_hook:
            _fail("E_TRUST", "trusted Claude project hook activation cannot be proved")
        mechanism = row.get("inspection_mechanism")
        if not isinstance(mechanism, str) or not mechanism or inspection.mechanism != mechanism:
            _fail("E_NATIVE_EVIDENCE", "active Claude native-source inspection is not current")
        root = workspace_root.resolve(strict=True)
        for path in expected_native_paths:
            try:
                w2b1._canonical_path(path, "Claude native source path")
                candidate = root.joinpath(*path.split("/"))
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
                if candidate.is_symlink() or not resolved.is_file():
                    _fail("E_NATIVE_EVIDENCE", "Claude native source is not a contained regular file")
                observed = hashlib.sha256(resolved.read_bytes()).hexdigest()
            except (OSError, ValueError) as error:
                _fail("E_NATIVE_EVIDENCE", f"Claude native source cannot be inspected: {error}")
            if inspection.source_sha256.get(path) != observed:
                _fail("E_NATIVE_EVIDENCE", "Claude native-source hash does not match inspection evidence")

    def prepare_and_handoff(
        self,
        *,
        request: DeliveryRequest,
        expected_native_paths: tuple[str, ...],
        inspection: ClaudeNativeInspection,
        transport: TransportAdapter,
        kernel: DeliveryKernel | None = None,
    ) -> DeliveryResult:
        """Perform the sole pre-task handoff after all Claude preflight gates."""
        self.preflight(
            workspace_root=request.workspace_root,
            expected_native_paths=expected_native_paths,
            inspection=inspection,
        )
        selected_channel = self.configuration.channels.select(
            len(request.resolved.envelope_bytes)
        )
        if request.channel_id != selected_channel:
            _fail("E_CHANNEL", "delivery request does not use the selected Claude channel")
        delivery_kernel = kernel or DeliveryKernel()
        prepared: PreparedDelivery = delivery_kernel.prepare(request)
        return delivery_kernel.handoff(prepared, transport)
