# M8 Workspace — Codex

`Workspace instruction set: m8-workspace-v2`

This is the compact Codex bootstrap for the workspace root. It is maintained
by hand; shared meaning is owned by `.workspace/`, not by agent configuration.

## Scope

For a registered direct child, identify its canonical repository root in
[`repo-types.json`](.workspace/repo-types.json). Codex may use the child's
`AGENTS.md` through native discovery after this bootstrap; child instructions
apply only within that repository and cannot authorize sibling work. A child
must remain usable without this parent workspace.

## Canonical owners

- Workspace architecture, ownership, security, portability, and standalone
  invariants: [architecture](.workspace/architecture.md) and
  [invariant catalog](.workspace/invariants.json).
- Environment profile rules and resolved `M8_*` tooling:
  [environment policy](.workspace/context/env.md).
- Repository facets and policy selection: [repository registry](.workspace/repo-types.json),
  [policy index](.workspace/policy.index.json), and
  [policy metadata](.workspace/policy.metadata.json).
- Semantic authority, repository scope, task authorization, and canonical
  delivery: [agent-context contract](.workspace/contracts/agent-context-w2a.contract.md).

## Selection and delivery

The resolver selects `always` units, then declared facets in registry order,
then explicitly requested task overlays. Tasks—especially mutating or
cross-repository tasks—require the recorded human authorization defined by the
contract; neither a repository nor these instructions can select them.

Use a verified launcher/adapter for canonical resolved-context delivery when
the capability evidence supports that mode; it must fail closed on an
unverified preflight or handoff. This bootstrap does not invoke the resolver or
hand off context. Unwrapped native use is limited and must not be described as
canonical delivery. This file never imports `CLAUDE.md`.
