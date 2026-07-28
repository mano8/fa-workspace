"""CLI target for the Step 12.3 canonical Claude launcher.

The launcher owns the human-authorization boundary and the runtime lifecycle;
the adapter owns preflight, classification, and delivery.  Nothing here can
select a mutating or cross-repository task on the agent's behalf: a signed
capability must be supplied explicitly, and it is verified and atomically
redeemed before any preflight touches the client.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_context import authorization, w2b1
from agent_context.claude_delivery_adapter import ClaudeLauncherAdapter, find_workspace_root
from agent_context.delivery_kernel import DeliveryKernel, exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Launch canonical Claude context for registered direct-child repositories.",
    )
    parser.add_argument("--repository", action="append", required=True, help="repeatable registered direct-child repository id")
    parser.add_argument("--task", action="append", default=[], help="repeatable selected task id")
    parser.add_argument("--operation", action="append", default=[], help="repeatable authorized operation id")
    parser.add_argument(
        "--project", metavar="REPOSITORY_ID",
        help="launch directory; defaults to the workspace root and must otherwise be a selected repository",
    )
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
        help="print a metadata-only signing request and exit without invoking Claude",
    )
    lifecycle = parser.add_mutually_exclusive_group()
    lifecycle.add_argument(
        "--resume-runtime", metavar="SESSION_DIR",
        help="resume one completed verified generation from this runtime session directory",
    )
    lifecycle.add_argument(
        "--fresh", metavar="SESSION_DIR",
        help="discard this prior runtime's reuse eligibility and start generation zero",
    )
    parser.add_argument(
        "--cleanup-retained", type=int, metavar="MAX_SESSIONS",
        help="perform only owner-safe startup retention cleanup, then exit",
    )
    parser.add_argument("prompt", help="the user task passed to the Claude pre-task gate")
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
        capabilities = tuple(
            authorization.load_capability(root, value) for value in arguments.authorization
        )
        records, provenance, launch_id, trust_store = authorization.verify_authorizations(
            root=root, capabilities=capabilities, repositories=arguments.repository,
            tasks=arguments.task, operations=arguments.operation, prompt=arguments.prompt,
            external_root=arguments.authorization_external_root,
            trust_store=arguments.authorization_trust_store,
            replay_store=arguments.authorization_replay_store,
        )
        kernel = DeliveryKernel()
        if arguments.cleanup_retained is not None:
            print(kernel.cleanup_retained(root, max_sessions=arguments.cleanup_retained))
            return 0
        # Retention cleanup is deliberately fail-closed: an unsafe or reparsed
        # child prevents a new task from beginning instead of being skipped.
        kernel.cleanup_retained(root, max_sessions=8)
        adapter = ClaudeLauncherAdapter(strict_trust_identity=True)
        shared = {
            "workspace_root": root, "repository_ids": arguments.repository,
            "tasks": arguments.task, "operations": arguments.operation,
            "authorizations": records, "verified_authorization_provenance": provenance,
            "authorization_trust_store": trust_store, "project": arguments.project,
            "launch_id": launch_id, "prompt": arguments.prompt, "kernel": kernel,
        }
        if arguments.resume_runtime:
            runtime_dir = Path(arguments.resume_runtime)
            kernel._validate_runtime_dir(runtime_dir, root)
            result = adapter.resume_and_handoff_repositories(runtime_dir=runtime_dir, **shared)
        elif arguments.fresh:
            runtime_dir = Path(arguments.fresh)
            kernel._validate_runtime_dir(runtime_dir, root)
            result = adapter.fresh_and_handoff_repositories(prior_runtime_dir=runtime_dir, **shared)
        else:
            result = adapter.prepare_and_handoff_repositories(**shared)
        # The kernel receipt is metadata-only; source and envelope content is
        # never printed, logged, or written outside the ignored runtime session.
        print(result.receipt["receipt_id"])
        return 0
    except w2b1.AgentContextError as error:
        print(f"{error.code}: {error.message}", file=sys.stderr)
        return exit_code(error)


if __name__ == "__main__":
    raise SystemExit(main())
