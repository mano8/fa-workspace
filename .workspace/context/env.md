# Environment Policy

## Rules

* Every service MUST define `.env.example`.
* All required keys MUST exist there.
* Placeholder values MUST be `changethis`.
* Workspace invariant:
  [`SEC-NO-TRACKED-SECRETS`](../architecture.md#sec-no-tracked-secrets).

## Runtime Rule

* System MUST fail fast if env validation is incomplete.

## Sync Rule

If env changes:

1. update code
2. update `.env.example`
3. update README if needed

## Workspace Tool Profiles

The workspace root uses two tool-only environment profiles:

* `.env.local` for Windows, Linux, or macOS host-local paths.
* `.env.devcontainer` for paths and commands inside the dev container.

Profile tracking follows
[`CFG-LOCAL-PROFILES-UNTRACKED`](../architecture.md#cfg-local-profiles-untracked).
The safe templates are `.env.local.example` and `.env.devcontainer.example`.

These profiles may contain workspace paths and tool locations only. Application
and service secret placement and credential handling follow
[`SEC-NO-TRACKED-SECRETS`](../architecture.md#sec-no-tracked-secrets).

`M8_RUNTIME` identifies `local` versus `devcontainer`. `M8_HOST_OS` identifies
the operating system as `windows`, `linux`, or `macos`. Tool values may be
absolute paths or command names available on `PATH`.

Each tool family uses a kind plus a resolved command:

* Python: `M8_PYTHON_ENV_KIND` and `M8_PYTHON`; optional manager/name metadata.
* JavaScript: `M8_JS_RUNTIME_KIND` and `M8_JS_RUNTIME`.
* Packages: `M8_PACKAGE_MANAGER_KIND` and `M8_PACKAGE_MANAGER`; optional
  `M8_PACKAGE_EXECUTOR`.
* Version control: `M8_VCS_KIND` and `M8_VCS`.
* Containers: `M8_CONTAINER_ENGINE_KIND` / `M8_CONTAINER_ENGINE` and
  `M8_COMPOSE_KIND` / `M8_COMPOSE`.

Supported kinds cover common tools and `other`; optional tool families also
support `none` with an empty command. Repository metadata and lockfiles remain
authoritative. For example, `packageManager`, `package-lock.json`,
`pnpm-lock.yaml`, `yarn.lock`, or `bun.lock` determines the package manager for
that repo; the workspace profile is only the user's available/default tooling.

Additional tools may be declared as `M8_TOOL_<NAME>=<command-or-path>`. Both
loaders export and availability-check every configured `M8_TOOL_*` entry, so
new tools do not require changes to the core profile schema.

Load or validate the active profile from PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\scripts\Import-WorkspaceEnv.ps1 -Profile local
. .\scripts\Import-WorkspaceEnv.ps1 -Profile local -ValidateOnly
. .\scripts\Import-WorkspaceEnv.ps1 -Profile devcontainer -ValidateOnly -SkipAvailability
```

Use `-Profile devcontainer` inside a PowerShell-enabled dev container. Both
loaders default to `devcontainer` only when a container runtime marker is
detected; otherwise they default to `local` on Windows, Linux, and macOS. They
validate required paths and commands without printing configured values. Use
`-SkipAvailability` only to validate a different runtime's profile structure
from the current host; normal loading must perform availability checks.

From Bash inside the dev container, source the Bash loader so exported values
remain in the current shell:

```bash
source scripts/import-workspace-env.sh devcontainer
source scripts/import-workspace-env.sh devcontainer --validate-only
```

For a Linux or macOS host, use the same Bash loader with the local profile:

```bash
source scripts/import-workspace-env.sh local
```

Codex and Claude must prefer the configured `M8_*` values over remembered or
hardcoded machine paths. Profile output follows
[`SEC-NO-SECRET-DISCLOSURE`](../architecture.md#sec-no-secret-disclosure).

## AI Runtime

* Codex and Claude Code may run from Windows, Linux, macOS, or inside the dev
  container.
* Detect the active environment before selecting paths or commands; do not
  assume `/workspace` paths exist on the Windows host.

## Host Shell

* Use the resolved commands from the active profile. On Windows these may point
  to `.cmd` wrappers; on Linux or macOS they may be command names or executable
  paths. Do not replace them with remembered platform-specific commands.

### Headroom MCP

Headroom is available through MCP.
MCP server command:
```bash
$HOME/.venvs/headroom/bin/headroom mcp serve --proxy-url http://headroom-proxy:8787
```
Expected MCP tools:
```text
headroom_compress
headroom_retrieve
headroom_stats
```
Usage rules:
* Use `headroom_compress` for large non-secret outputs: logs, test output, grep results, JSON, stack traces, long file excerpts, and build output.
* Use `headroom_retrieve` only when exact original details are needed after compression.
* Use `headroom_stats` when token savings or compression state matters.
* External processing follows
  [`SEC-NO-SECRET-DISCLOSURE`](../architecture.md#sec-no-secret-disclosure).
* Do not use Headroom as `ANTHROPIC_BASE_URL` or `OPENAI_BASE_URL` unless explicitly requested.
* Do not use `headroom wrap claude` or `headroom wrap codex` unless explicitly requested.
Verification:

* In Codex, use the MCP/tool listing available in the active environment.
* In Claude Code, use `claude mcp list` or `/mcp`.


