# Agent context W2a contract

**Contract version:** `2.1.1`

**Frozen:** 2026-07-21

**Activation status:** `APPROVED_FOR_W2B`

**Implementation status:** the Codex devcontainer non-interactive required row
is implemented; the W9a remediation contract governs its signed authorization,
trust, source, lifecycle, and receipt amendments

**Capability evidence:**
`scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md`

**Capability evidence SHA-256:**
`d921bcdbc26cb4e65ffc6f0ab642d191d543987594df5291cc904a01a4562e7b`

**Post-remediation precedence:** Sections 4, 6, 8, 9, 10, 12, and 13 below
retain the frozen pre-remediation baseline. The tracked W9a contract explicitly
amends those sections and governs wherever they disagree, including external
signed authorization provenance and the
`SUBMISSION_STARTED`/`COMPLETED`/`EXECUTION_AMBIGUOUS` lifecycle.

## 1. Decision and activation gate

This contract freezes the public W2a data, authority, serialization, runtime,
delivery, accounting, standalone, lifecycle, and exit behavior that later W2b
implementation must follow. It does not claim a capability that the installed
clients did not demonstrate.

The current capability evidence yields this exact mode set:

| Agent | Platform | Mode | Status | Canonical channel | Blocks canonical activation |
|---|---|---|---|---|---|
| Codex | devcontainer | non-interactive | `REQUIRED` | `cli-config-developer-instructions`, 32,768 bytes | yes |
| Codex | devcontainer | interactive | `LIMITED` | none frozen | no |
| Claude | devcontainer | interactive | `LIMITED` | none frozen | no implementation obligation |
| Claude | devcontainer | non-interactive | `LIMITED` | none frozen | no implementation obligation |
| Codex and Claude | Windows / POSIX outside the devcontainer | interactive and non-interactive | `UNSUPPORTED` | none | no implementation obligation |

The minimum viable `REQUIRED` set contains exactly Codex devcontainer
non-interactive mode. For that row:

- `canonical_enabled` is true only after W2b1-W2b4 implement and pass this
  contract; W2a approval alone does not enable runtime behavior;
- `codex debug prompt-input` is the preflight native/model-input inspection;
- project trust must be `trusted`, and the controlled probe proves project
  configuration is absent when the same project is marked `untrusted`;
- CLI `developer_instructions` is the sole full-content handoff channel;
- 32,768 bytes is the workspace-capped verified channel maximum and effective
  hard limit; and
- interactive Codex and both Claude modes remain limited and noncanonical.

The qualifying evidence for a `REQUIRED` row must include the installed client
and configuration identities, project trust result, active native-source
inspection, exact full-content round trip and maximum byte count, and observed
start/resume/clear identities plus an explicit fail-closed compact disposition.
A documentation claim, model acknowledgement, preview, pointer to a temporary
file, or inferred behavior from another platform does not qualify.

## 2. Normative language and common primitives

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative. All JSON objects are
closed: unknown properties fail schema validation. Unless a field explicitly
allows `null`, it must not be null. Identifiers use ASCII lowercase letters,
digits, `.`, `_`, `$`, and `-`; they are case-sensitive and 1-128 bytes.

Common primitives are:

| Name | Exact definition |
|---|---|
| `sha256` | 64 lowercase hexadecimal characters over the exact bytes named by the field. |
| `reviewed_tree` | Closed object containing `algorithm` (`git-sha1` or `git-sha256`) and the lowercase hexadecimal Git tree object identifier in `value`. |
| `canonical_path` | `/`-separated path relative to the reviewed workspace root; no drive, URI, empty segment, `.`, `..`, backslash, NUL, or percent-decoded alias. |
| `scope_prefix` | `.` for the workspace root or a `canonical_path` directory prefix ending at a registered repository root. |
| `repository_id` | `$workspace` or one exact registry repository identifier. |
| `ordered_ids` | A duplicate-free JSON array whose order is semantically declared by the owning schema. |
| `canonical_set` | A duplicate-free JSON array sorted by Unicode code point order of the canonical identifier. |
| `timestamp` | UTC RFC 3339 with `Z` and whole seconds. |
| `byte_count` | Integer from 0 through 2,147,483,647; floats are forbidden. |

All source, registry, index, manifest, envelope, native-evidence, session, and
receipt paths are containment-checked against their declared root before use.

A capability row is a closed object with `agent`, `platform`, `mode`, `status`,
`inspection_mechanism`, `channel_id`, `verified_channel_limit`,
`client_context_allowance`, `reserved_margin`, `start_supported`,
`resume_supported`, `clear_supported`, `compact_supported`,
`launcher_identity_available`, `client_session_identity_available`, and
`blocks_closeout`. The three numeric limit fields and unavailable mechanisms or
channels may be null only for `LIMITED` or `UNSUPPORTED` rows. A `REQUIRED` row
must provide every mechanism, channel, limit, lifecycle, and identity field,
must set start/resume/clear to true, may set compact to false only with the
normative `E_LIFECYCLE` disposition, and must set `blocks_closeout` to true.
`OPTIONAL`, `LIMITED`, and `UNSUPPORTED` rows never become implementation
obligations merely by appearing in the matrix.

## 3. Registry and policy-index shapes

### 3.1 Historical migration fixture

`scripts/agent_context/fixtures/historical/v1-routing-2026-07-19.json` is a
read-only historical record of the pre-W3 routing data. It is not parsed by a
production validator, resolver, adapter, or launcher. Restoring the W3 adapter
requires a Git rollback; no active configuration accepts the historical shape.

### 3.2 Registry v2

Registry v2 is one closed object with exactly these fields:

```json
{
  "schema_version": 2,
  "repositories": [
    {
      "id": "repository-id",
      "path": "direct-child-path",
      "kind": "repository-kind",
      "layer": "platform|service|client|shared",
      "facets": ["ordered-facet-id"]
    }
  ]
}
```

`repositories` is sorted by `id`; `id` and `path` are unique. `path` must name a
direct child Git repository and must equal its canonical repository root.
Internal paths and infrastructure directories owned by a child are rejected.
The registry rejects all migration and compatibility fields.

### 3.3 Policy-index v2

The active policy index is one closed object with this exact shape:

```json
{
  "schema_version": 2,
  "mode": "faceted",
  "budgets": {
    "preferred_bytes": 24576,
    "hard_bytes": 32768
  },
  "always": ["policy-unit"],
  "facet_ids": ["canonical-set-of-evidenced-facet-id"],
  "facets": {"facet-id": ["policy-unit"]},
  "tasks": {"task-id": {"policies": ["policy-unit"], "authorization": "none|mutating|cross-repository"}},
  "exclusions": {"exclusion-id": ["policy-unit-id"]}
}
```

`facet_ids` is the complete, canonical set of evidenced language, layer, kind,
framework, and domain identifiers. `facets` contains only identifiers with at
least one policy unit; a declared-but-unmapped facet intentionally contributes
no shared policy, avoiding empty slices. Every registered repository facet must
be declared in `facet_ids`.

All map keys are serialized in JCS order. Policy arrays retain declared order; selected facet, task,
repository, exclusion, conflict, invariant, override, and capability sets use
`canonical_set` ordering. The index rejects all compatibility-bundle and
transitional-mode fields.

### 3.4 Policy unit and authority

A `policy-unit` is a closed object with exactly these required fields:

```json
{
  "id": "policy-unit-id",
  "path": "workspace-relative-path",
  "authority_tier": "security|workspace|task|repository",
  "scope": {"repository_id": "$workspace|repository-id", "prefix": ".|repository-prefix"},
  "invariant_ids": ["canonical-set"],
  "conflicts_with": ["canonical-set"],
  "may_override": ["canonical-set"],
  "required": true,
  "capabilities_granted": ["canonical-set"]
}
```

Authority descends in this order: `security`, `workspace`, `task`,
`repository`. The existing workspace priority inside the `workspace` tier is
environment, matched language policy, architecture, then validation contract.
That internal order is declared in metadata and is not inferred from array or
serialization order.

Every referenced invariant, conflict, override, capability, unit, repository,
and scope must exist. A unit may override only a listed target at the same or a
lower authority tier. Lower authority cannot weaken a higher tier. Unresolved
same-tier declared conflicts fail. Excluding a required unit fails. Undeclared
prose disagreement is a classification defect and is not auto-resolved.

## 4. Scope and authorization provenance

Resolution accepts one canonical repository set and one canonical task set.
Repository-local units have authority only under their registered prefix. A
child cannot grant authority in another child. Selecting more than one
repository requires a selected cross-repository task and explicit human
authorization whose scope contains exactly the requested repositories and
operations.

Mutating and cross-repository tasks carry this closed authorization record:

```json
{
  "authorization_id": "identifier",
  "kind": "explicit-user-message|named-owner-decision",
  "authorized_by": "non-empty identity label",
  "source_ref": "stable non-secret reference",
  "source_sha256": "sha256",
  "repositories": ["canonical-set"],
  "operations": ["canonical-set"],
  "issued_at": "timestamp"
}
```

The plan, repository metadata, policy metadata, an agent-generated statement,
or mere task selection cannot create authorization. The resolver derives an
`authorization_sha256` over each complete canonical record and carries only
the authorization ID, that record hash, and `source_sha256` into manifests,
sessions, and receipts; raw user or owner content is never persisted there.

## 5. Source bytes and canonical serialization

Source SHA-256 and `source_bytes` cover the exact original bytes on disk. The
source must decode as strict UTF-8. For a tagged unmigrated legacy source,
exactly one leading UTF-8 BOM may be stripped for `content`; the original hash
and count still include it and `leading_bom_bytes` is `3`. New or migrated
sources with a leading BOM fail. Embedded BOM code points are content. NUL
bytes fail. No newline or Unicode normalization is permitted.

The injected envelope is a closed JSON object:

```json
{
  "schema_version": 2,
  "manifest_id": "sha256",
  "generation": 0,
  "entries": [
    {
      "policy_id": "identifier",
      "repository_id": "$workspace|repository-id",
      "scope_prefix": ".|repository-prefix",
      "path": "canonical-path",
      "authority_tier": "security|workspace|task|repository",
      "source_sha256": "sha256",
      "source_bytes": 0,
      "leading_bom_bytes": 0,
      "serialized_content_bytes": 0,
      "content": "exact decoded content"
    }
  ]
}
```

The envelope uses RFC 8785 JCS UTF-8 with no floating-point values. Its SHA-256
covers the complete serialized bytes. Entries retain resolver order. Reordered
CLI repository/task sets resolve identically because those inputs are canonical
sets before resolution; declared facet/policy order remains schema order.

A repeated canonical path is removed only when repository, scope, source hash,
authority, and all policy metadata are identical. Any mismatch fails. JSON-like
content, delimiter strings, fake headers, closing braces, Unicode, and CRLF are
ordinary string content and cannot alter framing.

## 6. Manifest and native-load evidence

The manifest is a closed JSON object with these required fields:

```json
{
  "schema_version": 2,
  "manifest_id": "sha256",
  "reviewed_tree": {"algorithm": "git-sha1|git-sha256", "value": "lowercase-hex"},
  "agent": "codex|claude",
  "platform": "windows|posix|devcontainer",
  "mode": "interactive|non-interactive",
  "capability_evidence_id": "sha256",
  "repositories": ["canonical-set"],
  "tasks": ["canonical-set"],
  "operations": ["canonical-set"],
  "authorization_ids": ["canonical-set"],
  "authorization_provenance": [
    {
      "authorization_id": "identifier",
      "authorization_sha256": "sha256",
      "source_sha256": "sha256"
    }
  ],
  "entries": [
    {
      "policy_id": "identifier",
      "repository_id": "$workspace|repository-id",
      "scope_prefix": ".|repository-prefix",
      "path": "canonical-path",
      "delivery": "native|inject",
      "source_sha256": "sha256",
      "source_bytes": 0,
      "metadata_sha256": "sha256",
      "native_evidence_id": "sha256-or-null"
    }
  ],
  "accounting": {
    "policy_hard_limit": 32768,
    "verified_channel_limit": 0,
    "client_context_allowance": 0,
    "reserved_margin": 0,
    "effective_hard_limit": 0,
    "native_model_visible_bytes": 0,
    "serialized_injected_envelope_bytes": 0,
    "other_model_visible_bootstrap_bytes": 0,
    "model_visible_total": 0,
    "raw_injected_source_bytes": 0,
    "serialization_overhead_bytes": 0,
    "estimated_tokens": 0,
    "excluded_external_layers": ["canonical-set"]
  }
}
```

`manifest_id` is the JCS SHA-256 of the manifest with `manifest_id` omitted.
The accounting numbers shown above illustrate their integer type; a canonical
manifest uses the measured row values and cannot substitute zero for an
unavailable capability input.

A native-evidence record is closed and contains `native_evidence_id`, `agent`,
`platform`, `mode`, `client_identity`, `client_version`, `config_sha256`,
`capability_evidence_id`, `trust_state`, `inspection_mechanism`, `captured_at`,
and inspected `sources` as canonical path/hash pairs. `native_evidence_id` is
the JCS SHA-256 of that record without the identifier field.

Native evidence is invalid after a change to client identity/version,
configuration hash, capability-evidence hash, trust state, platform, mode,
inspection mechanism, project instruction discovery, or any inspected source
path/hash. If native activity cannot be inspected, a source may become
`inject` only when native discovery is demonstrably disabled and exact-once
handoff is preserved. Otherwise the row is noncanonical.

## 7. Accounting and budgets

For each mode/channel row:

```text
effective_hard_limit = min(
    policy_hard_limit,
    verified_channel_limit,
    client_context_allowance - reserved_margin
)

model_visible_total =
    native_model_visible_bytes
  + serialized_injected_envelope_bytes
  + other_model_visible_bootstrap_bytes
```

The accounting object contains all five formula inputs, the three visible-byte
components, `raw_injected_source_bytes`, `serialization_overhead_bytes`,
`estimated_tokens`, and `excluded_external_layers`. The serialized envelope
already contains injected source content, so raw injected bytes are diagnostic
and are never added again. Launcher-only manifests, receipts, and session
metadata are excluded. A separately model-visible manifest or bootstrap is
counted exactly once.

The workspace policy ceilings are 24,576 preferred bytes and 32,768 hard bytes.
They are not general transport guarantees. The required Codex devcontainer
non-interactive row has these evidence-backed values:

```text
min(32768 policy, 32768 verified channel, 65536 allowance - 32768 margin)
= 32768 effective hard limit
```

The 65,536-byte allowance and 32,768-byte margin are conservative controlled
probe values, not claims about the client's or model's physical maximum.

## 8. Delivery, lifecycle, session, and receipts

Channel selection is exact-byte and row-specific. A channel is eligible only
when the current capability record demonstrates that the full serialized
envelope round trips identically and fits its verified limit. Truncation,
preview text, and file pointers fail. If no eligible full-content channel
exists, preparation fails before the user task.

The only legal lifecycle is:

```text
RESOLVED -> PREPARED -> HANDED_OFF
    |           |
    +-----------+-> FAILED
```

`FAILED` and `HANDED_OFF` are terminal for one `(launch_id, generation)`.
Resume preserves `launch_id` only when the client provides a verifiable session
identity and increments `generation`. In the required row, the
`thread.started` JSONL event exposes the client session ID before
`turn.started`; `codex exec resume` must return that same ID. Clear is a fresh
`codex exec` invocation and creates a new launch, client-session identity, and
generation. Non-interactive compaction is unsupported and returns
`E_LIFECYCLE`; it cannot invalidate and silently rebuild context. Session-start
and resume handlers may validate or invalidate state but must not inject. One
pre-task gate is the sole injection authority.

The session record is closed and contains `schema_version`, `launch_id`,
`client_session_id`, `generation`, `state`, `manifest_id`, `envelope_sha256`,
`capability_evidence_id`, `native_evidence_ids`, the selected `repositories`,
`tasks`, and `operations`, `authorization_ids`, metadata-only
`authorization_provenance`, `created_at`, `updated_at`, and
`previous_receipt_sha256`. Identifiers unavailable from the client make the row
noncanonical rather than accepting placeholders.

A receipt is closed and contains the same identity/link fields, selected
repository/task/operation sets, and metadata-only authorization provenance plus
`receipt_id`, `previous_state`, `state`, `channel_id`, `delivered_bytes`,
`failure_code`, and `recorded_at`. `receipt_id` is the JCS SHA-256 of the record
without that field. Only an adapter callback confirming the exact envelope hash
and byte count may create `HANDED_OFF`. A receipt proves launcher/adapter
handoff, not model retention or behavior.

## 9. Runtime and threat boundary

The trust root is the reviewed Git tree hash plus installed-client,
configuration, capability-evidence, and native-evidence identities. The covered
threats are accidental drift, stale or concurrent state, path substitution,
unsafe cleanup, reparse traversal, and interference by another OS identity.
Compromise by a malicious process under the same user identity is out of scope.
Receipts are drift/integrity evidence within that boundary and are not
tamper-proof.

Materialized runtime data is permitted only below ignored
`.workspace/.runtime/` in a cryptographically unpredictable per-session
directory. Creation is atomic and no-replace; updates are atomic
same-directory replacements guarded by generation. POSIX permissions are
`0700` for directories and `0600` for files; Windows uses equivalent owner-only
ACLs. Every operation revalidates containment, ownership, and absence of
symlinks, junctions, mount substitutions, and other reparse points.

Concurrent sessions are isolated. Receipts and normal logs contain metadata and
hashes only. Normal and abnormal cleanup plus bounded startup retention remove
only validated direct runtime children and never follow a discovered path.

## 10. Standalone semantics

Parent-found mode may select workspace units only from the reviewed workspace
root and repository units only for explicitly selected registered children.
Parent-absent standalone mode cannot assume or fetch workspace context. It may
use only native child-owned instructions whose paths/hashes are verified inside
that child clone. Workspace tasks, cross-repository tasks, `$workspace` policy
units, and sibling injection are unavailable and fail with
`E_SCOPE_UNAVAILABLE` when requested.

Standalone success is a distinct limited/native result unless its own
agent/platform/mode row has demonstrated inspection, lifecycle, and delivery
evidence. Missing optional targets do not fail an unrelated standalone task;
missing required selected targets do.

## 11. Stable exit codes

| Exit | Symbol | Meaning |
|---:|---|---|
| 0 | `OK` | The requested noncanonical inspection/resolve action completed, or a future enabled canonical action reached its requested terminal state. |
| 2 | `E_USAGE` | Invalid CLI arguments or mutually exclusive inputs. |
| 3 | `E_SCHEMA` | Unknown field, wrong type/version/mode, malformed identifier, or non-JCS-compatible value. |
| 4 | `E_UNKNOWN_ID` | Unknown repository, policy, facet, task, invariant, capability, conflict, override, or exclusion target. |
| 5 | `E_SCOPE_UNAVAILABLE` | Path/repository/task is outside the selected or available scope, including unavailable standalone parent context. |
| 6 | `E_AUTHORITY` | Invalid precedence, conflict, override, required exclusion, or capability grant. |
| 7 | `E_AUTHORIZATION` | Missing, invalid, stale, or scope-mismatched human authorization provenance. |
| 8 | `E_SOURCE` | Missing/drifted source, hash/count mismatch, invalid UTF-8/BOM/NUL, duplicate mismatch, or framing/serialization failure. |
| 9 | `E_NATIVE_EVIDENCE` | Native source cannot be proven active or its evidence is stale/mismatched. |
| 10 | `E_TRUST` | Project trust, reviewed tree, client, configuration, or capability identity cannot be proved. |
| 11 | `E_RUNTIME` | Runtime containment, ownership, ACL/mode, reparse, atomicity, cleanup, or storage failure. |
| 12 | `E_CONCURRENCY` | Collision, stale generation, competing writer, or invalid state replacement. |
| 13 | `E_CHANNEL` | No verified full-content channel, byte mismatch, callback mismatch, or truncation. |
| 14 | `E_BUDGET` | Missing effective limit or payload exceeds the effective hard limit. |
| 15 | `E_LIFECYCLE` | Unsupported or invalid start/resume/clear/compact/generation transition or missing client-session identity. |
| 16 | `E_RECEIPT` | Illegal receipt transition, linkage/hash mismatch, duplicate handoff, or terminal-state rewrite. |
| 17 | `E_CAPABILITY` | Capability evidence is absent, stale, or does not demonstrate the requested behavior. |
| 18 | `E_UNSUPPORTED_MODE` | The selected agent/platform/mode is `LIMITED` or `UNSUPPORTED` for canonical use. |
| 19 | `E_INTERNAL` | Unexpected implementation failure; no handoff may be claimed. |

Errors are emitted as metadata-only structured diagnostics. Secret values,
source content, serialized envelopes, and raw authorization content must not be
logged.

## 12. Required negative fixtures before activation

Later implementation cannot enable canonical delivery until deterministic
fixtures reject: unknown metadata targets; cross-scope child authority; lower-
tier overrides; unresolved conflicts; required exclusions; absent or mismatched
authorization; tree/client/config/capability drift; source/hash/count drift;
native path/hash mismatch; unsupported lifecycle transitions; missing session
identity; channel truncation or callback mismatch; absent effective limit;
over-budget payloads; NUL, BOM, malformed UTF-8, CRLF/Unicode/framing attacks;
duplicate path metadata mismatch; runtime escape/reparse/ownership attacks;
collisions, stale generations, concurrent writers, invalid receipt transitions,
duplicate handoff, and unsafe interrupted cleanup.

## 13. Capability freeze and invalidation

The tracked 2026-07-19 capability artifact at
`scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md`
satisfies the W2a activation gate for the
single required row. Steps 2.2-2.5 may implement that row within their separate
W2b boundaries. The completed W3 switch makes the faceted v2 configuration
authoritative; it does not enable a transport or canonical
delivery adapter.

Ignored `.workspace/status/` files are historical observations only and are
not read by workspace validation or canonical preflight. If the tracked
artifact is absent or its pinned hash differs, canonical preflight fails with
`E_CAPABILITY` until a verified refresh updates the artifact and its identities.

Any change to the required Codex binary/version, devcontainer lock, project
trust/configuration, inspection mechanism, native source discovery, channel,
32,768-byte fixture result, allowance, margin, or lifecycle identity behavior
invalidates this approval. Re-freeze then requires a new dated capability
artifact and evidence hash. `LIMITED` and `UNSUPPORTED` rows remain outside the
implementation obligation unless separately demonstrated and reclassified.
