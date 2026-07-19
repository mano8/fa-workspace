# M8 FastAPI workspace

Shared workspace configuration for the M8 FastAPI microservices ecosystem. This repository is the workspace control plane: it provides the shared architecture, policies, environment profiles, developer tooling, and Dev Container—not the application services themselves.

[English](README.md) | [Español](README.es.md) | [Français](README.fr.md)

## Table of contents

- [Purpose and source of truth](#purpose-and-source-of-truth)
- [Workspace layout](#workspace-layout)
- [Configuration guide](#configuration-guide)
  - [Shared workspace configuration](#shared-workspace-configuration)
  - [Tool-specific configuration](#tool-specific-configuration)
  - [Environment profiles](#environment-profiles)
  - [Git safety hooks](#git-safety-hooks)
  - [Dev Container and Headroom](#dev-container-and-headroom)
- [First-time setup](#first-time-setup)
- [Everyday use](#everyday-use)
- [Troubleshooting](#troubleshooting)

## Purpose and source of truth

The complete presentation of the shared workspace, its ownership model, and its directory structure is in [`.workspace/README.md`](.workspace/README.md). Read it before changing workspace-level configuration.

`.workspace/` is the tool-neutral source of truth. It owns shared architecture, repository classification, policies, contracts, plans, analyses, and status. This root README is a navigation and onboarding guide; it deliberately links to that source instead of copying policies into another location.

## Workspace layout

```text
fa-workspace/                # This repository: the workspace root and control plane
├── .workspace/              # Canonical shared workspace context
├── .agents/ .claude/ .codex/ .devcontainer/ .githooks/ scripts/
├── auth-sdk-m8/ fastapi-m8/ imgtools_m8/ media-sdk-m8/ security-tests-m8/
├── fa-auth-m8/ media-service-m8/ media-worker-m8/ prompt-engine-m8/
├── reparto-docente-m8/
├── astro-auth-m8/ astro-media-m8/ astro-prompt-m8/ astro-reparto-m8/
└── astro-ui-m8/ fa-ui-m8/
```

The directories above are direct children of `fa-workspace`; they are not siblings of it. The Dev Container bind-mounts this repository root as `/workspace`. Its initial setup reads development requirements from the direct children `fa-auth-m8`, `imgtools_m8`, and `media-service-m8`.

Within `fa-workspace`:

| Path | Role |
| --- | --- |
| [`.workspace/`](.workspace/README.md) | Canonical shared architecture, policies, contracts, plans, analyses, and status. |
| [`AGENTS.md`](AGENTS.md) | Codex workspace entry point and operating rules. |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code workspace entry point and operating rules. |
| [`.codex/`](.codex/README.md) | Codex-specific configuration only. |
| [`.claude/`](.claude/README.md) | Claude Code-specific configuration only. |
| [`.agents/`](.agents/) | Shareable agent skills, including the Astro CI setup skill. |
| [`.devcontainer/`](.devcontainer/devcontainer.json) | Reproducible Docker Compose-based development environment. |
| [`scripts/`](scripts/) | Cross-platform environment-profile loaders. |
| [`.githooks/`](.githooks/) | Optional local commit and push safety hooks. |

## Configuration guide

### Shared workspace configuration

Use [`.workspace/README.md`](.workspace/README.md) as the entry point. The key files are:

- [`architecture.md`](.workspace/architecture.md) — layers and dependency direction;
- [`repo-types.json`](.workspace/repo-types.json) — v2 direct-child repository classification and its active selector;
- [`policy.index.json`](.workspace/policy.index.json) — the active v2 policy index and transitional compatibility bundles;
- [`context/`](.workspace/context/) — language, environment, Git, Docker, and Astro guidance; and
- [`contracts/`](.workspace/contracts/) — validation-only shared contracts.

When working in a repository, read its own `AGENTS.md` as well as the root workspace entry point. During the active transitional index mode, resolve its `migration.v1_bundle` through `repo-types.json` and load only that ordered compatibility bundle. The environment policy has priority over language policy, architecture, and validation contracts.

Plans, analyses, and status artifacts belong in `.workspace/`. Do not duplicate them under `.codex/` or `.claude/`.

### Tool-specific configuration

Codex uses [`AGENTS.md`](AGENTS.md) and [`.codex/README.md`](.codex/README.md); Claude Code uses [`CLAUDE.md`](CLAUDE.md) and [`.claude/README.md`](.claude/README.md). These locations may contain tool-specific workflows and local state, but they must not redefine shared workspace facts.

The Dev Container installs Codex CLI and the Claude Code feature. Sign in to either tool inside the container when you want to use it. Their container configuration is held in named Docker volumes, not copied from your host account directories.

### Environment profiles

Machine-specific paths and commands are local-only. Start from the safe templates and never commit the resulting files:

```bash
cp .env.local.example .env.local
cp .env.devcontainer.example .env.devcontainer
```

Inside the Dev Container or on Linux/macOS, load the profile in the current shell:

```bash
source scripts/import-workspace-env.sh devcontainer
source scripts/import-workspace-env.sh devcontainer --validate-only
```

Use `local` instead of `devcontainer` on a Linux or macOS host. On Windows PowerShell, allow the loader only in the current process, then dot-source it:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\scripts\Import-WorkspaceEnv.ps1 -Profile local
. .\scripts\Import-WorkspaceEnv.ps1 -Profile local -ValidateOnly
```

Profiles describe available tools and paths; repository lockfiles and metadata still select each project's package manager. Keep service credentials in the corresponding service repository, never in root workspace profiles.

### Git safety hooks

The supplied hooks reject commits and pushes that contain files below a `todo/` directory. Enable them once per clone:

```bash
git config core.hooksPath .githooks
```

They are a local safeguard, not a replacement for review. Check `git status` before committing and never push directly to `main`.

### Dev Container and Headroom

The active configuration is [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json) with [`.devcontainer/docker-compose.devcontainer.yml`](.devcontainer/docker-compose.devcontainer.yml). It supplies an Ubuntu workspace container with Node.js 24, Python 3.12, Docker access, recommended VS Code extensions, a shared Python virtual environment, Codex CLI, and Claude Code.

[Headroom](https://github.com/headroomlabs-ai/headroom) is an open-source MCP helper that compresses large, non-sensitive tool outputs before they reach an AI model. The Compose stack runs `headroom-proxy` only on a private Docker network at `http://headroom-proxy:8787`; it exposes no host port. Container startup registers it with Codex and, when available, Claude Code.

Use Headroom for logs, test output, JSON, stack traces, and long file excerpts. Do **not** send `.env` files, credentials, tokens, private keys, OAuth files, SSH keys, or production signing material. The configured proxy disables telemetry and subscription tracking.

> The `.devcontainer/.headroom/` files are reference material. The active setup uses the proxy/stdio configuration above.

## First-time setup

1. Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Install [Visual Studio Code](https://code.visualstudio.com/) and the **Dev Containers** extension.
3. Keep `fa-auth-m8`, `imgtools_m8`, and `media-service-m8` as direct children of this workspace root. The initial setup installs their configured development requirements.
4. Open `fa-workspace` in VS Code.
5. Open the Command Palette (`F1` or `Ctrl+Shift+P`) and select **Dev Containers: Reopen in Container**.
6. Wait for the first build. It installs system tools, development dependencies, Codex CLI, and Headroom.
7. Verify the environment in a new integrated terminal:

   ```bash
   python3 --version
   node --version
   docker --version
   headroom --help
   ```

`setup.sh` runs when the container is created. `configure-mcp.sh` runs whenever it starts. After changing any Dev Container or Compose file, select **Dev Containers: Rebuild and Reopen in Container**.

## Everyday use

- Use `.workspace/` as the canonical reference before making a shared architectural or policy decision.
- Use a repository's own `AGENTS.md` before changing that repository.
- Load the appropriate local or Dev Container environment profile instead of relying on machine-specific paths.
- Let your AI tool use `headroom_compress` for large, non-secret output; retrieve the original only when it is necessary.
- Keep plans, analyses, and status in `.workspace/`, and keep secrets out of Git.

To check the Headroom service or repair its MCP registration from inside the container:

```bash
docker compose -f .devcontainer/docker-compose.devcontainer.yml ps
docker logs --tail 200 headroom-proxy-server
bash .devcontainer/configure-mcp.sh
```

## Troubleshooting

| Problem | What to do |
| --- | --- |
| Docker is unavailable | Start Docker Desktop, then rebuild the Dev Container. |
| First setup fails while installing Python requirements | Check that `fa-auth-m8`, `imgtools_m8`, and `media-service-m8` exist beside `fa-workspace`, then rebuild. |
| Headroom proxy is unavailable | Check the Compose status and logs with the commands above, then restart or rebuild the Dev Container. |
| Headroom MCP tools are missing | Run `bash .devcontainer/configure-mcp.sh`, then reopen the Dev Container. |
| A VS Code extension is missing | Rebuild the Dev Container so VS Code reapplies the extensions listed in `devcontainer.json`. |
| A policy seems unclear | Start with [`.workspace/README.md`](.workspace/README.md), then read the matching context file selected by `repo-types.json` and `policy.index.json`. |
