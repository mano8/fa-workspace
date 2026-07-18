# M8 Workspace

This is the workspace-level entrypoint.

For work inside a registered child repository, also load that repository's own AGENTS.md. Workspace rules apply globally; repository rules apply only
to that repository.

---

## Configuration Ownership

- Shared workspace truth lives in `.workspace/`.
- Codex-specific behavior lives in `AGENTS.md` and `.codex/`.
- Do NOT duplicate shared architecture, policies, plans, analyses, or status in
  tool-specific directories.

---

## Load Strategy

1. Read `.workspace/architecture.md`
2. Read `.workspace/repo-types.json`
3. Resolve repo type
4. Load `.workspace/policy.index.json`
5. Load ONLY matched `.workspace/` context files

> ALWAYS also read the target repo's own `AGENTS.md` before doing any work in
> that repo, every session. The workspace root `AGENTS.md` is the general one
> for all repos; the per-repo `AGENTS.md` carries repo-specific rules. Read both.

---

## Context Priority (STRICT)

If conflicts occur:

1. env.md (highest priority)
2. language policy (python/typescript/docker)
3. architecture.md
4. workspace.contract.md (validation only)

---

## Hard Constraints

- No cross-service imports without contracts
- No platform awareness of services
- No duplicated configuration across repos
- No implicit architecture decisions outside `.workspace/`
- NEVER ever mention a `co-authored-by` or similar aspects. In particular, never mention the tool used to create the commit message or PR.
