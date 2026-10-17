# M8 Workspace — Claude

`Workspace instruction set: m8-workspace-v2`

Compact, hand-maintained Claude bootstrap. Shared meaning is owned by
`.workspace/`, not by agent configuration. The workspace agent conventions
are imported here:

@.workspace/context/agent-conventions.md

## Scope

For a registered direct child, find its canonical root in
[`repo-types.json`](.workspace/repo-types.json). Its instructions
apply only within that repository and cannot authorize sibling
work. A child must remain usable without this parent workspace.

## Canonical owners

[Architecture](.workspace/architecture.md),
[invariants](.workspace/invariants.json),
[environment](.workspace/context/env.md),
[policy index](.workspace/policy.index.json),
[policy metadata](.workspace/policy.metadata.json) and the
[agent-context contract](.workspace/contracts/agent-context-w2a.contract.md).

## Claude delivery

The current Claude capability evidence is limited. Canonical resolved-context
delivery needs a verified launcher that fails closed on an unverified
preflight or handoff. Mutating or cross-repository tasks need the
recorded human authorization the contract defines.

This bootstrap does not invoke the resolver or hand off context.
Unwrapped native use is limited and is not canonical delivery. This
file never imports `AGENTS.md`.
