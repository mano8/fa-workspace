# Claude launcher-adapter — 2026-07-28

**Step:** 12.3
**Scope:** the fail-closed canonical Claude adapter and launcher over the two
`REQUIRED` devcontainer non-interactive rows frozen by
[Step 12.1](w12-claude-capability-evidence-2026-07-27.md), using the native-load
evidence mechanism established by
[Step 12.2](w12-claude-native-load-evidence-2026-07-28.md). The Codex required
row and its [2026-07-19 artifact](capability-evidence-2026-07-19.md) are
unchanged.

**Machine-readable freeze:**
[`w12-claude-adapter-evidence-2026-07-28.json`](w12-claude-adapter-evidence-2026-07-28.json)

## What the adapter is

[`claude_delivery_adapter.py`](../../claude_delivery_adapter.py) performs one
ordered launch and stops at the first thing it cannot prove:

1. **Preflight** — the evidenced devcontainer, the workspace's own
   `.m8-workspace-root` marker, the pinned 12.1 and 12.2 artifacts, the exact
   installed client (path, version, SHA-256), the reviewed project settings
   layer, the client's own recorded project trust, and each selected direct
   child with its `.git` and regular `CLAUDE.md`.
2. **Native-load inspection** — one separate `claude-loopback-model-input-capture`
   run for the launch scope. Nothing is assumed about discovery: the active set
   is enumerated from the client's own labels, and the capture must agree with
   the settings and client identity preflight already proved.
3. **Classification** — proven-active sources are `native`; the policy units and
   the selected children's instruction files are `inject` only after the same
   capture proves each one absent. `verify_manifest_native_binding` compares the
   manifest with that evidence in both directions *before* any injected entry is
   omitted.
4. **Resolution and channel selection** — the faceted resolver produces the
   manifest and the JCS envelope, and the shared validator decides whether a row
   fits. Selection is by `model_visible_total`, never by envelope size.
5. **Delivery and lifecycle** — the shared W2b3 kernel owns runtime storage,
   source rehashing, the immutable journal, and
   `RESOLVED`/`PREPARED`/`SUBMISSION_STARTED`/`COMPLETED`/`EXECUTION_AMBIGUOUS`/
   `FAILED`. The receipt is metadata only.

[`claude_repo_launcher.py`](../../claude_repo_launcher.py) and
[`claude-repo.sh`](../../../claude-repo.sh) are the CLI boundary. A mutating or
cross-repository task requires an explicitly supplied signed capability, which
is verified and atomically redeemed — through the same `authorization` boundary
the Codex launcher uses — before any preflight touches the client. There is no
Windows wrapper because no row outside this devcontainer is evidenced.

## Channel selection

| Row | Channel | Effective limit | Status in 12.3 |
|---|---|---:|---|
| `…-hook-additional-context` | `claude-hook-additional-context` | 10,000 | rejected: no byte-exact round-trip evidence is frozen |
| `…-append-system-prompt` | `claude-cli-append-system-prompt` | 32,768 | selected when the total fits |

The hook row is not disabled by opinion: `HOOK_ROUND_TRIP_EVIDENCE` is `None`
because Step 12.4 owns that fixture and the single injection authority. The
tests prove the seam works in both directions — with the evidence supplied and a
single `UserPromptSubmit` hook registered, a fitting generation selects the hook
row, and the same generation falls back when its total grows. While a hook is
registered, the wrapper channel is refused: bypassing the hook would inject a
second copy.

## The driven run

One complete live run on the trusted workspace root scope with `fa-auth-m8`
selected. The native-load capture was a real client launch against the loopback
recorder; delivery used a recording transport seam, so no client was invoked for
the handoff and the vendor API was never contacted.

| Observation | Value |
|---|---|
| Client | `/home/vscode/.local/share/claude/versions/2.1.220`, SHA-256 `674f61f2…` |
| Configuration identity | `62467e11…`, `registered_hook_events: []` |
| Trust | `trusted` (workspace root) |
| Native | `CLAUDE.md`, 1,905 B |
| Injected | 7 policy units + `fa-auth-m8/CLAUDE.md` + `fa-auth-m8/REPOSITORY_CONTEXT.md` |
| Absence proofs | 33 |
| Envelope | 9,019 B |
| `model_visible_total` | 10,924 B against a 32,768 B effective limit |
| Hook row | rejected — `E_BUDGET` **and** the unwired round trip |
| Receipt | `COMPLETED` from `SUBMISSION_STARTED`, 9,019 delivered bytes |
| Transport | the recorded `--append-system-prompt` argument hashes to the receipt's `envelope_sha256` |

The command shape is
`claude -p --output-format json --session-id <uuid> --append-system-prompt <envelope> <prompt>`.
The launcher owns the session identity before invocation and the transport
confirms the client reported that same identity; anything else is `E_LIFECYCLE`
and the submission stays terminal.

Independently, the adapter reproduces Step 12.2's frozen
`with-injected-child-instructions` classification byte-for-byte — the same
manifest identity `c8322263…`, envelope `133f51d9…`, and native evidence
`480f90ee…` — when it is driven with that record's own capture and reviewed
tree. The 33 absence proofs are the same 33.

## Fail-closed matrix

Twenty-two stages, each with its own frozen exit code and named test, cover
platform, discovery, capability and native-load artifact pins, client identity,
settings, trust, scope, native binding, injection authority, channel, budget,
authorization, usage, source drift, transport drift, session identity,
submission ambiguity, and trust-identity drift. The machine-readable artifact
lists every row; `E_UNSUPPORTED_MODE`, `E_SCOPE_UNAVAILABLE`, `E_CAPABILITY`,
`E_NATIVE_EVIDENCE`, `E_TRUST`, `E_CHANNEL`, `E_BUDGET`, `E_AUTHORIZATION`,
`E_USAGE`, `E_SOURCE`, and `E_LIFECYCLE` all appear.

## Boundary

No hook is registered, no project configuration was written, no child repository
file was touched, and no Claude row was promoted anywhere outside its own
capability artifact. The W2a contract mode table and the Step 5.6 wording are
unchanged; Step 12.6 reconciles them. `claude_adapter.py` keeps its Phase 5
`LIMITED` seam. The Codex adapter, its required row, and its bound evidence hash
are untouched.

The intended child-scope topology remains blocked: `/workspace/fa-auth-m8` still
records `hasTrustDialogAccepted = false`, and a launcher must never grant its own
trust, so that scope fails closed with `E_TRUST` until a human accepts it.
