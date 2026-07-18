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
