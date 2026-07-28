# Claude hook channel and single injection authority — 2026-07-28

**Step:** 12.4
**Scope:** the byte-exact `UserPromptSubmit` `additionalContext` delivery channel
for the `REQUIRED` row
`claude-devcontainer-non-interactive-hook-additional-context` frozen by
[Step 12.1](w12-claude-capability-evidence-2026-07-27.md), delivered by the
fail-closed adapter of [Step 12.3](w12-claude-adapter-evidence-2026-07-28.md)
over the native-load evidence of
[Step 12.2](w12-claude-native-load-evidence-2026-07-28.md). The Codex required
row and its [2026-07-19 artifact](capability-evidence-2026-07-19.md) are
unchanged.

**Machine-readable freeze:**
[`w12-claude-hook-channel-evidence-2026-07-28.json`](w12-claude-hook-channel-evidence-2026-07-28.json)

## What is wired

The injection authority is **launcher-owned and one per launch**. When the hook
row is selected, the transport writes three owner-only artifacts into the
kernel's runtime session for that generation and invokes the client with
`--settings <that file>` and **no** `--append-system-prompt`:

| Artifact | Contents |
|---|---|
| `channel-envelope.bin` | the exact serialized JCS envelope, nothing else |
| `channel-state.json` | the closed armed state: channel, launch, client session, generation, manifest, envelope hash and byte count, verified limit, effective limit, `model_visible_total`, round-trip identity, launch scope |
| `channel-settings.json` | one `UserPromptSubmit` registration naming [`claude_hook_gate.py`](../../claude_hook_gate.py) with this runtime session |

No workspace, project, or user settings file is ever written. The reviewed
project settings layer still forbids `hooks`, and the registration disappears
with the runtime session.

[`claude_hook_gate.py`](../../claude_hook_gate.py) is the gate the client runs
before it builds any model input. It answers only `UserPromptSubmit`, only for
the launcher-owned client session, only after re-verifying the armed payload
against its recorded hash, byte count, and the row's verified channel limit, and
it claims each generation through **atomic no-replace creation** of
`channel-claim-<generation>.json`. A repeated prompt in the same generation is
answered with no `additionalContext`. Every failure exits `2` with no claim,
which blocks the prompt; the launcher then fails closed on its own post-run
claim check, independently of the client's exit status.

## Measured round trip

Two independent full probe runs, each pointing `ANTHROPIC_BASE_URL` at a
loopback recorder started by the probe with a dummy `ANTHROPIC_API_KEY`, agreed
exactly apart from per-run session identifiers and timestamps. The vendor API
was never contacted, request bodies only were stored, and no workspace file was
written.

| Measurement | Result |
|---|---|
| Complete 4,211-byte serialized JCS envelope in the model input | byte-exact |
| Occurrences of that envelope in the captured model input | 1 |
| Injection claims after the first prompt | 1 |
| Same generation resumed and prompted again | 1 occurrence (transcript replay), still 1 claim |
| `additionalContext` at 10,000 bytes | byte-exact |
| `additionalContext` at 10,001 bytes | `<persisted-output>` preview plus a temporary-file pointer — never delivery |

## Driven run

One live root-scope launch selected `imgtools_m8` and delivered over the wired
hook row. The native-load capture and the delivery were both real client
launches against a loopback recorder; the vendor API was never contacted.

| Fact | Value |
|---|---|
| Selected row / rejected rows | hook row / none |
| Registered hook events in the settings layer | none — the launcher owns its own |
| Native / injected | `CLAUDE.md` (1,905 B) native; 5 injected entries including both child instruction files |
| `model_visible_total` | 6,651 against the 10,000 B effective limit |
| Envelope | 4,746 B, delivered by the gate |
| Occurrences in the real client's model input | 1 |
| Receipt | `COMPLETED` from `SUBMISSION_STARTED`, 4,746 delivered bytes, hash equal to the armed envelope |
| Client command | `-p --output-format json --session-id … --settings …` — no `--append-system-prompt` |
| Runtime artifacts | four `channel-*` files, all `0600` inside the ignored session directory |

At root scope on this tree, ten of the sixteen registered repositories resolve
under the hook row and six fall through to `--append-system-prompt`; the
`fa-auth-m8` total of 10,924 B remains the worked example from Step 12.1.

## Findings

1. **F-1 — the channel carries the real artifact.** The complete envelope,
   including backslash, quote, CRLF, tab, and non-ASCII content, reaches the
   model input byte-exactly through the gate.
2. **F-2 — resume replays, it does not re-inject.** A resumed session shows the
   envelope once more because its own transcript contains it; the gate writes no
   second claim and returns no second copy. The count, not the presence, is the
   evidence.
3. **F-3 — `--settings` hooks *merge*.** A hook registered in the project layer
   and the launcher's own hook both ran and both delivered. A foreign
   `SessionStart` or `UserPromptSubmit` registration is therefore a second
   injection authority the launcher does not own, and it makes **both** rows
   ineligible with `E_CHANNEL`. This is the explicit arbitration Step 12.3
   deferred.
4. **F-4 — a refused gate produces no model input at all.** The unowned session,
   the oversize payload, and the drifted envelope each recorded **zero**
   model-input requests: the prompt was blocked before any model input existed,
   so no user task ran without its context.
5. **F-5 — the gate cannot become a second authority.** Registered on
   `SessionStart` it delivers nothing and claims nothing, so even a misconfigured
   launcher injects at most once.
6. **F-6 — the launcher keeps the default setting sources.** Narrowing
   `--setting-sources` to `user` suppressed the project memory that the Step 12.2
   native evidence enumerated, which would make the launch a different one from
   the evidence run. The canonical launch keeps the default sources and adds only
   its own hook.
7. **F-7 — the boundary holds through this path.** The 10,000/10,001 boundary
   measured in Step 12.1 with a project-settings hook is reproduced exactly with
   a launcher-supplied one.

## Injection authority

| Situation | Authority |
|---|---|
| Hook row selected | the launcher's own one-launch `UserPromptSubmit` gate; no `--append-system-prompt` |
| Full-content row selected | `--append-system-prompt`; the launcher registers no hook |
| Foreign `additionalContext` hook registered | neither row is eligible (`E_CHANNEL`) |
| `SessionStart` | never registered by the launcher and refused by the gate |
| Resume | validates and continues; the per-generation claim prevents a second copy |
| Compaction | unsupported and fail-closed; the frozen rows record `compact_supported: false` |

Selection itself is unchanged and still by `model_visible_total`: the hook row's
10,000-byte ceiling is a total, not an envelope allowance, so a generation that
outgrows it falls through to the verified `--append-system-prompt` row.

## Never delivery

A truncated value, a temporary-file pointer, a `<persisted-output>` preview, a
payload above the verified channel limit, and an armed envelope whose hash or
byte count drifted are each refused before any client sees them.

## Reproduction

```bash
python3 scripts/agent_context/probe_claude_hook_channel.py --output <path>
"$M8_PYTHON" -m unittest scripts.agent_context.tests.test_w12_claude_hook_channel -v
```

## Invalidation

Any Claude executable/version/SHA-256 change including an automatic update; any
change to `claude_hook_gate.py`; any change to the hook row, its verified channel
limit, or its capability evidence; any change to the registered event or the
launcher's registration mechanism; and any change to the native-load evidence
mechanism or its identically configured launch.
