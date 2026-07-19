# Astro Plugin Policy

Shared architecture for the M8 Astro integration packages:
`astro-ui-m8` (canonical shared UI), `astro-auth-m8`, `astro-media-m8`,
`astro-prompt-m8`, `astro-reparto-m8`.

This file is the single source of truth for the rules common to all of them.
Per-repo `AGENTS.md` and `CLAUDE.md` files carry only what is specific to that
repo and must not restate the rules below. Loaded on top of
`context/typescript.md`.

---

## What these repos are

Each business plugin (`astro-auth-m8`, `astro-media-m8`, `astro-prompt-m8`,
`astro-reparto-m8`) is a self-contained Astro **integration package** (npm,
`@mano8/*`) that fronts exactly one backend service over its HTTP contract and
ships the full frontend it needs: typed schemas, API wrappers, an auth adapter,
optional React provider/hooks, injectable `.astro` routes, and default UI. They
are installed into a **host** Astro/Starlight app (`fa-ui-m8`); they never
contain the host and never depend on it.

`astro-ui-m8` is the **canonical shared UI layer** — not a business plugin and
not an Astro integration. It owns the shared shadcn registry (data-table, state
components, dialog-form/table-page recipes), the design-token bridge, generic
list-params helpers, and the shared test harness. It is exempt from the "fronts
one FastAPI service" rule. Business plugins consume it as a normal `dependency`.

---

## Dependency model (STRICT)

```text
fa-ui-m8 (host)
  └─ requires  astro-auth-m8            ← foundation plugin (baseline)
        ▲
        │ required auth peer
        ├─ astro-media-m8    (optional)
        ├─ astro-prompt-m8   (optional)
        └─ astro-reparto-m8  (optional)

UI registry edge (shadcn registryDependencies — install/copy-time, NOT runtime import):
  astro-auth-m8    ─┐
  astro-media-m8   ├─▶ astro-ui-m8  registry/r/{data-table,state,...}.json
  astro-prompt-m8  ┤
  astro-reparto-m8 ─┘
```

Each business plugin fronts exactly one FastAPI backend service that lives in
this workspace, pinned to that service's HTTP contract:

| Plugin              | FastAPI backend      | contract metadata block |
| ------------------- | -------------------- | ----------------------- |
| `astro-auth-m8`     | `fa-auth-m8`         | `faAuthM8`              |
| `astro-media-m8`    | `media-service-m8`   | `mediaServiceM8`        |
| `astro-prompt-m8`   | `prompt-engine-m8`   | `promptEngineM8`        |
| `astro-reparto-m8`  | `reparto-docente-m8` | `repartoDocenteM8`      |

The dependency is on the service's **HTTP contract only** (schemas + version
range), never on its Python source — see Contract pinning below.

- `astro-auth-m8` is the **foundation**: required by the host and by every
  other plugin. It owns authentication; no other plugin re-implements it.
- Every non-auth plugin is **optional per deployment** and depends on
  `@mano8/astro-auth-m8` as a peer, coupling only through that plugin's
  `*AuthAdapter` interface / the `fa-auth-astro` provider — never by importing
  auth internals.
- **No plugin imports another optional plugin.** No circular dependencies.
- Dependency direction follows
  [`ARCH-LAYER-DIRECTION`](../architecture.md#arch-layer-direction).
- Package portability follows
  [`PORTABLE-NO-WORKSPACE-PATHS`](../architecture.md#portable-no-workspace-paths).

---

## Canonical package layout

Keep to this shape; a repo omits parts it does not need but does not rename.

- `src/integration.ts` — Astro integration entry (default export). Route
  injection, vite env defines, auth-order/provider warnings.
- `src/middleware.ts` — request-middleware slot (guards live in the auth plugin).
- `src/runtime/config.ts` / `errors.ts` — runtime config + typed error classes.
- `src/runtime/client.ts` — fetch client (base resolution, bearer attach,
  401-refresh retry, Zod parse).
- `src/runtime/schemas.ts` — Zod schemas for the whole contract.
- `src/runtime/authAdapter.ts` — `*AuthAdapter` contract + `fa-auth` impl.
- `src/runtime/api/**` — typed API wrappers, one module per resource.
- `src/runtime/compatibility.ts` — backend version-range assertions.
- `src/runtime/routes.ts` — route-pattern builder for injection.
- `src/runtime/hooks/**`, `src/runtime/react/**` (+ `default-ui/`) — optional
  React layer.
- `src/routes/**` — injectable `.astro` starter routes.
- `src/scaffold/styles/*.css` — framework-neutral starter styling.
- `registry.json` + `registry/r/*.json` (+ `scripts/build-registry.mjs`) —
  shadcn skins, when the repo ships them (see UI delivery).

---

## Integration entry & modes

The default export is an `AstroIntegration` factory taking at least:
`{ apiBase, apiPrefix?, mode, auth: { provider }, locales, defaultLocale }`.

- `headless` — schemas/clients/adapter/hooks only; no pages injected. Host
  mounts UI through React islands wrapped in the plugin provider.
- `starter` — injects the plugin's default `.astro` routes via `injectRoute()`.
- `scaffolded` — consumer-owned views copied/edited in the host.

The integration must warn (not throw) when `astro-auth-m8` is absent or ordered
after this plugin, and must be listed **after** `faAuth` in the host config so
its auth adapter is backed by fa-auth-m8 tokens.

---

## Contract pinning

Each `package.json` carries a metadata block (`faAuthM8`, `mediaServiceM8`,
`promptEngineM8`, `repartoDocenteM8`) with `contract`, `testedServiceVersion`,
and `serviceVersionRange`. Keep it in sync with `schemas.ts` and
`compatibility.ts`; never widen the range silently. Browser-facing responses
follow
[`SEC-NO-SECRET-DISCLOSURE`](../architecture.md#sec-no-secret-disclosure).
Public modules are reached through explicit `package.json` `exports` subpaths;
update `exports` whenever a public module is added.

---

## UI delivery

Two supported ways to ship UI; a repo may use either or both:

1. **Package exports** — components/hooks via `/react`, `/hooks`, `/ui`,
   `/default-ui`. The host imports these directly.
2. **shadcn registry** — `registry.json` + built `registry/r/*.json` (via
   `scripts/build-registry.mjs`), listed in `files`, consumed by the host's
   `components.json` `registries` map as
   `./node_modules/@mano8/<pkg>/registry/r/{name}.json`. Skins stay pure
   shadcn/Tailwind and import live logic from this package's `/react` + `/hooks`
   exports rather than reimplementing it. Version-lock skin and logic together.

React UI targets React 18/19 islands, Tailwind, and shadcn/ui. Admin landing
views should be dashboards; destructive/maintenance actions go behind focused
confirmation panels.

---

## Host-registration contract (how `fa-ui-m8` mounts a plugin)

A plugin is enabled in a deployment when **its package is installed** AND **its
`PUBLIC_*_API_BASE` env is set**. The host must be able to satisfy the following
with only small, stable, clearly-marked integration points — never by copying
plugin logic:

- Detect install via `require.resolve`; wire the integration through a
  **dynamic `import()`** so an auth-only build never requires the package.
- Register a Starlight sidebar/menu group and (for `starter` mode) let the
  plugin inject its routes.
- Provide env defines and, for headless plugins whose modules the host imports
  statically, **stub aliases** (`src/lib/<plugin>-stubs/*`) so the build
  resolves when the plugin is absent.
- Add the registry to `components.json` `registries` (if the plugin ships one).

Optional plugins **must degrade safely when absent**: no install + no env ⇒ the
host builds and runs unchanged. Any new host-side requirement a plugin needs
must be documented in that plugin's repo-specific instruction file as a host
integration point; do not invent host APIs that do not exist — record missing
ones as follow-ups.

---

## Canonical UI layer — `astro-ui-m8` (extend-not-fork)

Shared-block ownership follows
[`CFG-SINGLE-WORKSPACE-OWNER`](../architecture.md#cfg-single-workspace-owner),
with `astro-ui-m8` as the declared owner. Business plugins consume the blocks
via `shadcn add` against
`./node_modules/@mano8/astro-ui-m8/registry/r/{name}.json`; files are **copied**
into the consumer app at install/setup time. `astro-ui-m8` is a build/registry
source — plugins do **not** runtime-import the copied components from it.

Canonical registry items (frozen names — never rename after a consumer depends):
`data-table`, `data-table-column-header`, `data-table-pagination`,
`data-table-view-options`, `data-table-server-toolbar`,
`data-table-server-faceted-filter`, `state-loading`, `state-empty`,
`state-error`, `state-unauthorized`, `dialog-form`, `table-page`.

**Extend-not-fork rule**: if a block is missing a capability, extend
`astro-ui-m8/registry/blocks/data-table` (with tests + rebuild) and document it
in `registry/README.md`, then consume downstream. Never copy a one-off table or
fork a registry block into a business plugin.

Runtime exports from `astro-ui-m8` are minimal: shared types, design-token
bridge (`src/lib/tokens.css`), generic list-params, and the test harness
(`@mano8/astro-ui-m8/testing`).

Every business plugin must:

- List `@mano8/astro-ui-m8` in `dependencies` (not devDependencies).
- Declare any `registryDependencies` on `astro-ui-m8` registry items in its
  own `registry.json`.
- Never own a `registry/blocks/data-table/data-table.tsx` — that file lives
  only in `astro-ui-m8`.

---

## Dual-mode + standalone-usability (hard requirement)

Every business plugin must provide **both modes**:

- **Full / starter routes** — registers production-ready, Starlight-layout-correct
  pages (Starlight page shell, left/top menu, global CSS wrappers). No bare/broken
  routes permitted.
- **Headless** — exposes the same views as React islands + hooks + schemas + API
  wrappers + registry skins for custom host composition.

Additional rules:

- [`STANDALONE-CHILD-USABILITY`](../architecture.md#standalone-child-usability)
  applies to every business plugin; a bare Starlight host is its standalone
  fixture.
- Configurable `basePath` per plugin (e.g. `auth`→`/account`, `media`→`/media`,
  `prompt`→`/prompt`, `reparto`→`/reparto`); two plugins must not register the
  same route path.
- In full mode a plugin registers default sidebar/nav metadata; in headless mode
  the host owns nav.
- Full mode must fail fast with a clear error when the required auth adapter is
  missing — never render broken runtime.
- Standalone installability is verified with the repository-selected package
  manager by running the `build` and `build:registry` scripts, a package dry
  run, and an install-from-tarball smoke test in a fresh Astro fixture.

---

## Shared hard rules

- Stateless client — no business logic beyond the service contract.
- Depend on `astro-auth-m8`; never re-implement auth. Couple via the adapter.
- [`ARCH-LAYER-DIRECTION`](../architecture.md#arch-layer-direction).
- [`SEC-NO-SECRET-DISCLOSURE`](../architecture.md#sec-no-secret-disclosure).
- [`CFG-SINGLE-WORKSPACE-OWNER`](../architecture.md#cfg-single-workspace-owner)
  and
  [`PORTABLE-NO-WORKSPACE-PATHS`](../architecture.md#portable-no-workspace-paths).
- Preserve each repository's existing coverage gate; where it is 100%, it must
  remain 100%. New features need tests.

---

## Commands (uniform scripts)

Run these package scripts through the manager selected by repository metadata
and the active tool profile:

- `build` - `tsc -p tsconfig.json` to `dist/` plus `build:registry` where
  shipped.
- `typecheck` - `tsc --noEmit`.
- `test` - Vitest with coverage.
- `test:unit` - Vitest without coverage.
