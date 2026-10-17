# Installed-Claude canonical-delivery capability evidence — 2026-10-17

**Step:** 12.1 (dated refresh)
**Scope:** the Claude rows of the installed-client capability matrix. The
required Codex devcontainer non-interactive row and its bound
[2026-07-19 artifact](capability-evidence-2026-07-19.md) are unchanged.

**Machine-readable freeze:**
[`w12-claude-capability-evidence-2026-10-17.json`](w12-claude-capability-evidence-2026-10-17.json)

**Refreshes:** [the 2026-07-27 freeze](w12-claude-capability-evidence-2026-07-27.md),
kept unchanged as history.

**Probe source:**
[`probe_claude_capabilities.py`](../../probe_claude_capabilities.py), SHA-256
`496c904abd01256e1edd932985bba60318b68bbca070aa5d8025db88f2738bb6`.

## Why this refresh

The 2026-07-27 rows were invalidated by four independent changes, each named
in that artifact's invalidation list:

- the installed client auto-updated from `2.1.220` to `2.1.302`, part-way
  through the first refresh attempt;
- the user settings layer changed after the freeze;
- root `CLAUDE.md` was slimmed to 1,326 bytes and now imports
  `.workspace/context/agent-conventions.md`;
- the registry grew from 16 to 19 repositories (`ai-gateway-m8`,
  `ai-sdk-m8`, `doctools-m8`).

## Result

**Every capability row and its identity reproduced exactly.** On `2.1.302`,
both independent runs measured the same boundaries as the 2026-07-27 freeze:

```text
hook channel:      min(32768 policy, 10000 channel, 262144 allowance - 32768 margin) = 10000
full-content:      min(32768 policy, 65536 channel, 262144 allowance - 32768 margin) = 32768
```

- Hook `additionalContext`, both `UserPromptSubmit` and `SessionStart`: exact
  at 10,000 characters, substituted at 10,001.
- `--append-system-prompt`: exact at 32,768, 65,536 and 131,000 bytes.
- stdin prompt: exact from 32,768 through 1,048,576 bytes.
- Lifecycle: `--session-id` honored, resume preserves it, fork and a fresh
  launch create new identities, and no compaction transition was observed.
- Native discovery: the probe project's 99-byte `CLAUDE.md` appears
  byte-exact in the model input.
- Interactive: the hook is exact at 10,000 characters and substituted at
  10,001, and `--append-system-prompt` is exact at 32,768 bytes.

The six `capability_evidence_id` values are therefore unchanged, and the two
`REQUIRED` rows still block closeout.

## What changed in the client, and in the probe

Two `2.1.302` behaviours broke the probe's interactive pty script. Neither
touches a measured channel. The probe was corrected in place:

1. **The folder-trust dialog now defaults to `No, exit`.** The old script's
   first bare Enter exited before any model input existed. The script now
   moves to `Yes, I trust this folder` before it confirms.
2. **A session identity that is already in use is refused** (`Session ID … is
   already in use`). The three interactive launches had shared one identity,
   so only the first started. Each now requests its own identity.

A third change affects Step 12.2, not this probe. A clean `2.1.302` CLI launch
frames project memory as a block that opens with "Codebase and user
instructions are shown below." and no longer carries the `# claudeMd`
heading. The per-file labels and the exact bytes are unchanged.

## Measurement on this tree

The worked example is re-measured for the `fa-auth-m8` launch scope. Its
native Claude bootstrap is 3,702 bytes: `CLAUDE.md` is 1,326,
`fa-auth-m8/CLAUDE.md` 161, and `fa-auth-m8/REPOSITORY_CONTEXT.md` 2,215.
The resolved envelope is 7,160 bytes, so the model-visible total is 10,862
bytes. That overruns the hook row by 862 bytes, so canonical `fa-auth-m8`
delivery selects the full-content row.

Root `CLAUDE.md`'s import is external to a child launch scope. The client
therefore skips it there until the human approves that project's external
`CLAUDE.md` imports, and no approval is recorded for `/workspace/fa-auth-m8`.

## Exact observations

- Client: command `/home/vscode/.local/bin/claude` resolving to
  `/home/vscode/.local/share/claude/versions/2.1.302`, SHA-256
  `60d7eb7f12fbb28a52533fe8be5884097403562aa02dc73991a021c7067e29a5`,
  version `2.1.302 (Claude Code)`, commit `2ef144e6f98c`, native install,
  `linux-x64`. The leftover npm-global installation at
  `/usr/local/share/nvm/versions/node/v24.16.0/bin/claude` remains; a
  launcher must pin the resolved executable.
- **Automatic updates are still enabled.** Both freeze runs ran with
  `DISABLE_AUTOUPDATER=1` in the probe environment and outside any parent
  Claude session environment (every inherited `CLAUDE*`, `ANTHROPIC_*`,
  `MCP_*` and `OTEL_*` variable removed). An update after this freeze
  invalidates it again.
- Environment: Ubuntu 26.04 LTS, `x86_64`, Linux
  `5.15.167.4-microsoft-standard-WSL2`, Node `v24.16.0`, devcontainer
  bootstrap lock SHA-256
  `4d6caca02cf82b993ac88ff5487f5ebe8196fb3468f39599c5a451abb6d42a6f`
  (unchanged).
- Authentication: `loggedIn: true`, method `claude.ai`, first-party provider,
  `pro` subscription. Account identifiers are not recorded. Authentication is
  a precondition, never delivery evidence.
- `SessionStart` still injects `additionalContext` with the same boundary, so
  a launcher keeps exactly one injection authority per generation.

## Rerun

```bash
python3 scripts/agent_context/probe_claude_capabilities.py \
  --output <observation.json> --interactive
```

Run it from a shell that is not itself inside a Claude session, with
`DISABLE_AUTOUPDATER=1`. Two independent runs were executed for this freeze.
They agreed exactly apart from the per-run fork and fresh session
identifiers.

Any Claude executable, version, or SHA-256 change — including an automatic
update — any settings, hook-registration, or trust change, any channel, limit,
or margin change, any native-load inspection change, and any devcontainer
bootstrap-lock or platform change invalidates these rows and requires a rerun
before a canonical claim.

## Boundary

This artifact freezes capability only. It activates no hook, writes no project
configuration, and changes no row status; the bound Step 12.2 and 12.4
refreshes carry the native-load classification and the channel round trip.
