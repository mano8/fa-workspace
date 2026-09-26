# Markdown Lint Conventions

Canonical owner of the fleet's `.markdownlint` file format and canonical
`CHANGELOG.md` release-heading form. Ratified by `B10-markdownlint-parity` of
`.workspace/plans/stack/done/consumer-alignment-closure-remediation-plan-2026-08-16.md`
(gitignored; not the authority — this file is), which found both decisions
outstanding while adding the four repository configs that still lacked one.

Workspace invariant: [`CFG-SINGLE-WORKSPACE-OWNER`](../architecture.md#cfg-single-workspace-owner)
— this file is the sole canonical owner of both decisions below; no child
repository or agent-specific directory may keep a competing copy of either.

## Decision 1 — config file format: YAML

**`.markdownlint.yaml`, not `.markdownlint.json`.** Measured at ratification
time: 7 of 12 existing repository configs were already `.yaml`
(`astro-auth-m8`, `astro-media-m8`, `astro-ui-m8`, `fastapi-m8`,
`media-sdk-m8`, `media-service-m8`, `media-worker-m8`) against 5 `.json`
(`auth-sdk-m8`, `fa-auth-m8`, `imgtools_m8`, `prompt-engine-m8`,
`security-tests-m8`) — a plurality, not a tie. YAML also supports `#`
comments; JSON does not, and every existing YAML config uses that room to
record the rationale below inline, which a JSON config cannot do without an
external doc nobody would find. `astro-ui-m8`'s config (added under this same
step) is the most recent and most complete example of the wording to copy.

**Do not churn the twelve existing configs to match.** This decision governs
new files only; re-formatting a working `.json` config into `.yaml` is pure
churn with no behavior change, and `B10` was explicit that the residual split
is a follow-up, not part of the step itself.

## Decision 2 — `CHANGELOG.md` release-heading form: Keep a Changelog

**`## [x.y.z] - YYYY-MM-DD`**, the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
form already used by the majority of the fleet. Two repositories deviate and
are not touched by this decision: `astro-auth-m8` (bare `## x.y.z`, no date)
and `security-tests-m8` / `fastapi-m8` (em-dash variants). Rewriting a
repository's already-published changelog headings to match is a documentation
churn with no behavior change and is explicitly out of scope here — file it as
its own follow-up if the fleet decides the existing three are worth
correcting.

## The `MD024` override every `CHANGELOG.md`-bearing config carries

Every repository config in the fleet that has a `CHANGELOG.md` restricts
`MD024`/`no-duplicate-heading` to `siblings_only`, because Keep a Changelog's
format repeats the same subsection names (`### Added` / `### Changed` /
`### Fixed` …) once per release, which the rule's default setting reports as a
duplicate-heading error once per repetition. `siblings_only` flags a duplicate
only when it shares a parent heading, so the same subsection name recurring
across releases passes while a real duplicate inside one release still fails.
See any current `.markdownlint.yaml` (e.g. `astro-ui-m8`'s) for the canonical
comment text.

This override is scoped to `MD024` alone unless a repository's own
pre-existing, unrelated findings (`MD013`, `MD049`, …) were already
suppressed before that repository gained a config — restating an
already-suppressed rule is not this file's decision to make on a repository's
behalf, and adding one where none existed would be a scope-creeping,
unrequested behavior change. `B10`'s four new configs (`astro-prompt-m8`,
`astro-reparto-m8`, `fa-ui-m8`, `reparto-docente-m8`) therefore carry the
`MD024` override only, even where a repository's `CHANGELOG.md` has
pre-existing, unrelated findings — those are out of scope for `B10` and remain
open follow-ups, not regressions introduced by this file.
