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
closed human authorization record with the exact repository and operation set;
the resolver records only its identifier and hashes in manifests, sessions, and
receipts. Exclusions cannot remove security, ownership, required, or otherwise
non-waivable units.

The active format is faceted v2. The v1/transitional parser and compatibility
selectors were removed in Phase 9.2. The historical routing record under
`scripts/agent_context/fixtures/historical/` is non-authoritative rollback
evidence only.

## Capability evidence and modes

Capability evidence is per installed client, platform, and loading mode; it is
not inferred from documentation or another platform. The current evidence is
recorded in [`status/fa-workspace/agent-configuration-token-efficiency-capability-evidence-2026-07-19.md`](status/fa-workspace/agent-configuration-token-efficiency-capability-evidence-2026-07-19.md):

| Client/mode | Status | Canonical consequence |
|---|---|---|
| Codex devcontainer non-interactive | `REQUIRED` | Supported canonical row; native inspection is `codex debug prompt-input`; full content uses the verified `developer_instructions` channel. |
| Codex devcontainer interactive | `LIMITED` | Noncanonical; no frozen full-content or lifecycle evidence. |
| Claude devcontainer interactive/non-interactive | `LIMITED` | Noncanonical; no verified native inspection or exact full-content channel. |
| Windows and host-POSIX rows | `UNSUPPORTED` | No behavior is inferred; these rows do not create implementation obligations. |

The required row is invalidated by a changed client binary/version, project
trust or configuration, capability evidence, native inspection mechanism,
channel, lifecycle behavior, source hash, allowance, or safety margin. A new
dated capability refresh is required before making a canonical claim.

## Resolution and delivery

The inactive but validated W2b tools live in [`scripts/agent_context/`](../scripts/agent_context/).
The resolver validates authority, repository/task scope, conflicts,
overrides, required exclusions, source hashes, and native evidence before it
creates a deterministic manifest and RFC 8785 JCS UTF-8 envelope.

For a verified native source, the launcher checks the current native evidence
and source hash. For an injected source, native discovery must be demonstrably
disabled and the launcher must prove one exact-once handoff for the requested
generation. The canonical Codex devcontainer launcher passes the full envelope
through `developer_instructions` immediately before `codex exec`; a model reply
is not delivery proof. Claude and unsupported client rows remain limited or
unsupported and must fail closed rather than claim canonical delivery.

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
user secrets. A `HANDED_OFF` receipt proves launcher/adapter handoff and exact
linkage; it does not prove model retention or behavior. Receipt and session
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
"$M8_PYTHON" -m unittest discover -s scripts/agent_context/tests -v
```

Use [`status/`](status/) for dated capability, measurement, rollout, and
validation evidence. A critical-file change invalidates a final review until
the reviewer records an amendment or reruns it. No plan text authorizes a
commit, push, child delivery, or destructive cleanup.
