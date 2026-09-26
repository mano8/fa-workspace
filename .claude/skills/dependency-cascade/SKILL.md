---
name: dependency-cascade
description: Drive a release cascade that starts at auth-sdk-m8 or fastapi-m8 through fa-auth-m8, the consumer services, every compose stack, env templates and READMEs, the astro plugin compatibility matrices, and the workspace version matrix. Use when the user bumps or releases auth-sdk-m8 or fastapi-m8, asks to "cascade", "repin compose stacks", "propagate a version", or to update compat matrices after a platform release. Arguments are the root package and target version, e.g. `auth-sdk-m8 3.3.0`.
---

# Dependency cascade

The graph, the touchpoints per repository, the phase order and the rules are
owned by `.workspace/context/dependency-cascade.md`. Read it in full first; this
skill is only the procedure for walking it. Do not restate or fork its tables.
If the fleet disagrees with that file, stop and propose a fix to the file
before continuing.

Also read `.workspace/context/version-sources.md` (published state and the read
command per mechanism) and `.workspace/context/env.md` (env-file rules).

## Authority

Nothing in this skill, the cascade doc or a plan authorizes a change. Every
child repository is separately owned. Before the first write in **each**
repository, obtain from the user, for that repository:

1. the branch to use (never `main`; do not create or switch branches unless
   told to);
2. the delivery choice: edit only, commit, commit + push, or also a PR
   description;
3. whether a release is authorized, or whether you stop at the merged PR.

Authorization for one repository does not carry to the next. Ask per
repository at the point its phase starts, not all up front, unless the user
volunteers a standing answer for a named set.

Commits: no `Co-Authored-By` trailer and no tool/model reference. PR
descriptions: a fenced `markdown` block with no tool/model reference.

## Procedure

### 0. Plan

1. Parse the root package and target version from the arguments; ask if
   either is missing.
2. Load the workspace tool profile without printing values, then run the
   checker to get the work list:

   ```bash
   source scripts/import-workspace-env.sh <local|devcontainer>
   "$M8_PYTHON" scripts/cascade/check_cascade.py                        # current drift
   "$M8_PYTHON" scripts/cascade/check_cascade.py --set <package>=<version>  # planned bump
   ```

   Report pre-existing drift (the first run) separately from what the bump
   causes, and ask whether to fold it into the cascade.
3. Run the env diff between the root's published tag and the target ref
   (`WORKTREE` for the checkout):

   ```bash
   "$M8_PYTHON" scripts/cascade/check_cascade.py --env-diff <package> v<published> <to-ref>
   ```

   For an `auth-sdk-m8` cascade, run it for `fastapi-m8` too once Phase 2 has
   a candidate ref.

   A non-empty diff activates Phase 4 inside every later phase.
4. For each repository in the graph, read its version with the documented
   command and its published state from `version-sources.md`, then decide
   *ride* or *new version* and the bump level using the doc's rules.
5. Write the plan as a ledger at
   `.workspace/plans/stack/todo/<YYYY-MM-DD>-<package>-<version>-cascade.md`
   (gitignored): one row per repository with phase, decision, branch,
   authorization received, PR, published evidence, status. Show it to the
   user and wait for approval. The ledger is how a cascade that waits days on
   CI and registries resumes in a later session; update it after every gate.

### 1–7. Phases

Walk the doc's phases in order. For each repository in a phase:

1. Ask for that repository's authorization (see *Authority*).
2. Read the repository's own `CLAUDE.md` / `REPOSITORY_CONTEXT.md`; its rules
   apply inside it (for example `fa-auth-m8`'s three-file version alignment).
3. Apply exactly the touchpoints the doc lists for that phase, plus Phase 4's
   env steps for the keys the env diff reported.
4. Run the repository's own quality gate (the `testing` and `commit` task
   policies name the order); do not commit on a failing required check.
5. Deliver only as far as authorized. Record the result in the ledger.

Within a phase, independent repositories may be done one after another in
this session. Do not delegate mutating edits to subagents: each repository
needs the user's answer at its own gate. A read-only search agent is fine for
locating touchpoints the checker cannot see.

### Gates

At each phase's gate, **stop**. Tell the user what must happen outside the
session (merge, tag, publish workflow) and what evidence you will read back.
Resume only when the user says the release is out, then verify it yourself
(registry read-back, pulled image `__version__`, npm `dist-tags.latest`) before
pinning it anywhere. Never pin an unpublished version.

### Env sync (Phase 4)

For every key in the env diff and every inheritor in the doc's inheritance
table: code, repository `.env.example`, every compose-stack env template,
compose `README.md`, repository `README.md`. Placeholders are `changethis`.
Never open a real env file (`.env`, `*.env`, `.env.local`); list the
operator-local files that need the key instead.

### Close

1. Phase 7: update `version-sources.md` from read-back evidence only.
2. Pull each touched repository's `main` (ask first if a checkout has local
   changes), then re-run the checker with no `--set`: every working tree now
   carries its new version. The cascade is closed when it reports nothing;
   otherwise list what remains and why. Then check by hand the free-text
   version statements the checker cannot see (the doc names them).
3. List operator-local follow-ups (e.g. `rpi_server/` repins, real env keys)
   that no commit delivers.
