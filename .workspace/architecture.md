# Workspace Architecture

## Layers

### Platform Layer

- auth-sdk-m8
- media-sdk-m8
- fastapi-m8
- imgtools_m8
- security-tests-m8

### Service Layer

- fa-auth-m8
- media-service-m8
- media-worker-m8
- prompt-engine-m8
- reparto-docente-m8

### Client Layer

- fa-ui-m8 (Astro/Starlight host)
- astro-auth-m8
- astro-media-m8
- astro-prompt-m8
- astro-reparto-m8

### Shared Layer

- astro-ui-m8
- schemas
- contracts

---

## Dependency Rule

Clients -> Services -> Platform

NEVER reverse.

No service may import another service directly.

All cross-service communication must use contracts or HTTP APIs.

---

## Shared Workspace Context

The canonical storage for architecture, repository classification, policies,
contracts, plans, analyses, and status is `.workspace/`.

Codex and Claude may use different tools and execution workflows, but both must
load the same shared facts from `.workspace/`. Tool-specific configuration must
not redefine or copy shared workspace truth.

---

## Configuration Boundary

`fa-workspace` owns shared agent configuration, repository classification,
cross-repository architecture, shared policies and contracts, workspace
tooling, context resolution and launchers, workspace validation, and
workspace-only CI.

Each registered child repository independently owns its source code, internal
layout, repository-specific agent instructions, Git history, branches, CI,
tests, workflows, releases, delivery state, and local quality gates.

Workspace validation may check the presence and static shape of child
instruction files only as non-blocking integration diagnostics. It must not
run, emulate, parse, or interpret child CI, tests, workflows, Git branches,
remotes, releases, or delivery state.
