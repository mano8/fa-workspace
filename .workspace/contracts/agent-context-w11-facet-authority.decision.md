# Agent context W11 facet-authority decision

**Decision version:** `1.0.0`

**Frozen:** 2026-07-27

**Scope:** Phase 11 Step 11.1. Binding input for Steps 11.4 and 11.5 only.

**Status:** `DECIDED`. This record fixes the identity, category, and authority
tier of the `auth-security` facet policy. It drafts no policy text, changes no
mapping, closes no other step, and grants no authorization.

## 1. Decision

The `auth-security` facet is a workspace-tier domain facet, not a second
`security`-tier unit:

| Field | Frozen value |
|---|---|
| Facet key | `auth-security` |
| Unit id | `facet.domain.auth-security` |
| Category | `domain` (precedent `facet.domain.auth-client`) |
| Path | `.workspace/policies/facets/domain-auth-security.md` |
| `authority_tier` | `workspace` |
| `scope` | `{"repository_id": "$workspace", "prefix": "."}` |
| `invariant_ids` | `SEC-NO-SECRET-DISCLOSURE`, `SEC-NO-TRACKED-SECRETS`, `SEC-VALIDATE-UNTRUSTED-INPUT` |
| `conflicts_with` | empty |
| `may_override` | empty |
| `required` | `false` |
| `capabilities_granted` | empty |

Non-waivable security force stays with `always.security` at tier `security`.
The new unit carries auth-specific handling guidance that *references* the
canonical invariants in [`architecture.md`](../architecture.md); it never
redefines them.

## 2. Frozen inputs

Tracked authority, by SHA-256:

- `.workspace/invariants.json` —
  `bd53750ac750b1f21204505c84d2779622de6b6e4a698080e315d3da071f495e`
- `.workspace/policy.index.json` —
  `9b88858a809c28012539ca260109e8c534c36381661fadcd1b3b728312c5540e`
- `.workspace/policy.metadata.json` —
  `6a8a03d2c7e85d34aae44b3f7f3a30e775b9b5974d99342890aa70be18fe0705`
- `.workspace/policies/always/security.md` —
  `f73a5e520bc237bb70851569ef039a549db65c28a580b2cdb95f5b9db11525f2`
- `.workspace/contracts/agent-context-w2a.contract.md` (version 2.1.1) —
  `acdfa4503da251548893e2fd824e21406c2663a24438de0a84be8aa37cb5b7fd`

The Phase 11 drafting brief
(`ffde58a2c5da3fe458b7b142335c7b7824f482f0323b57d13de3146753d4a542`) and the
2026-07-24 resolved-configuration snapshot
(`72322ddc22b403a7eafa63076f6f32dc313cc2ada6f4bde4260ba2c4b53c52c1`) are
untracked informational inputs. They are not authority; W2a Section 3.4 and the
tracked files above govern.

## 3. Rationale

W2a Section 3.4 orders authority `security`, `workspace`, `task`, `repository`
and states that lower authority cannot weaken a higher tier. Two probes of the
active root-owned stack, run on this tree, decide the tier:

1. **The schema permits the alternative.** `w2b1.validate_policy_unit` accepts a
   non-`always` unit at `authority_tier: "security"`; `AUTHORITY_TIERS` is a
   flat set with no `always`-only restriction. The alternative's stated
   precondition is therefore satisfiable — but schema permission is not an
   authority-model safeguard, so it does not by itself justify the tier.
2. **The alternative removes a real resolver guarantee.** In
   `resolve_context._validate_authority`, an override is rejected only when the
   declaring unit sits at a strictly lower tier. A unit at tier `security`
   declaring `may_override: ["always.security"]` is accepted; the identical unit
   at tier `workspace` fails with `E_AUTHORITY` (`lower authority cannot
   override always.security`). Placing an optional, repository-selected facet at
   tier `security` would make weakening the non-waivable security owner a
   declarable, validator-passing state.

Two further properties confirm the choice:

- Tier does not confer non-waivability. Exclusion refusal keys on `required`,
  not on `authority_tier`, so a `required: false` unit at tier `security` would
  advertise an authority it does not have while remaining excludable.
- `authority_tier` is carried per entry into the manifest and envelope, so a
  mislabelled facet would misreport authority to every downstream reviewer and
  parity check.

At tier `workspace` the facet still reaches every carrier that declares the
label — `auth-sdk-m8`, `fa-auth-m8`, and `fastapi-m8` — because facet selection
is by registry label, not by tier. Nothing about the intended content requires
the higher tier.

## 4. Binding consequences

**Step 11.4** drafts `.workspace/policies/facets/domain-auth-security.md` as
repo-neutral auth-*handling* guidance spanning SDK, framework, and service
carriers. It composes with `always.security` and must not restate, weaken,
qualify, or claim exceptions to the three `SEC-*` invariants, and must not
carry any single carrier's token or session schema. It cites invariants by
relative link only, never an absolute `/.workspace/...` path
([`PORTABLE-NO-WORKSPACE-PATHS`](../architecture.md#portable-no-workspace-paths)).

**Step 11.5** wires `"auth-security": ["facet.domain.auth-security"]` into
`policy.index.json.facets` and adds exactly one `policy.metadata.json` unit with
the Section 1 field values. No `security`-tier unit, no second registry, and no
duplicated invariant definition is created.

Any deviation from Section 1 by 11.4 or 11.5 requires a superseding decision
record; it is not resolved by drafting or wiring choices.

## 5. Rejected alternative

A `security`-tier `security-auth.md` unit is rejected for the Section 3
reasons. Its schema precondition was confirmed satisfiable and is recorded
above so the rejection rests on the authority model rather than on an untested
assumption.

## 6. Invalidation

This decision is invalidated, and must be reissued before 11.4 or 11.5
proceeds, by a change to any Section 2 tracked input hash, to `AUTHORITY_TIERS`
or `TIER_ORDER`, to `_validate_authority` or the exclusion rule, or to the W2a
Section 3.4 authority model.
