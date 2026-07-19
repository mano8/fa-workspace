# W2b1 agent-context schemas

This additive, inactive package implements Phases 2.2 through 2.5. It validates the
v1 and frozen v2 registry/index shapes, policy units, manifests, sessions, and
receipts; it also creates RFC 8785 JCS UTF-8 injected envelopes from supplied
source bytes. The scoped resolver consumes explicit v2 fixture inputs, performs
authority/scope/authorization/native-evidence checks, and emits deterministic
manifests plus envelopes. It does not activate transport, write runtime state,
or invoke an agent.

Run its deterministic suite with the configured devcontainer Python runtime:

```bash
source scripts/import-workspace-env.sh devcontainer
"$M8_PYTHON" -m unittest discover -s scripts/agent_context/tests -v
```

The CLI accepts a strict UTF-8 JSON file and returns `0` on success. For an
envelope it writes the exact canonical bytes to stdout and its SHA-256 to
stderr:

```bash
source scripts/import-workspace-env.sh devcontainer
"$M8_PYTHON" scripts/agent_context/validate_w2b1.py registry-v2 path/to/registry.json
```

Phase 4.3 activates the faceted v2 policy index. The registry retains its W3
`migration.v1_bundle` selectors until Phase 9.2, but the active resolver does
not select them. The historical W3 compatibility arrays remain test-only
rollback evidence; policy selection now uses the active `always`, `facets`, and
explicitly selected task overlays. A declared facet with no workspace slice is
an intentional no-op, never an empty policy file.

Phase 4.4 adds opt-in environment, testing, per-operation Git, pull-request,
release, Headroom, and cross-repository overlays. Default resolution selects
none of them. Mutating and cross-repository tasks require a closed human
authorization record whose repository and operation sets match exactly;
manifests, sessions, and receipts retain only its identifier, canonical record
hash, and source hash alongside the selected repository/task/operation sets.

```bash
"$M8_PYTHON" scripts/agent_context/resolve-context.py \
  --registry .workspace/repo-types.json \
  --policy-index .workspace/policy.index.json \
  --format resolution --root . --policy-metadata .workspace/policy.metadata.json \
  --capability-row path/to/capability-row.json --reviewed-tree path/to/reviewed-tree.json \
  --agent codex --platform devcontainer --mode non-interactive \
  --injection-evidence path/to/injection-evidence.json --repository auth-sdk-m8
```

Validate the coupled active workspace files with:

```bash
"$M8_PYTHON" scripts/agent_context/validate_w2b1.py workspace-v2 \
  .workspace/repo-types.json --policy-index .workspace/policy.index.json
```

Phase 4 Step 4.2 establishes the canonical workspace-invariant catalog and
definition ownership. Validate unique definitions, resolved references, and the
absence of tracked authoritative copies under tool-specific directories with:

```bash
"$M8_PYTHON" scripts/agent_context/validate_invariants.py --workspace .
```

The faceted resolver mode in [`resolve-context.py`](resolve-context.py) remains
an explicit, inactive W2b2 tool. It requires a faceted v2 registry/index and policy metadata fixture, then accepts repeatable
repository, task, exclusion, operation, and authorization arguments. Its
canonical `resolution` output includes the manifest and envelope; `manifest`
and `envelope` formats are also available. Native sources need current verified
native evidence. Injected sources need evidence that native discovery is
disabled and an exact-once handoff is proven for the requested generation;
runtime enforcement is provided by the inactive W2b3 client-neutral kernel in
[`delivery_kernel.py`](delivery_kernel.py). It owns only isolated runtime
state, source-drift rehashing, receipt transitions, stable exit mapping, and a
fake exact-payload adapter. It has no Codex/Claude hook, launcher, or real
transport adapter, and must remain disabled until W2b4 fixtures pass.

W2b4 keeps that boundary client-neutral. Its deterministic fixtures exercise v1/v2
schema modes, scoped multi-repository authorization and authority failures, native
evidence drift, exact accounting, delimiter/JSON/Unicode/CRLF/BOM/NUL framing,
exact channel limits, lifecycle/receipt terminality, source drift, concurrent fake
adapter handoff, runtime collisions/substitution/permissions, and safe interrupted
cleanup/retention. The only capability-supported canonical row is Codex
non-interactive in the devcontainer; Windows and host-POSIX client rows remain
explicitly unsupported rather than being inferred from these kernel fixtures.

Phase 4.6 measures active workspace-controlled context without activating a
client transport. It separately accounts for current verified Codex-native root
bootstrap and the resolver's JCS injected-policy envelope; raw injected bytes
remain diagnostic and are never double-counted. Run it with:

```bash
source scripts/import-workspace-env.sh devcontainer
"$M8_PYTHON" scripts/agent_context/measure_w4_context.py \
  --workspace . --captured-at 2026-07-19T15:10:00Z
```

The report keeps unsupported, limited, child-owned, and authorization-blocked
fixtures explicit rather than treating them as successful canonical delivery.
