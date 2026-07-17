---
name: astro-github-ci-setup
description: Set up or repair a GitHub Actions CI.yaml quality workflow for an Astro or TypeScript package, including repository-adapted linting, tests, LCOV coverage, Codecov, Codacy, package checks, and audit gates. Use when adding CI, making CI parity changes, or diagnosing CI coverage uploads in an Astro package. Require the user to state the branch and whether to commit and/or push before modifying files.
---

# Astro GitHub CI Setup

## Delivery authority

Before any write, require the user to provide all of:

1. Target repository.
2. Exact branch to use.
3. Delivery choice: no commit/push, commit only, or commit and push.

Do not infer any of these from the current branch. Inspect read-only context first
if needed, then ask for the missing choice. Verify the current branch matches the
named branch; do not create or switch branches unless the user explicitly asks.

## Discover the repository

1. Read workspace and repository `AGENTS.md` instructions, then the matched
   TypeScript/Astro policies.
2. Inspect `git status`, current branch, `package.json`, lockfile, existing
   `.github/workflows`, test configuration, ESLint configuration, and coverage
   output after a local test run.
3. Preserve existing publish workflows and repository-specific checks. Consolidate
   duplicate CI workflows only when the user asks for that change.
4. Reuse the repository's package manager and lockfile. Do not copy a workflow
   verbatim from another package.

## Build the adapted quality workflow

Create or update `.github/workflows/CI.yaml` using the repository's existing
action pinning and Node support policy. Keep least-privilege permissions and
trigger on `main` push, `main` pull requests, and manual dispatch unless the
repository already defines different required triggers.

Include only applicable jobs and commands:

- quality: clean install, typecheck, lint, build, and `npm pack --dry-run`;
- test: the supported Node matrix, tests with coverage, a coverage artifact, and
  Codecov and Codacy uploads from one canonical matrix entry;
- security: dependency audit at the project's intended severity threshold.

Start with `npm ci`. Use `npm ci --legacy-peer-deps` only when a clean install
proves a peer-resolution conflict and the lockfile was generated with that mode;
apply it consistently to every CI and publish install step.

For the current Astro baseline, use these dev-dependency ranges:

- `@eslint/js`: `^9.39.5`;
- `eslint`: `^9.39.5`;
- `eslint-plugin-react`: `^7.37.5`;
- `eslint-plugin-react-hooks`: `^5.1.0`;
- `eslint-plugin-security`: `^4.0.1`.

Preserve the repository's established ESLint configuration format. In packages
that already use a root `.eslintrc.json`, retain that format; do not migrate to
flat config merely because ESLint 9 is in use. Scope linting to source files,
ignore generated output and fixture consumers, preserve existing conventions,
and keep repo-specific exceptions narrow and documented.

For the `.eslintrc.json` setup, verify all of the following together:

- `package.json` exposes `lint`, declares the current ESLint baseline above,
  and its lockfile contains the parser and every enabled TypeScript, React,
  hooks, or security plugin;
- `root`, `env`, `parser`, `plugins`, `extends`, `settings`, `rules`, and
  `ignorePatterns` are valid JSON and match the repository's language surface;
- browser and Node environments are enabled only where needed, while typed
  parser project rules are limited to files included by the TypeScript project;
- `ignorePatterns` covers generated `dist`, coverage, build caches, registry
  output, and fixture consumers without masking package source;
- no conflicting ESLint configuration file remains;
- `npm run lint` passes after a clean install.

Always add `.codacy.yml`. Enable the ESLint and Markdownlint engines, then
exclude generated output, coverage, dependencies, and non-product agent
documents as applicable; do not hide source or tests merely to improve a score.

Add `CODECOV_TOKEN` and `CODACY_PROJECT_TOKEN` to workflow environment only as
secret references, never as literals. Always include Codecov and Codacy coverage
actions after the test step. Guard each upload on its token being non-empty and
skip Dependabot where the repository policy requires it. Verify Codacy's
`coverage-reports` input matches the generated report path exactly.

## Coverage uploads

Generate the exact report that uploaders consume. For Vitest V8 coverage, retain
the useful existing reporters and add `lcov`, which creates `coverage/lcov.info`.
Confirm the file exists locally and contains source paths relative to the package
root before wiring upload steps.

Use `coverage/lcov.info` for both Codecov and Codacy. Keep coverage reporting
in one matrix entry to avoid duplicate uploads. Do not add unsupported Codacy
action inputs; when an uploader reports zero files, fix report generation or its
relative path first.

## Validate before delivery

Run the same install mode and relevant commands as CI, then verify:

1. clean install succeeds;
2. lint, typecheck, tests, build, package dry-run, and audit pass where present;
3. `coverage/lcov.info` exists after tests and is non-empty;
4. workflow command paths, cache lockfile paths, and package scripts agree;
5. Codecov and Codacy upload steps each use `coverage/lcov.info`, their secret
   guard, and only the canonical coverage matrix entry;
6. ESLint imports, package dependencies, lockfile entries, and `.codacy.yml`
   engine names agree;
7. `git diff --check` passes.

Treat runtime dependencies required by the test harness as direct dev
dependencies. For example, add `@testing-library/dom` explicitly when tests
use `@testing-library/react` and its peer is otherwise absent.

Report unavailable external checks precisely; do not claim that Codecov or Codacy
accepted data without a completed remote run.

## Deliver exactly as authorized

- **No commit/push:** leave the validated changes local and report the diff.
- **Commit only:** commit the requested scope on the specified branch; do not push.
- **Commit and push:** commit the requested scope, push that exact branch, and
  verify its upstream status.

If a push fails because of local credentials or environment state, keep the
validated commit intact and report the exact blocker. Do not claim it was pushed.
