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

The W3 migration makes the v2 registry and tagged transitional policy index
authoritative. It retains the current ordered path arrays only as
`compatibility_bundles`; each repository selects one with
`migration.v1_bundle`. The default resolver mode returns those exact paths and
does not activate faceted policy units, transport, or runtime state:

```bash
"$M8_PYTHON" scripts/agent_context/resolve-context.py \
  --registry .workspace/repo-types.json \
  --policy-index .workspace/policy.index.json \
  --repository auth-sdk-m8
```

Validate the coupled active workspace files with:

```bash
"$M8_PYTHON" scripts/agent_context/validate_w2b1.py workspace-v2 \
  .workspace/repo-types.json --policy-index .workspace/policy.index.json
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
