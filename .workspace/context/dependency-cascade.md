# Dependency Cascade

Canonical owner of the **order** and the **touchpoints** of a release cascade
that starts at a platform package — today `auth-sdk-m8` or `fastapi-m8` — and
ends at the compose stacks, the client compatibility matrices and the
workspace version matrix. The next cascade is a walk down this file, not a
rediscovery of the fleet.

Workspace invariant: [`CFG-SINGLE-WORKSPACE-OWNER`](../architecture.md#cfg-single-workspace-owner)
— no child repository or agent-specific directory keeps a competing copy of
this graph. Agent skills that drive a cascade reference this file; they do not
restate it.

This file does **not** own:

- versions, published state, or the read command per mechanism —
  [version sources](version-sources.md) owns those;
- the environment-file rules — [environment policy](env.md) owns those;
- authorization — the [agent-context contract](../contracts/agent-context-w2a.contract.md)
  and the `release`, `cross-repository`, `branch`, `commit`, `push` and
  `pull-request` task policies own those. **Nothing here authorizes a change
  in any repository.** Every child step below is child-owned and needs its
  own recorded human authorization for that repository and operation.

## Rules every phase obeys

These are already binding elsewhere; they are collected here because a
cascade breaks when one of them is skipped.

1. **Pin only what is published.** A consumer may pin a version only after it
   has been read back from its registry (PyPI, npm, Docker Hub) — not from a
   local tag list, not from a merged PR ([version sources](version-sources.md#published-release-vs-working-tree-version)).
2. **One bump per unpublished release.** If a repository already has an
   unpublished version on `main`, the cascade change rides it (`### Changed`
   or `### Fixed` under the existing heading). Only a repository whose current
   version is published takes a new version.
3. **Narrow lock moves.** Regenerate a hashed lock with
   `pip-compile --upgrade-package <name>==<version>` for exactly the cascade
   packages. A blanket `--upgrade` moves dozens of unrelated pins (`G22`).
4. **Layer order.** Phases run top-down; within one phase the repositories are
   independent and may proceed in parallel.
5. **Env changes ship with the code that reads them.** An env-surface change
   is never a follow-up PR: the settings code, every `.env.example`-class file
   and every README that documents the key move in the same child change.
6. **Real env values are never read or printed**
   ([`SEC-NO-SECRET-DISCLOSURE`](../architecture.md#sec-no-secret-disclosure)).
   The fleet's compose stacks are development-only, so a real env file may be
   compared with its template **by key name only** and aligned: a missing key
   is appended with the template's value (a secret therefore arrives as
   `changethis` and fails closed at boot), a key the template no longer has is
   removed. Every template secret is exactly `changethis` and carries a
   `# Value:` comment with its length and character rules; each stack README
   has a generated `Environment files` section listing which service reads
   which file.
7. **The version matrix is written last**, from read-back evidence.

## The graph (measured 2026-09-26 from working trees)

```text
auth-sdk-m8                         platform SDK
├── fastapi-m8                      pyproject range + COMPAT_MATRIX row
│   ├── media-service-m8            fastapi-m8 floor; auth-sdk-m8 transitive in lock
│   ├── prompt-engine-m8            fastapi-m8 floor; auth-sdk-m8 transitive in lock
│   ├── reparto-docente-m8          fastapi-m8 floor; auth-sdk-m8 transitive in lock
│   └── (fa-auth-m8 examples/fastapi_full — rides fa-auth-m8, not a repository)
└── fa-auth-m8                      issuer; direct auth-sdk-m8 floor + lock

service images ──► compose stacks (five repositories + operator-local rpi_server)
service versions ─► astro plugin compatibility.ts ─► plugin patch releases
plugin releases ──► fa-ui-m8/app floors
everything ───────► .workspace/context/version-sources.md
```

**Not in this cascade** (no `auth-sdk-m8` or `fastapi-m8` pin, measured
2026-09-26): `media-worker-m8`, `media-sdk-m8`, `imgtools_m8`,
`security-tests-m8`. `security-tests-m8/tests/test_deployment.py` names
`tepochtli/fa-auth-m8` tags as test fixtures, not as pins; leave them.

Consumer services never import `auth-sdk-m8` directly
(`media-service-m8/REPOSITORY_CONTEXT.md`); their `auth-sdk-m8` pin exists only
in the hashed lock, pulled in via `fastapi-m8`. It still moves, because the
lock is what the image ships.

### Env-settings inheritance

An env key is a field on a pydantic-settings class. The cascade's env surface
is the union of these bases:

| Class | Owner | Inherited by |
| --- | --- | --- |
| `CommonSettings` | `auth-sdk-m8` `auth_sdk_m8/core/config.py` | issuer and every consumer |
| `ObservabilitySettingsMixin` | `auth-sdk-m8` `auth_sdk_m8/observability/settings.py` | issuer and every consumer |
| `ConsumerAuthMixin` | `auth-sdk-m8` `auth_sdk_m8/core/consumer.py` | consumers only (via `ConsumerServiceSettings`) |
| `ConsumerServiceSettings` | `fastapi-m8` `fastapi_m8/config.py` | `media-service-m8`, `prompt-engine-m8`, `reparto-docente-m8`, `fa-auth-m8/examples/fastapi_*` |
| `Settings(ObservabilitySettingsMixin, CommonSettings)` | `fa-auth-m8` `auth_user_service/core/config.py` | — (the issuer) |

So a key added to `ConsumerAuthMixin` touches the three consumers but **not**
the issuer's own `.env.example`; a key added to `CommonSettings` touches all
four services. A **renamed or removed** key is breaking for every inheritor
and forces at least a minor bump in each (a major if the service contract
changes).

## Phases

Each phase ends at a **gate**. Do not start the next phase until its gate is
read back.

### Phase 0 — Plan

1. Run the checker (see [*Checker*](#checker)) with the target versions to
   list every touchpoint that disagrees.
2. For each repository in the graph, decide *ride* or *new version* under rule
   2, and the bump level: a dependency-only move is a **patch**; a new env key
   or new behavior is a **minor**; a removed/renamed key or contract break is
   a **major**.
3. Diff the settings classes between the published tag and the target (the
   checker's env diff). If nothing changed, Phase 4 is skipped.
4. Obtain one authorization per repository and operation before touching it.

### Phase 1 — `auth-sdk-m8`

Child-owned release under that repository's own procedure.

**Gate:** the new version is PyPI's latest and installs.

### Phase 2 — `fastapi-m8`

| Touchpoint | What moves |
| --- | --- |
| `pyproject.toml` `dependencies` | the `auth-sdk-m8[...]` floor |
| `pyproject.toml` `[project] version` **and** `fastapi_m8/_version.py` | the version (two sources; `tests/test_version_source_parity.py` holds them equal) |
| `fastapi_m8/_compat.py` `COMPAT_MATRIX` | a row for every new `fastapi-m8` **minor**, with the new `auth-sdk-m8` range. Since `4.4.0` a missing row **fails closed at startup** |
| `README.md` `## Compatibility` table | the same row, for every minor that `COMPAT_MATRIX` has |
| `fastapi_m8/config.py` `ConsumerServiceSettings` | only when the SDK's settings surface changed (Phase 4) |
| `.env.example`, `README.md` | only when Phase 4 applies |
| `CHANGELOG.md` | the entry |

**Gate:** the new version is PyPI's latest.

### Phase 3 — Issuer and consumers (parallel)

**`fa-auth-m8`** (issuer):

| Touchpoint | What moves |
| --- | --- |
| `auth_user_service/requirements_base.txt` | the `auth-sdk-m8` floor |
| `auth_user_service/requirements_prod.lock` | narrow `pip-compile --upgrade-package auth-sdk-m8==<v>` |
| `examples/fastapi_full/requirements_base.txt` | the `fastapi-m8` floor |
| `examples/fastapi_full/requirements_prod.lock` | narrow upgrade of `fastapi-m8` and `auth-sdk-m8` |
| `.github/workflows/database-integration.yaml` | the inline `fastapi-m8[...]` install range |
| version in **three** files | `auth_user_service/__init__.py`, `examples/fastapi_full/__init__.py`, `examples/fastapi_minimal/__init__.py` (repository rule: *Example version alignment*) |
| `CHANGELOG.md` | the entry |

**`media-service-m8`, `prompt-engine-m8`, `reparto-docente-m8`** (consumers):

| Touchpoint | What moves |
| --- | --- |
| `<pkg>/requirements_base.txt` | the `fastapi-m8` floor |
| `<pkg>/requirements_prod.lock` | narrow upgrade of `fastapi-m8` and `auth-sdk-m8` |
| `<pkg>/__init__.py` `__version__` | the version (re-surfaced as `SERVICE_VERSION` in `<pkg>/core/config.py`) |
| `README.md` | any stated `fastapi-m8 >=` / `auth-sdk-m8 >=` floor the change makes false |
| `CHANGELOG.md` | the entry |

Package directories: `media_service`, `promt_engine_service` (sic),
`reparto_service`.

**Gate:** each image tag is on Docker Hub and pulled, and its in-container
`__version__` equals the tag.

### Phase 4 — Env sync (conditional; runs **inside** Phases 2, 3 and 5)

Runs only if Phase 0's settings diff is non-empty. Per rule 5 it is not a
separate step in time: each repository applies it in the same change as its
bump. For each changed key, per affected inheritor (see the inheritance
table):

1. Service code that reads or validates the key, if any.
2. The repository's own `.env.example` (placeholder `changethis` for secrets).
3. Every compose stack template in that repository that configures the
   service: `.env.example`, `env.example`, `*.env.example`,
   `.env.production.example`.
4. The compose stack's `README.md` and the repository `README.md`, where they
   document the key.
5. Operator-local real env files — listed for the operator, never opened.

A key with a safe default may be omitted from templates only if the owning
repository's existing templates already omit keys of that kind; otherwise add
it.

### Phase 5 — Compose repin

Pin each stack to the tags published in Phase 3. Image tags measured
2026-09-26:

| Stack | Pins |
| --- | --- |
| `fa-auth-m8/examples/docker_compose/hardened_m8` (base + `production`) | `fa-auth-m8` |
| `fa-auth-m8/examples/docker_compose/vault_dev_m8` | `fa-auth-m8` |
| `fa-ui-m8/docker_compose/dev_ui_m8` | `fa-auth-m8`, `media-service-m8`, `media-worker-m8` |
| `fa-ui-m8/docker_compose/hardened_ui_m8` (base + `production`) | `fa-auth-m8`, `media-service-m8`, `media-worker-m8` |
| `media-service-m8/docker_compose/dev_media_m8` | `fa-auth-m8`, `media-worker-m8` |
| `media-service-m8/docker_compose/hardened_media_m8` | `fa-auth-m8`, `media-service-m8`, `media-worker-m8` |
| `prompt-engine-m8/docker_compose/dev_prompt_engine_m8` | `fa-auth-m8` |
| `reparto-docente-m8/docker_compose/dev_reparto_m8` | `fa-auth-m8` |
| `rpi_server/docente_reparto` (**operator-local, gitignored**) | `fa-auth-m8`, `reparto-docente-m8` |

The other stacks build their service from source and pin no tag. Tags are
also **stated in prose**: `fa-auth-m8/README.md`, `fa-auth-m8/DOCKERHUB.md`,
and the `README.md` beside each pinned stack (and
`media-service-m8/docker_compose/README.md`). Those move with the pin.

`rpi_server/` is ignored by the workspace repository, so no commit delivers
its repin; it is the operator's deployment and is reported, not edited,
unless the operator asks.

**Gate:** each stack's `docker compose config` resolves (run by the child's
own gate — workspace tooling does not run child compose).

### Phase 6 — Client compatibility matrices

Each plugin's `src/runtime/compatibility.ts` carries four constants for its
backend:

| Plugin | Backend | Prefix |
| --- | --- | --- |
| `astro-auth-m8` | `fa-auth-m8` | `FA_AUTH_M8_` |
| `astro-media-m8` | `media-service-m8` | `MEDIA_SERVICE_M8_` |
| `astro-prompt-m8` | `prompt-engine-m8` | `PROMPT_ENGINE_M8_` |
| `astro-reparto-m8` | `reparto-docente-m8` | `REPARTO_` |

- `*_TESTED_SERVICE_VERSION` moves to the published service version.
- `*_MIN_SERVICE_VERSION` / `*_MAX_SERVICE_VERSION_EXCLUSIVE` move **only**
  when the service's API contract or service-version range changed; the
  service axis and contract axis move independently
  ([version sources](version-sources.md), *Service version is not contract
  version*).
- `*_CONTRACT_VERSION` moves only on a contract change.
- The explanatory comment above the constants and any README sentence naming
  the tested version move with them.

Order: `astro-auth-m8` first — the three siblings peer it — then the others in
parallel, each raising its auth peer floor only if `astro-auth-m8` released.
Each is a plugin release under rule 2. Then `fa-ui-m8/app` moves its floors
(it is never published, so it has no version row). The Wave 9 cascade in
[version sources](version-sources.md) is the precedent.

**Gate:** each plugin's npm `latest` equals the release and the tarball's
`compatibility` export carries the new tested version.

### Phase 7 — Workspace records

Workspace-owned, so a `fa-workspace` change (still under authorization):

| Touchpoint | What moves |
| --- | --- |
| [version sources](version-sources.md) | the mechanism map row, the *Published release vs working-tree version* table, and a dated section recording the cascade (package, version, tag = `main` merge, floors shipped), under that file's evidence rules |
| `scripts/conformance/local_package_matrix.py` `EXPECTED_SDK_VERSION` / `EXPECTED_FASTAPI_VERSION` / `EXPECTED_ISSUER_VERSION` | the platform matrix the conformance harness proves |
| `.github/workflows/cross-repo-conformance.yml` `SDK_REF` / `FASTAPI_REF` / `ISSUER_REF` | the tags that harness checks out — they move with the constants above, never apart |

The conformance pair was last moved on 2026-07-31 (`3.1.0` / `4.2.1` /
`2.0.0`) and was not part of any later cascade; the checker reports it until
it catches up. Moving it re-runs the harness against the new tags, which can
fail on a real parity break — that failure is a cascade finding, not noise.

## Checker

`scripts/cascade/check_cascade.py` is this file's executable mirror. It reads
the touchpoints above from the working trees and reports every one that
disagrees with its target:

```bash
# Consistency: targets default to each repository's working-tree version.
"$M8_PYTHON" scripts/cascade/check_cascade.py
# Preview a planned bump: override any target.
"$M8_PYTHON" scripts/cascade/check_cascade.py --set auth-sdk-m8=3.3.0 --set fastapi-m8=4.6.0
# Env surface between two refs of a platform package (TO may be WORKTREE).
"$M8_PYTHON" scripts/cascade/check_cascade.py --env-diff auth-sdk-m8 v3.2.0 WORKTREE
```

Add `--json` for machine output. Exit `0` means nothing to report, `1` means
findings, `2` means a source could not be read. Findings in `rpi_server/` are
tagged `[operator-local]`.

It is operator tooling. It reads tracked child source files (and `git show`
for `--env-diff`), prints paths and key names but never values, and never
opens a real env file, runs child CI, tests or compose, or reads a registry.
It is not part of workspace validation. It does not see prose that states a
version in free text (for example a plugin README's "tested against"
sentence); the phase tables above list those.

Run it at Phase 0 to build the work list and after Phase 7 as the exit check;
a cascade is closed when it reports nothing.

When a new pin, stack, plugin or settings base appears in the fleet, update
this file and the checker in the same change.
