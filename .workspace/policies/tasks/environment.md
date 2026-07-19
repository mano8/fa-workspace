# Environment task

Use this overlay only while creating, changing, loading, or validating an
environment or workspace tool profile.

## Application environment files

- Every service defines `.env.example`; all required keys are present and
  placeholder values are `changethis`.
- When an environment key changes, update the code, `.env.example`, and the
  README when its setup instructions change.
- Secret placement follows
  [`SEC-NO-TRACKED-SECRETS`](../../architecture.md#sec-no-tracked-secrets).

## Workspace tool profiles

- Select `.env.local` for a host and `.env.devcontainer` inside the development
  container. Real profiles stay ignored; only their safe `.example` templates
  are tracked.
- Detect `M8_RUNTIME` (`local` or `devcontainer`) and `M8_HOST_OS` (`windows`,
  `linux`, or `macos`) before selecting paths or commands. Do not assume a
  workspace path or environment manager exists on another host.
- Prefer the configured `M8_*` command over remembered paths. Repository
  `packageManager` metadata and `package-lock.json`, `pnpm-lock.yaml`,
  `yarn.lock`, or `bun.lock` remain authoritative; the profile is only the
  user's available/default tooling. Do not create or replace a lockfile merely
  to match the local default.
- Python uses `M8_PYTHON_ENV_KIND` and `M8_PYTHON`, with optional manager/name
  metadata. Invoke routine scripts through `M8_PYTHON`; when the kind is
  `none`, fail instead of silently choosing another interpreter.
- JavaScript uses `M8_JS_RUNTIME_KIND`/`M8_JS_RUNTIME`; packages use
  `M8_PACKAGE_MANAGER_KIND`/`M8_PACKAGE_MANAGER` and optional
  `M8_PACKAGE_EXECUTOR`; version control and container tooling use their
  corresponding configured kind/command pairs. Optional families may use
  `none` with an empty command.
- Additional tools use `M8_TOOL_<NAME>`. Loaders export and availability-check
  every configured entry.

From PowerShell, import or validate a profile with
`scripts/Import-WorkspaceEnv.ps1 -Profile <local|devcontainer>`; use
`-ValidateOnly` for validation and `-SkipAvailability` only when checking a
different runtime's structure. From Bash, source
`scripts/import-workspace-env.sh <local|devcontainer>` so exports remain in the
current shell. Normal loading performs availability checks and never prints
configured values.
