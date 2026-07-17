# Codex-specific configuration

Codex loads shared workspace truth from `.workspace/` through the root
`AGENTS.md`. Keep only Codex-specific workflows or local agent state here.

Do not duplicate architecture, repository classification, shared policies,
contracts, plans, analyses, or status in this directory.

Legacy shared files may remain locally after migration because the workspace
protects `.codex/` history from destructive cleanup. They are ignored by Git,
are not authoritative, and must not be loaded; use `.workspace/` instead.
