"""CLI target shared by the POSIX and PowerShell Phase 6.3 launchers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_context import w2b1
from agent_context.codex_adapter import CodexDeliveryAdapter, find_workspace_root
from agent_context.delivery_kernel import DeliveryKernel, exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch canonical Codex context for registered direct-child repositories.")
    parser.add_argument("--repository", action="append", required=True, help="repeatable registered direct-child repository id")
    parser.add_argument("--task", action="append", default=[], help="repeatable selected task id")
    parser.add_argument("--operation", action="append", default=[], help="repeatable authorized operation id")
    parser.add_argument(
        "--authorization", action="append", default=[], metavar="PATH",
        help="repeatable workspace-relative JSON authorization record",
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
        authorizations = tuple(_load_authorization(root, value) for value in arguments.authorization)
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
                authorizations=authorizations, prompt=arguments.prompt, kernel=kernel,
            )
        else:
            result = adapter.prepare_and_handoff_repositories(
                workspace_root=root, repository_ids=arguments.repository, tasks=arguments.task,
                operations=arguments.operation, authorizations=authorizations, prompt=arguments.prompt,
                kernel=kernel,
            )
        # The kernel receipt is metadata-only; do not write source/envelope content.
        print(result.receipt["receipt_id"])
        return 0
    except w2b1.AgentContextError as error:
        print(f"{error.code}: {error.message}", file=sys.stderr)
        return exit_code(error)


def _load_authorization(root: Path, value: str) -> dict[str, object]:
    """Load one explicit record without permitting a pointer outside the workspace."""
    try:
        w2b1._canonical_path(value, "authorization path")
        candidate = root.joinpath(*value.split("/"))
        info = candidate.lstat()
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError, w2b1.AgentContextError) as error:
        raise w2b1.AgentContextError("E_SCOPE_UNAVAILABLE", f"authorization path is unsafe: {error}") from error
    if candidate != resolved or not info or candidate.is_symlink() or not candidate.is_file():
        raise w2b1.AgentContextError("E_SCOPE_UNAVAILABLE", "authorization must be a regular workspace-relative file")
    try:
        parsed = w2b1.parse_strict_json(candidate.read_bytes())
    except (OSError, UnicodeDecodeError, w2b1.AgentContextError) as error:
        raise w2b1.AgentContextError("E_AUTHORIZATION", f"authorization record is invalid: {error}") from error
    if not isinstance(parsed, dict):
        raise w2b1.AgentContextError("E_AUTHORIZATION", "authorization record must be a JSON object")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
