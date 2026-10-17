# Agent Conventions

Canonical owner of the commit, branch and pull-request conventions every
agent follows in every repository of this workspace, and of the agent-facing
pointers to the context owners the root bootstrap does not list. The root
`CLAUDE.md` imports this file, so Claude loads it natively with the
bootstrap.

Workspace invariant: [`CFG-SINGLE-WORKSPACE-OWNER`](../architecture.md#cfg-single-workspace-owner)
— no child repository or agent-specific directory may keep a competing copy.

## Commit conventions

- Never add a `Co-Authored-By` trailer to a commit. Commits are authored
  under the human's identity alone.
- Never put a Claude, Claude Code, Anthropic or model reference (no
  "Generated with Claude Code" footer, no model name) in a pull request's
  title or body.
- Never commit on, push to, or open a pull request from `main`. If the
  current branch has commits ahead of `main`, keep using it; otherwise
  create a new branch from `main`.

## Other context owners

- Per-repository version-source mechanism and one read command per
  mechanism: [version sources](version-sources.md).
- Release-cascade order and touchpoints from `auth-sdk-m8` / `fastapi-m8`:
  [dependency cascade](dependency-cascade.md).
- Object-storage backend contract, default and validated fallback:
  [object storage](object-storage.md).
- Debian patch-layer form of the five service images and the base-digest
  rule: [debian patch layer](debian-patch-layer.md).
- The full ownership index: [workspace README](../README.md).

## Does not own

Authorization for a commit, push or pull request belongs to the
[agent-context contract](../contracts/agent-context-w2a.contract.md) (W2a).
These conventions shape an authorized git operation; they never authorize
one.
