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

## Canonical Workspace Invariants

`.workspace/invariants.json` indexes these definitions. Each identifier below
has exactly one normative definition in the workspace.

### `ARCH-LAYER-DIRECTION`

Dependencies flow from clients to services to platform, never in reverse.
Services do not import other services directly; cross-service communication
uses contracts or HTTP APIs. Platform code remains reusable and has no service
awareness.

### `ARCH-NO-CROSS-SERVICE-DATA`

A service never reads or writes another service's database or private storage
directly. Cross-service data access uses an owned contract or HTTP API.

### `CFG-LOCAL-PROFILES-UNTRACKED`

Real host and devcontainer tool profiles remain local and ignored. Only safe,
secret-free profile templates may be tracked.

### `CFG-SINGLE-WORKSPACE-OWNER`

Every workspace-shared configuration or shared asset has one declared
canonical owner. Children and agent-specific directories consume or reference
that owner; they do not create authoritative duplicates or runtime forks.

### `PORTABLE-NO-WORKSPACE-PATHS`

An installable or published child artifact never depends on a hard-coded
workspace path or the presence of the parent checkout.

### `SEC-NO-SECRET-DISCLOSURE`

Agents, tools, logs, public browser contracts, and external processors never
disclose credentials, secrets, private keys, tokens, or private session
material. Secret-bearing local profiles are never printed.

### `SEC-NO-TRACKED-SECRETS`

Credentials, secrets, private keys, tokens, and other secret material are never
committed. They come from an ignored child-owned environment file, an approved
secret store or vault, or the system credential manager.

### `SEC-VALIDATE-UNTRUSTED-INPUT`

External or otherwise untrusted input is validated at its trust boundary before
it is used by application or infrastructure logic.

### `STANDALONE-CHILD-USABILITY`

When a repository kind requires standalone use, the child remains installable,
buildable, testable, and usable without the workspace host checkout.

---

## Ownership Allocation

Shared workspace truth follows
[`CFG-SINGLE-WORKSPACE-OWNER`](#cfg-single-workspace-owner) and lives in
`.workspace/`. Codex and Claude may use different tools and execution workflows,
but both load the same shared facts from that owner.

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
