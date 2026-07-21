"""CLI target shared by the POSIX and PowerShell Phase 6.3 launchers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_context import authorization, w2b1
from agent_context.codex_adapter import CodexDeliveryAdapter, find_workspace_root
from agent_context.delivery_kernel import DeliveryKernel, exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch canonical Codex context for registered direct-child repositories.")
    parser.add_argument("--repository", action="append", required=True, help="repeatable registered direct-child repository id")
    parser.add_argument("--task", action="append", default=[], help="repeatable selected task id")
    parser.add_argument("--operation", action="append", default=[], help="repeatable authorized operation id")
    parser.add_argument(
        "--authorization", action="append", default=[], metavar="PATH",
        help="repeatable workspace-relative signed authorization capability",
    )
    parser.add_argument(
        "--authorization-external-root", type=Path, metavar="PATH",
        help="owner-only external authorization root outside the workspace",
    )
    parser.add_argument(
        "--authorization-trust-store", type=Path, metavar="PATH",
        help="trust-store file contained by --authorization-external-root",
    )
    parser.add_argument(
        "--authorization-replay-store", type=Path, metavar="PATH",
        help="replay-store directory contained by --authorization-external-root",
    )
    parser.add_argument(
        "--prepare-authorization-request", action="store_true",
        help="print a metadata-only signing request and exit without executing Codex",
    )
    lifecycle = parser.add_mutually_exclusive_group()
    lifecycle.add_argument(
        "--resume-runtime", metavar="SESSION_DIR",
        help="resume one completed verified generation from this runtime session directory",
    )
    lifecycle.add_argument(
        "--fresh", action="store_true",
        help="start a new launch/thread and do not reuse any prior generation (the default)",
    )
    parser.add_argument(
        "--cleanup-retained", type=int, metavar="MAX_SESSIONS",
        help="perform only owner-safe startup retention cleanup, then exit",
    )
    parser.add_argument("prompt", help="the user task passed to codex exec")
    arguments = parser.parse_args(argv)
    try:
        root = find_workspace_root(Path.cwd())
        if arguments.prepare_authorization_request:
            if arguments.authorization or any((
                arguments.authorization_external_root,
                arguments.authorization_trust_store,
                arguments.authorization_replay_store,
            )):
                raise w2b1.AgentContextError(
                    "E_USAGE", "authorization request preparation cannot redeem a capability"
                )
            request = authorization.create_request(
                repositories=arguments.repository, tasks=arguments.task,
                operations=arguments.operation, user_task=arguments.prompt,
            )
            print(w2b1.canonical_bytes(request.as_dict()).decode("utf-8"))
            return 0
        capabilities = tuple(_load_capability(root, value) for value in arguments.authorization)
        records, provenance, launch_id, trust_store = _verified_authorizations(
            root=root, capabilities=capabilities,
            repositories=arguments.repository, tasks=arguments.task,
            operations=arguments.operation, prompt=arguments.prompt,
            external_root=arguments.authorization_external_root,
            trust_store=arguments.authorization_trust_store,
            replay_store=arguments.authorization_replay_store,
        )
        kernel = DeliveryKernel()
        if arguments.cleanup_retained is not None:
            print(kernel.cleanup_retained(root, max_sessions=arguments.cleanup_retained))
            return 0
        # Retention cleanup is deliberately fail-closed: unsafe/reparse
        # children prevent a new task from beginning instead of being skipped.
        kernel.cleanup_retained(root, max_sessions=8)
        adapter = CodexDeliveryAdapter(strict_trust_identity=True)
        if arguments.resume_runtime:
            runtime_dir = Path(arguments.resume_runtime)
            kernel._validate_runtime_dir(runtime_dir, root)
            result = adapter.resume_and_handoff_repositories(
                workspace_root=root, runtime_dir=runtime_dir, repository_ids=arguments.repository,
                tasks=arguments.task, operations=arguments.operation,
                authorizations=records, verified_authorization_provenance=provenance,
                authorization_trust_store=trust_store, launch_id=launch_id,
                prompt=arguments.prompt, kernel=kernel,
            )
        else:
            result = adapter.prepare_and_handoff_repositories(
                workspace_root=root, repository_ids=arguments.repository, tasks=arguments.task,
                operations=arguments.operation, authorizations=records,
                verified_authorization_provenance=provenance,
                authorization_trust_store=trust_store, launch_id=launch_id,
                prompt=arguments.prompt,
                kernel=kernel,
            )
        # The kernel receipt is metadata-only; do not write source/envelope content.
        print(result.receipt["receipt_id"])
        return 0
    except w2b1.AgentContextError as error:
        print(f"{error.code}: {error.message}", file=sys.stderr)
        return exit_code(error)


def _load_capability(root: Path, value: str) -> dict[str, object]:
    """Load one signed carrier without permitting a pointer outside the workspace."""
    try:
        w2b1._canonical_path(value, "authorization path")
        candidate = root.joinpath(*value.split("/"))
        info = candidate.lstat()
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError, w2b1.AgentContextError) as error:
        raise w2b1.AgentContextError("E_SCOPE_UNAVAILABLE", f"authorization capability path is unsafe: {error}") from error
    if candidate != resolved or not info or candidate.is_symlink() or not candidate.is_file():
        raise w2b1.AgentContextError("E_SCOPE_UNAVAILABLE", "authorization capability must be a regular workspace-relative file")
    try:
        parsed = w2b1.parse_strict_json(candidate.read_bytes())
    except (OSError, UnicodeDecodeError, w2b1.AgentContextError) as error:
        raise w2b1.AgentContextError("E_AUTHORIZATION", f"authorization capability is invalid: {error}") from error
    if not isinstance(parsed, dict):
        raise w2b1.AgentContextError("E_AUTHORIZATION", "authorization capability must be a JSON object")
    return parsed


# Retained only for source compatibility with older fixture imports.  The
# canonical launcher now interprets the loaded object as a signed capability.
_load_authorization = _load_capability


def _verified_authorizations(
    *, root: Path, capabilities: tuple[dict[str, object], ...],
    repositories: list[str], tasks: list[str], operations: list[str], prompt: str,
    external_root: Path | None, trust_store: Path | None, replay_store: Path | None,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, str], ...], str | None, Path | None]:
    """Authenticate and consume all signed capabilities before adapter preflight."""
    del root
    external_values = (external_root, trust_store, replay_store)
    if not capabilities:
        if any(value is not None for value in external_values):
            raise w2b1.AgentContextError(
                "E_USAGE", "external authorization paths require a signed capability"
            )
        return (), (), None, None
    if any(value is None for value in external_values):
        raise w2b1.AgentContextError(
            "E_AUTHORIZATION",
            "signed capabilities require external root, trust store, and replay store",
        )
    assert external_root is not None and trust_store is not None and replay_store is not None
    resolved_trust_store = trust_store if trust_store.is_absolute() else external_root / trust_store
    resolved_replay_store = replay_store if replay_store.is_absolute() else external_root / replay_store
    records: list[dict[str, object]] = []
    provenance: list[dict[str, str]] = []
    launch_ids: set[str] = set()
    for capability in capabilities:
        request = authorization.request_from_capability(
            capability, repositories=repositories, tasks=tasks,
            operations=operations, user_task=prompt,
        )
        verified = authorization.verify_and_redeem(
            capability, request=request, external_root=external_root,
            trust_store=resolved_trust_store, replay_store=resolved_replay_store,
        )
        item = verified.provenance.as_dict()
        launch_ids.add(request.launch_id)
        provenance.append(item)
        records.append({
            "authorization_id": item["authorization_id"],
            "kind": "named-owner-decision",
            "authorized_by": item["issuer"],
            "source_ref": f"ed25519:{item['key_id']}:{item['redemption_id']}",
            "source_sha256": item["signed_payload_sha256"],
            "repositories": list(request.repositories),
            "operations": list(request.operations),
            "issued_at": item["issued_at"],
        })
    if len(launch_ids) != 1:
        raise w2b1.AgentContextError(
            "E_AUTHORIZATION", "all signed capabilities must bind the same launch_id"
        )
    ordered = sorted(zip(records, provenance, strict=True), key=lambda pair: pair[0]["authorization_id"])
    return (
        tuple(pair[0] for pair in ordered),
        tuple(pair[1] for pair in ordered),
        next(iter(launch_ids)),
        resolved_trust_store,
    )


if __name__ == "__main__":
    raise SystemExit(main())
