# Shared Workspace Context

`.workspace/` is the tool-neutral source of truth for the M8 workspace control
plane. It is owned by `fa-workspace`; child repositories remain independently
owned and usable outside this checkout.

## Ownership and semantic authority

- [`architecture.md`](architecture.md) owns workspace layers, dependency
  direction, security, portability, and standalone invariants.
- [`invariants.json`](invariants.json) catalogs the invariant IDs; definitions
  remain in `architecture.md`.
- [`repo-types.json`](repo-types.json) is the one registry of the 16 registered
  direct-child repositories. Internal paths such as `fa-ui-m8/app` are not
  repositories.
- [`policy.index.json`](policy.index.json) and
  [`policy.metadata.json`](policy.metadata.json) define the active faceted
  policy set. [`policies/always/`](policies/always/), `facets/`, and `tasks/`
  contain the selected policy slices.
- [`contracts/agent-context-w2a.contract.md`](contracts/agent-context-w2a.contract.md)
  owns authority, scope, authorization, delivery, accounting, runtime,
  receipt, and capability rules.
- [`plans/`](plans/), [`analyse/`](analyse/), and [`status/`](status/) own plans,
  analyses, and evidence artifacts. Do not copy shared facts into `.codex/` or
  `.claude/`.

The workspace owns shared classification, policies, schemas, resolver,
launchers, and workspace validation. A child owns its source, local
instructions, Git history, branches, CI, tests, releases, and delivery state.
Workspace validation may inspect child instruction presence and static shape,
but does not run or interpret child CI, tests, workflows, Git, or release state.

## Repository and task scope

Resolution is deterministic and ordered as follows:

```text
always -> declared repository facets in registry order -> explicit tasks -> exclusions
```

Tasks are opt-in. Environment, testing, Git, release, pull-request,
Headroom, and cross-repository procedures are not loaded by repository
selection or agent inference. Mutating and cross-repository tasks require a
single-use Ed25519 capability signed outside the workspace for the exact launch,
repository, task, operation, and user-task hash. The launcher redeems it
atomically against owner-only external trust and replay stores before
resolution; only metadata-only verified provenance enters manifests, sessions,
and receipts. Exclusions cannot remove security, ownership, required, or
otherwise non-waivable units.

The active format is faceted v2. The v1/transitional parser and compatibility
selectors were removed in Phase 9.2. The historical routing record under
`scripts/agent_context/fixtures/historical/` is non-authoritative rollback
evidence only.

## Capability evidence and modes

Capability evidence is per installed client, platform, and loading mode; it is
not inferred from documentation or another platform. The tracked canonical
artifacts consumed by validation and preflight are
[`capability-evidence-2026-07-19.md`](../scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md)
for Codex and
[`w12-claude-capability-evidence-2026-07-27.md`](../scripts/agent_context/fixtures/evidence/w12-claude-capability-evidence-2026-07-27.md)
(plus its bound 12.2 native-load and 12.4 hook-channel artifacts) for Claude.
Ignored `.workspace/status/` observations are historical only and cannot alter
canonical authority:

| Client/mode | Status | Canonical consequence |
|---|---|---|
| Codex devcontainer non-interactive | `REQUIRED` | Supported canonical row; native inspection is `codex debug prompt-input`; full content uses the verified `developer_instructions` channel. |
| Codex devcontainer interactive | `LIMITED` | Noncanonical; no frozen full-content or lifecycle evidence. |
| Claude devcontainer non-interactive | `REQUIRED` | Supported canonical row (Phase 12); native inspection is the out-of-band `claude-loopback-model-input-capture`; channel is the hook `additionalContext` row or the full-content `--append-system-prompt` row, selected by `model_visible_total`, never by envelope size alone. A repository scope must already carry the client's own recorded project trust or the launch fails closed with `E_TRUST`; a launcher never self-grants trust. |
| Claude devcontainer interactive | `OPTIONAL` | Byte-for-byte parity with the non-interactive rows, but startup can block on trust/onboarding dialogs a launcher cannot drive deterministically, so it does not block closeout. |
| Windows and host-POSIX rows | `UNSUPPORTED` | No behavior is inferred; these rows do not create implementation obligations. |

The required Codex row is the current canonical Codex launch mode after the
Phase 10 remediation; the two required Claude rows are canonical after the
Phase 12 remediation. Each is invalidated by a changed client or Node
binary/version, project trust or configuration, capability evidence, native
inspection mechanism, channel, lifecycle behavior, source hash, allowance, or
safety margin. A new dated capability refresh is required before making or
retaining a canonical claim. The Phase 9.5 rejection and parent-tree
observations remain historical and do not describe this current tree.

## Resolution and delivery

The active shared resolver, trust, authorization, delivery, and validation
stack lives in [`scripts/agent_context/`](../scripts/agent_context/). The
resolver validates authority, repository/task scope, conflicts,
overrides, required exclusions, source hashes, and native evidence before it
creates a deterministic manifest and RFC 8785 JCS UTF-8 envelope.

The canonical Codex devcontainer launcher runs from the reviewed workspace root:
root `AGENTS.md` is native, and each selected child `AGENTS.md` is injected once
with its repository scope. It checks native evidence and rehashes every source
immediately before submission, then passes the full envelope through
`developer_instructions` immediately before `codex exec`; a model reply is not
delivery proof. The authoritative runtime journal records
`SUBMISSION_STARTED` before transport and makes crashes, kills, timeouts, or
uncertain persistence terminal `EXECUTION_AMBIGUOUS`. Only a successful
`COMPLETED` generation may resume. `--fresh SESSION_DIR` first invalidates that
validated prior runtime, then starts generation zero with a new thread;
client-native `clear` and `compact` are not claimed. Interactive Claude/Codex
and unsupported client rows remain limited/unsupported and fail closed.

For an authorized launch, first run `scripts/codex-repo.sh` with
`--prepare-authorization-request`; this emits a metadata-only request and never
executes Codex. After an external owner signs that exact request, rerun with the
workspace-relative signed capability plus `--authorization-external-root`,
`--authorization-trust-store`, and `--authorization-replay-store`. The launcher
verifies and consumes the capability before it creates runtime state or invokes
the adapter.

The canonical Claude launcher (Phase 12) reuses the same resolver, kernel,
authorization boundary, shared validator, and trust identity from
`scripts/claude-repo.sh` / `claude_delivery_adapter.py`. It proves the
devcontainer, the pinned 12.1/12.2/12.4 evidence, the installed client
identity, the project's own recorded trust, and a real native-load capture
before it classifies any source `inject`; it then selects the hook or
full-content channel by `model_visible_total` and records the same
`RESOLVED`/`PREPARED`/`SUBMISSION_STARTED`/`COMPLETED`/`EXECUTION_AMBIGUOUS`
lifecycle. A repository scope without its own recorded trust decision (for
example an unaccepted `hasTrustDialogAccepted` entry) fails closed with
`E_TRUST` rather than being silently skipped or self-granted. See
[`scripts/agent_context/README.md`](../scripts/agent_context/README.md) for the
full boundary and [`agent-context-w2a.contract.md`](contracts/agent-context-w2a.contract.md)
for the reconciled mode table.

Parent-found mode may add reviewed workspace context. Parent-absent standalone
mode uses only verified child-owned native instructions; workspace policies,
tasks, sibling context, and cross-repository scope are unavailable. Missing
optional targets do not fail an unrelated standalone task.

## Accounting and budgets

For each client/platform/mode/channel row, the effective hard limit is:

```text
min(policy limit, channel limit, client allowance - reserved margin)
```

The non-overlapping model-visible total is:

```text
native_model_visible_bytes
+ serialized_injected_envelope_bytes
+ other_model_visible_bootstrap_bytes
```

Raw injected source bytes and serialization overhead are reported separately;
raw injected bytes are already contained in the serialized envelope and are not
added again. Launcher-only manifests, receipts, sessions, and global metadata
are excluded unless separately model-visible. The workspace ceilings are
24,576 preferred bytes and 32,768 hard bytes. These are workspace accounting
limits, not claims about a model's physical context window.

Instruction context size is an input-accounting concern. It is distinct from
reasoning effort, output compression, latency, and price: changing one does
not prove a change in the others.

## Secure runtime and receipts

Materialized runtime state is allowed only below ignored
`.workspace/.runtime/`, in an unpredictable per-session directory owned by the
current user. Writes are generation-aware and atomic; containment, ownership,
permissions/ACLs, symlink/reparse behavior, collisions, source drift, and
bounded interrupted cleanup are checked. Cleanup follows validated direct
runtime children and never an untrusted discovered path.

Normal logs and receipts contain metadata and hashes, never raw policy text or
user secrets. A `COMPLETED` receipt proves the expected client identity returned
success and framing/linkage passed; it does not prove model retention or
external-effect exactly-once behavior. `SUBMISSION_STARTED` and
`EXECUTION_AMBIGUOUS` are terminal for retry purposes. Receipt and session
metadata are excluded from model-visible accounting.

## Validation entry points

Load the selected profile without printing secrets:

```bash
source scripts/import-workspace-env.sh devcontainer
```

Then use the configured `$M8_PYTHON` for root-owned checks:

```bash
"$M8_PYTHON" scripts/agent_context/validate_w2b1.py workspace-v2 \
  .workspace/repo-types.json --policy-index .workspace/policy.index.json
"$M8_PYTHON" scripts/agent_context/validate_invariants.py --workspace .
"$M8_PYTHON" scripts/agent_context/validate_root_agents.py --workspace .
"$M8_PYTHON" scripts/agent_context/validate_claude_settings.py --workspace .
"$M8_PYTHON" scripts/agent_context/validate_codex_config.py --workspace .
"$M8_PYTHON" scripts/agent_context/validate_workspace.py --workspace .
"$M8_PYTHON" scripts/agent_context/validate_migration_guards.py --workspace .
"$M8_PYTHON" scripts/agent_context/validate_w9a_contract.py --workspace .
"$M8_PYTHON" -m unittest discover -s scripts/agent_context/tests -v
```

Use [`status/`](status/) for dated capability, measurement, rollout, and
validation evidence. A critical-file change invalidates a final review until
the reviewer records an amendment or reruns it. No plan text authorizes a
commit, push, child delivery, or destructive cleanup.
