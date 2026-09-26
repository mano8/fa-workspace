# Version Sources

`A33-version-source-parity` (`.workspace/plans/stack/todo/` — gitignored, not
the authority; this file is). A fleet cannot be audited on a property it
stores four different ways. This file is the one workspace-owned map of how
each registered repository's authoritative version is stored, plus one
documented read command per mechanism, so the next sweep is a command and not
an investigation.

Workspace invariant: [`CFG-SINGLE-WORKSPACE-OWNER`](../architecture.md#cfg-single-workspace-owner)
— this record is the sole canonical owner of the fleet-wide version-source
map; no child repository or agent-specific directory may keep a competing
copy.

## Map (measured 2026-08-16 against on-disk source, whole fleet re-read)

Rows of this map have been corrected after that measurement from targeted
source re-reads rather than a fleet re-measurement: `astro-prompt-m8` `1.2.0`
→ `2.0.0` (2026-08-23), then `astro-ui-m8` `1.4.2` → `1.5.0` and
`media-sdk-m8` `0.6.0` → `0.7.0` (2026-08-24), then on 2026-08-30
`astro-auth-m8` `2.4.0` → `2.4.1`, `astro-ui-m8` `1.5.0` → `1.5.1` and
`media-worker-m8` `0.4.0` → `0.4.1` (see *The media pair re-measured*).

`prompt-engine-m8` `2.0.0` → `2.1.0` was corrected in the same pass for a
different reason: this table had been **contradicting the two tables below it**,
which already carried `2.1.0 (pending)`. A row can go stale against source; a
row that disagrees with its own file is a transcription miss, and it survived
because the 2026-08-30 prompt-pair edit moved the published and contract tables
without moving the mechanism map. Every other value here still dates from
2026-08-16. The published table below records the independently verified
release state.

| Mechanism | Repos (version at measurement) |
| --- | --- |
| npm `package.json` at repo root | `astro-auth-m8` 2.6.0 · `astro-media-m8` 2.2.0 · `astro-prompt-m8` 2.1.0 · `astro-reparto-m8` 2.3.0 · `astro-ui-m8` 1.5.1 |
| npm `package.json` **not** at repo root | `fa-ui-m8` 0.1.0 — at `app/package.json` |
| `pyproject.toml` `[project] version` literal | `auth-sdk-m8` 3.2.0 · `fastapi-m8` 4.5.1 · `media-sdk-m8` 1.0.0 · `security-tests-m8` 0.7.0 |
| `pyproject.toml` `dynamic` → `__init__.__version__` | `imgtools_m8` 2.1.3 — read from `origin/main` 2026-09-26 |
| package `__init__.__version__` only (no pyproject version) | `fa-auth-m8` (`auth_user_service`) 2.2.3 · `media-service-m8` (`media_service`) 3.0.2 · `media-worker-m8` (`worker`) 1.0.1 · `prompt-engine-m8` (`promt_engine_service`) 2.2.1 · `reparto-docente-m8` (`reparto_service`) 2.2.2 — read from `origin/main` 2026-09-22; the three consumers re-surface it as `SERVICE_VERSION` in `<pkg>/core/config.py`. `fa-auth-m8` also carries the string in `examples/fastapi_full/__init__.py` and `examples/fastapi_minimal/__init__.py`, which move with it |

## Published release vs working-tree version

The map above records what the **working tree** holds. That is not the same
question as what a consumer can install, and conflating the two is how the
fleet's pin drift started. The table below separates them: *published* is the
newest tag on `origin` (verified with `git ls-remote --tags origin`, not from
a local tag list — several clones' local tags are stale), *working tree* is the
value the map above reads.

A consumer may only pin a **published** version. An unpublished working-tree
version rides its repo's pending release per the remediation plan's Wave 6c
one-bump-per-unpublished-release rule.

| Repo | Published | Working tree | Pending? |
| --- | --- | --- | --- |
| `auth-sdk-m8` | 3.2.0 | 3.2.0 | — published |
| `fastapi-m8` | 4.5.1 | 4.5.1 | — published |
| `fa-auth-m8` | 2.2.3 | 2.2.3 | — published (2026-09-26, tag `v2.2.3` = `main` `3df05f5`, the `B32` pin merge; `tepochtli/fa-auth-m8:2.2.3` pulled, in-container `__version__` `2.2.3`). Carries `B27`, `B29`, `B30` and `B32` |
| `imgtools_m8` | 2.1.3 | 2.1.3 | — published (2026-09-26, tag `v2.1.3` on `origin`, on PyPI; PR #75 — CI and dev-requirement bumps only, dependencies unchanged since `2.1.1`) |
| `security-tests-m8` | 0.7.0 | 0.7.0 | — published |
| `media-sdk-m8` | 1.0.0 | 1.0.0 | — published (2026-09-15; see *Wave 8 publish* below) |
| `media-service-m8` | 3.0.2 | 3.0.2 | — published (2026-09-26, tag `v3.0.2` = `main` `35e518b`; `tepochtli/media-service-m8:3.0.2` pulled, `__version__` `3.0.2`). Carries `B23`, `B27`, `B29`, `B30` and `B32`; `3.0.0`/`3.0.1` published 2026-09-16, see *Wave 8 publish* below |
| `media-worker-m8` | 1.0.2 | 1.0.2 | — published (2026-09-26, tag `v1.0.2` = `main` `de3282b`, the `imgtools_m8` `2.1.3` pin merge, PR #10; `tepochtli/media-worker-m8:1.0.2` pulled, `__version__` `1.0.2`). Carries `B29`, `B30` and the `imgtools_m8` `2.1.3` pin |
| `prompt-engine-m8` | 2.2.1 | 2.2.1 | — published (2026-09-26, tag `v2.2.1` = `main` `fd74ef3`; `tepochtli/prompt-engine-m8:2.2.1` pulled, `__version__` `2.2.1`). Carries `B23`, `B24`, `B27`, `B29`, `B30` and `B32` |
| `reparto-docente-m8` | 2.2.2 | 2.2.2 | — published (2026-09-26, tag `v2.2.2` = `main` `169121b`; `tepochtli/reparto-docente-m8:2.2.2` pulled, `__version__` `2.2.2`). Carries `B27`, `B28`, `B30` and `B32` |
| `fa-ui-m8` | — never published | 0.1.0 | pending |
| `astro-ui-m8` | 1.5.1 | 1.5.1 | — published. `main` (`07da9b1`, PR #16) adds `CHANGELOG.md` to `files` and changes nothing a consumer runs; it reaches npm with the next ordinary release, and no bump is owed |
| `astro-auth-m8` | 2.7.0 | 2.7.0 | — published (2026-09-26, tag `v2.7.0` = `main` `a5273f6`, PR #29; npm `latest` = `2.7.0`, tarball `testedServiceVersion` `2.2.3`). Tracks `fa-auth-m8` `2.2.3` (`B31`) and carries `B30`'s publish-workflow hardening |
| `astro-media-m8` | 2.3.0 | 2.3.0 | — published (2026-09-26, tag `v2.3.0` = `main` `4bcd4f6`, PR #16; npm `latest` `2.3.0`; tarball tests `media-service-m8` `3.0.2`, auth peer `^2.7.0`, ships `CHANGELOG.md`). `2.1.0` and the `2.2.0` tracking release were published 2026-09-16, see *Wave 8 publish* below |
| `astro-prompt-m8` | 2.2.0 | 2.2.0 | — published (2026-09-26, tag `v2.2.0` = `main` `b9dcebf`, PR #21; npm `latest` `2.2.0`; tarball tests `prompt-engine-m8` `2.2.1`, auth peer `^2.7.0`). The unpublished `2.1.1` (`B12`, on `main` since 2026-09-20) was renumbered `2.2.0` by `B31` and never shipped |
| `astro-reparto-m8` | 2.3.0 | 2.3.0 | — published (2026-09-26, tag `v2.3.0` = `main` `b887c8d`, PR #9; npm `latest` `2.3.0`; tarball tests `reparto-docente-m8` `2.2.2`, auth peer `^2.7.0`, ships `CHANGELOG.md`; see *`astro-reparto-m8` 2.3.0 — the service-version gate* below) |

Three rows moved on 2026-08-23, each re-read against its own remote rather
than as part of a fleet sweep. `prompt-engine-m8` `1.0.0` → `2.0.0` and
`astro-prompt-m8` `1.1.1` → `2.0.0`: the service/client pair released
together, because the `1.1.1` client cannot drive a `2.0.0` service. Evidence
is the tag on `origin` in both cases — `816e083` and `f69d6c1`, each the tip
of its own `main` — plus the artifact each tag produced: the
`Publish Docker Image` run for the service and
`@mano8/astro-prompt-m8@2.0.0` on the npm registry for the client.
`astro-auth-m8` `2.0.0` → `2.1.0` is not part of that release; the row was
simply stale, caught because `astro-prompt-m8@2.0.0` names auth `^2.1.0` as a
peer and the version was checked before the pin was moved. Its `v2.1.0` tag is
on `origin` and `2.1.0` is npm's `latest`.

The requester supplied the current fleet publication ledger on 2026-08-24:
`auth-sdk-m8@3.1.3`, `fastapi-m8@4.4.0`, `fa-auth-m8@2.0.3`,
`imgtools_m8@2.1.1`, `security-tests-m8@0.6.0`,
`prompt-engine-m8@2.0.0`, `astro-ui-m8@1.4.2`,
`astro-auth-m8@2.1.0`, and `astro-prompt-m8@2.0.0` are published. A direct PyPI
check additionally confirms `media-sdk-m8@0.7.0` is published; its wheel hash
matches both consumer production locks. The other rows retain the pending state
shown above. For this UX wave, `astro-ui-m8` has additionally moved to 1.5.0 in
source for the shared `tree-view`, but npm and `origin` still stop at 1.4.2;
`astro-media-m8` cannot produce a valid registry-backed 1.5.0 lock until that
release exists.

Three rows moved on 2026-08-29 while preparing the reparto release pair
(remediation `W7.3`, plan
`.workspace/plans/docentes/todo/2026-08-28-reparto-limitations-remediation-plan.md`).

`astro-auth-m8`'s row was **stale, not merely behind**: it read published
`2.1.0` / working tree `2.1.0`, while `2.2.0` had been the working-tree value
since `53bf224 chore(release): prepare astro auth 2.2.0` and is published.
`fa-ui-m8/app/package-lock.json` resolves
`https://registry.npmjs.org/@mano8/astro-auth-m8/-/astro-auth-m8-2.2.0.tgz`,
which is the independent evidence for the published column. The working tree is
now `2.3.0`: additive behaviour (a coordinated single-flight refresh, a
negative-only session hint) plus **one new `localStorage` key**, which reads as
a minor rather than a patch.

`reparto-docente-m8` and `astro-reparto-m8` keep published `1.1.0` / `1.0.0`
against a working tree of `2.0.0` **and do not move to `3.0.0`**, though both
carry breaking changes. The operator ruled on 2026-08-29 that neither `2.0.0`
was ever published, so the breaking work rides the pending release rather than
taking a number of its own — the Wave 6c one-bump-per-unpublished-release rule
recorded above, and the same ruling that settled this repository's earlier
`3.0.0`/`2.0.0` split (see *Convergence*). Both `[Unreleased]` changelog
sections were folded into the existing, never-published `## [2.0.0]` sections
and redated `2026-08-29`. This supersedes the remediation plan's decision 6,
which had argued `3.0.0` for the pair.

`astro-prompt-m8` moved `2.0.0` → `2.1.0` on 2026-08-29, closing the reparto
remediation plan's own loose end. `2.0.0` **is** published, so the two changes
`W7.3` and `W7.7` left in its `[Unreleased]` section — the auth peer floor
`^2.1.0` → `^2.3.0`, which is published surface, and the fleet gate exemption —
had no version to ride, and the repository's `C22` changelog/version parity test
was failing on exactly that (it requires the `package.json` version to head a
non-empty entry *and* `[Unreleased]` to be genuinely empty after a fold). The
same release carries `W7.7`'s named follow-up: the third copy of the role
hierarchy is deleted in favour of the `@mano8/astro-auth-m8/authorization`
import the widened `C12` now permits. A minor, not a major: this repository's
own rule is that its major tracks the supported `prompt-engine-m8` **API
contract**, which does not move here, and no published name, signature or
answer changes. ~~Pending until it is tagged, so the Wave 6c rule applies to it
— further pre-tag work belongs in `## [2.1.0]` rather than in a new section.~~
Publication is the human's act, and it has happened: `astro-prompt-m8@2.1.0` is
tagged on `origin` (`092cf70da0b3`), so the Wave 6c ride is over and further
work here takes a new version rather than joining `## [2.1.0]`.

The rule above — a consumer may only pin a published version — has a
converse this release made visible: a consumer does not pick up a **major**
through a caret it already carries. `fa-ui-m8` pinned
`@mano8/astro-prompt-m8@^1.1.1`, which excludes `2.0.0`, so the host needed an
explicit repoint to `^2.0.0` after the publish rather than an install. When a
row here moves across a major, check the consumers' ranges as well as their
lockfiles.

~~**Open as of 2026-08-29:** all four `astro-auth-m8` consumers
(`astro-media-m8`, `astro-prompt-m8`, `astro-reparto-m8` in both
`peerDependencies` and `devDependencies`, and `fa-ui-m8/app` as a direct
dependency) now name `^2.3.0`, which is **not yet published**.~~ ✅ **Half
closed 2026-08-29: `astro-auth-m8@2.3.0` is published.** Independent evidence,
as this file requires: `npm view @mano8/astro-auth-m8 versions` lists `2.3.0`
and `dist-tags.latest` is `2.3.0`. The manifest ranges are no longer ahead of
the registry, so the deliberate inversion of the pin-only-published rule is
over.

✅ **Fully closed 2026-08-29.** `npm install` was run in each of
`astro-media-m8`, `astro-prompt-m8`, `astro-reparto-m8` and `fa-ui-m8/app`; all
four lockfiles now resolve `astro-auth-m8-2.3.0.tgz`, so `npm ci` no longer
disagrees with the manifest in any of them. The host was rebuilt against the
new install and verified to actually carry `W3.1`/`W3.2`: the installed
package now ships `dist/src/runtime/sessionHint.js` and `runRefresh`
references, both absent from the old `2.2.0` install. This was the remainder
of the plan's `W7.4`, now fully delivered.

### `astro-auth-m8` 2.3.0 → 2.4.0 (2026-08-30, pending)

The working tree moved to `2.4.0` on the open PR
[`mano8/astro-auth-m8#21`](https://github.com/mano8/astro-auth-m8/pull/21)
(`feat/auth-role-superuser-consistency`). **This is the fleet's first release
whose entire justification is a commitment rather than a code change.** The
published diff against `2.3.0` is one JSDoc block in
`src/runtime/authorization.ts`; nothing a consumer executes moves at all. The
bump exists because `./authorization` changed *standing*: remediation `W7.7`
made it the one subpath of this package a sibling business plugin may import,
and `^2.4.0` is the range that carries that guarantee. Two consumers already
depend on it in code rather than in principle —
`astro-prompt-m8/src/runtime/authAdapter.ts` and
`astro-reparto-m8/src/runtime/authAdapter.ts` both `import … from
"@mano8/astro-auth-m8/authorization"` instead of mirroring the hierarchy — so
for them the floor is load-bearing, not bookkeeping.

Minor rather than patch, on this repository's own rule: the major tracks the
supported `fa-auth-m8` API contract, which does not move (`fa-auth-m8@2.0`,
`>=2.0.0 <3.0.0`), and a *new supported import surface* is added capability, not
a fix.

The release was blocked by a red gate, since green: `d9254e2` bumped
`package.json`/`package-lock.json` but left the work in `[Unreleased]`, so the
`A32` changelog/version-parity test failed on both Node matrix legs — the same
defect class this file records for `astro-prompt-m8@2.1.0`, one release later.
`e4812fa` folded the entry.

✅ **Closed 2026-08-30, in one pass.** `2.4.0` is published — `npm view
@mano8/astro-auth-m8 dist-tags.latest` answers `2.4.0`, the independent
evidence this file requires. The pin-ahead-of-registry window was real but
short: all four consumer manifests were moved to `^2.4.0` first and `npm
install` answered `ETARGET — No matching version found` in each, so no
lockfile could be or was regenerated until the publish landed. Afterwards
`npm install` ran in `astro-media-m8`, `astro-prompt-m8`, `astro-reparto-m8`
and `fa-ui-m8/app`; all four lockfiles now resolve
`astro-auth-m8-2.4.0.tgz`, and `npm ls @mano8/astro-auth-m8` from
`fa-ui-m8/app` resolves the host's own dependency and all three plugins to a
single `2.4.0` — no duplicate copy of the hierarchy in the host's tree, which
is the property the whole `W7.7` exercise exists to produce.

Every consumer gate was re-run green against that install: `astro-media-m8`
(9 fleet gates, 100% coverage), `astro-prompt-m8` (9 gates, 100%),
`astro-reparto-m8` (9 gates, 992 tests at 100%, and
`verify:contract-operations` reporting 116 declared operations all served by
`reparto-docente-m8@2.0.0`), and the `fa-ui-m8` host (144 tests, clean
typecheck and lint, 192 pages built with `dist/index.html` present).

### Three further rows measured 2026-08-30

Re-measured in the same pass, because a matrix that is only right about the
row you came to change is not a matrix.

`reparto-docente-m8` `1.1.0` → **`2.0.0`, published.** Evidence is the tag on
`origin`: `git ls-remote --tags origin` lists
`e523f40da0cc04ee211add88a2c3d3267b1587f0 refs/tags/v2.0.0`. This is the
service half of the release pair remediation `W7.3` prepared and decision 6
settled (the breaking work rides the never-published `2.0.0` rather than
taking a `3.0.0`). ~~**The client half is still pending** — `astro-reparto-m8`
remains published `1.0.0` against a working tree of `2.0.0` — so the pair is
currently half-released, which is exactly the state this table exists to make
visible rather than to hide.~~ ✅ **Closed 2026-08-30: `astro-reparto-m8@2.0.0`
is published** (`refs/tags/v2.0.0` on `origin`, `01144c558a3f`). The reparto
pair is whole.

`astro-ui-m8` `1.4.2` → **`1.5.0`, published.** This closes the constraint
recorded above under the 2026-08-24 ledger, that "`astro-media-m8` cannot
produce a valid registry-backed 1.5.0 lock until that release exists". It now
exists.

`astro-media-m8`'s **working tree** row was stale, not behind: it read
`1.2.0`, while `package.json` has been `2.0.0`. Corrected by direct read
(`(Get-Content astro-media-m8/package.json -Raw | ConvertFrom-Json).version`
→ `2.0.0`) and confirmed by the resolved install tree, which reports
`@mano8/astro-media-m8@2.0.0`. Published still stops at `1.1.1`, so the row
stays pending, and the gap is now a **major**.

~~That last point does **not** trigger the converse rule recorded below, and
the reason is worth stating because it is easy to get wrong: `fa-ui-m8/app`
consumes the three business plugins as path links
(`"@mano8/astro-media-m8": "file:../../astro-media-m8"`, likewise prompt and
reparto), not as registry ranges. A `file:` link has no semver range to
exclude a major, so the host tracks those three working trees directly and
needs no repoint when they publish.~~ ❌ **Retracted 2026-09-06: this is not
what the host does.** There is no `file:` specifier in
`fa-ui-m8/app/package.json`; all three business plugins are registry caret
ranges under `optionalDependencies`, so the host tracks *published versions*
and not the working trees, and the converse rule binds it like any other
consumer. See *`fa-ui-m8` does not consume the business plugins as `file:`
links* below for the measurement and its two consequences. The retraction is
written in place rather than replacing the text, because the claim was
load-bearing for several conclusions above it.

Only `@mano8/astro-auth-m8` (`^2.4.1`) and
`@mano8/astro-ui-m8` (`^1.5.1`) are registry-ranged **as ordinary
dependencies** in the host, and both are now published at their floor. The
converse rule still binds any *external* consumer of these packages, and it
bound `fa-ui-m8` itself for
`astro-prompt-m8@2.0.0` when that dependency was registry-ranged.

### `reparto-docente-m8` 2.0.0 → 2.1.0 (2026-08-30, pending)

The working-tree row moves `2.0.0` → **`2.1.0`** (`reparto_service/__init__.py`,
read via the documented source-file command, not `import`). Prepared under the
SSE-DB-session-pinning plan's `R1`/`R2`: the `/{process_id}/events` SSE route no
longer holds a `SessionDep` open for the life of the stream, which previously
pinned one connection pool slot per concurrent viewer. `reparto-docente-m8@2.0.0`
is published (`git ls-remote --tags origin` shows `v2.0.0` as the newest tag), so
this is its own bump, not a ride.

**The contract does not move.** `CONTRACT_VERSION`/`CONTRACT_RANGE` stay
`2.0.0`/`>=2.0.0 <3.0.0` — the fix changes no endpoint, schema, status code or
field, and `astro-reparto-m8`'s gate is an exact-match `Set`, not a range, so
moving the contract would reject every published client at preflight.
`astro-reparto-m8` needs **no release**: its `serviceVersionRange` metadata
already admits `2.1.0`, and `npm run verify:contract-operations` was re-run
against `reparto-docente-m8@2.1.0` and confirms the served surface is
unchanged.

### The prompt pair moves the contract axis (2026-08-30, pending)

`prompt-engine-m8`'s working-tree row moves `2.0.0` → **`2.1.0`**, and the
contract row moves with it: `prompt-engine-m8@2.0.0` → **`@2.1.0`**, with
`CONTRACT_RANGE` and `astro-prompt-m8`'s client gate both raised to
`>=2.1.0 <3.0.0`. Prepared under remediation `B20` (service) and `B6`
(client); neither was published when that note was written, so both rows read
**pending**. ✅ **Both published 2026-08-30** — `refs/tags/v2.1.0` is on
`origin` for each (`ae95f4fedf45`, `092cf70da0b3`), so the rows now read
`— published` and the release-together constraint below is satisfied rather
than outstanding.

**The service row had been reading `— published` while carrying unreleased
routes.** `A-C8` added `GET /prompt-block/export/` and
`GET /prompt-template/export/` after `2.0.0` shipped, and wrote its changelog
entries into the **already-published** `## [2.0.0]` section of *both*
repositories while leaving `[Unreleased]` empty and neither version bumped —
finding `G14`. So the changelog of a shipped artifact claimed routes that
artifact does not serve, and this table said there was nothing pending. Both
halves are corrected: the entries moved to `2.1.0` sections and the service
version follows. `astro-prompt-m8` was already at `2.1.0` from the `W7.7`
auth wave, but its release note read "no published API surface changes" while
the export wrappers shipped inside it; that summary is corrected too.

**Why the range moves here when `media-service-m8`'s did not.** The precedent
recorded above is that a contract range names who the service still serves —
media went `1.0` → `1.1` and kept `>=1.0.0 <2.0.0`, because 1.0 clients are
still served. The prompt pair is the documented exception, and the difference
is in the *client*: `astro-media-m8` carries a tolerant
`MEDIA_SERVICE_M8_COMPATIBLE_CONTRACTS` set (`{1.0, 1.1}`), so a 1.0 client
genuinely can drive a 1.1 service. `astro-prompt-m8` compares the contract
axis by **exact string equality**, so a published `astro-prompt-m8@2.0.0`
refuses a `2.1.0` service on its own side no matter what the service
declares. Declaring `>=2.0.0` would advertise support nothing can take up.

⚠️ **Consequence, recorded rather than smoothed over:** the pair must be
released and installed **together**. A `2.1.0` client refuses a `2.0.0`
service — which is the point, since it calls routes `2.0.0` does not serve —
and a published `2.0.0` client refuses a `2.1.0` service. `fa-ui-m8` consumes
this plugin as a `file:` link, so the host tracks both working trees directly;
the constraint binds external consumers and any stack pinning the published
image.

### The media pair re-measured (2026-08-30)

Measured on request against on-disk source and `git ls-remote --tags origin`,
because the pair's rows had been carried forward since the 2026-08-16 sweep
without being re-read. **Four rows moved, and the pair is no longer
half-released in the direction this file recorded.**

`media-service-m8` `1.0.0` → **`2.0.0`, published.** Evidence is the tag on
`origin`: `git ls-remote --tags origin` lists
`693a577d6e7bc7bc1356427b2afc4c338146356e refs/tags/v2.0.0`, contained in
`origin/main`. The row had read published `1.0.0` / working tree `2.0.0` /
pending; in fact the working tree **is** the tag — `git rev-list --count
v2.0.0..HEAD` answers `0`, `CHANGELOG.md` opens on
`## [2.0.0] — 2026-08-26` with no `[Unreleased]` section, and
`media_service/__init__.py` reads `2.0.0`. Nothing was pending. The service half
of the media pair has been fully released since 2026-08-26 and this table said
it was not.

`media-worker-m8` `0.3.0`/`0.4.0` → **`0.4.1`/`0.4.1`, published.** Both halves
of the row were stale. `refs/tags/v0.4.1` is on `origin` and
`worker/__init__.py` reads `0.4.1`. The bump is visible in the media-service
tag's own tip commit, `chore(compose): re-pin media-worker-m8 0.4.0 -> 0.4.1
(B22)` — the compose pin moved while this table still named `0.3.0` published.

`astro-media-m8` keeps published `1.1.1` / working tree `2.0.0` / **pending** —
the one row of the four that was already right. `refs/tags/v1.1.1` is still the
newest tag on `origin`; `package.json` and `package-lock.json` both read
`2.0.0`, so the repo is internally self-consistent. The gap remains a **major**.

**Consequence for the pair, restated because it has inverted.** An earlier
2026-08-30 note described the *reparto* pair as half-released; that pair has
since closed, and the media pair now holds the shape alone — more sharply, in
fact: the service is published at `2.0.0` while the client that targets it is
published only at `1.1.1`. After this pass `astro-media-m8` is the fleet's
**only** library row still pending (`fa-ui-m8` aside, which is a host and has
never published). A consumer installing `@mano8/astro-media-m8`
from the registry gets a `1.1.1` client whose service gate predates the role
tiers, pointed at a `2.0.0` service that enforces them. The working-tree client
is correct — `MEDIA_SERVICE_M8_MIN_SERVICE_VERSION = "2.0.0"` — but it is not
published. `fa-ui-m8` is insulated, since it consumes this plugin as a `file:`
link and tracks the working tree directly; any external consumer is not.
Publishing `astro-media-m8@2.0.0` is the human's act and closes it.

~~⚠️ **A version-source split inside `astro-media-m8`.**
`package.json`/`package-lock.json` read `2.0.0`, but `CHANGELOG.md`'s newest
released section is `## [1.2.0] - 2026-08-25` — there is no `## [2.0.0]`
section at all, and the work sits in a non-empty `## [Unreleased]`.~~ ✅
**Closed 2026-08-30.** The `[Unreleased]` body was folded into a new
`## [2.0.0] - 2026-08-30` section and `## [Unreleased]` left empty, the
convention `astro-prompt-m8` and `astro-auth-m8` already follow. This was the
same defect class this file records for those two (`astro-prompt-m8@2.1.0` and
`astro-auth-m8@2.4.0`), with one difference that explains why it went unseen for
longer: both of those were **caught by a changelog/version-parity gate**, and
`astro-media-m8` has no such gate, so nothing was red and nothing announced it.
Adding one is named follow-on work, not done here.

**How the split arose, and what actually makes it a major.** `ac96cbf
feat(media): add category page and library upload dialog` moved `package.json`
`1.2.0` → `2.0.0` inside an ordinary feature commit, one-line message, no
changelog section and no stated reason. The fold had to supply the reason after
the fact, and the **governing** one is the backend repoint, not the auth peer:
`e3e3b72 fix(compat): admit media-service-m8 2.x service versions` moved
`MEDIA_SERVICE_M8_MIN_SERVICE_VERSION` `1.0.0` → `2.0.0` and the exclusive
maximum `2.0.0` → `3.0.0`, so a pre-tier `1.x` service is **no longer
admitted** — it cannot serve the role-tier authorization this plugin's guards
assume, and a consumer pointed at one is refused at preflight. The auth
generation jump (`^1.5.0` → `^2.4.1`) is the second, weaker reason. No export
is removed or renamed; both breaking changes are to what the package requires
around it.

**This package's major tracks the supported `media-service-m8` *service-version
line*, not its contract** — the distinction matters here and nowhere else in the
fleet. The sibling plugins state that their major tracks the backend **API
contract**; for `astro-media-m8` that would be wrong, because its compatibility
helper admits several contracts (`{1.0, 1.1}`) against one service line, so the
contract can move without moving the major. That policy note is now carried in
the repository's own changelog header rather than only here.

~~⚠️ **Open, an operator decision rather than a matrix fact:** `1.2.0` was
**never published either** … A strict reading of the Wave 6c
one-bump-per-unpublished-release rule folds `1.2.0` into `2.0.0` as well.~~ ✅
**Settled and applied 2026-08-30 (`e13322b`).** The operator ruled the strict
reading. `1.2.0` and `2.0.0` are one unpublished release — `origin`'s newest tag
is `v1.1.1` — and are folded under `## [2.0.0]`. The decisive fact is that
`1.2.0` **was numbered a minor while carrying the backend repoint above**, so
folding it was a correction rather than tidying: the merged section takes the
major the work actually earns. All ten entry bullets from both sections are
preserved. This follows the same operator practice as the `3.0.0`/`2.0.0` split
under *Convergence* and reparto decision 6.

The pair's pins were checked in the same pass and are clean: `astro-media-m8`
names `@mano8/astro-auth-m8@^2.4.1` (peer and dev) and
`@mano8/astro-ui-m8@^1.5.1`, its lockfile resolves
`astro-auth-m8-2.4.1.tgz` and `astro-ui-m8-1.5.1.tgz`, and both of those are
published (`refs/tags/v2.4.1`, `refs/tags/v1.5.1`). No pin here is ahead of the
registry. The contract table's media row was verified against source and needed
no change: package `2.0.0`, contract `media-service-m8@1.1`
(`CONTRACT_VERSION = "1.1"`), client gate `>=2.0.0 <3.0.0`, and
`package.json`'s `mediaServiceM8` metadata block agrees with
`compatibility.ts` on all three. `CONTRACT_RANGE` was **wrongly reported as a
defect** in the first pass of this section and is not one — see *Service version
is not contract version* below for the corrected reading.

**Two rows outside the media pair moved in the same read** and are corrected
here rather than left for a later sweep, since both are `astro-media-m8`'s own
pins: `astro-auth-m8` `2.4.0` → `2.4.1` and `astro-ui-m8` `1.5.0` → `1.5.1`,
each published on `origin` and each with working tree equal to the tag. The
`^2.4.0`/`^1.5.0` figures in the host paragraph above were updated to match.

#### What this pass changed in the repositories

The matrix corrections above are documentation. Two repository commits were
made alongside them, both changelog-only — no source, manifest, lockfile or
**version** moved in either.

`media-service-m8` `docs/record-shipped-2-0-0-changes` (`7d7aa3c`, branched
from `main`, pushed): two commits contained in the `v2.0.0` tag had no
changelog entry, so the published notes understated the tag. The OpenSSL apt
pin raise `3.5.6-1~deb13u2` → `3.5.7-1~deb13u2` for CVE-2026-14456
(`aeee519`) — 3 HIGH Trivy findings that **blocked the 2.0.0 publish run** —
and both stacks' `media-worker-m8` `0.4.0` → `0.4.1` re-pin (`693a577`) for
the same CVE. Gate: 16 tests green including
`tests/test_changelog_version_parity.py`, markdownlint clean.

### `media-service-m8` 2.0.0 → 2.1.0 (2026-08-30, pending)

`71297bb`, on the same branch. The repository had **zero** commits since
`v2.0.0` and a clean tree, so the first ruling was to amend the published
`## [2.0.0]` section and leave the version alone. The operator then reversed
that: a repository change takes a version rather than editing a published tag's
notes silently. Both rulings are recorded because the reversal is the rule —
**this fleet does not edit shipped release notes without releasing the edit.**

**No runtime change.** No dependency floor, lock, image pin, contract or served
response moves; `GET /media/meta` answers what `2.0.0` answered apart from
`version`. The two recovered entries stay under `## [2.0.0]`, where they
factually belong — both shipped inside that tag — and `## [2.1.0]` records that
the correction was made. This is the second release in the fleet whose entire
justification is not a code change; `astro-auth-m8@2.4.0` was the first, and
set the minor-not-patch precedent followed here.

**Neither contract constant moves.** `CONTRACT_VERSION` stays `1.1` and
`CONTRACT_RANGE` stays `>=2.0.0 <3.0.0`. Since that range is the
**service-version** range, `2.1.0` is inside it and the service keeps
advertising a range that admits itself — the defect `1256b99` fixed does not
recur. **`astro-media-m8` needs no release:** its gate is `>=2.0.0 <3.0.0` on
the service version and already admits `2.1.0`. Same shape as the
`reparto-docente-m8` `2.1.0` precedent recorded above.

Gate: 1158 tests at 100% coverage, markdownlint clean. One incidental change:
`media_service/__init__.py`'s blob had been committed with CRLF against the
repo's own `.gitattributes` (`* text=auto eol=lf`); editing the version line
normalized it to LF, so the whole five-line file shows as changed.

**The re-pin was written ahead of the image, on operator instruction
(2026-08-30).** All **ten** live pin sites moved `2.0.0` → `2.1.0`:
`media-service-m8` `aeb1130` (five — `hardened_media_m8/docker-compose.yml`
×2, that stack's README ×2, the `docker_compose/README.md` stacks index) and
`fa-ui-m8` `525e4ab` on `pre-alpha` (five — `dev_ui_m8` ×2, `hardened_ui_m8`
×1, and `compose_policy_tests/test_compose_image_pins.py` in both its docstring
and its `_PREVIOUSLY_LATEST` map, which must move in the same commit or that
stack's gate goes red).

⚠️ **This inverts the rule the rest of this file records.** `A29`/`B5`/`B17`
require confirming `docker pull` before writing any pin, and §0.2 of the
consumer-alignment plan states "publishing precedes pinning, always". Here the
pins were written first, deliberately, so
`docker pull tepochtli/media-service-m8:2.1.0` fails and **all three stacks —
`hardened_media_m8`, `dev_ui_m8`, `hardened_ui_m8` — are unrunnable until the
`v2.1.0` GitHub Release is published.** The window is the cost of pinning
ahead; it closes on publish and nothing else needs to change afterwards.
Recorded because a future reader comparing this to `B17`'s pull-confirmed
re-pins should see the difference was a decision, not an omission.

`dev_media_m8` carries no media-service pin (it builds from local source), and
the `fa-auth-m8` `2.0.3` / `media-worker-m8` `0.4.1` pins are untouched — both
published, neither moved by this release. Gates: `test_compose_image_pins.py`
7 passed in `media-service-m8`, the full `compose_policy_tests` suite 171
passed in `fa-ui-m8`.

`astro-media-m8` `feat/eslint-10-flat-config` (`8b40b83` then `e13322b`): the
`[Unreleased]` fold, then the `1.2.0` fold and the corrected major
justification. Gate: typecheck, lint and markdownlint clean.

### `media-service-m8` 2.1.0 → 2.1.1 and the media pair re-measured (2026-09-01)

**`2.1.0` is published.** `git ls-remote --tags origin` now answers
`903f8a3 refs/tags/v2.1.0`, and that SHA is `origin/main` — the merge of
`docs/record-shipped-2-0-0-changes` (PR #17). So the ordering inversion recorded
immediately above has closed on its own terms: the ten pin sites that were
written ahead of the image are now pins on a released version, and all three
stacks are runnable again with no further change. The row moves published
`2.0.0` → `2.1.0`, and the Wave 6c ride for this repository is over —
further work takes a number rather than joining `## [2.1.0]`.

**`media-service-m8` `2.1.0` → `2.1.1`, pending.** `fde8fc0` on
`fix/object-detail-category-projection`, branched from `origin/main` at
`903f8a3` and pushed. `GET /media/v1/objects/{id}` answered `categories: []` for
an object that *was* filed — the detail path validated the database model
directly while the list and both write paths passed their filing through
`update=`. `MediaObject` names the relationship `user_categories` precisely so
that `model_validate` cannot lazy-load it per row, so the unenriched call could
only ever produce the schema's empty default. It now uses
`category_refs_by_object`, the list path's own helper, chosen over
`assigned_category_refs` because it takes `UserModel | None` and this route's
principal is `OptionalPrincipal`.

**A patch, and the first entry in this file to take one.** The field was already
declared, already documented and already populated on every other surface, so no
served shape changes — which is exactly what separates it from the two
minor-not-patch precedents above (`astro-auth-m8@2.4.0`, `media-service-m8@2.1.0`),
both of which had no code change at all and needed a number only to carry a
notes correction. **Neither contract constant moves:** `CONTRACT_VERSION` stays
`1.1`, `CONTRACT_RANGE` stays `>=2.0.0 <3.0.0`, and `2.1.1` is inside it.

**All ten pin sites moved `2.1.0` → `2.1.1`, ahead of the image, on operator
instruction (2026-09-01).** `media-service-m8` `546c5b4` on
`chore/pin-media-service-2.1.1` (five — `hardened_media_m8/docker-compose.yml`
×2, that stack's README ×2, the `docker_compose/README.md` stacks index; PR #19)
and `fa-ui-m8` `5aa7738` on `pre-alpha`, pushed (five — `dev_ui_m8` ×2,
`hardened_ui_m8` ×1, and `compose_policy_tests/test_compose_image_pins.py` in
both its docstring and its `_PREVIOUSLY_LATEST` map, which must move in the same
commit or that stack's gate goes red).

⚠️ **This inverts the rule this file records, for the second consecutive
release.** `A29`/`B5`/`B17` require confirming `docker pull` before writing any
pin, and §0.2 of the consumer-alignment plan states "publishing precedes
pinning, always". The operator's standing rule is the inverse — *all pins
updated before publish* — so `docker pull tepochtli/media-service-m8:2.1.1`
fails and **all three stacks — `hardened_media_m8`, `dev_ui_m8`,
`hardened_ui_m8` — are unrunnable until the `v2.1.1` GitHub Release is
published.** The window is the cost of pinning ahead; it closes on publish and
nothing else needs to change afterwards.

An earlier revision of this section recorded the opposite — that the pins would
stay at `2.1.0` because a consumer may only pin a published version. That was
the file's own rule applied correctly and it was overridden by instruction, not
by error; the retraction is written here rather than silently replaced, because
the inversion has now happened twice and should be expected to be the operating
norm rather than the exception. The rule as stated near the head of this file is
left standing and unedited: it remains what the plan requires, and each
departure is recorded at the release that took it.

`dev_media_m8` carries no media-service pin (it builds from local source), and
the `fa-auth-m8` `2.0.3` / `media-worker-m8` `0.4.1` pins are untouched — both
published, neither moved by this release. Gates: `test_compose_image_pins.py`
7 passed and the full suite 1159 passed at 100% coverage in `media-service-m8`,
the full `compose_policy_tests` suite 171 passed in `fa-ui-m8`.

**`astro-media-m8` needs no release, and takes no number.** `e8ee005` on
`feat/eslint-10-flat-config`, pushed. Its `2.0.0` is still unpublished
(`origin`'s newest tag remains `v1.1.1`), so this work rides it under the Wave
6c rule — the opposite side of the ruling applied to the service in the same
pass, and worth reading as a pair: the rule turns on whether a tag exists, not
on how much changed. Three tree-view defects (the category pane clipped a deep
hierarchy with no horizontal scroll, the child indent was the largest single
contributor to that width, and every branch opened expanded) plus two contract
gaps.

**The contract axis was measured on both sides, not assumed.** Every Zod schema
and every call site in `astro-media-m8` was diffed against `media-service-m8`'s
generated OpenAPI. All 40 client calls resolve to a real endpoint, every
response model pairs with the right schema, and the object-list query parameters
match one for one. Three findings, all client-side:

1. `UploadCompleteRequestSchema` omitted `category_ids`, which the served
   endpoint accepts and which the `.strict()` schema would therefore have
   rejected client-side. Added.
2. `astro-media-m8/REPOSITORY_CONTEXT.md` recorded the range as
   `>=1.0.0 <2.0.0` — **the same `CONTRACT_RANGE` misreading this file itself
   corrected on 2026-08-30**, surviving in a second repository after the first
   was fixed. It is a service-version range, not a range of contract versions,
   and the value also predated the 2.x repoint, so it excluded every service the
   package admits. Corrected in place, with the retraction written into the line
   rather than silently replacing it — the misreading has now recurred once and
   should be expected to recur again.
3. `MEDIA_SERVICE_M8_TESTED_SERVICE_VERSION` and
   `mediaServiceM8.testedServiceVersion` were stale at `2.0.0`; both move to
   `2.1.1`, the service the client was actually exercised against. Written ahead
   of that tag and recorded as such, but **not** the same hazard as a pin-ahead:
   the constant resolves nothing and installs nothing, and the gate is the
   range, which admits the published `2.1.0` unchanged.

**What did *not* move, and why.** The service's `OpenAPI` declares `slug`
required on `CategoryCreate`/`CategoryUpdate` while the client sends only
`name`, which reads as a break and is not one: `CategoryGenerators` carries a
`model_validator(mode="before")` that slugifies `name`, so the field is filled
before validation. The schema is misleading, the runtime is correct, and the
client is right to omit it — recorded here so the next audit does not re-report
it. Likewise `apply_scan_result` returns an unenriched `MediaObjectPublic`, but
it is `include_in_schema=False`, has no principal to scope a category query by,
and answers the worker rather than a UI.

Gates: `media-service-m8` 1159 tests, ruff and mypy clean over 80 source files;
`astro-media-m8` 237 tests, typecheck, `eslint --max-warnings 0`, 9 fleet gates
and the registry-drift gate all green.

Read the published column with:

```powershell
# newest tag on the remote, per repo (local tags are frequently stale)
git -C <repo> ls-remote --tags origin
```

### Service version is not contract version

Four repos carry a second, independent version: the HTTP **contract** version,
which does **not** move merely because the package version does.
`media-service-m8` is the worked example — its package went `1.0.0` → `2.0.0`
for the role tiers while `CONTRACT_VERSION` stayed `1.0`. The later additive UX
surface moved that contract to `1.1`, and 1.0 clients are still served —
`astro-media-m8` carries the tolerant `{1.0, 1.1}` set recorded below.

**`CONTRACT_RANGE` is a *service-version* range, not a contract-version
range.** This file claimed `>=1.0.0 <2.0.0` until 2026-08-30 and was wrong on
both the value and the meaning; the source reads `>=2.0.0 <3.0.0`. The field is
served as `contract.range` by `GET {prefix}/meta`, and `media-service-m8`'s own
history uses it that way twice — `0.0.9` moved it to `>=0.0.9 <0.1.0` and
`1.0.0` to `>=1.0.0 <2.0.0`, each tracking the **package** version. It was left
behind by the `2.0.0` major, so the service briefly advertised a supported range
excluding its own version; `1256b99 fix(meta): bump CONTRACT_RANGE to the 2.x
service line` corrected it before the `2.0.0` tag, deliberately matching
`astro-media-m8`'s `MEDIA_SERVICE_M8_SERVICE_VERSION_RANGE`.
`tests/test_meta.py` asserts the served block as a literal, so the value cannot
drift silently.

Read the field's name with care: `fastapi-m8/fastapi_m8/config.py` describes it
as "Compatible **contract** semver range", which is what misled this file. The
two sibling services are no evidence either way — their contract and package
versions coincide, so one range brackets both.

| Service | Package version | Contract | Client gate (`<plugin>/src/runtime/compatibility.ts`) |
| --- | --- | --- | --- |
| `fa-auth-m8` | 2.2.1 | `fa-auth-m8@2.0` | `astro-auth-m8` `>=2.0.0 <3.0.0` |
| `media-service-m8` | 3.0.1 | `media-service-m8@1.1` | `astro-media-m8` `>=2.0.0 <4.0.0` (published in `2.1.0`; `2.2.0` tests against `3.0.1`) |
| `prompt-engine-m8` | 2.2.0 | `prompt-engine-m8@2.1.0` | `astro-prompt-m8` `>=2.1.0 <3.0.0` |
| `reparto-docente-m8` | 2.2.0 | `reparto-docente-m8@2.0.0` | `astro-reparto-m8` contract-only (no numeric service gate); `2.2.0` tests against `2.2.0` |

Each plugin's gate is bounded on the **service** version and must admit its
backend's package version; each also repeats the pair as declarative
`package.json` metadata (`faAuthM8` / `mediaServiceM8` / `promptEngineM8` /
`repartoDocenteM8`). Nothing enforces agreement between that metadata block and
the `compatibility.ts` constants — a known gap, recorded rather than fixed.

`fastapi-m8` is a special case: it carries **two** version sources for the
same value — a literal `version = "x.y.z"` in `[project]` **and**
`fastapi_m8/_version.py`'s `__version__`, kept in sync by hand. Nothing
enforced their agreement until `fastapi-m8/tests/test_version_source_parity.py`
(added by this step) locked `fastapi_m8.__version__` to the `pyproject.toml`
literal. `auth-sdk-m8` has no `_version.py` at all, only the `[project]`
literal — a single source, just not the dynamic one.

Two rows moved on 2026-09-06, both inside the media stack.

`media-sdk-m8` `0.7.0` → **`0.8.0` in the working tree, still `0.7.0`
published.** The row was stale, not behind: `T8-sdk-release-cut` of the
object-storage backend migration cut `0.8.0` in `pyproject.toml` on
2026-09-05 (boto3 replaces `minio-py` inside `ObjectStorage`) and this table
was not re-read then. PyPI still answers `0.7.0` for
`pip index versions media-sdk-m8`, so both consumers' `>=0.8.0,<0.9.0` floor
and their regenerated `requirements_prod.lock`s pin ahead of the publish —
the inversion recorded twice above for this fleet's Docker image tags, now
recorded for a Python package too. It closes on publish.

`media-service-m8` `2.1.1` → **`2.2.0` in the working tree**, published still
`2.1.0`. `T10-settings-s3-rename` renames the storage settings `MINIO_*` →
`S3_*` behind a deprecation shim; a feature plus a deprecation cannot ride the
already-written `2.1.1` patch heading, so the pending release takes a minor
number. **Consequence, recorded rather than smoothed over:** the fleet now
holds *two* unpublished `media-service-m8` versions, and the five compose
sites re-pinned `2.1.0` → `2.1.1` on 2026-09-01 name the older of them. Either
`2.1.1` publishes first and `2.2.0` follows with its own re-pin, or the
operator applies the Wave 6c one-bump-per-unpublished-release rule above and
folds `2.1.1` into `2.2.0` — which is a five-site re-pin of its own, which is
why this step did not decide it unilaterally. The `3.0.0` that removes the
shim is deliberately *not* taken here: `astro-media-m8`'s published
`MEDIA_SERVICE_M8_MAX_SERVICE_VERSION_EXCLUSIVE` is `3.0.0`, so that bump must
be coordinated with the client, and Wave 2 of the migration plan routes no
client repository.

### The reparto pair re-measured and cut (2026-09-06)

Measured against on-disk source and `git ls-remote --tags origin`. **Both rows
were wrong, in the two different ways this file distinguishes**, and both are
corrected here.

`reparto-docente-m8` `2.1.0` → **`2.1.1` in the working tree**, published still
`2.1.0`. The row was *behind*, not stale: `v2.1.0` is on `origin`
(`77adff7ceb9a`) and was the newest tag, but `20f9d8b fix(exports): render the
plan §15 documents instead of refusing them` had landed on top of it with no
version and no changelog entry, so the repository was carrying a released
number over unreleased code. The bump is cut here.

**A patch, on this file's own precedent.** `POST …/exports` answered `501` for
every `pdf` request while the export centre asks for `pdf` on every document
type but the backup, so three of four document buttons and the final export
could never succeed. Nothing in the request or response *schema* moves — the
`format` and `export_type` values were already declared and already accepted —
so this closes a gap between what the schema promised and what the handler
served, which is the same shape as `media-service-m8@2.1.1` (a declared field
that was empty on one path) and takes the same number class. Evidence that no
surface moved is the service's own drift gate:
`tests/test_served_api_surface.py` is green against the working tree, and
`docs/served-api-surface.json` is byte-identical to `astro-reparto-m8`'s
vendored `contract/served-api-surface.json`.

**Neither contract constant moves.** `CONTRACT_VERSION` stays `2.0.0` and
`CONTRACT_RANGE` stays `>=2.0.0 <3.0.0`, which admits `2.1.1`.
**`astro-reparto-m8` needs no release for it** — its gate is an exact-match
`Set` on the contract, not a numeric service range, so a moved contract would
reject every published client at preflight. Same shape as the
`reparto-docente-m8@2.1.0` precedent recorded above.

⚠️ **The export commit had shipped below the repository's own coverage bar,
and the bump is what caught it.** `pytest --cov --cov-fail-under=100` was red
at **99.85%** — 6 statements and 7 branches, *all* of them in the new
`services/document_rendering.py` and none anywhere else in 7342 statements.
The uncovered paths were the renderer's defensive joins: a link whose
group-subject is absent, a cell whose teaching group is absent, a repeated
group code, an assignment naming an activity or participant the snapshot does
not carry, and the two plan warnings (stale, and not-`FEASIBLE`). A route
cannot produce those, since a live process is internally consistent — but
`restore-draft` accepts a caller-supplied payload, so a restored backup can,
which is what makes them worth holding rather than excluding. Six unit tests
against `DocumentRenderingService.render` on deliberately broken snapshots
close it; the suite is 2048 passing at **100.00%**. Recorded here because the
gap was invisible to every other gate — ruff, mypy and bandit were green
throughout, and the feature's own route tests passed.

Gates at the cut: 2048 tests at 100% coverage, `ruff format --check` and
`ruff check` clean over 167 files, `mypy reparto_service --ignore-missing-imports`
clean over 105 files, `bandit -r . --severity-level medium` clean, and
`tests/test_served_api_surface.py` green. One note for a future reader: this
repository's `REPOSITORY_CONTEXT.md` documents the local command as `mypy .`,
which includes `tests/` and reports 15 pre-existing errors there, while CI
gates `mypy reparto_service` and is clean. The two are not the same command,
and only the narrower one is a gate.

`astro-reparto-m8` `2.0.0`/`2.0.0`/published → **`2.0.0` published, `2.1.0`
working tree, pending.** This row was **stale in both columns at once**:
`package.json` had read `2.1.0` since a `## [2.1.0] - 2026-09-04` changelog
section, and `origin`'s newest tag has never been anything but `v2.0.0`
(`01144c558a3f`) — independently confirmed against the registry, where
`npm view @mano8/astro-reparto-m8 versions` answers `['0.0.1', '1.0.0',
'2.0.0']`. So the table called a version published that npm has never held.

That discovery changed the number this pass cut. A first pass took the new
export-delivery and checklist/UX work to `2.2.0` on the reading that `2.1.0`
was a released boundary; on finding `2.1.0` unpublished, the operator ruled the
Wave 6c one-bump-per-unpublished-release rule instead, and the two changelog
sections were folded into one `## [2.1.0]` redated `2026-09-06` with every
entry bullet preserved. `package.json` and `package-lock.json` are back at
`2.1.0`. This is the fourth application of that rule recorded in this file
(after the reparto pair's own `2.0.0`, `astro-media-m8`'s `1.2.0`/`2.0.0`, and
this repository's earlier `3.0.0`/`2.0.0` split) and the first where the rule
*reversed* a bump already applied.

**One range moved, and it is the one that should.** `astro-reparto-m8`'s
`repartoDocenteM8.testedServiceVersion` was stale at `2.0.0` and moves to
`2.1.1` — the service the client is now exercised against, with
`npm run verify:contract-operations` re-run green (116 declared operations, all
served, every wrapper declared). `contract` stays `reparto-docente-m8@2.0.0`
and `serviceVersionRange` stays `>=2.0.0 <3.0.0`. This is the same stale-tested
-version defect this file records for `astro-media-m8` on 2026-09-01, in the
sibling repository, caught the same way: by checking all three fields when only
one had a reason to move. `REPOSITORY_CONTEXT.md` carried the same stale `2.0.0`
and is corrected with it, plus a note stating why the three fields move
independently — the misreading recurred once already and should be expected to
recur again.

#### No compose pin exists for this service, and that is the answer

The pass went looking for the `reparto-docente-m8` pin sites to re-pin, on the
`media-service-m8` model of five sites moving per release. **There are none**,
and the fleet is asymmetric here in a way worth recording so the next sweep
does not re-investigate it:

- Every stack that runs `reparto_service` **builds it from local source**:
  `reparto-docente-m8/docker_compose/dev_reparto_m8` (`build:` on `../..`) and
  `fa-ui-m8/docker_compose/dev_local_full_ui_m8` (`build:` on
  `../../../reparto-docente-m8`), which is the only `fa-ui-m8` stack carrying
  the service at all.
- The two stacks that consume **published** images — `dev_ui_m8` and
  `hardened_ui_m8` — do not run `reparto_service`. Their pins are
  `fa-auth-m8:2.0.3`, `media-worker-m8:0.4.1` and `media-service-m8:2.1.1`,
  and `compose_policy_tests/test_compose_image_pins.py`'s `_PREVIOUSLY_LATEST`
  map names those three and no reparto entry.
- `reparto-docente-m8/.github/workflows/docker-publish.yaml` **does** publish
  `<registry-user>/reparto-docente-m8` on release, so an image exists; nothing
  in this workspace consumes it.

The consequence is the useful part: **publishing `reparto-docente-m8@2.1.1`
requires no re-pin anywhere**, so the pin-ahead-of-image inversion recorded
twice above for the media stack has no analogue here and no window to open. A
stack that later consumes the published reparto image is the point at which
that changes.

**Superseded 2026-09-19 — one such stack exists, and it is off-tree.** The
host-local `rpi_server/docente_reparto` compose (git-ignored at the workspace
root, the 2026-09-13 entry below already names it) pins
`image: tepochtli/reparto-docente-m8:<version>` for `reparto_service`; the
base file also bind-mounts the sibling source over `/opt/reparto_service` and
the production overlay `!override`s that mount away, so in production the
image is what runs. It read `2.1.0` and was moved to **`2.2.0`** on disk
ahead of publish, per the pin-before-publish rule (see *The reparto pair cut
at 2.2.0* below). The three in-tree statements above still hold: no tracked
stack pins the reparto image, `_PREVIOUSLY_LATEST` has no reparto entry, and
the sweep that assumed otherwise would still find nothing to change in git.

#### ⚠️ `fa-ui-m8` does **not** consume the business plugins as `file:` links

The 2026-08-30 entry above states that "`fa-ui-m8/app` consumes the three
business plugins as path links (`"@mano8/astro-media-m8":
"file:../../astro-media-m8"`, likewise prompt and reparto), not as registry
ranges", and draws the conclusion that "the host tracks those three working
trees directly and needs no repoint when they publish". **Measured against
`fa-ui-m8/app/package.json` on 2026-09-06, that is not what the host does**,
and the conclusion does not hold. There is no `file:` specifier in the file.
All three are registry caret ranges under `optionalDependencies`:

| Declared | Range | Installed in `node_modules` | Newest on npm |
| --- | --- | --- | --- |
| `@mano8/astro-media-m8` | `^2.0.0` | 2.0.0 | 1.1.1 |
| `@mano8/astro-prompt-m8` | `^2.1.0` | 2.1.0 | 2.1.0 |
| `@mano8/astro-reparto-m8` | `^2.0.0` | 2.1.0 | 2.0.0 |

Two of the three installed trees are therefore **hand-placed local builds
that no registry could supply** — the layout under `node_modules` is exactly
the `files` allowlist of an `npm pack`, not a symlink. They are real, they are
what the host builds against, and they are invisible to git. A plain
`npm ci` replaces them with whatever the range resolves to, silently.

Two consequences, both the opposite of what the superseded paragraph implies:

- **The host does not track any plugin working tree.** A change made in
  `astro-reparto-m8` reaches `fa-ui-m8` only when someone rebuilds and
  re-places that tree, or when the version publishes. This is the mechanism
  behind a "the fix isn't showing in the running stack" report, and the answer
  is to rebuild and re-place, not to look for a caching bug.
- **`astro-media-m8`'s range cannot currently resolve at all.** `^2.0.0` has
  no match on a registry whose newest is `1.1.1`; because the entry is
  *optional*, npm skips it rather than failing, so a clean `npm ci` yields a
  host silently missing the media plugin. Recorded, not acted on — the media
  stack is out of scope for this pass — but it should be treated as open.

The reparto row is the benign one: `^2.0.0` admits `2.1.0`, so once
`@mano8/astro-reparto-m8@2.1.0` publishes the host picks it up on the next
install with no repoint. That is a property of the caret, not of a `file:`
link.

### The auth triad re-measured (2026-09-13)

Measured against on-disk source, `git ls-remote --tags origin`, and
`pip index versions`. **Three rows were stale**, none *behind*: every value
this file carried had been true once and was simply never re-read after the
JWKS `kid` release train (`J1`–`J4`, 2026-09-09 → 09-12) moved all three
repositories in four days. Caught while cutting `fa-auth-m8@2.2.1`, by
checking the neighbours a patch release has no reason to move.

`fa-auth-m8` `2.0.3` → **`2.2.0` published, `2.2.1` in the working tree.**
Two minors had shipped since the row was last read — `v2.1.0` (the issuer half
of the `kid` binding, with a `BREAKING` boot refusal for an unbound
`ACCESS_KEY_ID`) and `v2.2.0` (the dependency realignment onto the published
consumer half) — and the row still read the `2026-08-24` ledger value. Both
tags are on `origin`; `origin/main` reads `2.2.0`. The pending `2.2.1` is
`fix/jwks-kid-key-binding`, a patch: `init-keys.sh`'s keys-exist rerun branch
now verifies the `kid` binding instead of skipping it (`W3.1`). No service
behaviour, API, or dependency floor moves, so `CONTRACT_VERSION` and
`CONTRACT_RANGE` (`>=2.0.0 <3.0.0`) stay, and the compatibility table's gate
column needs nothing: `astro-auth-m8`'s `compatibility.ts` already reads
`FA_AUTH_M8_TESTED_SERVICE_VERSION = "2.2.0"` inside an unchanged
`>=2.0.0 <3.0.0` range — that client was re-read against `2.2.0` when this
file was not.

`auth-sdk-m8` `3.1.3` → **`3.2.0`, published.** `v3.2.0` is on `origin` and
`pip index versions auth-sdk-m8` answers `3.2.0`. This is the consumer half of
`J3` (`JwksKeyResolver` recovers from key material changing under an unchanged
`kid`), and `fa-auth-m8@2.2.0`'s own changelog names it as the reason its
floor moved to `>=3.2.0,<4.0.0` — evidence this file could have read a day
earlier.

`fastapi-m8` `4.4.0` → **`4.5.1`, published.** `v4.5.1` is on `origin` and
PyPI answers `4.5.1`. `4.5.0` declared the `auth-sdk-m8>=3.2.0` floor while
its compiled `constraints.txt` still pinned `3.1.3`; `4.5.1` (2026-09-12) is
the release where the lockfiles stopped contradicting the floor, which is why
the `fa-auth-m8` examples pin `>=4.5.1` rather than `>=4.5.0`.

**The compose sites had already moved; this file had not.** The
`fa-auth-m8` `2.0.3` pins recorded above under 2026-09-01 as "untouched" were
re-pinned to `2.2.0` by the release train at six of seven sites — `dev_ui_m8`,
`hardened_ui_m8` (both compose files), `dev_media_m8`, `hardened_media_m8`,
and `dev_prompt_engine_m8` — measured by `git grep 'tepochtli/fa-auth-m8:'`
over each sibling's tracked compose files. The one holdout was
`reparto-docente-m8/docker_compose/dev_reparto_m8/docker-compose.yml`, still
`2.0.3` on the plan branch (its `2.2.0` repin sits on
`fix/export-document-text-renderer`, a branch the plan's never merges with).

**Superseded the same day.** The human ruled the whole fleet onto `2.2.1`
ahead of its publish, per the standing pin-before-publish rule. All seven
sites now pin `tepochtli/fa-auth-m8:2.2.1`, one commit per repository on each
repository's `fix/jwks-kid-key-binding`: `media-service-m8` `16f06f6`,
`fa-ui-m8` `0e57a49` (its `_PREVIOUSLY_LATEST` pin test moved with it),
`prompt-engine-m8` `699cdf5`, `reparto-docente-m8` `b03ad2f` (`2.0.3` →
`2.2.1` directly; the `2.2.0` line on the export branch will conflict on
merge — resolve to `2.2.1`). The host-local `rpi_server/docente_reparto`
compose was repinned on disk and, being ignored, propagates nowhere. The
`fa-ui-m8` pin sits on a branch cut from `feat/object-storage-backend-migration`,
not `main`, and reaches `main` only through that branch (recorded under
`W0.4` of the plan).

`astro-auth-m8` `2.4.1` → **`2.5.0` published, `2.6.0` in the working tree.**
Two rows stale at once, same shape as `fa-auth-m8` above: `v2.5.0` is on
`origin` and npm `latest` answers `2.5.0` (released 2026-09-12 to track the
`2.2.0` issuer — `testedServiceVersion` `2.0.0` → `2.2.0`, `MIN` held at
`2.0.0`), and this file still carried the `2.4.1` the 2026-08-29 pass
recorded. The pending `2.6.0` (`5928f88`, `fix/jwks-kid-key-binding` off
`main` `47be766`) moves `testedServiceVersion` to `2.2.1` with the contract
and range unchanged, so the compatibility table above keeps its gate column.
It tracks an unpublished issuer and must not publish to npm before
`tepochtli/fa-auth-m8:2.2.1` exists. `fa-ui-m8` depends on
`@mano8/astro-auth-m8 ^2.4.1`, which admits `2.6.0` without a repoint.

### `fa-auth-m8` 2.2.1 published (2026-09-13)

✅ **`fa-auth-m8` `2.2.1` is published; the row above flips to
`2.2.1 · 2.2.1 · — published`.** Independent evidence, as this file requires:
PR #126 merged to `main` at `77f302c` (2026-09-13 05:40Z); `v2.2.1` is on
`origin` and resolves to that merge commit, no stale local tag; the GitHub
release is published and the `docker-publish.yaml` run for it (`34740917970`)
is green; Docker Hub serves `tepochtli/fa-auth-m8:2.2.1` (also `2.2`, `2`,
`latest`) at index digest
`sha256:12ac4d5194bea94990893e2bd7379cc01c8d8e995dc9031123503b8204409272`;
the pulled image answers `auth_user_service.__version__` → `2.2.1` and
`importlib.metadata.version("auth-sdk-m8")` → `3.2.0`; the Hub overview is
byte-identical to `DOCKERHUB.md` (9729 chars, `2.2.1` ×3). Every `2.2.1`
compose pin recorded above is now a pin on a published version — the
pin-before-publish debt is cleared.

~~The `astro-auth-m8` `2.6.0` row **stays pending**: the condition it was
waiting on (the `2.2.1` image existing) is now met, but `5928f88` has no PR,
`v2.6.0` is not on `origin`, and npm `latest` still answers `2.5.0`.~~
✅ **Closed later the same day: `astro-auth-m8` `2.6.0` is published**, row
flipped to `2.6.0 · 2.6.0 · — published`. Evidence: PR #28 merged at
`898679c`, `v2.6.0` on `origin` at that commit, `npm-publish.yml` run
`34743230244` green (06:38Z — after the `2.2.1` image push at 05:45Z, so the
pin-only-published rule held), `npm view @mano8/astro-auth-m8
dist-tags.latest` → `2.6.0`, tarball `astro-auth-m8-2.6.0.tgz` on the
registry. The published `compatibility.ts` reads
`FA_AUTH_M8_TESTED_SERVICE_VERSION = "2.2.1"`, `MIN` `2.0.0`, range
`>=2.0.0 <3.0.0` — the compatibility table's gate column is unchanged.

### `prompt-engine-m8` 2.1.0 → 2.2.0 (2026-09-13, pending)

`promt_engine_service.__version__` reads `2.2.0` on `fix/jwks-kid-key-binding`
(`2081752`, [`mano8/prompt-engine-m8#39`](https://github.com/mano8/prompt-engine-m8/pull/39)),
cut to carry the `fastapi-m8>=4.5.1` floor (transitive `auth-sdk-m8 3.2.0`),
the `fa-auth-m8:2.2.1` image repin and the re-vendored `init-keys.sh` under
their own number. The contract axis does not move — `CONTRACT_VERSION`
`2.1.0`, `CONTRACT_RANGE` `>=2.1.0 <3.0.0` — so the compatibility table's
gate column and `astro-prompt-m8`'s `>=2.1.0 <3.0.0` need nothing;
`astro-prompt-m8`'s `PROMPT_ENGINE_M8_TESTED_SERVICE_VERSION` (`2.1.0`) is a
tracked-version note for that repo, not a gate. ~~Published `2.1.0` stands
(`v2.1.0` on `origin`, Hub `latest` 2026-08-30) until `v2.2.0` is tagged and
the image workflow publishes.~~ ✅ **Closed later the same day: `2.2.0` is
published**, row flipped to `2.2.0 · 2.2.0 · — published`. Evidence: #39
merged at `2616be7`; #40 (`19caa6e`) then regenerated
`requirements_prod.lock`, which the floor raise had left at
`fastapi-m8 4.4.0` / `auth-sdk-m8 3.1.3` — the constraints had moved, the
`--require-hashes` graph the image installs had not; `v2.2.0` is on `origin`
at `19caa6e` (after #40); release published, `docker-publish.yaml` run
`34752711752` green; Hub `2.2.0` / `2.2` / `2` / `latest` at index digest
`sha256:dca03f6a8f1f3628cde967a5be489aa578528459ee259d31ece74611fec868f4`;
the pulled image answers `promt_engine_service 2.2.0`, `fastapi-m8 4.5.1`,
`auth-sdk-m8 3.2.0`. It is the first published consumer image resolving
`auth-sdk-m8 3.2.0`. Lesson for the next consumer cut (`reparto-docente-m8`,
`media-service-m8` — both held with in-course work, not to be hurried): a
floor raise is not done until `requirements_prod.lock` moves with
`constraints*.txt`.

### Wave 4 release cut — `media-service-m8` and `media-worker-m8` (2026-09-13, pending publish)

`T26-changelog-release` closes Wave 4 of the object-storage backend
migration plan (`.workspace/plans/media-service-m8/done/
object-storage-backend-migration-2026-09-05.md`, under `todo/` until it
closed on 2026-09-16). Both moved rows are
**image-publish pending** — the version bump, `CHANGELOG.md` entry and
compose image-pin re-point are cut here on the plan's own branch
(`feat/object-storage-backend-migration`) and pushed; building and tagging
the Docker image (the GitHub Release / tag that triggers
`docker-publish.yaml`) is the human operator's own act, not done by this
step, matching this file's write-then-verify convention: the pin sites are
updated first, the matrix rows are re-measured only after the images
actually exist on the registry.

`media-service-m8` `2.1.0` (published) → **`2.3.0` in the working tree**,
folding the two already-unpublished rows this file recorded on 2026-09-06
(`2.1.1`, `2.2.0`) together with Wave 3 (the MinIO → SeaweedFS backend swap,
`T15`-`T21`) and Wave 4 (`T22`-`T25`: hygiene, live e2e, the S1-S15 security
regression matrix, the data-migration runbook, and the F1 filename-key fix)
under the Wave 6c one-bump-per-unpublished-release rule above — none of
`T15`-`T25` took a version number of their own, each explicitly deferring to
this step. `CONTRACT_VERSION` stays `1.1`, `CONTRACT_RANGE` stays
`>=2.0.0 <3.0.0` — nothing at the served HTTP contract moved. The existing
`## [2.1.1]` and `## [2.2.0]` `CHANGELOG.md` sections are left as written
(they are historically accurate — that content really was cut on those
dates); the fold is at the *publish* event, not the changelog record — all
three numbers arrive at the registry as one `2.3.0` image, and `2.1.1`/`2.2.0`
never get their own tag. Five compose sites moved, the same shape as the
`2.1.0` → `2.1.1` precedent: `docker_compose/hardened_media_m8/docker-compose.yml`
(×2), `docker_compose/hardened_media_m8/README.md` (×2, table rows) and
`docker_compose/README.md` (×1, stack-index row), all in `media-service-m8`
itself; `fa-ui-m8`'s three stacks (`docker_compose/dev_ui_m8/docker-compose.yml`
×2, `docker_compose/hardened_ui_m8/docker-compose.yml` ×1, plus the
`compose_policy_tests/test_compose_image_pins.py` fixture) re-point their own
`tepochtli/media-service-m8` pin to `2.3.0` in step. Gates: `media-service-m8`
49 passed (`tests/test_compose_image_pins.py`,
`tests/test_compose_storage_policy.py`); `fa-ui-m8` 216 passed
(`docker_compose/compose_policy_tests`); `docker compose config -q` clean on
`hardened_media_m8`. Branch `feat/object-storage-backend-migration`,
`media-service-m8` commit `a8cbc7a`, `fa-ui-m8` commit `a79fbc1`, both pushed.

`media-worker-m8` `0.4.1` (published) → **`0.5.0` in the working tree,
pending.** This row was *behind*, not stale: `T9-consumers-repin` and
`T11-worker-s3-rename` (Waves 1-2) had both landed on the plan branch with
their content left under `[Unreleased]` and an explicit note deferring the
version number to `T26`, and this file had not been told. No shim — unlike
`media-service-m8`'s `Settings` (`extra="forbid"`), `WorkerConfig` already
uses `extra="ignore"`, so an unmigrated `MINIO_*` deployment silently falls
back to defaults rather than failing to load; combined with the
`media-sdk-m8@0.8.0` repin (dependency floor `>=0.7.0,<0.8.0` →
`>=0.8.0,<0.9.0`, `minio` dropped), this is enough behind-the-scenes change
to take a minor number rather than a patch, on the same reasoning
`media-service-m8@2.2.0` used for its own `S3_*` rename. No Wave 3+ content
applies to this repository — the worker only consumes `media_sdk_m8`'s
storage client, so the SeaweedFS backend swap itself is invisible to it.
Two compose sites moved to match: `media-service-m8/docker_compose/
{dev_media_m8,hardened_media_m8}/docker-compose.yml` (+ both stacks'
`README.md` service tables) and `fa-ui-m8/docker_compose/
{dev_ui_m8,hardened_ui_m8}/docker-compose.yml` (+ the same
`test_compose_image_pins.py` fixture, alongside the `media-service-m8` pin
above). Gates: `media-worker-m8` 110 passed, 100% coverage. Branch
`feat/object-storage-backend-migration`, commit `a7f8b7b`, pushed.

`media-sdk-m8` and `security-tests-m8` need **no change** for `T26`:
`media-sdk-m8`'s `CHANGELOG.md` carries no `[Unreleased]` section — its
`0.8.0` release (`T8-sdk-release-cut`, Wave 1) and its one follow-on doc fix
(`T14`, folded into the same `0.8.0` entry) are its whole contribution to
this plan, and both rows above are unchanged (`0.7.0` published, `0.8.0`
working tree, still pending on the same PyPI-publish window recorded since
Wave 1). `security-tests-m8`'s `T22` work (blocking the `seaweedfs/` runtime
directory name) already shipped inside its own, unrelated `0.7.0` release
cut (`CHANGELOG.md`'s `## 0.7.0 — 2026-09-13`, published — see below); this
file's mechanism-map row for it (`0.6.0`) is now stale against source and is
corrected here to `0.7.0` in passing, though the publish itself predates and
is outside `T26`'s own scope.

`fa-ui-m8` needs **no version bump** for `T26` — it carries no
`CHANGELOG.md` at all (confirmed: only vendored Grafana-plugin changelogs
exist under `docker_compose/dev_local_full_ui_m8/grafana/data/plugins/`,
none of them this repository's own), so there is no changelog convention for
this step to fold into, and its row stays `— never published · 0.1.0
working tree · pending` exactly as this file already recorded. Its `T26`
contribution is the compose re-pin above only.

**Not done here, and is the operator's own step:** building and pushing the
`tepochtli/media-service-m8:2.3.0` and `tepochtli/media-worker-m8:0.5.0`
images (creating the GitHub Release / tag that triggers each repo's
`docker-publish.yaml`). Until that happens, `docker pull` for both tags
fails and the re-pinned compose stacks are red — the same pin-ahead-of-publish
window this file has now recorded four times (`media-sdk-m8@0.8.0`,
`media-service-m8@2.1.0`, `media-service-m8@2.1.1`, and now this cut). The
map above and the published-vs-working-tree table are updated on the
assumption that the human takes that step next; if the eventual published
tag differs from `2.3.0`/`0.5.0` (e.g. the operator instead publishes `2.1.1`
first per the alternative this file flagged on 2026-09-06), this section
needs a follow-up correction, not a silent re-read.

**Re-measured 2026-09-14 (`T31-operator-closeout`, Step 1): nothing has
moved.** PyPI's JSON index for `media-sdk-m8` lists releases through `0.7.0`;
Docker Hub's tag list for `tepochtli/media-service-m8` stops at `2.1.1` and
for `tepochtli/media-worker-m8` at `0.4.1`; `gh pr list --state all` shows no
pull request on `media-sdk-m8`'s `feat/wave0-s3-conformance-contract` or on
the `feat/object-storage-backend-migration` branches of `media-service-m8`,
`media-worker-m8` and `fa-ui-m8`. The pending rows above therefore stand as
written. The operator recorded the plan's open decisions that day and chose
to leave the publish, the PRs and the release tags for a later session; the
`pending` rows flip only after those acts, per the write-then-verify
convention.

### Major recut — the media triad crosses 1.0 / 3.0 together (2026-09-14, pending publish)

`T37-fleet-repin-and-record` closes Wave 7 of the object-storage backend
migration plan (`.workspace/plans/media-service-m8/done/
object-storage-backend-migration-2026-09-05.md`, under `todo/` until it
closed on 2026-09-16). The operator's read of
Waves 1-6 (`T31` Step 1) was that this is a major change for the three media
repos and the `MINIO_*` deprecation shim should not survive into the first
published version that speaks `S3_*`, so the `0.8.0`/`2.3.0`/`0.5.0` cut this
file recorded above under *Wave 4 release cut* was renumbered before
publish, not published and then re-cut — none of those three tags was ever
pushed, so nothing here is a retraction of a released artefact, and the Wave
6c one-bump-per-unpublished-release rule applies as it does to any
unpublished row.

`media-sdk-m8` `0.8.0` → **`1.0.0` in the working tree**
(`T33-sdk-1-0-0`, `3a5ec86`): the boto3-based, provider-neutral
`ObjectStorage` is the stable API. Still `0.7.0` published.

`media-service-m8` `2.3.0` → **`3.0.0` in the working tree**
(`T34-service-3-0-0-drop-shim`, `8d4d5d0`/`7a8d55c`): the fourteen `MINIO_*`
settings fields and their translation shim are removed in the same cut that
would otherwise have published `2.3.0` — `Settings` is `extra="forbid"`, so a
stray `MINIO_*` key now fails at boot. `CONTRACT_RANGE` moves
`">=2.0.0 <3.0.0"` → `">=3.0.0 <4.0.0"`, tracking the package major as it
always has; `CONTRACT_VERSION` stays `1.1` (service version is not contract
version, as above). SDK floor raised to `>=1.0.0,<2.0.0`. Still `2.1.0`
published.

`media-worker-m8` `0.5.0` → **`1.0.0` in the working tree**
(`T35-worker-1-0-0`, `a53933b`): no code change — the worker never carried
the shim — but the SDK floor raise to `>=1.0.0,<2.0.0` rides the same
unpublished-release fold as its sibling. Still `0.4.1` published.

`astro-media-m8` `MEDIA_SERVICE_M8_MAX_SERVICE_VERSION_EXCLUSIVE` `"3.0.0"`
→ **`"4.0.0"`** (`T36-astro-media-gate`, `1ef0af6`), admitting the `3.x`
service line; `MIN_SERVICE_VERSION` stays `"2.0.0"`, so the gate widens
additively and the client cut is a minor, `package.json` `2.0.0` → `2.1.0`.
The client-gate row in the table above now reads `astro-media-m8`
`>=2.0.0 <4.0.0`. `astro-media-m8` itself keeps published `1.1.1` / working
tree `2.1.0` / pending — the Wave 7 client work is additive to the same
unpublished row this file already tracked.

**Eight pin sites re-pointed from the superseded `2.3.0`/`0.5.0` cut to
`3.0.0`/`1.0.0`** (`T37-fleet-repin-and-record`): `media-service-m8`
`docker_compose/{dev_media_m8,hardened_media_m8}/docker-compose.yml` and
their `README.md`s, plus `docker_compose/README.md`'s stack-index row;
`fa-ui-m8` `docker_compose/{dev_ui_m8,hardened_ui_m8}/docker-compose.yml` and
`compose_policy_tests/test_compose_image_pins.py`'s docstring and
`_PREVIOUSLY_LATEST` map. Gates: `media-service-m8`
`tests/test_compose_image_pins.py` + `tests/test_compose_storage_policy.py`
73 passed; `fa-ui-m8`'s full `compose_policy_tests` suite 240 passed. No
image was ever built for `2.3.0`/`0.5.0` under any tag, so this re-pin
carries no `docker pull` regression — both tags were already unpublished and
red before this cut.

**Not done here, and still the operator's own act:** publishing
`media-sdk-m8@1.0.0` to PyPI and cutting the
`tepochtli/media-service-m8:3.0.0` / `tepochtli/media-worker-m8:1.0.0` /
`astro-media-m8` images/releases — that is `T31` Step 2 (Wave 8), gated on
this wave. Until then all three re-pinned stacks' `docker pull` stays red,
the same window this file has recorded for every prior media-stack cut.

### Wave 8 publish — the media triad is published, and a 3.0.1 patch follows (2026-09-16)

`T31-operator-closeout` Step 2 (Wave 8 of the object-storage backend
migration plan, `.workspace/plans/media-service-m8/done/
object-storage-backend-migration-2026-09-05.md`, moved from `todo/` when
it closed on 2026-09-16). The publish is the
operator's own act and it has happened; this file's rows flip on the
independent evidence this file requires, re-measured on 2026-09-16:

- `media-sdk-m8` **`1.0.0` published** — PyPI's JSON index lists `1.0.0`
  as the latest release; `v1.0.0` on `origin` (`dbf0e1c`, tip of `main`),
  the `Upload Python Package` run for that release succeeded on
  2026-09-15T17:13Z. PR #26 (`feat/wave0-s3-conformance-contract` → `main`,
  Waves 0–1 + `T33`) and #27 (`chore/release-1.0.0-lock-refresh`, the lock
  regenerated against the real index before publish) merged the same day.
  Both consumers' `requirements_prod.lock` now pin a version the index
  serves — `media-worker-m8` `75ea054` re-pinned to the published wheel
  hashes; the `T9` pin-ahead-of-publish window recorded since 2026-09-05 is
  closed.
- `media-service-m8` **`3.0.0` published** — Docker Hub serves
  `tepochtli/media-service-m8:3.0.0` (pushed 2026-09-16T16:49Z, digest
  `sha256:2f87fcc…`); `v3.0.0` on `origin` at `1828254`, the merge of PR
  #20 (`fix/jwks-kid-key-binding` → `main`; the branch name is historical,
  the diff is Waves 1–7 merged onto it). `2.1.1`, `2.2.0` and `2.3.0` never
  got a tag of their own, as the *Wave 4 release cut* and *Major recut*
  sections predicted.
- `media-worker-m8` **`1.0.0` published** — Docker Hub serves
  `tepochtli/media-worker-m8:1.0.0` (2026-09-16T03:32Z, digest
  `sha256:5a7ac60…`); `v1.0.0` on `origin` at `482106b`, the merge of PR #6.
- `astro-media-m8` **`2.1.0` published** — `npm view @mano8/astro-media-m8
  dist-tags.latest` → `2.1.0`; `v2.1.0` release on `origin` (2026-09-16T19:46Z)
  at `3bf34f4`, the merge of PR #13 (`feat/service-3-x-gate-widen`, `T36`
  plus `23bb883`'s `astro-auth-m8` `^2.6.0` repin and `js-yaml` `4.3.2` lift).
  The published client's gate is `>=2.0.0 <4.0.0`, so a deployed `3.x`
  service is admitted. **This row had been stale twice over**: it still read
  published `1.1.1` / working tree `2.0.0` although `2.0.0` was tagged and
  on npm since 2026-09-01 (`v2.0.0` at `e974bee`, PR #11) and the working
  tree had been `2.1.0` since `T36` — the *Major recut* section noted the
  latter in prose without moving the row.
- `fa-ui-m8` — its share (compose pins and docs only, PR #22 →
  `pre-alpha`, then PR #23 `integration/pending-work` → `main` at `64dc59c`)
  is on `main`; the repo's own row is unchanged (never published, `0.1.0`).

**The live acceptance found a bug in the published `3.0.0`, so the cut does
not close here.** `T31` re-ran the plan's live suites against
`hardened_media_m8` on the published images with the base stack's
working-tree source bind mount dropped (the same `volumes: !override` shape
`docker-compose.production.yml` uses — the base compose file mounts
`../../media_service` over the image's own code, so a run without that
override measures the working tree, not the artefact): `T24`'s invariants
42 passed, `T29`'s admin-surface probes 11 passed, `T23`'s workflow steps
1–8 pass — including the `T32` archive tier, live for the first time — and
step 9 (`purge-expired`) answers **500**: `media_variant` / `variant_job`
reference `media_object` without `ON DELETE CASCADE`, so the hard purge was
a foreign-key violation for every image that ever had a variant (the only
prior live purge, 2026-09-13, purged the quarantined EICAR upload, which has
none; the unit suite runs SQLite with foreign keys off). Fixed as
`media-service-m8` **`3.0.1` in the working tree** (`2a6f90c` on
`release/3.0.1-hard-purge-fk`, cut off `main`; PR #22 → `main`, pushed, not
tagged — PR #21, opened from the historical `fix/jwks-kid-key-binding`
branch, was closed in its favour and that branch restored to its merged
tip `0cbaac8`): the purge
deletes the variant and job rows first and removes the variant bytes from
the bucket as stored; pinned by a foreign-keys-on unit test; the full live
workflow passes on an image built from that tree with the mount dropped.
Contract untouched (`1.1`, range `>=3.0.0 <4.0.0`), so the patch needs no
client release. Pins moved first, per this file's write-then-verify
convention: the five `media-service-m8` sites (`2fcd69b`, same PR) and
`fa-ui-m8`'s three stacks + `test_compose_image_pins.py` fixture (`9ced278`
on `chore/pin-media-service-3.0.1`, PR #24 → `main`) now name `3.0.1`, which
the registry does not serve yet — the same window this file has recorded for
every media-stack cut, expected to close when the operator merges #22/#24
and cuts `v3.0.1`. The `media-service-m8` row above flips only after that.

`astro-media-m8` **`2.2.0` in the working tree** (`e72f02e` on
`chore/tested-service-3.0.1`, PR #14 → `main`, pushed, not published) is
the matching client tracking release: `MEDIA_SERVICE_M8_TESTED_SERVICE_VERSION`
and `mediaServiceM8.testedServiceVersion` move `3.0.0` → `3.0.1`, a minor
rather than a patch on the same reasoning `astro-auth-m8` `2.5.0`/`2.6.0`
recorded (an exported compatibility constant changes value); the contract
(`1.1`) and the `>=2.0.0 <4.0.0` gate are untouched, so this release gates
nothing and exists to keep the tracked version in step with the compose
pins. Merge order: after `media-service-m8` #22 and its `v3.0.1` release,
so the tested version names a published service; then `v2.2.0` publishes
the client. Both rows flip on the registry evidence, not before.

**Closed 2026-09-16, both rows flipped.** `media-service-m8` `v3.0.1`
(`a6ecbe6`, merge of PR #22, release 20:50Z) → Docker Hub serves
`tepochtli/media-service-m8:3.0.1` (20:57Z, digest `sha256:9674dbd…`),
`Publish Docker Image` run green; `fa-ui-m8` PR #24 merged (`48a07c3`);
`astro-media-m8` `v2.2.0` (`4b3a075`, merge of PR #14, release 20:49Z) →
`npm view @mano8/astro-media-m8 dist-tags.latest` → `2.2.0`, `Publish
Package` run green. The plan's acceptance was then re-run against the
published `3.0.1` with the source mount dropped (container reads
`__version__` `3.0.1`, `GET /media/meta` serves it): `T23` workflow **9/9
steps pass**, `T24` invariants 42 passed, `T29` admin-surface 11 passed.
Every consumer pin in the fleet now names a version its registry serves,
and the plan moved to `.workspace/plans/media-service-m8/done/`.
Re-measured 2026-09-17 for the JWKS `kid`/key-binding plan's residual: the
pulled `tepochtli/media-service-m8:3.0.1` (index digest
`sha256:9674dbda01b8b8c7f681a056e3c750a3b0536c633a6ae671ce799e4d00ae4f07`)
answers `media_service 3.0.1`, `fastapi-m8 4.5.1`, `auth-sdk-m8 3.2.0` —
the second published consumer image resolving `auth-sdk-m8 3.2.0`, after
`prompt-engine-m8 2.2.0`; its `requirements_prod.lock` at `v3.0.1` already
pinned both, so the `prompt-engine-m8` #40 lock lesson did not recur.
`reparto-docente-m8` remains the one consumer still on the pre-`W3.2`
floor (`2.1.0` on Hub, 2026-08-30).

### The reparto pair cut at 2.2.0 (2026-09-19, pending publish)

Measured against on-disk source, `git ls-remote --tags origin` and
`npm view`. Both rows were wrong again, in both of this file's ways.

`astro-reparto-m8` `2.0.0`/`2.1.0`/pending → **`2.1.0` published, `2.2.0`
working tree, pending.** The published column had been *stale* since
2026-09-08: `v2.1.0` was tagged and `npm view @mano8/astro-reparto-m8`
answers `latest: 2.1.0` (PR #3), yet the row went on saying `2.0.0`. The
working tree then accumulated four commits under `[Unreleased]` — C8
code-based error classification, C9 `Accept-Language` on every request, the
C13 client half (optional `locale` on both export schemas), and the auth-peer
`^2.6.0` / `js-yaml` `4.3.2` remediation — while `package.json` still read
the already-live `2.1.0`. Cut to **`2.2.0`** (`a60d536`): a field and a
header are a minor. `repartoDocenteM8.testedServiceVersion` moves `2.1.1` →
`2.2.0` — the old value named a service version that was never published
(next paragraph). `contract` stays `reparto-docente-m8@2.0.0`,
`serviceVersionRange` stays `>=2.0.0 <3.0.0`; `verify:contract-operations`
re-run green (116 operations). PR
[#4](https://github.com/DocentesTools/astro-reparto-m8/pull/4) is open to
`main`.

`reparto-docente-m8` `2.1.0`/`2.1.1`/pending → **`2.1.0` published, `2.2.0`
working tree, pending.** The row was *behind*, and the working-tree value it
carried was itself a number that will never ship: `2.1.1` was bumped on
2026-09-06 but never tagged, and C4–C14 (validation `params`, document
identity, the 157-code error envelope, `Accept-Language` negotiation with
`es`/`fr` gettext catalogs, coded bulk-preview prose, the persisted export
`locale` column, the three-locale document catalog) plus the `fastapi-m8`
`4.5.1` floor and the compose `fa-auth-m8` `2.2.1` repin all landed on top
of it. Fifth application of the one-bump rule: `[2.1.1]` folds into
**`[2.2.0]`** with every entry preserved (`7ee5c4a`), and the five task
commits that had landed without CHANGELOG entries got them at the cut.
`CONTRACT_VERSION` / `CONTRACT_RANGE` unchanged; `docs/served-api-surface.json`
still byte-identical to the client's vendored copy. This release also closes
the "one consumer still on the pre-`W3.2` floor" note two paragraphs up: the
`2.2.0` image will resolve `fastapi-m8 4.5.1` / `auth-sdk-m8 3.2.0`. PR
[#30](https://github.com/DocentesTools/reparto-docente-m8/pull/30) is open to
`main`.

**Publish order is load-bearing this time.** The service emits `locale` on
every `ExportArtifactPublic` row; the live `2.1.0` client's schema is Zod
`.strict()` without that field and would reject every export listing.
`fa-ui-m8/app` pins `^2.0.0` from the registry (the `file:` link in its
working tree is uncommitted). So: merge and publish `astro-reparto-m8@2.2.0`
→ `npm install` in `fa-ui-m8/app` and rebuild the host → then tag and
release `reparto-docente-m8@2.2.0`. Both CHANGELOGs and both PR bodies state
it.

**Pin sweep for `reparto-docente-m8` `2.2.0`** — every site that names a
reparto version, in tree and on this host:

| Site | Was | Now |
| --- | --- | --- |
| `astro-reparto-m8/package.json` `repartoDocenteM8.testedServiceVersion` | `2.1.1` | `2.2.0` (`a60d536`) |
| `astro-reparto-m8/REPOSITORY_CONTEXT.md` "tested at service version" | `2.1.1` | `2.2.0` (`a60d536`) |
| `astro-reparto-m8` comments/docs naming the older service (`schemas.ts`, three tests, `docs/contract-inventory.md`) | `2.1.1` | `2.1.0` — the version that actually shipped (`a60d536`) |
| `rpi_server/docente_reparto/docker-compose.yml` `reparto_service.image` (host-local, ignored) | `tepochtli/reparto-docente-m8:2.1.0` | `:2.2.0`, ahead of publish; README row corrected from "local build" |
| `fa-ui-m8/docker_compose/dev_local_full_ui_m8` | `build:` from sibling source | unchanged — no version to pin |
| `reparto-docente-m8/docker_compose/dev_reparto_m8` | `build:` from `../..` | unchanged — no version to pin |
| `fa-ui-m8` `dev_ui_m8` / `hardened_ui_m8` | no `reparto_service` | unchanged — nothing to pin |
| `.workspace/context/version-sources.md` mechanism table, published/working-tree table, fleet compatibility table | `2.1.1` / `2.1.0`–`2.1.1` / `2.1.1 (pending)` | `2.2.0` / `2.1.0`–`2.2.0` / `2.2.0 (pending)` |

`CONTRACT_VERSION` `reparto-docente-m8@2.0.0` is deliberately **not** in this
table: it is the contract axis, moves only when the served surface does, and
the client's gate is an exact-match `Set` on it. The `fa-ui-m8` UI image tag
the Pi runs (`tepochtli/fa-ui-m8:0.1.0-reparto*`) bakes in
`@mano8/astro-reparto-m8` at build time, so it is not a reparto *pin* but it
is on the critical path: it must be rebuilt on `2.2.0` of the plugin, under a
new tag, before `reparto_service` `2.2.0` is pulled.

Gates at the cut — service (Conda `fa_auth_m8`): Ruff format/check over 187
files, **`mypy .` 0 errors over 180 files** (the 15 test-only errors this
file recorded on 2026-09-06 are fixed in `3a67424`, so the README's command
and CI's command finally agree), 2142 tests at 100% coverage, Bandit zero
medium/high, Docker image builds and both catalogs load in a fresh container.
Client (Node 24.18.1): typecheck, lint, build, 1085 tests at 100%, contract
operations, nine fleet gates, registry drift/consumer, starter and headless
fixture builds, `2.2.0` tarball standalone install, `npm audit` clean.

### The reparto pair published (2026-09-19)

Measured against GitHub, Docker Hub, npm and the pulled image, the same
day as the cut above. Both rows flip to *published*.

`reparto-docente-m8` `2.1.0`/`2.2.0`/pending → **`2.2.0` published.** PR
[#30](https://github.com/DocentesTools/reparto-docente-m8/pull/30) merged
at `90a0c22` (16:45Z); PR
[#31](https://github.com/DocentesTools/reparto-docente-m8/pull/31)
(`09e979a`, constraints regenerated after the Dependabot floor bumps,
recorded under `[2.2.0]`) merged on top at 17:09Z; `v2.2.0` is tagged on
`09e979a`, the `main` tip, release published 17:10Z;
`docker-publish.yaml` run `35457262029` green. Hub `2.2.0` and `latest`
share index digest
`sha256:803e9c18671f7317cdb0ed191c50cc459525471da6d59bf3250eec5cc7562650`;
the pulled image answers `reparto_service 2.2.0`, `fastapi-m8 4.5.1`,
`auth-sdk-m8 3.2.0` — the last consumer onto the `W3.2` floor, which
closes the JWKS `kid` plan
(`.workspace/plans/stack/done/fa-auth-jwks-kid-key-binding-plan-2026-09-08.md`,
`W3.7` line 6). `fix/jwks-kid-key-binding` is 0 ahead of `origin/main`;
no PRs open.

`astro-reparto-m8` `2.1.0`/`2.2.0`/pending → **`2.2.0` published.** PR
[#4](https://github.com/DocentesTools/astro-reparto-m8/pull/4) merged at
17:18Z, `v2.2.0` on `cf494b1`, `Publish Package` run `35458967201` green,
`npm view @mano8/astro-reparto-m8 time` puts `2.2.0` at 17:45:43Z.

**Registry order was service-first**, the reverse of the load-bearing
order the cut section states: the service image was on Hub at ~17:10Z,
the client on npm at 17:45Z. Nothing consumed the service image in that
window — every stack that runs `reparto_service` builds from source, and
the one host-local pin (`rpi_server/docente_reparto`) is pulled by hand —
so the constraint that matters is unchanged and still stands for the
deploy: rebuild the `fa-ui-m8` host on `@mano8/astro-reparto-m8@2.2.0`
under a new tag *before* pulling `tepochtli/reparto-docente-m8:2.2.0` on
the Pi. Recorded so the deploy does not read the registry timestamps as
proof the order was honoured.

### The published fleet verified live under `TOKEN_MODE=stateful` (2026-09-20)

The consumer-alignment closure plan's `B7` (`.workspace/plans/stack/todo/
consumer-alignment-closure-remediation-plan-2026-08-16.md`), run on the
Windows host against Docker Desktop 4.86.0 / Compose v5.3.1, one stack at a
time, every stack torn back down to 0 containers and 0 project networks.
Every consumer ran the **published** image, not a source build — each
newest tag is byte-identical to `origin/main` (`fa-auth-m8` `v2.2.1` =
`77f302c`, `media-service-m8` `v3.0.1` = `a6ecbe6`, `media-worker-m8`
`v1.0.0` = `482106b`, `prompt-engine-m8` `v2.2.0` = `19caa6e`,
`reparto-docente-m8` `v2.2.0` = `09e979a`), so "what the registry ships" and
"what `main` carries" are the same measurement here. Issuer in every stack:
`tepochtli/fa-auth-m8:2.2.1`, `TOKEN_MODE=stateful`, one login and one
token per stack (a second login of the same user revokes the first token
under stateful mode — the JWKS plan's `W3.4` trap, avoided by design).

| Stack (compose dir) | Consumer image | Probe (reader/admin floor) | no token / garbage / **authenticated** | `fastapi-m8` / `auth-sdk-m8` resolved in the image | `~introspect:*` grant |
| --- | --- | --- | --- | --- | --- |
| `media-service-m8/docker_compose/hardened_media_m8` (+ `media-worker-m8:1.0.0`) | `tepochtli/media-service-m8:3.0.1` | `GET /media/category/` | `401` / `403` / **`200`** (×2) | `4.5.1` / `3.2.0` | answers as user `auth`; out-of-grant key → `NOPERM`; 0 `NOPERM` in either log |
| `reparto-docente-m8/docker_compose/dev_reparto_m8` (build swapped for the image) | `tepochtli/reparto-docente-m8:2.2.0` | `GET /reparto/departments/` | `401` / `403` / **`200`** (×2) | `4.5.1` / `3.2.0` | same |
| `prompt-engine-m8/docker_compose/dev_prompt_engine_m8` (provisioned from its `*.env.example`, build swapped for the image) | `tepochtli/prompt-engine-m8:2.2.0` | `GET /prompt/category/` | `401` / `403` / **`200`** (×2) | `4.5.1` / `3.2.0` | same |

All three consumers therefore resolve the `W3.2` floor (`auth-sdk-m8 3.2.0`,
`fastapi-m8 4.5.1`) **from the published tag**, which is what the JWKS plan's
`W3.4` finding 1 said only a rebuilt local image did at the time. Measured
with `importlib.metadata.version` inside each container: none of the three
images ships `pip`, so the `pip show` form the plan's §6 named cannot run
against them. Consumer `RestartCount` 0 and no `ERROR`/`Traceback` in any
consumer log after the probes.

**`fa-ui-m8` host against `@mano8/astro-reparto-m8@2.2.0` (the `B8`
residual).** `fa-ui-m8/app` at the `origin/main` tree (`415df4f`, PR #26;
lock `2.6.0` / `1.5.1` / `2.2.0` / `2.1.0` / `2.2.0`) served by `astro dev`
through its same-origin proxy onto the reparto stack above; headless Chrome
153 logged in through the plugin's form and loaded `/en/reparto`,
`/en/reparto/setup/departments` and `/en/reparto/processes`. All three
rendered — `data-reparto-route` `no-process` / `departments` / `processes`,
three-stage sidebar, departments data table with its columns and paging,
no `role=alert`, no page error — and every `/reparto/*` call the pages made
(`assignment-processes/`, `schools/`, `departments/`) answered `200`. The
`G12`(a) config crash is gone on the live payload, not only at install.
Screenshots and the per-stack transcripts live in the session scratchpad;
no token, credential or password hash is in either.

Nothing under any repository changed: the two dev stacks ran under a
scratchpad override (`image:` in place of `build:`, source bind mount
dropped), the prompt stack's secrets were generated in the scratchpad and
destroyed after, and every `git status` read clean afterwards.

### `astro-reparto-m8` 2.3.0 — the service-version gate (2026-09-20, pending publish)

The consumer-alignment closure plan's `B11` (`.workspace/plans/stack/todo/
consumer-alignment-closure-remediation-plan-2026-08-16.md`, finding `G6`).
Since `2.0.0` the client's `package.json` had advertised
`repartoDocenteM8.serviceVersionRange` `>=2.0.0 <3.0.0` while
`src/runtime/compatibility.ts` compared only the contract identity — the one
plugin of four whose stated range was documentation, and three service
releases shipped against it. `2.3.0` (PR #7, merged by the operator as
`5d527b1`) adds `REPARTO_MIN_SERVICE_VERSION` `2.0.0`,
`REPARTO_MAX_SERVICE_VERSION_EXCLUSIVE` `3.0.0`,
`REPARTO_SERVICE_VERSION_RANGE` and `REPARTO_TESTED_SERVICE_VERSION`
`2.2.0` — the manifest verbatim, in the shape `astro-media-m8` carries — and
`assertRepartoCompatibility` now refuses a GET `/meta` `version` outside the
range, after the contract-identity checks. `contract`, `serviceVersionRange`
and `testedServiceVersion` are all unchanged; a minor because a host that
was reaching a `1.x` or `3.x` service through the guard now fails at
startup. The plan's `G7` gap (*"a known gap, recorded rather than fixed"*
above) is still open for this repository until `B12` lands its
manifest↔runtime lock, which could not exist before this release gave it a
`MIN`/`MAX` pair to assert.

The working tree and `main` read `2.3.0`; `origin` tags still end at
`v2.2.0` and `npm view @mano8/astro-reparto-m8 version` reads `2.2.0`. The
tag and publish are the operator's and, by the plan's eleventh amendment
(2026-09-20), deliberately deferred: the operator publishes once per
repository when the plan is done (`B25`), so anything `B12` lands on this
repository before then rides `2.3.0` under the one-bump-per-unpublished-
release rule. `fa-ui-m8`'s `^2.2.0` pin follows the publish, never precedes
it.

### Three of the five `B23` patches published; two still on branches (2026-09-22)

The consumer-alignment closure plan's `B23-converge-patch-layer` (`G18`): the
five service images converge on one Debian patch-layer form and one base
digest, owned by [`debian-patch-layer.md`](debian-patch-layer.md). Cut
2026-09-20 on `chore/patch-layer-convergence` in each repository; on
2026-09-22 the operator merged and published three of them.

| Repo | Published | On `main` | State |
| --- | --- | --- | --- |
| `fa-auth-m8` | **2.2.2** (2026-09-22) | 2.2.2 (`cc27ae0`) | published; image pulled and read back |
| `reparto-docente-m8` | **2.2.1** (2026-09-22) | 2.2.1 (`d29ee51`) | published; image pulled and read back |
| `media-worker-m8` | **1.0.1** (2026-09-22) | 1.0.1 (`585327f`) | published; image pulled and read back |
| `prompt-engine-m8` | 2.2.0 | 2.2.1 | `2.2.1` cut on [PR #42](https://github.com/mano8/prompt-engine-m8/pull/42) (also carries the plan's `B24` stack `.gitignore`); merged 2026-09-22 (`0b9f573`) after `B27`'s #43 (`a5013c0`) cleared `G20`; **published 2026-09-26** as `v2.2.1` (`fd74ef3`), see the mechanism map above |
| `media-service-m8` | 3.0.1 | 3.0.2 | `3.0.2` cut on [PR #23](https://github.com/mano8/media-service-m8/pull/23); merged 2026-09-22 (`a98ed16`) after `B27`'s #24 (`d8ea9cd`) cleared `G20`; **published 2026-09-26** as `v3.0.2` (`35e518b`), see the mechanism map above |

Each published image was read back inside the container: Debian 13.7,
`OpenSSL 3.5.7`, no `curl`, no pip, `__version__` matching the tag.

⚠️ **The three published versions are closed.** The plan's `B27` (dev-set
drift repair) therefore takes **new** numbers in those repositories —
`fa-auth-m8` `2.2.3`, `reparto-docente-m8` `2.2.2` — and rides the pending
`2.2.1` / `3.0.2` in the two that have not published. The
one-bump-per-unpublished-release rule applies to an unpublished version; a
published one cannot be reused, and this exact mistake was caught once in
this session because a local clone still showed the older tag. **Read
`git ls-remote --tags origin`, not a local tag list.**

⚠️ **§0.2 re-pins are owed, not done.** The three pulls are confirmed, so the
stack pins that name those images may now move (`fa-auth-m8` ×10 sites plus
`DOCKERHUB.md`/`README.md`, `media-worker-m8` ×4, `reparto-docente-m8`'s
stacks). A pin still never precedes its publish.

⚠️ **`reparto-docente-m8`'s image is not reproducible** (plan finding `G21`):
its Dockerfile installs `-r requirements_prod.txt` unpinned where the other
four install `--require-hashes -r requirements_prod.lock`. Measured inside
the images published 2026-09-22: `fa-auth-m8:2.2.2` carries SQLAlchemy
2.0.51 / sqlmodel 0.0.42 / pydantic 2.13.4, `reparto-docente-m8:2.2.1`
carries 2.0.54 / 0.0.46 / 2.13.5. Same day, same fleet, different library
generation — and an API timestamp spelling (`...Z` vs `...+00:00`) moved
with it.

## One documented read command per mechanism

Run from the workspace root; each command prints the repo's authoritative
version and nothing else.

```powershell
# npm package.json at repo root
(Get-Content astro-auth-m8/package.json -Raw | ConvertFrom-Json).version
(Get-Content astro-media-m8/package.json -Raw | ConvertFrom-Json).version
(Get-Content astro-prompt-m8/package.json -Raw | ConvertFrom-Json).version
(Get-Content astro-reparto-m8/package.json -Raw | ConvertFrom-Json).version
(Get-Content astro-ui-m8/package.json -Raw | ConvertFrom-Json).version

# npm package.json not at repo root
(Get-Content fa-ui-m8/app/package.json -Raw | ConvertFrom-Json).version

# pyproject.toml [project] version literal
python -c "import tomllib,pathlib; print(tomllib.loads(pathlib.Path('auth-sdk-m8/pyproject.toml').read_text())['project']['version'])"
python -c "import tomllib,pathlib; print(tomllib.loads(pathlib.Path('fastapi-m8/pyproject.toml').read_text())['project']['version'])"
python -c "import tomllib,pathlib; print(tomllib.loads(pathlib.Path('media-sdk-m8/pyproject.toml').read_text())['project']['version'])"
python -c "import tomllib,pathlib; print(tomllib.loads(pathlib.Path('security-tests-m8/pyproject.toml').read_text())['project']['version'])"

# pyproject.toml dynamic -> __init__.__version__ (a naive TOML read on this
# mechanism returns the literal string "imgtools_m8.__version__", not a
# version — that is a defect in the reader, not the repo. Read the attribute
# target's source file directly instead of `import`ing the package: an
# import resolves whatever is installed in site-packages, which can be a
# stale build rather than the checked-out working tree — verified 2026-08-15,
# the fa_auth_m8 conda env's installed imgtools_m8 read 2.1.0 while the
# working tree's __init__.py already read 2.1.1.)
python -c "import re,pathlib; print(re.search(r'__version__ = \"([^\"]+)\"', pathlib.Path('imgtools_m8/imgtools_m8/__init__.py').read_text()).group(1))"

# package __init__.__version__ only (no pyproject version) — same
# source-file-direct approach, same reason (no install/activation required,
# never stale relative to the working tree)
python -c "import re,pathlib; print(re.search(r'__version__ = \"([^\"]+)\"', pathlib.Path('fa-auth-m8/auth_user_service/__init__.py').read_text()).group(1))"
python -c "import re,pathlib; print(re.search(r'__version__ = \"([^\"]+)\"', pathlib.Path('media-service-m8/media_service/__init__.py').read_text()).group(1))"
python -c "import re,pathlib; print(re.search(r'__version__ = \"([^\"]+)\"', pathlib.Path('media-worker-m8/worker/__init__.py').read_text()).group(1))"
python -c "import re,pathlib; print(re.search(r'__version__ = \"([^\"]+)\"', pathlib.Path('prompt-engine-m8/promt_engine_service/__init__.py').read_text()).group(1))"
python -c "import re,pathlib; print(re.search(r'__version__ = \"([^\"]+)\"', pathlib.Path('reparto-docente-m8/reparto_service/__init__.py').read_text()).group(1))"

# fastapi-m8's second source (_version.py, kept in sync with the
# [project] literal above by tests/test_version_source_parity.py)
python -c "import re,pathlib; print(re.search(r'__version__ = \"([^\"]+)\"', pathlib.Path('fastapi-m8/fastapi_m8/_version.py').read_text()).group(1))"
```

All commands read the working tree's source file directly (`tomllib` on
`pyproject.toml`, a regex on the target `__init__.py`/`_version.py`) rather
than `import`ing the installed package — an import reflects whatever build is
in the active environment's site-packages, which can silently disagree with
the checked-out branch. If a command using `import <pkg>` is more convenient
for a one-off check, the target package must first be installed (this
workspace's convention: conda env `fa_auth_m8`) and its site-packages build
verified current — do not treat its output as authoritative otherwise.

## Convergence

The recommendation is `imgtools_m8`'s working `dynamic = ["version"]` +
`[tool.setuptools.dynamic]` pattern, applied to `fastapi-m8` and
`auth-sdk-m8` where non-disruptive. Not yet applied — `fastapi-m8`'s minimum
bar (closing its dual-source risk) is met by the parity test above rather
than a full convergence, and `auth-sdk-m8` convergence is unstarted follow-on
work, recorded here rather than silently dropped.

`astro-reparto-m8` also had a version-source split **inside** one repo:
`package.json` at `3.0.0`, `package-lock.json` at `2.0.0` — the same defect
class, npm side. It was first closed by regenerating the lockfile up to `3.0.0`
(`npm install --package-lock-only`); on 2026-08-16 the operator ruled `2.0.0`
the correct version — `3.0.0` was never published, and the lockfile's original
`2.0.0` was the right half of the split — so both files now read `2.0.0`. The
other four `astro-*` plugins were already self-consistent.

### `B27-dev-set-drift-repair` — four service repos (2026-09-22)

Recorded here because it moves two published-version rows and because the
mechanism map above was read from `origin/main`, not from a local clone —
three of these tags did not exist locally when the branches were cut.

`G20`: every one of these repositories declares its dev set with `>=` floors
and installs it in CI, so `test` and `typecheck` resolve a fresh dependency
graph on every run. The generation that resolved on 2026-09-22 — sqlmodel
`0.0.46` / SQLAlchemy `2.0.54` / pydantic `2.13.5` — rejects naive datetimes
at the column boundary and types SQLModel table constructors with their
required fields, which turned four of `B23`'s five PRs red on defects that
were already on `main`.

| Repo | Version | Where it went | Publish |
| --- | --- | --- | --- |
| `prompt-engine-m8` | rides `2.2.1` (`### Fixed`, no new heading) | `main` via PR #43 → #42 | owed |
| `media-service-m8` | rides `3.0.2` (`### Fixed`, no new heading) | `main` via PR #24 → #23 | owed |
| `reparto-docente-m8` | **`2.2.2`** — own heading | `main` via PR #34 | owed |
| `fa-auth-m8` | **`2.2.3`** — own heading | `main` via PR #128 (`259a609`) | owed |

The one-bump-per-unpublished-release rule decided which of those is a ride
and which is a new patch: `prompt-engine-m8` `2.2.1` and `media-service-m8`
`3.0.2` were still unpublished, so the fix folded into them; `fa-auth-m8`
`2.2.2` and `reparto-docente-m8` `2.2.1` were **published earlier the same
day** and are therefore closed, so each takes a patch of its own.

**Closed 2026-09-22: all four legs are on `main`**, each read with
`merge-base --is-ancestor`, and `fa-auth-m8`'s `main` is green on all three
of its workflows (`CI`, `Database integration`, `Maintained example smoke`).
Four publishes are now owed — `prompt-engine-m8` `2.2.1`,
`media-service-m8` `3.0.2`, `reparto-docente-m8` `2.2.2` and `fa-auth-m8`
`2.2.3` — all of them `B25` rows, none of them a condition of `B27`.

⚠️ **`fa-auth-m8` carries its version in three files**, not one:
`auth_user_service/__init__.py` plus `examples/fastapi_full/__init__.py` and
`examples/fastapi_minimal/__init__.py`. All three move together.

⚠️ **`fa-auth-m8`'s gate is two mypy invocations and 23 checks**, not the one
invocation the closure plan's §4 summarised: its `typecheck` job type-checks
`auth_user_service` *and* `examples/fastapi_full`, and it has two workflows
beyond `CI.yaml` (`database-integration.yaml`'s three-engine matrix and
`example-smoke.yaml`'s six stack smokes). The bundled example keeps its own
copies of the audit and category models, so it carries its own copy of any
defect found in the service — 11 errors in 7 files in this case.

### `G21` has a step: `B28-reparto-hash-locked-release-set` (opened 2026-09-23)

`reparto-docente-m8` is still the only service image in the fleet installing
an **unpinned** set (`reparto_service/Dockerfile` → `-r requirements_prod.txt`);
the other four install `--require-hashes -r requirements_prod.lock`. So what
that image ships is a property of the day it was built, not of the repository.

Measured 2026-09-23, the gap is **three** things:

| # | The four siblings have | `reparto-docente-m8` |
| --- | --- | --- |
| 1 | `requirements_prod.lock`, pinned + hashed | nothing |
| 2 | `--require-hashes` install in the non-development branch | `-r requirements_prod.txt` |
| 3 | a `test-shipped-lock` job + `scripts/shipped_lock_env.py`, and a `pip-audit` over the shipped lock | neither; `pip-audit` reads `requirements_dev.txt` only |

Item 3 is the one that is easy to miss and is half the value: `pip-audit` and
`trivy` **scan** a lock, neither **runs** it.

**Version:** `B28` **rides `2.2.2`**, which is on `main` and unpublished, under
the one-bump-per-unpublished-release rule. ⚠️ **That is conditional** — if
`2.2.2` is published first, `B28` costs a `2.2.3` instead, so `B28` must land
before this repository's publish.

**Open decision (operator's):** which generation the lock pins. The published
`2.2.1` image runs SQLAlchemy `2.0.54` / sqlmodel `0.0.46` / pydantic `2.13.5`;
the four sibling locks pin `2.0.51` / `0.0.42` / `2.13.4`. Pinning today's
resolve keeps the image contents where they already are but leaves this service
on a different generation from the fleet; pinning the siblings' generation makes
the five comparable but downgrades what this service ships.

### `G22` — the fleet tests one library graph and ships another (2026-09-23)

Measured from `origin/main` while scoping `B29`:

| Repo | lock SQLAlchemy | lock sqlmodel | lock pydantic | runs its lock? |
| --- | --- | --- | --- | --- |
| `fa-auth-m8` | 2.0.51 | **0.0.42** | 2.13.4 | no |
| `prompt-engine-m8` | 2.0.51 | **0.0.39** | 2.13.4 | **yes** |
| `media-service-m8` | 2.0.51 | **0.0.39** | 2.13.4 | no |
| `media-worker-m8` | — | — | 2.13.4 | no |
| `reparto-docente-m8` | *no lock* | *no lock* | *no lock* | no |

Every `test`/`typecheck` job installs `requirements_dev.txt`'s `>=` floors,
which on 2026-09-23 resolve to **SQLAlchemy 2.0.54 / sqlmodel 0.0.46 /
pydantic 2.13.5** — a generation **no lock pins**. There is also no single
"older" generation: sqlmodel is split three ways across the fleet.

⚠️ **Only `prompt-engine-m8` has a job that executes the shipped lock**
(`test-shipped-lock`). `pip-audit` and `trivy` scan a lock; neither runs it.

⚠️ **A second unpinned image exists** and it is not a service repo:
`fa-auth-m8/examples/fastapi_full` installs `-r requirements_prod.txt` with
floors and has no lock. It is never published, but `example-smoke.yaml`
builds and runs it six times per CI run. `fastapi_minimal` is **not** in this
class — two floors, none of the three packages, and nothing builds it.

**Owner: `B29-align-shipped-library-generation`.** Four of the five ride an
unpublished version on `main`, so the realignment costs no extra release —
**until `B25` publishes**, which closes that window. `media-worker-m8` is
already published and therefore takes a real `1.0.2`.

Mechanism note for whoever runs it: use
`pip-compile --upgrade-package <name>==<version>` for exactly the named pins.
A blanket `--upgrade` moves ~49 pins per repository (`B23`'s anyio fix is the
precedent for the narrow form).
