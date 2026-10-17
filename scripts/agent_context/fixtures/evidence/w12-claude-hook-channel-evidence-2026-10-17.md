# Claude hook channel and single injection authority — 2026-10-17

**Step:** 12.4 (dated refresh)
**Scope:** the byte-exact `UserPromptSubmit` `additionalContext` delivery channel
for the `REQUIRED` row
`claude-devcontainer-non-interactive-hook-additional-context` frozen by
[Step 12.1](w12-claude-capability-evidence-2026-10-17.md), delivered by the
fail-closed adapter of [Step 12.3](w12-claude-adapter-evidence-2026-07-28.md)
over the native-load evidence of
[Step 12.2](w12-claude-native-load-evidence-2026-10-17.md). The Codex required
row and its [2026-07-19 artifact](capability-evidence-2026-07-19.md) are
unchanged.

**Machine-readable freeze:**
[`w12-claude-hook-channel-evidence-2026-10-17.json`](w12-claude-hook-channel-evidence-2026-10-17.json)

**Refreshes:** [the 2026-07-28 freeze](w12-claude-hook-channel-evidence-2026-07-28.md),
kept unchanged as history. The frozen round trip names the client, so the
`2.1.302` update invalidated it. The wiring, the gate
([`claude_hook_gate.py`](../../claude_hook_gate.py), unchanged) and the
injection-authority rules below are as frozen on 2026-07-28.

## Measured round trip

There were two independent full probe runs on `2.1.302`. Each ran outside any
parent Claude session environment with `DISABLE_AUTOUPDATER=1`, against a
loopback recorder with a dummy `ANTHROPIC_API_KEY`. The runs agreed exactly
apart from per-run session identifiers and timestamps, and the timestamped
round-trip identity derived from them. The vendor API was never contacted,
and no workspace file was written.

| Measurement | Result |
|---|---|
| Complete 4,211-byte serialized JCS envelope in the model input | byte-exact |
| Occurrences of that envelope in the captured model input | 1 |
| Injection claims after the first prompt | 1 |
| Same generation resumed and prompted again | 1 occurrence (transcript replay), still 1 claim |
| `additionalContext` at 10,000 bytes | byte-exact |
| `additionalContext` at 10,001 bytes | `<persisted-output>` preview plus a temporary-file pointer — never delivery |

The frozen round-trip identity is `db952a26…`, pinned by
`claude_delivery_adapter.py`.

## Driven run

One live root-scope launch selected `imgtools_m8` and delivered over the wired
hook row through the unmodified adapter. Its only seam was the documented
process runner pointing the real client at a loopback recorder.

| Fact | Value |
|---|---|
| Selected row / rejected rows | hook row / none |
| Registered hook events in the settings layer | none — the launcher owns its own |
| Native / injected | `.workspace/context/agent-conventions.md` (1,955 B) and `CLAUDE.md` (1,326 B) native; 5 injected entries including both child instruction files |
| `model_visible_total` | 8,027 against the 10,000 B effective limit |
| Envelope | 4,746 B, delivered by the gate |
| Occurrences in the real client's model input | 1 |
| Receipt | `COMPLETED` from `SUBMISSION_STARTED`, 4,746 delivered bytes, hash equal to the armed envelope |
| Client command | `-p --output-format json --session-id … --settings …` — no `--append-system-prompt` |
| Runtime artifacts | four `channel-*` files, all `0600` inside the ignored session directory |

## Row fit across the 19 registered repositories

At root scope on this tree, the native bootstrap is 3,281 bytes, against
1,905 on 2026-07-28. With each selected child's instruction files injected,
**4 of the 19 registered repositories fit the hook row**: `imgtools_m8`,
`security-tests-m8`, `auth-sdk-m8` and `media-worker-m8`. **The other 15 fall
through to `--append-system-prompt`.** That set includes all three new
repositories, `ai-gateway-m8`, `ai-sdk-m8` and `doctools-m8`. Every total
stays inside the full-content row's 32,768-byte limit; the largest is
`reparto-docente-m8` at 18,211. Canonical delivery therefore stays available
for every registered repository; what moved is which channel carries it. The
2026-07-28 survey had 10 of 16 on the hook row.

`media-service-m8` and `reparto-docente-m8` were measured from CRLF working
copies of their child instruction files. Their LF bytes are a few dozen bytes
smaller, which changes neither classification.

## Findings

The seven 2026-07-28 findings (F-1 to F-7) reproduce on `2.1.302`. The
complete envelope reaches the model input byte-exactly through the gate, and
resume replays rather than re-injects. `--settings` hooks still merge with the
project layer, so a foreign `additionalContext` hook makes both rows
ineligible with `E_CHANNEL`. A refused gate still produces zero model-input
requests, and registering the gate on `SessionStart` is still inert.
Narrowing `--setting-sources` to `user` still suppresses project memory. The
10,000/10,001 boundary holds through the launcher's own registration.

## Injection authority

| Situation | Authority |
|---|---|
| Hook row selected | the launcher's own one-launch `UserPromptSubmit` gate; no `--append-system-prompt` |
| Full-content row selected | `--append-system-prompt`; the launcher registers no hook |
| Foreign `additionalContext` hook registered | neither row is eligible (`E_CHANNEL`) |
| `SessionStart` | never registered by the launcher and refused by the gate |
| Resume | validates and continues; the per-generation claim prevents a second copy |
| Compaction | unsupported and fail-closed; the frozen rows record `compact_supported: false` |

## Reproduction

```bash
python3 scripts/agent_context/probe_claude_hook_channel.py --output <path>
"$M8_PYTHON" -m unittest scripts.agent_context.tests.test_w12_claude_hook_channel -v
```

Run the probe outside any Claude session's environment, with
`DISABLE_AUTOUPDATER=1`.

## Invalidation

Any Claude executable/version/SHA-256 change including an automatic update; any
change to `claude_hook_gate.py`; any change to the hook row, its verified channel
limit, or its capability evidence; any change to the registered event or the
launcher's registration mechanism; and any change to the native-load evidence
mechanism or its identically configured launch.
