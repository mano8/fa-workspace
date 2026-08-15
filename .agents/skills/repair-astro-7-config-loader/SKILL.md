---
name: repair-astro-7-config-loader
description: Diagnose and repair Astro 7.1.6 with Vite 8 when Astro cannot load astro.config.mjs and reports "require is not defined" from source-map-js or ModuleRunner.directRequest. Use for Windows/local-versus-CI runtime mismatches, Node minor-version parity, clean-install verification, or Astro sync/build failures that may be mistaken for dependency or config regressions.
---

# Repair Astro 7 Config Loader

Resolve the config-loader failure by proving the runtime boundary first. Keep
dependency and application changes evidence-driven.

## Establish authority and repository state

1. Read the workspace and repository instructions.
2. Confirm the target repository, current branch, dirty files, package root,
   lockfile, and the user's commit/push authorization before editing.
3. Inspect `package.json`, `.npmrc`, `astro.config.mjs`, and the CI Node matrix.
4. Record `node --version`, `npm.cmd --version`, and:

   ```powershell
   npm.cmd ls astro vite source-map-js --depth=3
   ```

Preserve unrelated work and the current dependency ranges unless a clean,
CI-equivalent reproduction proves they are responsible.

## Recognize the runtime-boundary signature

Treat this trace as a runtime/config-runner boundary until proven otherwise:

```text
[astro] Unable to load your Astro config
require is not defined
.../node_modules/source-map-js/lib/source-map-generator.js
... ModuleRunner.directRequest .../vite/dist/node/module-runner.js
```

On this workspace's validated Astro 7.1.6 baseline, run Astro through exact
Node `22.18.0`. A different local Node minor, invoking the cached `node.exe`
directly, or running inside the restricted Windows sandbox may reproduce the
trace even when the repository and CI configuration are sound.

Do not respond to this signature by:

- editing `node_modules/source-map-js/package.json`;
- replacing the `astro/config` `defineConfig` import with a local function;
- downgrading or pinning Astro or Vite without a clean external reproduction;
- changing application code merely to make a sandbox-only failure disappear.

## Prove the exact CI runtime

From the Astro package directory, use `npm.cmd` and a repository-local cache:

```powershell
$env:npm_config_cache='.npm-cache'
npx.cmd --yes node@22.18.0 node_modules/astro/bin/astro.mjs sync
npx.cmd --yes node@22.18.0 node_modules/astro/bin/astro.mjs build
```

If the restricted sandbox reports the signature, rerun the identical commands
outside the sandbox with approval. Do not substitute the local Node binary or
interpret the sandbox result as evidence for a source change.

If dependencies need reinstalling, preserve the lockfile and use the repository's
declared install mode. For this workspace baseline:

```powershell
$env:npm_config_cache='.npm-cache'
npx.cmd --yes npm@10.9.2 ci --prefer-offline
```

Honor `.npmrc` compatibility settings such as `legacy-peer-deps=true`; do not
add flags inconsistently across local, CI, and release installs.

## Diagnose a failure that persists outside the sandbox

Only after the exact Node 22.18 command fails outside the sandbox:

1. Confirm the clean install matches `package-lock.json` and contains no `file:`
   or `link:` workspace residue.
2. Inspect imports and top-level side effects in `astro.config.mjs`.
3. Use `npm.cmd explain source-map-js` and the dependency tree to identify its
   actual importer.
4. Compare the CI workflow's Node and npm versions with the commands above.
5. Reproduce after a clean install before changing versions or configuration.

Make the smallest durable change supported by that reproduction, then rerun the
exact command. Never keep exploratory mutations in `node_modules`.

## Separate subsequent application failures

Once Astro loads the config, treat the next error as a new diagnostic. For
example, a Starlight error such as a sidebar slug that no longer exists is a real
content/config mismatch, not the config-loader regression. Remove only stale
navigation references and preserve existing generated or plugin-owned routes.

## Run the complete quality gates

Use exact Node 22.18 for Node-executed gates:

```powershell
$env:npm_config_cache='.npm-cache'
npx.cmd --yes node@22.18.0 node_modules/eslint/bin/eslint.js src
npx.cmd --yes node@22.18.0 node_modules/astro/bin/astro.mjs sync
npx.cmd --yes node@22.18.0 node_modules/typescript/bin/tsc -p tsconfig.json --noEmit
npx.cmd --yes node@22.18.0 node_modules/vitest/vitest.mjs run --coverage --passWithNoTests
npx.cmd --yes node@22.18.0 node_modules/astro/bin/astro.mjs build
```

When present, also run auth-only/plugin-matrix verifiers, `npm pack --dry-run`,
the repository audit command, and non-Node policy tests. Confirm LCOV exists and
is non-empty when CI uploads coverage.

After push, follow the triggered CI run through completion. Report separately:

- the runtime under which the config loader passed;
- any real application error fixed after config loading;
- local gate results and remote CI status;
- any check that could not be verified.
