# Codex-specific configuration

Codex loads shared workspace truth from `.workspace/` through the root
`AGENTS.md`. Keep only Codex-specific workflows or local agent state here.

Do not duplicate architecture, repository classification, shared policies,
contracts, plans, analyses, or status in this directory. Shared workspace truth
is owned by `.workspace/` and selected through the faceted resolver.

## Delivery boundary

The only current canonical row is the evidence-backed Codex devcontainer
non-interactive mode. Its pre-task launcher verifies project trust, current
native evidence, source hashes, and the exact JCS envelope before passing
`developer_instructions` to `codex exec`. Interactive Codex and all current
Claude rows are `LIMITED`; unavailable Windows/host-POSIX rows are
`UNSUPPORTED`. Unwrapped native use is not canonical delivery.

Repository facets and explicit tasks are resolved after `always` units. Tasks
are opt-in and mutating or cross-repository tasks require exact human
authorization. See [`.workspace/README.md`](../.workspace/README.md) for
authority, overrides, budgets, accounting, standalone modes, runtime isolation,
receipt semantics, and capability-evidence invalidation. Instruction bytes are
separate from reasoning effort, output compression, and price.
