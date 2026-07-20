# Claude-specific configuration

Claude Code loads shared workspace truth from `.workspace/` through the root
`CLAUDE.md`. Keep only Claude-specific settings, agents, commands, hooks, or
local memory here.

Do not duplicate architecture, repository classification, shared policies,
contracts, plans, analyses, or status in this directory.

The tracked project settings contain only portable shared safety boundaries;
personal approvals, paths, and memory stay in ignored local storage. Auto-memory
is disabled for this project. Add a path-scoped rule only after measuring its
need; put a conditional procedure in a skill rather than an always-loaded rule.

## Delivery boundary

Current Claude capability evidence is `LIMITED` for both interactive and
non-interactive Dev Container rows. This project therefore makes no canonical
Claude delivery claim: native loading is reported separately, and an adapter
must fail closed when inspection, full-content transport, trust, or lifecycle
evidence is unavailable. Parent-found workspace enhancement and parent-absent
standalone child context are distinct modes.

See [`.workspace/README.md`](../.workspace/README.md) for the shared resolver
order, explicit task authorization, native/injected delivery rules, exact
non-overlapping byte accounting, budgets, runtime isolation, receipt meaning,
and evidence invalidation triggers. Instruction context is distinct from
reasoning effort, output compression, and price.
