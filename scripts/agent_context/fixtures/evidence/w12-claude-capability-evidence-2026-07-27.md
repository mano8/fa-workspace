# Installed-Claude canonical-delivery capability evidence — 2026-07-27

**Step:** 12.1
**Scope:** the Claude rows of the installed-client capability matrix. The
required Codex devcontainer non-interactive row and its bound
[2026-07-19 artifact](capability-evidence-2026-07-19.md) are unchanged.

**Machine-readable freeze:**
[`w12-claude-capability-evidence-2026-07-27.json`](w12-claude-capability-evidence-2026-07-27.json)

**Probe source:**
[`probe_claude_capabilities.py`](../../probe_claude_capabilities.py), SHA-256
`331df219ddd91ee682e2575f0e56ec9fb2a252ba727a2b2e759b709b206c37b8`.

## Method

Every measured invocation points `ANTHROPIC_BASE_URL` at a loopback recorder the
probe starts itself and supplies a dummy `ANTHROPIC_API_KEY`, so the vendor API
is never contacted and no real credential leaves the machine. The recorder
stores request bodies only; headers are read by the HTTP machinery and never
written or logged. A captured body is the exact model input the client
constructed, so a fixture either appears in it byte-for-byte or it does not.
This proves client-side model-input construction, not vendor acceptance or model
retention. The probe works in its own temporary project outside the workspace,
reads and writes no workspace or child repository file, and purges that
project's client state when it exits.

## Decision

Claude canonical delivery is now supported by evidence, which is a change from
the 2026-07-19 and 2026-07-20 refreshes: the client is authenticated, project
hooks execute, two independent channels carry an exact payload, project memory
is delivered verbatim, and the launcher can own the session identity before
invocation.

The minimum viable Claude completion set is two rows, both devcontainer
non-interactive: `claude-hook-additional-context` for a model-visible total of
at most 10,000 bytes, and `claude-cli-append-system-prompt` as the full-content
channel up to the workspace policy hard limit. Both are `REQUIRED` and block Phase 12
closeout. The interactive rows are `OPTIONAL`: they round-tripped byte-for-byte
with the same boundaries, but interactive startup can block on trust and
one-time onboarding dialogs that a launcher cannot drive deterministically, so
they are available to complete rather than required to close.

Two boundaries decide channel selection. The hook channel delivers at most
**10,000 characters** of `additionalContext`; at 10,001 the client silently
substitutes a `<persisted-output>` preview plus a temporary-file pointer, which
the delivery contract never accepts as delivery. Because a UTF-8 byte count is
never below the character or UTF-16 unit count, the frozen limit is stated as
10,000 **bytes**, which stays inside that boundary under any counting basis.

```text
hook channel:      min(32768 policy, 10000 channel, 262144 allowance - 32768 margin) = 10000
full-content:      min(32768 policy, 65536 channel, 262144 allowance - 32768 margin) = 32768
```

That 10,000-byte figure is a **total**, not an envelope allowance, because the
measurement boundary adds the native bytes:

```text
model_visible_total = native_model_visible_bytes
                    + serialized_injected_envelope_bytes
                    + other_model_visible_bootstrap_bytes
```

Worked against the current `fa-auth-m8` case, the native Claude bootstrap is
3,037 bytes (`CLAUDE.md` 1,905, `fa-auth-m8/CLAUDE.md` 162,
`fa-auth-m8/REPOSITORY_CONTEXT.md` 970) and the resolved envelope is 7,160
bytes, for a model-visible total of 10,197 bytes. Only 6,963 bytes remain
inside the hook row, so **the current `fa-auth-m8` envelope overruns the hook
row by 197 bytes and canonical delivery selects the full-content row**, where
10,197 sits well inside 32,768. Driving the real resolver with these frozen
rows reproduces exactly that: the hook row fails closed with `E_BUDGET` and the
full-content row validates. Step 12.4 must therefore select a channel by
`model_visible_total`, never by envelope size alone.

The 262,144-byte allowance is itself probe-verified rather than assumed: the
stdin channel carried exactly that payload, and a 1,048,576-byte payload, into
the model input byte-for-byte. Reserving 32,768 bytes for the task and variable
client layers follows the Codex row's convention. These are workspace-capped
verified maxima, not claims about the physical maximum the client or model
accepts.

## Capability matrix

| Agent | Platform / mode | Channel | Status | Native inspection | Verified limit | Lifecycle and identity | Closeout |
|---|---|---|---|---|---|---|---|
| Claude Code 2.1.220 | Devcontainer, non-interactive | `claude-hook-additional-context` | `REQUIRED` | `claude-loopback-model-input-capture`; the probe project's 99-byte `CLAUDE.md` appeared in the model input with its exact bytes, trailing newline, and absolute path. | Exact at 8,192 and 10,000 characters; substituted at 10,001. Effective hard limit 10,000 bytes, which is a model-visible total and not an envelope allowance. | `--session-id` is honored, so launcher identity exists before invocation; resume preserves it; a fresh launch creates a new one. Compaction is unverified and must fail closed. | Blocks Phase 12 closeout. |
| Claude Code 2.1.220 | Devcontainer, non-interactive | `claude-cli-append-system-prompt` | `REQUIRED` | Same mechanism. | Exact at 32,768, 65,536, and 131,000 bytes; a single argument at or above the operating-system `MAX_ARG_STRLEN` (131,072 here) fails `execve` with `E2BIG` before the client runs. Effective hard limit 32,768 bytes. | Same identities; the envelope is supplied once per launch. | Blocks Phase 12 closeout. |
| Claude Code 2.1.220 | Devcontainer, non-interactive | `claude-cli-stdin-prompt` | `OPTIONAL` | Same mechanism. | Exact at 32,768 through 1,048,576 bytes; no client boundary observed. Effective hard limit 32,768 bytes. | Same identities. | Does not block. |
| Claude Code 2.1.220 | Devcontainer, interactive | `claude-hook-additional-context` | `OPTIONAL` | Same mechanism, driven over a pty. | Exact at 10,000 characters and substituted at 10,001, identical to the non-interactive row. | `--session-id` is honored interactively. `UserPromptSubmit` fires on every prompt, so exactly-once needs launcher generation state. | Does not block. |
| Claude Code 2.1.220 | Devcontainer, interactive | `claude-cli-append-system-prompt` | `OPTIONAL` | Same mechanism, driven over a pty. | Exact at 32,768 bytes. Effective hard limit 32,768 bytes. | One startup injection per launch. | Does not block. |
| Claude Code | Windows / POSIX outside this devcontainer | none | `UNSUPPORTED` | Unavailable to this probe. | None frozen. | Unverified. | Does not block. |

## Exact observations

- Client identity: command `/home/vscode/.local/bin/claude` resolving to
  `/home/vscode/.local/share/claude/versions/2.1.220`, SHA-256
  `674f61f20ff306f3100cf9200e4c36c4b70278b5bef2884549819b942a89c863`, version
  `2.1.220 (Claude Code)`, commit `4073f59596e2`, native install, `linux-x64`.
  A leftover npm-global installation remains at
  `/usr/local/share/nvm/versions/node/v24.16.0/bin/claude`; a launcher must pin
  the resolved executable rather than the name.
- **Automatic updates are enabled and the client updated from `2.1.215` to
  `2.1.220` during this work.** Both versions produced identical channel
  boundaries, which is useful cross-version corroboration but does not extend
  the freeze: the recorded SHA-256 is the row identity, and an update
  invalidates it.
- Environment: Ubuntu 26.04 LTS, `x86_64`, Linux
  `5.15.167.4-microsoft-standard-WSL2`, Node `v24.16.0`, devcontainer
  bootstrap lock SHA-256
  `4d6caca02cf82b993ac88ff5487f5ebe8196fb3468f39599c5a451abb6d42a6f`.
- Authentication: `loggedIn: true`, method `claude.ai`, first-party provider,
  `pro` subscription. Account identifiers are intentionally not recorded.
  Authentication is a precondition, never delivery evidence.
- Hook events present in the executable: `SessionStart`, `SessionEnd`,
  `UserPromptSubmit`, `PreCompact`, `PostCompact`, `PreToolUse`, `PostToolUse`,
  `Notification`, `SubagentStop`. The probe executed `SessionStart` and
  `UserPromptSubmit`.
- **`SessionStart` also injects `additionalContext` into the first model input,
  with the same 10,000-character boundary.** A launcher that registers both
  events would deliver two copies, so Step 12.4 must keep exactly one injection
  authority per launcher-controlled generation.
- Native-load inspection is `claude-loopback-model-input-capture`. There is no
  in-band mechanism: `claude -p -d api,hooks --debug-file` logs `[API REQUEST]`
  lines but never the model-input body, and model self-report is not evidence.
  The capture run replaces the API endpoint, so it is a separate, identically
  configured evidence run, exactly as the Codex row's `debug prompt-input` is
  out of band.
- Trust: in print mode the trust dialog is skipped and project
  `.claude/settings.json` hooks executed with **no trust record present**, and
  invalid settings files are silently ignored. In interactive mode an untrusted
  project blocks at the trust dialog before any model-input request is built.
  The launcher must therefore prove the trusted, hook-active state itself
  through `~/.claude.json` `projects[<absolute path>].hasTrustDialogAccepted`
  and validate its own settings file.
- Measurement: the frozen rows were driven through the live resolver and the
  shared validator. With the measured 3,037-byte native bootstrap, the hook row
  fails closed with `E_BUDGET` and the full-content row validates at a
  10,197-byte model-visible total against its 32,768-byte effective limit.
- Lifecycle: `--session-id 22222222-2222-4222-8222-222222222222` was honored on
  start, `-r` preserved it, `--fork-session` produced a new identity, and a
  fresh launch produced another. No compaction transition was captured.

## Rerun

```bash
python3 scripts/agent_context/probe_claude_capabilities.py \
  --output <observation.json> --interactive
```

The interactive portion needs the trust and one-time onboarding dialogs already
settled for the temporary project; without that it records the startup block
instead of a round trip. Two independent runs were executed for this freeze and
agreed exactly, apart from the per-run session identifiers and the debug-log
byte count. Their raw observations are kept locally under the ignored
`.workspace/status/fa-workspace/` tree, which carries no authority; this
tracked artifact is the authority.

Any Claude executable, version, or SHA-256 change — including an automatic
update — any settings, hook-registration, or trust change, any channel, limit,
or margin change, any native-load inspection change, and any devcontainer
bootstrap-lock or platform change invalidates these rows and requires a rerun
before a canonical claim.

## Boundary

This artifact freezes capability only. It activates no hook, writes no project
configuration, and promotes no Claude row to canonical delivery; Steps 12.2
through 12.6 own native-load classification, the adapter, the channel wiring,
the fixtures, and the reconciled status.

**Step 12.6 reconciliation (2026-07-29):** the root and workspace
documentation, the W2a contract mode table, and the 2026-07-27 `fa-auth-m8`
loaded-config snapshot now describe the two `REQUIRED` rows above as
canonical, gated on the per-scope trust check this artifact and Step 12.2
already required. No field in this file or its bound 12.2/12.4 evidence
artifacts changed; their tracked SHA-256 identities are exactly as recorded
above and remain pinned by `claude_delivery_adapter.py`.
