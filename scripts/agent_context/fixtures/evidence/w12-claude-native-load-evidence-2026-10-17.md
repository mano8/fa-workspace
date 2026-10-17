# Claude native-load evidence — 2026-10-17

**Step:** 12.2 (dated refresh)
**Scope:** the native-load evidence for the two `REQUIRED` Claude devcontainer
non-interactive rows frozen by
[Step 12.1](w12-claude-capability-evidence-2026-10-17.md). The Codex rows and
their [2026-07-19 artifact](capability-evidence-2026-07-19.md) are unchanged.

**Machine-readable freeze:**
[`w12-claude-native-load-evidence-2026-10-17.json`](w12-claude-native-load-evidence-2026-10-17.json)

**Refreshes:** [the 2026-07-28 freeze](w12-claude-native-load-evidence-2026-07-28.md),
kept unchanged as history.

**Tool source:**
[`claude_native_evidence.py`](../../claude_native_evidence.py), SHA-256
`d354018997b92238c0de88ff8eb3950d4de4e5fd0244bfb7c035d3eee2201d9f`.

## Mechanism

The mechanism is unchanged: `claude-loopback-model-input-capture`, one
separate, identically configured launch against a loopback recorder with a
dummy `ANTHROPIC_API_KEY`. The vendor API is never contacted, request bodies
live only in a temporary directory, and no workspace file is written. Every
active source is enumerated from the client's own labels:

```text
Contents of <absolute path> (project instructions, checked into the codebase):

<the file's exact bytes>
```

Each label must name a contained regular workspace file. Its exact bytes must
follow the label and appear exactly once in the whole model input.

**One tool change, for `2.1.302`.** A clean `2.1.302` CLI launch no longer
puts the project-memory block under a `# claudeMd` heading. The block now
opens with the sentence "Codebase and user instructions are shown below.",
which `2.1.220` also emitted under that heading. The tool now keys the block
on that sentence. Every per-label byte-exact and exactly-once check is
unchanged, and a model input without the block still fails closed.

**One source-model change.** Root `CLAUDE.md` now imports
`.workspace/context/agent-conventions.md`, and the client lists it as its own
labelled source. The tool and the resolver accept exactly that file as a
second `$workspace`-tier native source (`instruction.root.claude-conventions`).
Any other `.workspace/` native source still fails closed.

Both captures ran outside any parent Claude session environment, with
`DISABLE_AUTOUPDATER=1`. Thirty-three injection candidates were proved
**absent** from the trusted root capture: the thirty-one policy units and both
`fastapi-m8` instruction files.

## Findings

| Launch scope | Trust | Active model-visible sources | Native bytes | Status |
|---|---|---|---|---|
| `.` (workspace root) | `trusted` | `.workspace/context/agent-conventions.md` (1,955), `CLAUDE.md` (1,326) | 3,281 | `CANONICAL` |
| `fa-auth-m8` | `untrusted` | `CLAUDE.md` (1,326), `fa-auth-m8/CLAUDE.md` (161), `fa-auth-m8/REPOSITORY_CONTEXT.md` (2,215) | 3,702 | `BLOCKED_UNTRUSTED_PROJECT` |

**The import loads only at the workspace root.** From inside a child, the
imported file lies outside the launch project. The client skips such external
`CLAUDE.md` imports until the human approves them for that project
(`hasClaudeMdExternalIncludesApproved`), and no approval is recorded for
`/workspace/fa-auth-m8`. That approval is a recorded human action, like folder
trust. The launcher never writes it.

The child scope is still the Phase 12 addendum's intended topology, but
`/workspace/fa-auth-m8` still has `hasTrustDialogAccepted = false`.
`build_native_evidence` therefore still fails closed with `E_TRUST`.

**Both `REQUIRED` rows were driven end to end in the trusted root scope for
`fastapi-m8`.** With the 3,281-byte root bootstrap, `fa-auth-m8` no longer fits
the hook row even workspace-only (10,287 bytes), so the fit-versus-overrun
demonstration moves to `fastapi-m8`. The artifact names it in
`classification_repository`.

| Variant | Row | Native | Envelope | Total | Effective limit | Result |
|---|---|---:|---:|---:|---:|---|
| workspace-only | `claude-hook-additional-context` | 3,281 | 5,759 | 9,040 | 10,000 | `COMPLETED` receipt |
| workspace-only | `claude-cli-append-system-prompt` | 3,281 | 5,759 | 9,040 | 32,768 | `COMPLETED` receipt |
| with injected child instructions | `claude-hook-additional-context` | 3,281 | 7,774 | 11,055 | 10,000 | fails closed `E_BUDGET` |
| with injected child instructions | `claude-cli-append-system-prompt` | 3,281 | 7,774 | 11,055 | 32,768 | `COMPLETED` receipt |

The channel is still selectable only from `model_visible_total` under a
specific launch scope and classification.

## Frozen identities

- Client `/home/vscode/.local/share/claude/versions/2.1.302`, SHA-256
  `60d7eb7f…`, version `2.1.302 (Claude Code)`, equal to the 12.1 refresh.
- Configuration identity `e914d9b8…`. It covers the reviewed project
  `.claude/settings.json` (`0285e6be…`, unchanged since the 2026-07-28
  freeze), `.claude/settings.local.json`, the user settings hash, and the
  registered hook events (none).
- Native evidence `23210d6f…` for the hook row and `1fafa88e…` for the
  full-content row. Each is `canonical_sha256` of its own record and reaches
  a kernel receipt's `native_evidence_ids`.

## Rerun

```bash
python3 scripts/agent_context/claude_native_evidence.py \
  --workspace-root . --project . --output <observation.json>
```

Add `--project fa-auth-m8` for the child scope and `--absent <path>` to record
an absence proof. Run it outside any Claude session's environment. Any Claude
executable, version, or SHA-256 change — including an automatic update — any
project or user settings, hook-registration, trust, or external-import
approval change, any change to a proven-active or proven-absent source, any
change of launch directory, and any 12.1 capability change invalidates this
evidence.

## Boundary

This artifact establishes the native-load evidence and the native/inject
classification it licenses. It registers no hook and writes no project
configuration. The fail-closed adapter remains Step 12.3; the channel and its
single injection authority are re-measured in the
[Step 12.4 refresh](w12-claude-hook-channel-evidence-2026-10-17.md).
