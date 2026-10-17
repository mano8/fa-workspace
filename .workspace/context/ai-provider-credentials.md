# AI Provider Credentials and Execution Trust

Canonical owner of the ratified credential-custody, data-boundary and
job-context rules for the AI platform (`ai-gateway-m8`, `ai-sdk-m8`,
`doctools-m8` and their consumers). Ratified across `R-07`, `R-10`, `D-02`,
`D-08`, `D-21` and `C-03` of
`.workspace/plans/stack/todo/ai-gateway-sdk-plan-2026-10-08.md` and the media
plan's `D-21` (gitignored; not the authority — this file is).

Workspace invariant: [`CFG-SINGLE-WORKSPACE-OWNER`](../architecture.md#cfg-single-workspace-owner)
— this file is the sole canonical owner of the rules below; no child
repository or agent-specific directory may keep a competing copy.

## Trust rule (D-02)

Only `ai-gateway-m8` retrieves or decrypts provider credentials.
`media-service-m8`, `media-worker-m8`, `doctools-m8`, `ai-sdk-m8` and
`astro-media-m8` never receive a provider key, KEK, or Vault token.

## Credential storage (R-10)

```text
database + local            default
database + vault_transit    recommended hardened mode
vault KV                    selectable, sequenced last, with reconciliation
```

## Data classes and provider boundaries (D-08)

Every execution carries `data_class ∈ {public, internal, restricted}` in its
signed job context; every provider carries `boundary ∈ {local, external}`.
Ownership is split: media-service owns *classification* (derives and signs
`data_class`, may apply a local deny-list); the gateway owns *policy
enforcement*, fail-closed, from the signed context — `restricted` → `local`
provider or the same tenant's/user's BYOK; `internal` → `local` or BYOK;
`public` → any enabled provider. The ratified default never lets `internal`
reach an `external` provider on a global platform credential; widening it is
a future, explicit operator exception, never a default. `rerank` is
categorically `local`-only at execution resolution, hard-wired, not
widenable by policy. Classification is re-derived from the object's live
state at every signing, never copied from a run snapshot.

## Job-context and signed-object contract (C-03, Ed25519)

One signed-object rule, implemented once in `ai_sdk_m8.signed` and reused by
`doctools-m8`: signed bytes = `UTF-8(domain_tag) ‖ 0x00 ‖ JCS(payload)`,
Ed25519, with a verifier-supplied domain tag, strict canonical parsing and a
size cap before any trust decision. A job context is single-use
(`max_uses = 1`), minted from live state immediately before the call it
authorizes, bound to the presenting client (`azp`) and never queued or
minted at enqueue.

## Capability-scope model (R-07)

Service clients hold capability-precise scopes (`execute:ocr`,
`execute:embedding`, `execute:rerank`, `execute:structured_output`,
`job-context:issue`). Every service execution carries a signed context;
there is no on-behalf-of header.

## Network posture (D-21)

Only the gateway image's web and scheduler run-modes hold AI credentials and
reach local AI runtimes (`ai_net`); no media service or worker may join that
network, so nothing reaches a model server except through the gateway. Every
other service with generic internet egress is explicitly justified and
listed; destination-restricted egress is not claimed by this topology alone.

## Does not own

- Version-source mechanisms: [version sources](version-sources.md).
- Environment profile rules and resolved `M8_*` tooling: [environment
  policy](env.md).
- Object-storage backend contract: [object storage](object-storage.md).
- Debian patch-layer form: [debian patch layer](debian-patch-layer.md).
- Release-cascade order and touchpoints: [dependency
  cascade](dependency-cascade.md).
- Authorization, scope, and capability-delivery rules: the
  [agent-context contract](../contracts/agent-context-w2a.contract.md) (W2a).
