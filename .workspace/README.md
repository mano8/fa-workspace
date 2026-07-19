# Shared Workspace Context

This directory is the tool-neutral source of truth for the M8 workspace.

Both Codex and Claude load architecture, repository classification, language
and environment policies, contracts, plans, analyses, and status from here.
Their tool-specific configuration remains separate in `AGENTS.md`/`.codex/`
and `CLAUDE.md`/`.claude/`.

## Ownership

- `architecture.md`: workspace layers and dependency rules
- `invariants.json`: canonical workspace-invariant IDs and definition owners
- `repo-types.json`: v2 direct-child repository classification and retained W3
  rollback selectors
- `policy.index.json`: active faceted v2 policy index, including the complete
  evidenced facet/task identifier set
- `policy.metadata.json`: closed metadata for active workspace policy units
- `policies/`: non-empty workspace invariant references plus facet and opt-in
  task policy slices
- `context/`: shared language, environment, Git, and framework policies
- `contracts/`: shared validation contracts
- `plans/`: canonical plans; migrated from `.claude/plans`
- `analyse/`: canonical architecture and security analyses
- `status/`: canonical operational status artifacts

Do not copy these files back into tool-specific directories. Tool-specific
instructions may define how work is performed, but must not redefine shared
workspace facts.

## Local tool profiles

Machine-specific workspace and tool paths for Windows, Linux, or macOS live in
ignored `.env.local` files. Container-specific values live in ignored
`.env.devcontainer` files. Safe templates are committed at the workspace root.
Use `scripts/Import-WorkspaceEnv.ps1` to validate and load a profile without
printing its values. On Windows, allow the script only for the current process
with `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then
dot-source it. In the dev container, source
`scripts/import-workspace-env.sh devcontainer`. Service credentials remain
owned by each service repo and must not be added to the root profiles.
