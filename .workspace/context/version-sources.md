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
| npm `package.json` at repo root | `astro-auth-m8` 2.4.1 · `astro-media-m8` 2.0.0 · `astro-prompt-m8` 2.1.0 · `astro-reparto-m8` 2.0.0 · `astro-ui-m8` 1.5.1 |
| npm `package.json` **not** at repo root | `fa-ui-m8` 0.1.0 — at `app/package.json` |
| `pyproject.toml` `[project] version` literal | `auth-sdk-m8` 3.1.3 · `fastapi-m8` 4.4.0 · `media-sdk-m8` 0.7.0 · `security-tests-m8` 0.6.0 |
| `pyproject.toml` `dynamic` → `__init__.__version__` | `imgtools_m8` 2.1.1 |
| package `__init__.__version__` only (no pyproject version) | `fa-auth-m8` (`auth_user_service`) 2.0.3 · `media-service-m8` (`media_service`) 2.0.0 · `media-worker-m8` (`worker`) 0.4.1 · `prompt-engine-m8` (`promt_engine_service`) 2.1.0 · `reparto-docente-m8` (`reparto_service`) 2.1.0 — the three consumers re-surface it as `SERVICE_VERSION` in `<pkg>/core/config.py` |

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
| `auth-sdk-m8` | 3.1.3 | 3.1.3 | — published |
| `fastapi-m8` | 4.4.0 | 4.4.0 | — published |
| `fa-auth-m8` | 2.0.3 | 2.0.3 | — published |
| `imgtools_m8` | 2.1.1 | 2.1.1 | — published |
| `security-tests-m8` | 0.6.0 | 0.6.0 | — published |
| `media-sdk-m8` | 0.7.0 | 0.7.0 | — published |
| `media-service-m8` | 2.0.0 | 2.0.0 | — published |
| `media-worker-m8` | 0.4.1 | 0.4.1 | — published |
| `prompt-engine-m8` | 2.1.0 | 2.1.0 | — published |
| `reparto-docente-m8` | 2.1.0 | 2.1.0 | — published |
| `fa-ui-m8` | — never published | 0.1.0 | pending |
| `astro-ui-m8` | 1.5.1 | 1.5.1 | — published |
| `astro-auth-m8` | 2.4.1 | 2.4.1 | — published |
| `astro-media-m8` | 1.1.1 | 2.0.0 | pending |
| `astro-prompt-m8` | 2.1.0 | 2.1.0 | — published |
| `astro-reparto-m8` | 2.0.0 | 2.0.0 | — published |

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

That last point does **not** trigger the converse rule recorded below, and the
reason is worth stating because it is easy to get wrong: `fa-ui-m8/app`
consumes the three business plugins as path links
(`"@mano8/astro-media-m8": "file:../../astro-media-m8"`, likewise prompt and
reparto), not as registry ranges. A `file:` link has no semver range to
exclude a major, so the host tracks those three working trees directly and
needs no repoint when they publish. Only `@mano8/astro-auth-m8` (`^2.4.1`) and
`@mano8/astro-ui-m8` (`^1.5.1`) are registry-ranged in the host, and both are
now published at their floor. The converse rule still binds any *external*
consumer of these packages, and it bound `fa-ui-m8` itself for
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

**How the split arose, since it bears on the number.** `ac96cbf feat(media): add
category page and library upload dialog` moved `package.json` `1.2.0` → `2.0.0`
inside an ordinary feature commit, one-line message, no changelog section and no
stated reason for a **major**. The fold therefore had to supply a justification
after the fact, and the defensible one is the install contract: the required
`@mano8/astro-auth-m8` peer moves `^2.2.0` → `^2.4.1`, so a consumer cannot take
this release without also moving its auth plugin. No export of this package is
removed or renamed.

⚠️ **Open, an operator decision rather than a matrix fact:** `1.2.0` was
**never published either** — `origin`'s newest tag is `v1.1.1`, so there are now
two unpublished numbered sections (`1.2.0` and `2.0.0`) against one unpublished
release. A strict reading of the Wave 6c one-bump-per-unpublished-release rule
folds `1.2.0` into `2.0.0` as well. That was **not** done here: it merges two
written, dated sections rather than an empty `[Unreleased]` into one, which is a
content decision of the kind the operator has settled before (the
`3.0.0`/`2.0.0` split recorded under *Convergence*, and reparto decision 6).

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

⚠️ **A `2.1.0` bump was requested for `media-service-m8` and deliberately not
made.** The repository had **zero** commits since `v2.0.0` and a clean tree, so
`2.1.0` would have been an empty release. The operator ruled on 2026-08-30 to
amend the published `## [2.0.0]` section instead, since both undocumented
commits are already inside that tag. The row therefore stays
`2.0.0 / 2.0.0 / — published`. Recorded because "the version did not move" is
exactly the kind of decision this file exists to make findable later.

`astro-media-m8` `feat/eslint-10-flat-config` (`8b40b83`, pushed): the fold
described above. Gate: typecheck and lint clean.

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
| `fa-auth-m8` | 2.0.3 | `fa-auth-m8@2.0` | `astro-auth-m8` `>=2.0.0 <3.0.0` |
| `media-service-m8` | 2.0.0 | `media-service-m8@1.1` | `astro-media-m8` `>=2.0.0 <3.0.0` |
| `prompt-engine-m8` | 2.1.0 | `prompt-engine-m8@2.1.0` | `astro-prompt-m8` `>=2.1.0 <3.0.0` |
| `reparto-docente-m8` | 2.1.0 | `reparto-docente-m8@2.0.0` | `astro-reparto-m8` contract-only (no numeric service gate) |

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
