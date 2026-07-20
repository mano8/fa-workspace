# Installed-client capability evidence — 2026-07-19

**Scope:** read-only capability refresh for the available devcontainer clients

**Machine-readable observation:**
`.workspace/status/fa-workspace/agent-configuration-token-efficiency-capability-probe-2026-07-19.json`

**Probe source:**
`.workspace/status/fa-workspace/probe-devcontainer-capabilities-2026-07-19.mjs`

## Decision

The minimum viable completion set is one row: Codex devcontainer
non-interactive mode. It is `REQUIRED`. Codex interactive mode remains
`LIMITED`, and both Claude modes remain `LIMITED`, so this evidence creates no
Claude or interactive implementation obligation.

The required row uses `codex debug prompt-input` as the exact native/model-input
inspection mechanism and the CLI `developer_instructions` configuration
override as its full-content channel. A deterministic backslash-dense,
32,768-byte JCS-shaped fixture round-tripped byte-for-byte, including the
command-line quoting expansion. A separate 65,536-byte exact prompt-input
fixture establishes a conservative client allowance; reserving 32,768 bytes
for the task and variable client layers yields this row's 32,768-byte effective
hard limit:

```text
min(32768 policy, 32768 channel, 65536 allowance - 32768 margin) = 32768
```

This is a workspace-capped verified maximum, not a claim about the physical
maximum accepted by Codex or the model.

Project-hook injection is not selected for this row and is not claimed as a
verified capability. The canonical wrapper is the pre-task gate immediately
before `codex exec`; lifecycle identity comes from the client's JSONL stream.
Future hook use requires its own capability refresh.

## Capability matrix

| Agent | Platform / mode | Status | Native inspection | Canonical channel and limit | Lifecycle and identity | Closeout |
|---|---|---|---|---|---|---|
| Codex 0.144.6 | Devcontainer, non-interactive | `REQUIRED` | `codex debug prompt-input`; isolated `AGENTS.md` content matched its 56 source bytes and SHA-256 exactly. Trusted project config was visible; the same config was absent when the project was marked untrusted. | `cli-config-developer-instructions`; exact 32,768-byte fixture; allowance 65,536 bytes; margin 32,768 bytes; effective hard limit 32,768 bytes. | Start emits `thread.started`; resume preserved `019f7996-c0ee-7cb3-9332-be868393affd`; a fresh invocation used `019f7996-f5e3-75e3-aeb3-7cc56b67c933`. Launcher identity exists before invocation; client identity exists before `turn.started`. Compaction is unsupported and must fail closed. | Blocks final acceptance. |
| Codex 0.144.6 | Devcontainer, interactive | `LIMITED` | The installed help/manual exposes interactive inspection and hooks, but no controlled interactive round trip or compact/clear transition was captured. | None frozen. | Unverified for canonical use. | Does not block this minimum viable set. |
| Claude Code 2.1.170 | Devcontainer, non-interactive | `LIMITED` | Client is installed but `claude auth status` reports `loggedIn: false`; no model-visible native inspection or full-content round trip was run. | None frozen. | CLI exposes session/resume flags, but no authenticated transition was captured. | No implementation obligation. |
| Claude Code 2.1.170 | Devcontainer, interactive | `LIMITED` | Same authentication limitation; no canonical evidence. | None frozen. | Unverified. | No implementation obligation. |
| Codex and Claude | Windows / POSIX outside this devcontainer | `UNSUPPORTED` | Unavailable to this probe; no behavior inferred. | None. | Unverified. | No implementation obligation. |

## Exact observations

- Codex identity: `/home/vscode/.npm-global/bin/codex`, SHA-256
  `134063e133f0b4244fa3b251acf973d4fe4b4aeeacbdc135211bf480f59f1477`,
  version `codex-cli 0.144.6`, authenticated with ChatGPT.
- Claude identity:
  `/usr/local/share/nvm/versions/node/v24.16.0/bin/claude`, SHA-256
  `849e007277a0442ab27570d3e3d6d43787507946590e8dd1947e5a39b7081f9e`,
  version `2.1.170 (Claude Code)`, not authenticated.
- Environment: Ubuntu 26.04 LTS, x86_64, Linux
  `5.15.167.4-microsoft-standard-WSL2`; devcontainer lock SHA-256
  `5d9d50410515b6a52755f0e7d717235e261418914956e1fb6fa29b29b1318020`.
- Native fixture: 56 bytes, SHA-256
  `4d25afa59ccbdb2148ac1ef3e93ab768ef53b03e8647ed69a6f5708302c49b7b`.
- Backslash-dense delivery fixture: 32,768 bytes, SHA-256
  `2c11bfd2b380f2996d9091b80c5c1d6c79a81176479c74e2113e894998013868`.
- Probe source SHA-256:
  `613754c1f57c8e75dc671968a958140d9147846a75581c44e5fc293cdcafadd6`.

The lifecycle calls returned these exact JSONL relationships:

```text
start  -> thread 019f7996-c0ee-7cb3-9332-be868393affd -> CAPABILITY_START_OK
resume -> thread 019f7996-c0ee-7cb3-9332-be868393affd -> CAPABILITY_RESUME_OK
clear  -> thread 019f7996-f5e3-75e3-aeb3-7cc56b67c933 -> CAPABILITY_CLEAR_NEW_SESSION_OK
```

For this non-interactive row, `clear` means discarding the prior receipt and
starting a fresh `codex exec` session. The client exposes no non-interactive
compact command; a canonical launcher must return `E_LIFECYCLE` rather than
infer preservation or duplicate injection.

## Rerun

Run the read-only exact-content, trust, native-source, and limit probe:

```bash
node .workspace/status/fa-workspace/probe-devcontainer-capabilities-2026-07-19.mjs
```

Then repeat the three minimal authenticated `codex exec --json` calls in one
temporary `CODEX_HOME` and Git repository: start, `codex exec resume` using the
reported thread ID, and a fresh start. Copy only `auth.json` into the owner-only
temporary profile, never print it, and remove that temporary directory after
the run. The required relationships are same ID on resume, a different ID on
fresh-start clear, and `thread.started` before `turn.started`.

Any Codex binary/version, devcontainer lock, project trust/configuration,
inspection mechanism, channel, lifecycle behavior, source hash, allowance, or
margin change invalidates this row and re-gates W2a.
