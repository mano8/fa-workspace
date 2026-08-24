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

One row of this map corrected since that measurement: `astro-prompt-m8`
`1.2.0` → `2.0.0` (2026-08-23), from a targeted re-read of that repository
rather than a fleet re-measurement. Every other value here still dates from
2026-08-16. Three rows of the **published** table below also moved on
2026-08-23; that section records which and why.

| Mechanism | Repos (version at measurement) |
| --- | --- |
| npm `package.json` at repo root | `astro-auth-m8` 2.1.0 · `astro-media-m8` 1.2.0 · `astro-prompt-m8` 2.0.0 · `astro-reparto-m8` 2.0.0 · `astro-ui-m8` 1.4.2 |
| npm `package.json` **not** at repo root | `fa-ui-m8` 0.1.0 — at `app/package.json` |
| `pyproject.toml` `[project] version` literal | `auth-sdk-m8` 3.1.3 · `fastapi-m8` 4.4.0 · `media-sdk-m8` 0.6.0 · `security-tests-m8` 0.6.0 |
| `pyproject.toml` `dynamic` → `__init__.__version__` | `imgtools_m8` 2.1.1 |
| package `__init__.__version__` only (no pyproject version) | `fa-auth-m8` (`auth_user_service`) 2.0.3 · `media-service-m8` (`media_service`) 2.0.0 · `media-worker-m8` (`worker`) 0.4.0 · `prompt-engine-m8` (`promt_engine_service`) 2.0.0 · `reparto-docente-m8` (`reparto_service`) 2.0.0 — the three consumers re-surface it as `SERVICE_VERSION` in `<pkg>/core/config.py` |

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
| `fa-auth-m8` | 2.0.2 | 2.0.3 | pending |
| `imgtools_m8` | 2.1.0 | 2.1.1 | pending |
| `security-tests-m8` | 0.5.1 | 0.6.0 | pending |
| `media-sdk-m8` | 0.5.1 | 0.6.0 | pending |
| `media-service-m8` | 1.0.0 | 2.0.0 | pending |
| `media-worker-m8` | 0.3.0 | 0.4.0 | pending |
| `prompt-engine-m8` | 2.0.0 | 2.0.0 | — published |
| `reparto-docente-m8` | 1.1.0 | 2.0.0 | pending |
| `fa-ui-m8` | — never published | 0.1.0 | pending |
| `astro-ui-m8` | 1.4.2 | 1.4.2 | — published |
| `astro-auth-m8` | 2.1.0 | 2.1.0 | — published |
| `astro-media-m8` | 1.1.1 | 1.2.0 | pending |
| `astro-prompt-m8` | 2.0.0 | 2.0.0 | — published |
| `astro-reparto-m8` | 1.0.0 | 2.0.0 | pending |

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

The rule above — a consumer may only pin a published version — has a
converse this release made visible: a consumer does not pick up a **major**
through a caret it already carries. `fa-ui-m8` pinned
`@mano8/astro-prompt-m8@^1.1.1`, which excludes `2.0.0`, so the host needed an
explicit repoint to `^2.0.0` after the publish rather than an install. When a
row here moves across a major, check the consumers' ranges as well as their
lockfiles.

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
surface moved that contract to `1.1`; its compatibility range remains
`>=1.0.0 <2.0.0` because 1.0 clients are still served.

| Service | Package version | Contract | Client gate (`<plugin>/src/runtime/compatibility.ts`) |
| --- | --- | --- | --- |
| `fa-auth-m8` | 2.0.3 | `fa-auth-m8@2.0` | `astro-auth-m8` `>=2.0.0 <3.0.0` |
| `media-service-m8` | 2.0.0 | `media-service-m8@1.1` | `astro-media-m8` `>=2.0.0 <3.0.0` |
| `prompt-engine-m8` | 2.0.0 | `prompt-engine-m8@2.0.0` | `astro-prompt-m8` `>=2.0.0 <3.0.0` |
| `reparto-docente-m8` | 2.0.0 | `reparto-docente-m8@2.0.0` | `astro-reparto-m8` contract-only (no numeric service gate) |

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
