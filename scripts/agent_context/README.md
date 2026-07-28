# Agent-context resolver and canonical Codex and Claude delivery

This package contains the active root-owned faceted resolver, signed external
authorization boundary, reviewed trust identity, delivery kernel, the canonical
Codex and Claude devcontainer non-interactive adapters, and root-only
validators. It
validates the v2 registry/index, policy units, manifests, journals, sessions,
receipts, and RFC 8785 JCS UTF-8 injected envelopes. Other client/platform rows
remain limited or unsupported as recorded by capability evidence.

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

Phase 9.2 removes the W3 compatibility adapter. The historical routing record
remains a fixture only; restoring it requires a Git rollback. Policy selection
uses the active `always`, `facets`, and explicitly selected task overlays. A
declared facet with no workspace slice is an intentional no-op, never an empty
policy file.

Phase 4.4 adds opt-in environment, testing, per-operation Git, pull-request,
release, Headroom, and cross-repository overlays. Default resolution selects
none of them. Mutating and cross-repository tasks require a single-use
externally signed capability whose launch, repository, task, operation, and
user-task hash match exactly. The canonical launcher verifies and atomically
redeems it against owner-only trust/replay stores in a filesystem tree disjoint
from the workspace (neither path may contain the other).
Manifests, sessions, and receipts retain only verified metadata provenance;
raw approval and signature content is excluded.

Phase 10 Steps 10.2--10.8 implement the W9b--W9d remediation boundaries. The
W9b external authorization verifier in
[`authorization.py`](authorization.py). It creates a launch-bound request and
accepts only an Ed25519 signature over an exact JCS payload from an
owner-controlled trust store in a disjoint external tree. It atomically consumes the
capability in an external replay store before submission and exposes only
authorization ID, issuer/key ID, payload/signature digests, issue/expiry, and
redemption ID for future manifest/session/receipt linkage. Raw approval and
signature bytes are never runtime artifacts. Canonical Codex launch is
available only for the required devcontainer non-interactive row after the
complete trust and capability preflight; Claude and unsupported rows remain
fail-closed limited/unsupported modes.

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

Phase 5 Step 5.3 keeps root `AGENTS.md` as a hand-maintained, compact Codex
bootstrap. Its static check enforces the visible version marker, canonical
workspace references, repository/task scope, no-resolver-invocation wording,
and the 2,048-byte limit:

```bash
"$M8_PYTHON" scripts/agent_context/validate_root_agents.py --workspace .
```

Phase 5 Step 5.5 keeps the tracked Claude project settings portable and
least-privilege: auto-memory is disabled, project permissions contain no allow
rules, only measured local-sensitive paths are denied, and destructive/network
actions require confirmation. Run its static check with:

```bash
"$M8_PYTHON" scripts/agent_context/validate_claude_settings.py --workspace .
```

Phase 5 Step 5.6 adds the Claude-only adapter boundary in
[`claude_adapter.py`](claude_adapter.py). Current Claude capability evidence is
`LIMITED`, so project-hook activation and real transport remain disabled; the
adapter fails before runtime creation or submission. Its synthetic fixtures
cover the future adapter seam, source hashes, and oversized-payload rejection
without truncation:

```bash
"$M8_PYTHON" -m unittest scripts.agent_context.tests.test_w5_claude_adapter -v
```

That Phase 5 seam is unchanged. Canonical Claude delivery is a separate module
added by Phase 12 below; this one still activates nothing.

Phase 6 Step 6.1 keeps the tracked Codex project configuration portable and
least-privilege: it uses on-request approval, workspace-write sandboxing,
cached search, and the unelevated Windows sandbox without model or reasoning
effort pins. Run its static check with:

```bash
"$M8_PYTHON" scripts/agent_context/validate_codex_config.py --workspace .
```

Phase 6 Steps 6.2--6.4 establish the Codex-only canonical launcher boundary.
[`codex-repo.sh`](../codex-repo.sh) and
[`codex-repo.ps1`](../codex-repo.ps1) discover the workspace only through the
exact root marker, accept a repeatable canonical set of registered direct
children and tasks, and independently prove root plus each selected child
`AGENTS.md` bytes through the installed `codex debug prompt-input` mechanism.
Codex's current instruction wrapper is accepted only when it contains the
exact source once; accounting includes the selected execution directory's
active native instruction once. They pass only the resolver's exact JCS
envelope through the verified `developer_instructions` channel. Mutating and
multi-repository requests use a workspace-relative signed capability whose
trust anchor and replay state remain in an owner-only tree disjoint from the
workspace. The reviewed identity binds the Codex wrapper and the Node runtime
that executes it, Python, platform/configuration inputs, all selected Git
trees, and every critical root file. The shared validator recomputes that full
identity for production preflight/state transitions as well as offline audit.
Traversal, duplicate identifiers, symlinked children/instructions, missing
direct `.git`, source/config/client/trust drift, and invalid authorization
records fail before `codex exec`. The adapter delegates runtime state,
source-drift checks, shared strict validation, collision handling, and the
hash-chained `SUBMISSION_STARTED`/`COMPLETED`/`EXECUTION_AMBIGUOUS` lifecycle
to the kernel; no printed/model response is treated as delivery proof. A
`COMPLETED` receipt means client success and framing/linkage validation, not
model retention or exactly-once external effects.

Phase 7 adds a root-only control-plane validator. Its default strict pass reads
tracked workspace inputs only and never checks out, runs, or interprets child
CI/tests. Missing child checkouts or `AGENTS.md` files are static diagnostics.
The optional manifest/envelope/session/receipt arguments validate an existing
delivery generation's exact JCS framing and linkage; they do not invoke an
agent or create runtime state:

```bash
"$M8_PYTHON" scripts/agent_context/validate_workspace.py --workspace .
"$M8_PYTHON" -m unittest scripts.agent_context.tests.test_w7_validate_workspace -v
```

The Phase 7 migration guard is intentionally narrow: it checks the portable
root agent/configuration files, rejects direct cross-agent imports and
prohibited `co-authored-by` metadata, and confirms the existing ignored
TODO-plan hook protection. It does not add generic secret detection; dedicated
secret-scanning tooling remains responsible for that concern.

```bash
"$M8_PYTHON" scripts/agent_context/validate_migration_guards.py --workspace .
```

Phase 10 Step 10.1 freezes the rejection-remediation decisions in a tracked
contract and closed finding register. Its validator checks the exact 11-finding
severity/owner/step mapping, capability ceiling, both audit digests, named
negative tests and closure artifacts, and the separate ZIP limitation. Ignored
audit inputs are optional in a clean checkout but must match their frozen hash
when present:

```bash
"$M8_PYTHON" scripts/agent_context/validate_w9a_contract.py --workspace .
"$M8_PYTHON" -m unittest scripts.agent_context.tests.test_w9a_contract -v
```

Passing W9a validation does not close a finding or enable canonical delivery.

Phase 7.5 preserves a reviewed, tracked baseline for the four workspace-owned
Codex fixtures that can be measured without a child checkout or a new
authorization record. It performs two independent measurements and compares
their selected policy paths, source hashes, envelope/manifest hashes, and byte
accounting to that baseline. Hard-limit overflow always fails; the preferred
limit is enabled explicitly by the root CI promotion command and can be rolled
back by removing that one command-line flag.

```bash
"$M8_PYTHON" scripts/agent_context/budget_promotion.py --workspace . --enforce-preferred
```

Phase 8 freezes the standalone child instruction template and the exact
C01--C16 three-path allowlists in the root-owned child rollout contract. The
validator checks the closed record without requiring child clones; the focused
fixture rehashes each pending classified input and validates any completed
boundary's three-file local owner, plus parent-found optional enhancement and
parent-absent local-only selection for Codex and Claude. It does not run child
CI or authorize any child edit:

```bash
"$M8_PYTHON" -m unittest scripts.agent_context.tests.test_w8_child_rollout -v
```

```bash
scripts/codex-repo.sh --repository auth-sdk-m8 "inspect the repository"
scripts/codex-repo.sh --repository auth-sdk-m8 --repository media-sdk-m8 \
  --task cross-repository --operation analyze \
  --prepare-authorization-request "compare both SDKs"
# An external owner signs the exact request without exposing its private key.
scripts/codex-repo.sh --repository auth-sdk-m8 --repository media-sdk-m8 \
  --task cross-repository --operation analyze \
  --authorization .workspace/authorizations/signed-cross-sdk.json \
  --authorization-external-root /owner-controlled/authorization \
  --authorization-trust-store /owner-controlled/authorization/trust-store.json \
  --authorization-replay-store /owner-controlled/authorization/replay \
  "compare both SDKs"
# Explicit fresh invalidates the named completed runtime before generation zero.
scripts/codex-repo.sh --repository auth-sdk-m8 \
  --fresh .workspace/.runtime/session-previous "start a replacement thread"
"$M8_PYTHON" -m unittest scripts.agent_context.tests.test_w6_codex_adapter -v
```

Phase 12 Steps 12.1--12.3 add the parallel Claude boundary. Step 12.1 froze the
installed-client capability matrix and Step 12.2 the out-of-band
`claude-loopback-model-input-capture` native-load mechanism; both are tracked
under [`fixtures/evidence`](fixtures/evidence) and pinned by the adapter and by
root workspace validation.
[`claude_delivery_adapter.py`](claude_delivery_adapter.py) and
[`claude-repo.sh`](../claude-repo.sh) reuse the same resolver, kernel,
authorization boundary, shared validator, and trust identity as the Codex path.
The launcher proves the devcontainer, the exact marker root, the pinned
evidence, the installed client identity, the reviewed project settings layer,
the client's own recorded project trust, and each selected direct child with its
`.git` and `CLAUDE.md`; it then enumerates the active instruction sources from a
real capture, proves every injected source absent from that same capture, and
compares the manifest with that evidence in both directions before omitting an
injected entry. There is no Windows wrapper because no row outside this
devcontainer is evidenced. A child launch scope requires that project's own
recorded trust and otherwise fails with `E_TRUST`; a launcher never grants its
own trust.

Channel selection is by `model_visible_total`, never by envelope size: the
shared validator is the budget oracle, the hook row's 10,000-byte ceiling is a
total rather than an envelope allowance, and an over-budget generation falls
through to the verified `--append-system-prompt` full-content channel or fails
closed. Until Step 12.4 freezes the byte-exact hook round trip and registers
exactly one injection authority, the hook row is rejected with a recorded reason
and no hook is configured; while any `additionalContext` hook is registered the
wrapper channel is refused, because bypassing the hook would inject twice.

```bash
scripts/claude-repo.sh --repository fa-auth-m8 "inspect the repository"
# --project selects the launch directory; it must be a selected repository and
# must already be trusted by a recorded human decision.
scripts/claude-repo.sh --repository fa-auth-m8 --project fa-auth-m8 \
  "inspect the repository"
"$M8_PYTHON" -m unittest scripts.agent_context.tests.test_w12_claude_adapter -v
```

The faceted resolver CLI in [`resolve-context.py`](resolve-context.py) remains
an explicit inspection/fixture entry point. It requires a faceted v2
registry/index and policy metadata fixture, then accepts repeatable
repository, task, exclusion, operation, and authorization arguments. Its
canonical `resolution` output includes the manifest and envelope; `manifest`
and `envelope` formats are also available. Native sources need current verified
native evidence. Injected sources need evidence that native discovery is
disabled and an exact-once handoff is proven for the requested generation;
runtime enforcement is provided by the active client-neutral kernel in
[`delivery_kernel.py`](delivery_kernel.py). It owns only isolated runtime
state, source-drift rehashing, receipt transitions, stable exit mapping, and a
fake exact-payload adapter seam; the Codex and Phase 12 Claude adapters are the
only capability-supported real transports, and every other client/platform row
remains fail-closed.

W2b4 keeps that boundary client-neutral. Its deterministic fixtures exercise
strict faceted-schema failures, scoped multi-repository authorization and authority failures, native
evidence drift, exact accounting, delimiter/JSON/Unicode/CRLF/BOM/NUL framing,
exact channel limits, lifecycle/receipt terminality, source drift, concurrent fake
adapter handoff, runtime collisions/substitution/permissions, and safe interrupted
cleanup/retention. Those fixtures were written for the Codex non-interactive
devcontainer row and Phase 12 adds the Claude devcontainer rows on their own
evidence; Windows and host-POSIX client rows remain explicitly unsupported
rather than being inferred from these kernel fixtures.

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
