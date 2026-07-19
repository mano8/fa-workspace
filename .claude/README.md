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
