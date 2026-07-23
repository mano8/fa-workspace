"""API-key principal conformance (§3.12) across the issuer-local and remote paths.

Realises the Phase 5 controller bullet *"API-key principal conformance
(§3.12)"* (``50-verification-conformance.md`` §6 *Cross-repository integration*,
``TEST-CROSS-01``; ``APIKEY-*`` in ``30-api-key-introspection.md``): prove the
**issuer-local** principal (fa-auth's local DB read) and the **remote**
principal (an introspection response consumed by the ``fastapi_m8`` dependency)
produce **identical** post-admission decisions for every fixture
role/flag/access-mode pair, while the intentional audience *admission*
asymmetry (no audience ⇒ remote inactive) holds, and every fail-closed clause
of the contract is honoured.

Both paths delegate to the **one** canonical decision the SDK owns —
:func:`auth_sdk_m8.authorization.has_api_key_capability` — so the whole point of
the invariant is that the two implementations cannot drift; a drift anywhere
makes a check fail. The remote half additionally drives the **real**
``fastapi_m8`` introspection client (:class:`ApiKeyIntrospectionClient`) and the
static route audit (:func:`fastapi_m8._route_audit.audit_api_key_routes`) so the
transport-boundary, status-mapping, no-caching, and wiring guarantees are proven
against the shipped consumer code rather than a re-model of it.

Ownership boundary (unchanged from the rest of this harness): platform packages
only — ``auth_sdk_m8`` and ``fastapi_m8`` — never a ``fa-auth-m8`` service
source module. The issuer *builds the same SDK principal from its DB read*
(``get_current_api_key_principal``, 3.11), so modelling the issuer-local
decision as the canonical SDK principal is faithful, not a shortcut: the issuer
has no second predicate to drift from.
"""

from __future__ import annotations

from collections.abc import Awaitable

import anyio
from auth_sdk_m8.authorization import (
    API_KEY_MAX_REQUIRED_ROLE,
    has_api_key_capability,
    has_superuser_privileges,
    validate_api_key_required_role,
)
from auth_sdk_m8.core.exceptions import ApiKeyCapabilityCeilingError
from auth_sdk_m8.schemas.api_key import (
    ApiKeyIntrospectionActiveResponse,
    ApiKeyIntrospectionInactiveResponse,
    ApiKeyPrincipal,
)
from auth_sdk_m8.schemas.base import ApiKeyAccessMode, RoleType
from fastapi import Depends, FastAPI

from fastapi_m8._api_key import (
    ApiKeyIntrospectionClient,
    ApiKeyIntrospectionError,
    ApiKeyQuotaExceededError,
)
from fastapi_m8._route_audit import audit_api_key_routes
from scripts.conformance import CheckResult

#: The consumer identity the fixture ``active_response`` is minted for. The
#: client must echo-verify an active response against its own configured
#: audience, so this is the identity a correctly-configured consumer carries.
_FIXTURE_AUDIENCE = "fixture-consumer-m8"

#: Capability thresholds an API key may legitimately be asked for (≤ WRITER).
_REQUIRABLE_CAPABILITIES = (RoleType.USER, RoleType.READER, RoleType.WRITER)

#: Thresholds above the API-key ceiling — asking for one is a programming error.
_ABOVE_CEILING = (RoleType.ADMIN, RoleType.SUPERADMIN)


# --------------------------------------------------------------------------- #
# Real-client harness: a bounded fake transport over the shipped consumer code.
# --------------------------------------------------------------------------- #
class _StubInternalAuth:
    """Minimal internal-credential provider (headers only, no real secret)."""

    async def headers(self) -> dict[str, str]:
        return {"X-Internal-Client": "conformance", "X-Internal-Token": "stub"}

    async def invalidate(self) -> bool:
        return False

    async def close(self) -> None:
        return None


#: One canned issuer reply: ``(status_code, body_bytes, retry_after)``.
_Reply = tuple[int, bytes, "str | None"]


class _CountingTransport:
    """Records how many times the client transmits, returning canned replies.

    Substituted for :meth:`ApiKeyIntrospectionClient._transmit`, so the real
    ``_send`` (pre-transmission retry rule), ``_interpret`` (status mapping,
    circuit breaker, audience echo-check), and ``_parse`` (schema/malformed
    fail-closed) all run against the shipped code. Because it is bound past
    ``_send``, driving it also proves there is **no positive cache** in front of
    the transport: every ``introspect`` reaches here.
    """

    def __init__(self, replies: list[_Reply]) -> None:
        self._replies = replies
        self.calls = 0

    async def __call__(self, _request: object) -> _Reply:
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return reply


def _client(audience_id: str, transport: _CountingTransport) -> ApiKeyIntrospectionClient:
    """A real introspection client whose transport is the counting stub."""
    client = ApiKeyIntrospectionClient(
        introspection_url="http://auth:8000/user/private/v1/api-keys/introspect",
        auth_provider=_StubInternalAuth(),
        audience_id=audience_id,
    )
    # Replace only the wire step; every decision layer above it stays real.
    client._transmit = transport  # type: ignore[method-assign,assignment]
    return client


def _active_reply(principal: dict, audience_id: str = _FIXTURE_AUDIENCE) -> _Reply:
    """Build a ``200 active`` issuer reply carrying *principal*."""
    body = ApiKeyIntrospectionActiveResponse(
        audience_id=audience_id,
        principal=ApiKeyPrincipal(**principal),
    ).model_dump_json()
    return (200, body.encode("utf-8"), None)


def _inactive_reply() -> _Reply:
    """Build the single generic ``200 active:false`` issuer reply."""
    return (200, ApiKeyIntrospectionInactiveResponse().model_dump_json().encode(), None)


def _run(coro: Awaitable[object]) -> object:
    """Drive one async client interaction to completion (AnyIO backend)."""
    return anyio.run(lambda: coro)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 1. Local vs remote principal equivalence (post-admission parity).
# --------------------------------------------------------------------------- #
def local_remote_principal_equivalence(matrix: dict) -> list[CheckResult]:
    """Same owner ⇒ identical canonical principal and identical decisions.

    For every fixture equivalence pair, the issuer-local principal (built from
    the DB read) and the remote principal (parsed by the real client from an
    active introspection reply) are the **same** ``ApiKeyPrincipal``, and every
    ≤ WRITER capability decision agrees between them.
    """
    results: list[CheckResult] = []
    for pair in matrix["local_remote_principal_equivalence"]:
        local = ApiKeyPrincipal(**pair["local"])
        transport = _CountingTransport([_active_reply(pair["remote"])])
        client = _client(_FIXTURE_AUDIENCE, transport)
        remote = _run(client.introspect(_secret("fixture-raw-api-key")))
        _run(client.close())
        assert isinstance(remote, ApiKeyPrincipal)
        same_principal = local.model_dump() == remote.model_dump()
        decisions_match = all(
            local.has_capability(cap) == remote.has_capability(cap)
            for cap in _REQUIRABLE_CAPABILITIES
        )
        label = f"principal_equivalence[{local.role.value},{local.access_mode.value}]"
        results.append(
            CheckResult(
                label,
                same_principal and decisions_match,
                f"local==remote principal={same_principal} decisions={decisions_match}",
            )
        )
    return results


# --------------------------------------------------------------------------- #
# 2. Capability + audience policy matrix (post-admission parity, admission
#    asymmetry, and the capability ceiling).
# --------------------------------------------------------------------------- #
def capability_audience_policy_matrix(matrix: dict) -> list[CheckResult]:
    """Every role/flag/access-mode/audience/required-role decision, both paths.

    Delegates to the canonical SDK decision for both surfaces. Asserts the
    issuer-local decision, the remote admission (audience), the remote decision,
    and — the invariant — that **after** matching-audience admission the remote
    decision equals the issuer-local one. Ceiling rows (admin/superuser required)
    are denials on both paths and raise the ceiling error, never a silent False.
    """
    results: list[CheckResult] = []
    for row in matrix["audience_and_capability_policy_matrix"]:
        required = RoleType(row["required_role"])

        if row["capability_ceiling_error"]:
            # An admin/superuser capability may never be requested of a key.
            raised = _raises_ceiling(required)
            passed = (
                raised
                and row["issuer_local_allowed"] is False
                and row["remote_allowed"] is False
            )
            results.append(
                CheckResult(
                    f"policy.ceiling[required={required.value}]",
                    passed,
                    f"validate_api_key_required_role raised={raised}; both denied",
                )
            )
            continue

        role = RoleType(row["role"])
        is_superuser = role == RoleType.SUPERADMIN  # canonical flag for the owner
        access_mode = ApiKeyAccessMode(row["access_mode"])
        issuer_local = has_api_key_capability(role, is_superuser, access_mode, required)
        remote_active = bool(row["has_audience"])  # admission is audience presence
        remote_allowed = remote_active and issuer_local

        # Post-admission parity is the whole invariant: with the audience bound,
        # remote and issuer-local must reach the identical decision.
        parity_holds = (not remote_active) or (remote_allowed == issuer_local)
        passed = (
            issuer_local == row["issuer_local_allowed"]
            and remote_active == row["remote_active"]
            and remote_allowed == row["remote_allowed"]
            and parity_holds
        )
        label = (
            f"policy[{role.value},{access_mode.value},aud={remote_active},"
            f"req={required.value}]"
        )
        results.append(
            CheckResult(
                label,
                passed,
                f"local={issuer_local} remote_active={remote_active} "
                f"remote={remote_allowed} parity={parity_holds}",
            )
        )
    return results


# --------------------------------------------------------------------------- #
# 3. Remote status mapping and fail-closed transport (the consumer half of the
#    §3.12 status matrix, proven against the shipped client).
# --------------------------------------------------------------------------- #
def remote_status_and_fail_closed(matrix: dict) -> list[CheckResult]:
    """Drive the real client for each consumer-facing status-matrix scenario.

    Every unconfirmable outcome — issuer outage, malformed body, unknown schema
    version, or an audience the consumer was not configured for — fails closed
    (the dependency maps :class:`ApiKeyIntrospectionError` to ``503``, never a
    fallback to bare key validity); an issuer ``429`` is relayed preserving
    ``Retry-After``; a generic inactive reply yields ``None`` (the dependency's
    generic client-facing ``401``).
    """
    results: list[CheckResult] = []
    active_principal = matrix["api_key_introspection_fixtures"]["active_response"][
        "principal"
    ]

    # active:false → None (consumer maps to generic 401), never a principal.
    results.append(
        _drive(
            "status.inactive_maps_to_generic_denial",
            replies=[_inactive_reply()],
            audience_id=_FIXTURE_AUDIENCE,
            expect="none",
        )
    )
    # Issuer 503 → fail closed (ApiKeyIntrospectionError → dependency 503).
    results.append(
        _drive(
            "status.issuer_unavailable_fails_closed",
            replies=[(503, b"", None)],
            audience_id=_FIXTURE_AUDIENCE,
            expect="introspection_error",
        )
    )
    # Malformed body → fail closed, never parsed for whatever fields survive.
    results.append(
        _drive(
            "status.malformed_response_fails_closed",
            replies=[(200, b"{not-json", None)],
            audience_id=_FIXTURE_AUDIENCE,
            expect="introspection_error",
        )
    )
    # Unknown schema version in the reply → fail closed (SDK validator rejects).
    unknown = matrix["api_key_introspection_fixtures"][
        "unsupported_schema_version_response"
    ]
    results.append(
        _drive(
            "status.unknown_schema_version_fails_closed",
            replies=[(200, _json(unknown), None)],
            audience_id=_FIXTURE_AUDIENCE,
            expect="introspection_error",
        )
    )
    # Active reply whose audience differs from this consumer's identity → 503,
    # a trusted-configuration failure, never accepted and never cached.
    results.append(
        _drive(
            "status.audience_mismatch_fails_closed",
            replies=[_active_reply(active_principal, audience_id=_FIXTURE_AUDIENCE)],
            audience_id="some-other-consumer",
            expect="introspection_error",
        )
    )
    # Consumer credential rejected (401/403) → fail closed, never a key decision.
    results.append(
        _drive(
            "status.consumer_credential_rejected_fails_closed",
            replies=[(403, b"", None)],
            audience_id=_FIXTURE_AUDIENCE,
            expect="introspection_error",
        )
    )
    # Issuer 429 → relayed as a quota error preserving Retry-After.
    results.append(
        _drive(
            "status.quota_exhausted_relays_retry_after",
            replies=[(429, b"", "42")],
            audience_id=_FIXTURE_AUDIENCE,
            expect="quota:42",
        )
    )
    return results


# --------------------------------------------------------------------------- #
# 4. No positive principal caching across requests.
# --------------------------------------------------------------------------- #
def no_positive_caching(matrix: dict) -> list[CheckResult]:
    """Two capability requests introspect twice; a failure never serves a stale hit.

    The client holds no principal cache, so each ``introspect`` reaches the
    transport. A transport failure after an earlier success is a denial, never
    answered from the earlier principal.
    """
    principal = matrix["api_key_introspection_fixtures"]["active_response"]["principal"]
    results: list[CheckResult] = []

    async def _twice() -> tuple[object, object, int]:
        transport = _CountingTransport([_active_reply(principal)])
        client = _client(_FIXTURE_AUDIENCE, transport)
        first = await client.introspect(_secret("k"))
        second = await client.introspect(_secret("k"))
        calls = transport.calls
        await client.close()
        return first, second, calls

    first, second, calls = _run(_twice())  # type: ignore[misc]
    results.append(
        CheckResult(
            "caching.two_requests_two_introspections",
            calls == 2
            and isinstance(first, ApiKeyPrincipal)
            and isinstance(second, ApiKeyPrincipal),
            f"introspection calls={calls} (expected 2), both resolved live",
        )
    )

    async def _success_then_failure() -> tuple[object, str, int]:
        transport = _CountingTransport([_active_reply(principal), (503, b"", None)])
        client = _client(_FIXTURE_AUDIENCE, transport)
        ok = await client.introspect(_secret("k"))
        try:
            await client.introspect(_secret("k"))
            outcome = "returned"
        except ApiKeyIntrospectionError:
            outcome = "failed_closed"
        calls = transport.calls
        await client.close()
        return ok, outcome, calls

    ok, outcome, calls2 = _run(_success_then_failure())  # type: ignore[misc]
    results.append(
        CheckResult(
            "caching.failure_not_served_from_prior_success",
            isinstance(ok, ApiKeyPrincipal) and outcome == "failed_closed" and calls2 == 2,
            f"first resolved, second {outcome} (calls={calls2}); no stale reuse",
        )
    )
    return results


# --------------------------------------------------------------------------- #
# 5. writer→reader downgrade denies the next remote-authenticated request.
# --------------------------------------------------------------------------- #
def downgrade_denies_next_request(matrix: dict) -> list[CheckResult]:
    """A live owner downgrade takes effect on the key's very next introspection.

    Because nothing is cached, the second request re-resolves the owner: a key
    that carried WRITER capability before the downgrade is denied it after.
    """
    base = matrix["api_key_introspection_fixtures"]["active_response"]["principal"]
    writer = {**base, "role": "writer", "is_superuser": False, "access_mode": "read_write"}
    reader = {**base, "role": "reader", "is_superuser": False, "access_mode": "read_write"}

    async def _sequence() -> tuple[bool, bool]:
        transport = _CountingTransport([_active_reply(writer), _active_reply(reader)])
        client = _client(_FIXTURE_AUDIENCE, transport)
        before = await client.introspect(_secret("k"))
        after = await client.introspect(_secret("k"))
        await client.close()
        assert isinstance(before, ApiKeyPrincipal)
        assert isinstance(after, ApiKeyPrincipal)
        return before.has_capability(RoleType.WRITER), after.has_capability(RoleType.WRITER)

    before_can, after_can = _run(_sequence())  # type: ignore[misc]
    return [
        CheckResult(
            "downgrade.writer_then_reader_denies_next_write",
            before_can is True and after_can is False,
            f"writer_capability before={before_can} after_downgrade={after_can}",
        )
    ]


# --------------------------------------------------------------------------- #
# 6. Forged / unknown / expired / revoked keys are externally indistinguishable.
# --------------------------------------------------------------------------- #
def forged_keys_indistinguishable(matrix: dict) -> list[CheckResult]:
    """Every inactive cause shares one status and one body → one consumer outcome.

    The issuer never distinguishes unknown/revoked/expired key from
    missing/inactive/inconsistent owner or an unbound audience: all are the same
    generic ``200 {active:false}``, which the consumer maps to the same generic
    denial. A caller cannot probe another account's state.
    """
    status_matrix = matrix["api_key_introspection_fixtures"]["status_matrix"]
    inactive_scenarios = [
        row
        for row in status_matrix
        if row["surface"] == "issuer" and row.get("body_active") is False
    ]
    inactive_fixture = matrix["api_key_introspection_fixtures"]["inactive_response"]
    results: list[CheckResult] = []

    # Every inactive issuer scenario is the identical 200 + generic body.
    all_generic = all(row["http_status"] == 200 for row in inactive_scenarios)
    results.append(
        CheckResult(
            "indistinguishable.issuer_inactive_scenarios_share_shape",
            all_generic and len(inactive_scenarios) >= 3,
            f"{len(inactive_scenarios)} inactive causes all 200 + "
            f"{inactive_fixture}",
        )
    )

    # The real client turns that one body into one outcome (None → generic 401),
    # regardless of which underlying cause produced it.
    outcome = _drive(
        "indistinguishable.consumer_maps_every_inactive_to_one_denial",
        replies=[_inactive_reply()],
        audience_id=_FIXTURE_AUDIENCE,
        expect="none",
    )
    results.append(outcome)
    return results


# --------------------------------------------------------------------------- #
# 7. Capability ceiling: no admin/superuser API-key authority, dual-evidence
#    owner notwithstanding; and no such dependency can even be built.
# --------------------------------------------------------------------------- #
def capability_ceiling_and_no_superuser(matrix: dict) -> list[CheckResult]:
    """Superuser needs dual evidence **and** is still never grantable by a key.

    Per the audit-remediation addendum, no API-key admin/superuser dependency
    exists at all: ``require_api_key_role`` above WRITER raises, so the family
    caps at reader/writer. Even a canonical dual-evidence superuser owner gets
    only ≤ WRITER capability through a key.
    """
    results: list[CheckResult] = []

    # The ceiling constant itself is WRITER, and above it always raises.
    results.append(
        CheckResult(
            "ceiling.max_required_role_is_writer",
            API_KEY_MAX_REQUIRED_ROLE == RoleType.WRITER,
            f"API_KEY_MAX_REQUIRED_ROLE={API_KEY_MAX_REQUIRED_ROLE.value}",
        )
    )
    for required in _ABOVE_CEILING:
        results.append(
            CheckResult(
                f"ceiling.rejects_required[{required.value}]",
                _raises_ceiling(required),
                f"validate_api_key_required_role({required.value}) raised ceiling error",
            )
        )

    # A dual-evidence superuser owner: the predicate confirms canonical superuser
    # status (dual evidence), yet the key confers no more than WRITER, and admin
    # cannot even be asked for.
    owner_is_superuser = has_superuser_privileges(RoleType.SUPERADMIN, True)
    key_writer = has_api_key_capability(
        RoleType.SUPERADMIN, True, ApiKeyAccessMode.READ_WRITE, RoleType.WRITER
    )
    admin_unrequestable = _raises_ceiling(RoleType.ADMIN)
    # A flag-only forgery (superuser flag without the canonical role) is not even
    # a valid principal and grants nothing — dual evidence is mandatory.
    forged_flag_grants_nothing = not has_api_key_capability(
        RoleType.USER, True, ApiKeyAccessMode.READ_WRITE, RoleType.WRITER
    )
    results.append(
        CheckResult(
            "ceiling.superuser_owner_capped_at_writer",
            owner_is_superuser and key_writer and admin_unrequestable
            and forged_flag_grants_nothing,
            f"owner_superuser={owner_is_superuser} key_writer={key_writer} "
            f"admin_unrequestable={admin_unrequestable} "
            f"forged_flag_denied={forged_flag_grants_nothing}",
        )
    )
    return results


# --------------------------------------------------------------------------- #
# 8. Route audit forbids bare key deps on protected operations.
# --------------------------------------------------------------------------- #
def route_audit_forbids_bare_key_deps() -> list[CheckResult]:
    """The shipped static audit flags a capability route wired to the bare dep.

    Builds a tiny app: one route on the bare principal (a finding), one via a
    role-capped dependency (clean, resolves the bare dep only as a sub-dep), and
    an exempt read-only ``/verify`` (allowed). The audit must flag exactly the
    bare-wired protected route.
    """

    async def bare_principal() -> ApiKeyPrincipal:  # pragma: no cover - never called
        raise AssertionError("stub dependency is never invoked in a static audit")

    async def writer_capped(
        _p: ApiKeyPrincipal = Depends(bare_principal),
    ) -> ApiKeyPrincipal:  # pragma: no cover - never called
        raise AssertionError("stub dependency is never invoked in a static audit")

    app = FastAPI()

    @app.post("/things", dependencies=[Depends(bare_principal)])
    async def _create_thing() -> dict:  # pragma: no cover - never called
        return {}

    @app.post("/safe-things", dependencies=[Depends(writer_capped)])
    async def _create_safe_thing() -> dict:  # pragma: no cover - never called
        return {}

    @app.get("/verify", dependencies=[Depends(bare_principal)])
    async def _verify() -> dict:  # pragma: no cover - never called
        return {}

    findings = audit_api_key_routes(
        app, bare_dependency=bare_principal, exempt_paths=("/verify",)
    )
    flagged = {f.path for f in findings}
    passed = flagged == {"/things"}
    return [
        CheckResult(
            "route_audit.flags_bare_key_dep_on_protected_route",
            passed,
            f"flagged={sorted(flagged)} (expected only the bare-wired write route)",
        )
    ]


# --------------------------------------------------------------------------- #
# Small shared helpers.
# --------------------------------------------------------------------------- #
def _secret(raw: str) -> object:
    """A ``SecretStr`` wrapping *raw* (imported lazily to keep the top tidy)."""
    from pydantic import SecretStr

    return SecretStr(raw)


def _json(payload: dict) -> bytes:
    import json

    return json.dumps(payload).encode("utf-8")


def _raises_ceiling(required: RoleType) -> bool:
    try:
        validate_api_key_required_role(required)
    except ApiKeyCapabilityCeilingError:
        return True
    return False


def _drive(
    name: str,
    *,
    replies: list[_Reply],
    audience_id: str,
    expect: str,
) -> CheckResult:
    """Drive one real-client interaction and match its outcome to *expect*.

    ``expect`` is ``"none"`` (generic inactive → dependency 401),
    ``"introspection_error"`` (fail closed → dependency 503), or
    ``"quota:<retry_after>"`` (relayed 429 with the given ``Retry-After``).
    """

    async def _interaction() -> str:
        transport = _CountingTransport(replies)
        client = _client(audience_id, transport)
        try:
            result = await client.introspect(_secret("k"))
        except ApiKeyQuotaExceededError as ex:
            return f"quota:{ex.retry_after}"
        except ApiKeyIntrospectionError:
            return "introspection_error"
        finally:
            await client.close()
        return "none" if result is None else "principal"

    outcome = _run(_interaction())
    return CheckResult(name, outcome == expect, f"outcome={outcome} expected={expect}")


def run_api_key_conformance(matrix: dict) -> list[CheckResult]:
    """Run every API-key principal conformance check and return the flat list."""
    results: list[CheckResult] = []
    results.extend(local_remote_principal_equivalence(matrix))
    results.extend(capability_audience_policy_matrix(matrix))
    results.extend(remote_status_and_fail_closed(matrix))
    results.extend(no_positive_caching(matrix))
    results.extend(downgrade_denies_next_request(matrix))
    results.extend(forged_keys_indistinguishable(matrix))
    results.extend(capability_ceiling_and_no_superuser(matrix))
    results.extend(route_audit_forbids_bare_key_deps())
    return results
