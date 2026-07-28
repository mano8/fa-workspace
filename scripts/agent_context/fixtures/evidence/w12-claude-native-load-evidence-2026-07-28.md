# Claude native-load evidence — 2026-07-28

**Step:** 12.2
**Scope:** the native-load evidence mechanism for the two `REQUIRED` Claude
devcontainer non-interactive rows frozen by
[Step 12.1](w12-claude-capability-evidence-2026-07-27.md). The Codex rows and
their [2026-07-19 artifact](capability-evidence-2026-07-19.md) are unchanged.

**Machine-readable freeze:**
[`w12-claude-native-load-evidence-2026-07-28.json`](w12-claude-native-load-evidence-2026-07-28.json)

**Tool source:**
[`claude_native_evidence.py`](../../claude_native_evidence.py), SHA-256
`01041ef6d293f615397bdd670fa945f8f4fe9279bab1d142e602062f287911d5`.

## Mechanism

There is no in-band inspection: `claude -p -d api,hooks --debug-file` logs
`[API REQUEST]` lines and never the body, and model self-report is explicitly
not evidence. The frozen mechanism is therefore the out-of-band
`claude-loopback-model-input-capture` — one separate, identically configured
launch whose `ANTHROPIC_BASE_URL` points at a loopback recorder the tool starts
itself, with a dummy `ANTHROPIC_API_KEY`. The vendor API is never contacted, the
recorder stores request bodies only, and those bodies live in a temporary
directory removed before the tool returns. No workspace or child repository file
is written.

The captured body is the exact model input the client built, so the active
instruction set is **enumerated from the client's own labels** rather than from
any assumption about discovery:

```text
Contents of <absolute path> (project instructions, checked into the codebase):

<the file's exact bytes>
```

For every label the tool then proves three things and fails closed otherwise:
the labelled file is a contained, regular, non-symlinked workspace file; its
exact decoded bytes follow its own label; and those bytes appear **exactly
once** in the whole captured model input. A label resolving outside the
workspace fails closed rather than being ignored, because a manifest cannot
carry what the workspace does not own.

Claude cannot disable its own project-memory discovery, so `inject`
classification uses the contract's alternative: each candidate injected source
is proved **absent** from the same exact model input. Thirty-three sources — the
thirty-one policy units and the two selected child instruction files — were
proved absent in the trusted scope.

`verify_manifest_native_binding` closes the loop the contract requires *before*
an injected entry is omitted: every `native` manifest entry must be proven
active with a matching hash and bind this evidence identity, no injected entry
may claim native evidence or shadow a proven-active source, and no proven-active
source may be missing from the manifest.

## Findings

**The active native set is scope-dependent, and so is the channel decision.**
The launch directory decides which `CLAUDE.md` files the client loads:

| Launch scope | Trust | Active model-visible sources | Native bytes | Status |
|---|---|---|---|---|
| `.` (workspace root) | `trusted` | `CLAUDE.md` | 1,905 | `CANONICAL` |
| `fa-auth-m8` | `untrusted` | `CLAUDE.md`, `fa-auth-m8/CLAUDE.md`, `fa-auth-m8/REPOSITORY_CONTEXT.md` | 3,037 | `BLOCKED_UNTRUSTED_PROJECT` |

The child scope reproduces Step 12.1's 3,037-byte measurement exactly, including
the `@REPOSITORY_CONTEXT.md` import, which the client delivers as its own
labelled source. It is the Phase 12 addendum's intended canonical topology, but
`~/.claude.json` records `projects["/workspace/fa-auth-m8"].hasTrustDialogAccepted
= false`. Trust is a recorded human action; a launcher that granted its own trust
would defeat the gate, so `build_native_evidence` fails closed with `E_TRUST` and
this scope cannot become canonical until a human accepts it.

**Both `REQUIRED` rows were driven end to end in the trusted root scope.** The
resolver, the shared validator, and the delivery kernel accept the classified
manifest, and the receipt carries the native-evidence identity:

| Variant | Row | Native | Envelope | Total | Effective limit | Result |
|---|---|---:|---:|---:|---:|---|
| workspace-only | `claude-hook-additional-context` | 1,905 | 7,160 | 9,065 | 10,000 | `COMPLETED` receipt |
| workspace-only | `claude-cli-append-system-prompt` | 1,905 | 7,160 | 9,065 | 32,768 | `COMPLETED` receipt |
| with injected child instructions | `claude-hook-additional-context` | 1,905 | 9,019 | 10,924 | 10,000 | fails closed `E_BUDGET` |
| with injected child instructions | `claude-cli-append-system-prompt` | 1,905 | 9,019 | 10,924 | 32,768 | `COMPLETED` receipt |

This **refines** Step 12.1's correction rather than contradicting it. Step 12.1
measured the child-scope native set (3,037 B) against the 7,160-byte envelope for
a 10,197-byte total, which overruns the hook row. In the root scope the native
set is 1,905 B and the same envelope totals 9,065 B, which fits the hook row with
935 bytes of headroom; adding the two child instruction files as injected entries
pushes the total to 10,924 B and the hook row fails closed again. The channel is
therefore selectable only from `model_visible_total` under a *specific* launch
scope and classification, exactly as Step 12.4 requires.

**Exactly-once is a configuration gate here and an authority gate in 12.4.**
Step 12.1 found that `SessionStart` also injects `additionalContext`. This tool
rejects a settings layer that registers both `SessionStart` and
`UserPromptSubmit` with `E_CHANNEL` rather than discovering the duplicate at
delivery; the single injection authority itself belongs to Step 12.4. No hook is
registered today (`registered_hook_events: []`).

## Frozen identities

- Client `/home/vscode/.local/share/claude/versions/2.1.220`, SHA-256
  `674f61f2…`, version `2.1.220 (Claude Code)` — unchanged from the 12.1 freeze,
  and `build_native_evidence` rejects any other client hash when the caller
  supplies the expected value.
- Configuration identity `62467e11…` over the project `.claude/settings.json`
  and `.claude/settings.local.json` hashes, the user settings hash, and the
  registered hook events. The user settings file is host state and changes when
  the user changes a client preference; per the native-load evidence contract
  that invalidates the evidence and requires a rerun.
- Native evidence `45ddd49d…` for the hook row and `480f90ee…` for the
  full-content row. The records differ only in `capability_evidence_id`, because
  the evidence binds the capability row it was captured for. Each identity is
  `canonical_sha256` of its own record without the identity field, and each was
  copied into a kernel receipt's `native_evidence_ids`.

## Rerun

```bash
python3 scripts/agent_context/claude_native_evidence.py \
  --workspace-root . --project . --output <observation.json>
```

Add `--project fa-auth-m8` for the child scope and `--absent <path>` to record an
absence proof. The observation is metadata only: hashes, byte counts, and labels,
never model input.

Any Claude executable, version, or SHA-256 change — including an automatic
update — any project or user settings, hook-registration, or trust change, any
change to a proven-active or proven-absent source, any change of launch
directory, and any 12.1 capability change invalidates this evidence and requires
a rerun before a canonical claim.

## Boundary

This artifact establishes the native-load evidence mechanism and the
native/inject classification it licenses. It registers no hook, writes no
project configuration, invokes no client during delivery, and promotes no Claude
row to canonical delivery: the adapter is Step 12.3, the channel and the single
injection authority are Step 12.4, the fixtures are Step 12.5, and the
reconciled status and documentation are Step 12.6. `claude_adapter` remains
`LIMITED` with no hook configured.
