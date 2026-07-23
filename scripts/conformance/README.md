# Cross-repository authorization conformance harness

Workspace-owned (`fa-workspace`) realisation of the Phase 5 controller bullet
**“Run local-package matrix in dependency order and prove issuer/consumer parity
for all valid and invalid claim combinations, including the
concurrent-login-during-downgrade generation race and the durable-outbox
propagation.”**

Canonical verification owner:
[`50-verification-conformance.md`](../../.workspace/plans/stack/todo/auth-role-superuser-consistency/50-verification-conformance.md)
§6 *Cross-repository integration* (`TEST-CROSS-01`), driven by the SDK-owned
checksum-verified fixture matrix (`FIXTURE-01`).

## What it proves

1. **Local-package matrix (dependency order).** `auth_sdk_m8` → `fastapi_m8` →
   `fa-auth-m8`/examples resolve to their in-workspace source at the intended
   versions (SDK `3.1.0`, fastapi `4.1.0`, issuer `2.0.0`), and each declared
   dependency floor admits the installed platform version. A shadowing PyPI
   copy, a drifted version, or an excluding floor fails closed.
2. **Issuer/consumer parity.** For every role/flag row, every current/required
   role pair, and every canonical signed JWT (valid **and** invalid), the
   issuer decision (the SDK predicate the issuer applies before signing) and the
   consumer decision (a real `fastapi_m8` guard over a token the consumer
   validated through the SDK `TokenValidator`) agree, and agree with the
   fixture’s canonical expectation. Inconsistent claim pairs are rejected
   identically on both sides.
3. **Concurrent-login-during-downgrade generation race.** At the consumer seam,
   a session minted against a superseded `auth_generation` is never served, in
   either interleaving; a fresh session at the new generation is.
4. **Durable-outbox propagation.** The `<` / `==` / `>` generation watermark
   rule with durable `event_id` dedup (v2) and conservative eviction (v1) is
   applied as the outbox delivers events to the consumer.
5. **API-key principal conformance (§3.12).** For every fixture
   role/flag/access-mode pair the issuer-local principal (the SDK principal
   fa-auth builds from its DB read) and the remote principal (an introspection
   reply parsed by the **real** `fastapi_m8` introspection client) reach
   **identical** post-admission decisions, delegating to the single canonical
   `has_api_key_capability`; the intentional admission asymmetry (no audience ⇒
   remote inactive) holds. It also proves, against the shipped client:
   `429` quota relay preserving `Retry-After`; a `writer→reader` downgrade
   denies the next remote request (no positive caching — two requests, two
   introspections); introspection outage / malformed / unknown-schema /
   audience-mismatch all fail closed (`503`) with no fallback to bare key
   validity; every inactive cause is externally indistinguishable (one generic
   denial); the capability ceiling (`require_api_key_role` above `WRITER`
   raises — no admin/superuser API-key dependency exists, a dual-evidence
   superuser owner is still capped at writer); and the static route audit flags
   a capability route wired to the bare key dependency.

## Ownership boundary

The harness imports **platform** packages only (`auth_sdk_m8`, `fastapi_m8`). It
never imports a **service** source module (`fa-auth-m8`), so it honours
`ARCH-LAYER-DIRECTION` and the no-cross-service-source-import rule in
[`policies/tasks/cross-repository.md`](../../.workspace/policies/tasks/cross-repository.md).
The issuer and consumer *halves* are each independently proven inside their own
repositories’ `test_*fixture_matrix_contract.py` suites; this harness proves the
two halves resolve **identically**. Issuer/example metadata (version, floors) is
read from source-of-truth files, not imported.

It is intentionally **not** part of `workspace-policy-lint` (which stays
child-agnostic and installs no platform packages). It runs in its own
[`cross-repo-conformance`](../../.github/workflows/cross-repo-conformance.yml)
workflow and locally.

## Running it

Install the local packages in dependency order, then run:

```bash
pip install ./auth-sdk-m8[security,fastapi,events,config,observability]
pip install ./fastapi-m8
python -m scripts.conformance.run_conformance          # report + fail-closed exit
python -m unittest discover -s scripts/conformance/tests -v
```

Against the repository’s shared virtualenv (packages already installed):

```bash
.shared-venv/bin/python -m scripts.conformance.run_conformance
```
