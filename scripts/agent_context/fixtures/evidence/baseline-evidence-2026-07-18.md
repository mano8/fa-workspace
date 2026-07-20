# Phase 0.6 capability and baseline reconciliation

**Captured:** 2026-07-18
**Boundary:** `W0` read-only evidence refresh
**Workspace revision:** `init_setup` at `df0e4e192f35a35386bd2ff079b0e665e133e138`

## Result

Phase 0.6 is complete. Historical results have an explicit disposition, current
mutable measurements have been reproduced, and every observable
agent/platform/mode row has a disposition. Documentation establishes vocabulary
only; it is not treated as evidence of transport, hooks, trust, lifecycle,
native-load inspection, or model-visible byte limits.

No canonical delivery mode is demonstrated. The minimum viable `REQUIRED` set
is empty. Canonical Codex or Claude delivery and W2a contract selection remain
blocked until a controlled environment can demonstrate the necessary behavior.
`LIMITED` and `UNSUPPORTED` rows are not implementation obligations.

## Historical evidence reconciliation

| Previous result | Status | Evidence and consequence |
|---|---|---|
| 0.1 root hashes, mutable measurements, and tool probes | `SUPERSEDED` | The 58-record historical baseline is valid and all listed paths still exist, but its hash/byte measurements are a snapshot and have drifted. The reproducible current baseline below is authoritative for later measurements. |
| 0.2 direct-child inventory | `REPRODUCED` | Exactly 16 direct child Git roots are present. No child CI, branch, remote, or dirty state was used for this refresh. |
| 0.3 repository classification | `REPRODUCED` | The authoritative registry has 18 flat keys: 16 present repositories plus the stale `docker_compose` and `traefik` infrastructure aliases. The historical 21-entry classification remains distinct evidence; `fa-ui-m8/app` is not a registry key. |
| 0.4 configuration vocabulary | `SUPERSEDED` | Current vendor vocabulary is retained as background only; it does not establish installed-client capability. |
| 0.5 raw-byte budgets and fixtures | `SUPERSEDED` | Its repaired source provenance remains valid, but the old mutable baselines no longer reproduce. The historical 10,526/14,563-byte gates are not reusable; the current fixture gates below preserve the >=35% objective. |

The recorded 24 child instruction files containing `/.workspace` remain a
historical/current-plan fact. This read-only boundary does not edit child
instructions.

## Reproducible current v1 byte baseline

Measurement is exact source bytes, with `ceil(bytes / 4)` reported only as
supplementary telemetry. Every fixture de-duplicates workspace-relative paths
and contains root `AGENTS.md`, architecture, registry, policy index, the
applicable v1 policy files, and its named child `AGENTS.md`.

| Fixture | Raw bytes | Estimated tokens |
|---|---:|---:|
| `auth-sdk-m8:implementation` | 17,484 | 4,371 |
| `fa-auth-m8:implementation` | 17,293 | 4,324 |
| `media-worker-m8:implementation` | 17,863 | 4,466 |
| `astro-auth-m8:implementation` | 24,417 | 6,105 |
| `fa-ui-m8:implementation` | 13,669 | 3,418 |
| `auth-sdk-m8+fa-auth-m8:cross-repository` | 17,911 | 4,478 |

The replacement absolute gates are 11,364 bytes for
`auth-sdk-m8:implementation` and 15,871 bytes for
`astro-auth-m8:implementation` (`floor(current baseline * 0.65)`). Using
`floor` ensures the maximum remains at or below 65% of its baseline and thus
meets the >=35% reduction objective. These are evidence-only gates until the
later clean-checkout reproducibility requirement is met.

Current root measurement inputs are:

| Path | Bytes | SHA-256 |
|---|---:|---|
| `AGENTS.md` | 1,470 | `f0348448a98ad2b4becf4dbcc9ef3a7d9a8660215d8f79c86c08988eb7e8ee59` |
| `CLAUDE.md` | 1,472 | `6b25eac3c7a3937fc87b44be3214bd73b7431cfd4e1b53e56866377a53f57b3a` |
| `.workspace/architecture.md` | 1,737 | `773187df376ce39a9509dd94570fdc7eb9827bfbbe0cad068feb758594fd3888` |
| `.workspace/repo-types.json` | 560 | `9d21d8e4f7a661175d1f810b4eb4d50829dc689610d8953a2396fab0f9e3e787` |
| `.workspace/policy.index.json` | 780 | `3647009132a489c6ffcba9f593c852e399a7bdfb9db39701bf5a13681344ee78` |

## Installed-client capability matrix

`REQUIRED` is reserved for a demonstrated canonical mode. No row qualifies.
The inspection mechanism, delivery channel, maximum exact bytes, lifecycle
transitions, and launcher/client-session identities are unavailable unless an
observation below proves them.

| Agent | Platform / mode | Status | Inspection / channel / maximum exact bytes | Lifecycle and identities | Closeout effect |
|---|---|---|---|---|---|
| Codex | Windows, interactive | `LIMITED` | `codex.exe` is installed at the Windows App path, but `--version` and `--help` both fail with access denied in this managed shell. Inspection, channel, and maximum are unavailable. | Start/resume/clear/compact and launcher/client identities are unavailable. | Blocks canonical Codex delivery claims and Codex W2a selection. |
| Codex | Windows, non-interactive | `LIMITED` | Same access-denied result. No full-content stdin/prompt transport or byte threshold was observed. | Unavailable. | Blocks canonical Codex delivery claims and Codex W2a selection. |
| Claude | Windows, interactive and non-interactive | `UNSUPPORTED` | `claude` is not on `PATH`; inspection, channel, and maximum are unavailable. | Unavailable. | No Claude implementation obligation; a later installed-client probe is required before canonical Claude work. |
| Codex and Claude | POSIX/WSL | `UNSUPPORTED` | WSL default version is 2, but no distribution is installed; no POSIX client can be probed. | Unavailable. | No POSIX implementation obligation. |
| Codex and Claude | Devcontainer | `LIMITED` | Docker client 29.6.1 is present, but its daemon pipe is inaccessible and `devcontainer` is absent. No container/client probe ran. | Unavailable. | Blocks devcontainer canonical claims; no behavior is inferred. |

## Raw observations and rerun commands

```powershell
Get-Command codex, claude, wsl, docker, devcontainer
codex --version
codex --help
claude --version
wsl --status
wsl --list --verbose
docker version --format '{{json .Client}}'
docker version --format '{{json .Server}}'
devcontainer --version
```

- Codex resolves to `C:\Program Files\WindowsApps\OpenAI.Codex_26.707.12708.0_x64__2p2nqsd0c76g0\app\resources\codex.exe`; both PowerShell CLI probes report access denied. Git Bash also fails: the extensionless shim reports an executable-format error and explicit `codex.exe` reports permission denied.
- Claude Code and `devcontainer` are absent from `PATH`.
- WSL reports default version 2 and no installed distribution.
- Docker reports client 29.6.1, but configuration and daemon-pipe access are denied.
- `.codex/config.toml` is absent. Local `.claude/settings.json` and `.claude/settings.local.json` remain ignored, so neither is project-capability evidence.
- The official Codex manual was refreshed on 2026-07-18. Its documented project configuration and hook behavior is not treated as proof that this blocked CLI accepted or delivered any configuration.

## Required follow-up before W2a

Repeat these probes from a controlled profile where the Codex CLI can execute;
install and probe Claude only if Claude delivery is proposed. For each proposed
mode, capture a round-trip full-content fixture, exact model-visible limit,
trusted/untrusted behavior, active-native-source inspection, and
start/resume/clear/compact receipt and identity transitions. Any changed
client, configuration, trust state, platform, inspection mechanism, or channel
makes this evidence stale.
