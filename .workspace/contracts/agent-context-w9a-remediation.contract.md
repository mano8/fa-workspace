# Agent context W9a remediation contract

**Contract version:** `1.0.0`

**Frozen:** 2026-07-20

**Activation status:** `APPROVED_FOR_W9B_TO_W9F`

**Canonical runtime status:** `DISABLED_PENDING_REMEDIATION`

**Finding register:**
`.workspace/contracts/agent-context-w9a-findings.json`

## 1. Scope, inputs, and precedence

This contract is the Phase 10 Step 10.1 (`W9a`) rejection-remediation
boundary. It reconciles the two critical follow-up audits into one closed
machine-readable register and freezes only behavior supported by the installed
client evidence. It does not close a finding, enable canonical delivery, or
approve Step 9.5.

The frozen inputs are:

- the English critical audit, SHA-256
  `f07be4be2bc39cad5cff72d741b9c84d4f6970b7a83d21d1afb74785d1109078`;
- the independent French critical audit, SHA-256
  `142bc1658704b1819a4310fb0b791f8cd1761fe2379b98cb854fbd18750132ff`;
- the W2a contract version 2.1.0, SHA-256
  `97e4fcac65f80b6b49a002842cf13c74fbbb933bef5a61993579c93c91934af2`;
  and
- the tracked copy of the 2026-07-19 capability evidence, SHA-256
  `3fce2371cada5b2cbe949b0398ba29a376ca1515c7577dc6881b62263ff7588b`.

This contract amends W2a Sections 4, 6, 8, 9, 10, 12, and 13 for remediation.
Where the two contracts disagree, this contract governs. Unamended W2a data,
serialization, authority, accounting, standalone, and exit-code rules remain
normative. The audit prose and ignored status files are evidence inputs, not
runtime authority. The tracked finding register is the one disposition source
for `C-1`, `C-2`, `H-1`--`H-3`, `M-1`--`M-4`, `L-1`--`L-2`, and the separate
ZIP reproducibility limitation.

## 2. Capability ceiling and activation gate

The only implementation-obligation row remains Codex devcontainer
non-interactive with `codex debug prompt-input` inspection and the exact
32,768-byte `cli-config-developer-instructions` channel. Codex interactive and
both Claude devcontainer rows remain `LIMITED`; external Windows/POSIX rows
remain `UNSUPPORTED`. W9a does not infer a client acknowledgement, a separate
context-acceptance event, interactive approval API, clear command, compaction,
or multi-working-directory behavior.

Canonical launch is disabled until Steps 10.2 through 10.8 all pass their
named negative tests and evidence gates. Steps 10.9 through 10.12 then update
claims, pin the supply chain, assemble the exact-tree bundle, and gate a fresh
Step 9.5 review. Passing W9a validation proves only that the remediation
contract and register are complete and internally consistent.

## 3. Closed finding register

Every register object is closed; unknown or missing fields fail validation.
The register contains exactly eleven findings and one non-finding input
limitation. Every item names one disposition step, dependencies, an owner,
negative tests, closure artifacts, amendment sections, and invalidation
triggers. Findings remain `OPEN`; only the owning later step may present closure
evidence, and only the W9f exact-tree audit may mark the final bundle ready for
Step 9.5 re-entry.

`scripts/agent_context/validate_w9a_contract.py` validates the closed shape,
the exact finding/severity/blocking/step mapping, audit provenance, capability
ceiling, path containment, canonical ordering, contract markers, and optional
local audit hashes. An absent ignored audit file does not make a clean checkout
depend on ignored state; if present, its bytes must match the frozen hash.

## 4. Authenticated external authorization amendment

Step 10.2 MUST replace the self-asserted authorization JSON with a single-use,
externally authorized launch capability:

1. Before approval, the launcher creates a cryptographically random
   `launch_id` and nonce and emits a metadata-only request containing the exact
   canonical repository, task, and operation sets plus the SHA-256 of the exact
   user task. This request cannot execute the task.
2. An external signer uses Ed25519 to sign the RFC 8785 JCS UTF-8 bytes of a
   closed payload containing `schema_version`, `authorization_id`, `issuer`,
   `key_id`, `nonce`, `issued_at`, `expires_at`, `launch_id`, `repositories`,
   `tasks`, `operations`, and `user_task_sha256`.
3. The verification trust store and replay store are outside the workspace
   write boundary, owner-controlled, containment checked, non-reparse, and
   owner-only. The workspace may contain a signed capability, but workspace
   writes cannot create a valid signature or alter the external trust anchor.
4. The verifier rejects an unknown/revoked key, malformed or noncanonical
   payload, invalid signature, duplicate identity/nonce, future issue time,
   expiry, a validity interval over fifteen minutes, and any launch,
   repository, task, operation, or task-hash mismatch.
5. Redemption atomically consumes `(issuer, key_id, authorization_id, nonce)`
   before `SUBMISSION_STARTED`. A consumed or ambiguously consumed capability
   is never retried. Authorization provenance in manifests, state, and receipts
   contains only the authorization ID, issuer, key ID, signed-payload SHA-256,
   signature SHA-256, issue/expiry, and redemption identity; raw approval or
   signature content is not persisted there.

The signing private key and approval act are outside the repository, plan,
agent, and launcher. A tracked public key alone is not the trust root. Step
10.5 later binds the verifier, algorithms, external trust-store identity, and
cryptographic toolchain into the complete reviewed trust identity.

## 5. Conservative submission-state amendment

The installed Codex channel combines developer instructions and the user task
in one `codex exec` invocation. It exposes no independently verified durable
context-acceptance event. Therefore Option A from finding `C-2` is not
capability-supported and is rejected. Steps 10.3 and later MUST remove
`HANDED_OFF`, pre-task acceptance, and exact-once task-execution claims for the
current row.

The replacement lifecycle for one `(launch_id, generation)` is:

```text
RESOLVED -> PREPARED -> SUBMISSION_STARTED -> COMPLETED
    |           |               |
    +-----------+-> FAILED      +-> EXECUTION_AMBIGUOUS
```

`SUBMISSION_STARTED` is durably recorded before spawning `codex exec` and means
only that execution may occur. `COMPLETED` means the expected client identity
returned success and its framing passed; it does not prove model retention or
exactly-once external effects. Any crash, kill, timeout, output/framing error,
or persistence uncertainty after `SUBMISSION_STARTED` becomes terminal
`EXECUTION_AMBIGUOUS`. Neither `SUBMISSION_STARTED` nor
`EXECUTION_AMBIGUOUS` may be automatically retried or resumed.

One immutable, hash-chained, atomically created generation journal is the
authoritative state. Session and receipt views are derived metadata, not a
second independently authoritative transition. A missing or divergent derived
view fails closed without changing the journal disposition. This removes the
two-file replacement window from the authoritative state decision.

## 6. One multi-repository source model

For the required row, the execution directory is the reviewed workspace root
for both single- and multi-repository canonical launches. Root `AGENTS.md` is
the sole native instruction source and must be proven active through the
frozen inspection mechanism. Every selected child `AGENTS.md` is absent from
that native hierarchy and is injected exactly once with its registered
`repository_id` and scope prefix. No sibling child is claimed native. Child
`CLAUDE.md` is not a Codex source.

The manifest source inventory contains every visible root instruction, child
instruction, and policy source. Each entry records source kind, canonical path,
repository ID, scope, delivery (`native` or `inject`), exact source hash/count,
and its native-evidence or envelope-entry identity. The envelope contains all
and only inject entries in deterministic resolver order. Manifest, envelope,
generation journal, receipt view, measurement, and actual transport invocation
must recompute to the identical source set and byte totals. Reordered repository
arguments cannot change those bytes or identities.

Standalone child launches remain distinct limited/native behavior unless a
future capability refresh proves them canonical. W9a does not claim that Codex
natively loads multiple sibling instruction hierarchies.

## 7. Content-bound reviewed trust identity

Step 10.5 MUST create one JCS-hashed trust identity covering:

- root commit and tree IDs plus clean tracked-worktree and clean-index proof;
- for every selected child, commit/tree identity, clean tracked/index proof,
  and the selected instruction-source hash;
- hashes for the registry, index, policy metadata, contracts, schemas,
  resolver, kernel, adapters, launchers, wrappers, validators, root/selected
  child instructions, project agent configuration, capability artifact,
  dependency locks, devcontainer definition/lock/bootstrap, and CI bootstrap;
- installed Codex version and binary hash, Python/runtime/tool versions and
  binary hashes, platform identity, and relevant project/user/global
  configuration path/hash or explicit absence inventory; and
- the external authorization trust-store identity without secret or private-key
  content.

Canonical preflight fails on dirty/staged tracked content, a missing identity,
or any hash/config/binary/platform mismatch. A parent-tree receipt cannot prove
a child tree or later root tree. Ignored runtime state and raw secrets are
excluded from authority. Step 10.7 must supply a tracked canonical capability
artifact or deterministically reproduce it; ignored status evidence cannot be
a hidden prerequisite.

## 8. Production lifecycle amendment

The required row supports only these client-observed operations:

- `start`: a new launch and client thread;
- `resume`: the same verified Codex thread after a prior `COMPLETED` generation,
  with generation incremented once and all trust/source inputs revalidated;
- `fresh`: discard reuse eligibility and start a new launch/thread at generation
  zero; this is the only meaning formerly called `clear`; and
- `compact`: unsupported and rejected with `E_LIFECYCLE`.

Production wrappers must expose start, resume, and fresh plus safe explicit and
startup retention cleanup. Source/trust drift invalidates resume. Ambiguous
generations cannot resume or retry. Cleanup operates only on validated direct
children of the owner-controlled runtime root and never follows a symlink,
junction, reparse point, mount substitution, or untrusted path. No separate
client-native clear or compaction capability is claimed.

## 9. Disposition ownership

| Finding | Step | Frozen disposition owner |
|---|---:|---|
| `C-1` | 10.2 | External authorization and replay boundary |
| `C-2` | 10.3 | Generation journal and conservative submission states |
| `H-1` | 10.4 | Root-execution multi-repository source inventory |
| `H-2`, `M-4` | 10.5 | Complete trust identity and pinned bootstrap |
| `H-3` | 10.6 | Production lifecycle and cleanup |
| `M-1` | 10.7 | Tracked or reproducible capability authority |
| `M-2` | 10.8 | Shared offline/live strict validator |
| `M-3` | 10.9 | Current documentation and evidence identities |
| `L-1` | 10.10 | Content-addressed CI/tool inputs |
| `L-2` | 10.11 | Deterministic root-tooling SBOM |
| ZIP reproducibility limitation | 10.12 | Self-contained exact-tree review bundle |

The finding register names the exact future negative-test methods and closure
artifact paths. A later implementation may add tests but cannot rename or omit
a frozen test/artifact without amending W9a and rerunning its validator.

## 10. Invalidation and exit

W9a is invalid after a change to either audit digest, the W2a or capability
input identity, the required-row status/channel/limit, an amendment decision,
the finding mapping, or a named test/artifact/invalidation trigger. A necessary
change requires a versioned W9a amendment and plan status update.

Step 10.1 exits successfully only when the tracked contract and register,
focused W9a validator tests, all root validators, the complete root test suite,
and Ruff pass. That success authorizes work to begin at Step 10.2; it does not
authorize canonical launch or Step 9.5 re-entry.
