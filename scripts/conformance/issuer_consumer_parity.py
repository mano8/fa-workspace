"""Issuer/consumer authorization parity over the canonical fixture matrix.

Realises the remainder of the Phase 5 bullet (§6, ``TEST-CROSS-01``): prove the
issuer and a ``fastapi_m8`` consumer reach **identical** authorization
decisions for every valid and invalid claim combination in the SDK-owned
checksum-verified fixture matrix, and prove the concurrent-login-during
-downgrade generation race and the durable-outbox propagation resolve at the
consumer seam.

Modelled decision paths (both delegate to the single canonical owner, the SDK —
that is the whole point of the invariant, so drift anywhere makes a check fail):

* **Issuer decision** — the SDK predicate the issuer applies when it validates
  persisted claims before signing (``has_superuser_privileges`` /
  ``has_minimum_role``), evaluated against each fixture's declared claims.
* **Consumer decision** — a real ``fastapi_m8`` guard (``_require_role`` and the
  ``get_current_active_superuser`` predicate) evaluated against a token the
  consumer has actually validated through the SDK ``TokenValidator``.

The three-way equality *consumer == issuer == fixture-expected* is what proves
parity end to end (serialization → signing → validation → guard).
"""

from __future__ import annotations

from auth_sdk_m8 import has_minimum_role, has_superuser_privileges
from auth_sdk_m8.core.exceptions import InvalidToken
from auth_sdk_m8.schemas.auth import TokenSecret
from auth_sdk_m8.schemas.base import RoleType
from auth_sdk_m8.security import TokenValidationConfig, TokenValidator
from fastapi import HTTPException
from fastapi_m8._deps import _require_role
from fastapi_m8._revocation import RemoteRevocationClient
from pydantic import SecretStr

from scripts.conformance import CheckResult

#: Role thresholds the consumer's ``_require_role`` guard is exercised against.
_REQUIRABLE_ROLES = (RoleType.USER, RoleType.READER, RoleType.WRITER, RoleType.ADMIN)


class _ConsumerUser:
    """Duck-typed stand-in the consumer guards read (``.role``/``.is_superuser``).

    ``_require_role`` reads only ``.role`` and ``get_current_active_superuser``
    reads both — the same two attributes a validated ``UserModel`` exposes.
    """

    __slots__ = ("is_superuser", "role")

    def __init__(self, role: RoleType, is_superuser: bool) -> None:
        self.role = role
        self.is_superuser = is_superuser


def _consumer_requires_role(user: _ConsumerUser, required: RoleType) -> bool:
    """Return whether the consumer's ``_require_role`` guard admits *user*."""
    try:
        _require_role(user, required)  # type: ignore[arg-type]
        return True
    except HTTPException:
        return False


def build_validator(matrix: dict) -> TokenValidator:
    """Build the consumer-side validator keyed with the trusted test key."""
    fixtures = matrix["canonical_jwt_fixtures"]
    return TokenValidator(
        secrets=TokenSecret(
            secret_key=SecretStr(fixtures["trusted_test_signing_key"]),
            algorithm=fixtures["algorithm"],
        ),
        config=TokenValidationConfig(allowed_algorithms=[fixtures["algorithm"]]),
    )


def role_flag_superuser_parity(matrix: dict) -> list[CheckResult]:
    """Superuser decision parity across all 10 role/flag rows (valid + invalid)."""
    results: list[CheckResult] = []
    for row in matrix["role_flag_matrix"]:
        role = RoleType(row["role"])
        # Issuer and consumer both compute the canonical predicate; the fixture
        # carries the canonical expectation. All three must agree.
        issuer = has_superuser_privileges(role, row["is_superuser"])
        consumer = has_superuser_privileges(role, row["is_superuser"])
        expected = row["has_superuser_privileges"]
        passed = issuer == consumer == expected
        results.append(
            CheckResult(
                f"role_flag.superuser[{row['role']},is_superuser={row['is_superuser']}]",
                passed,
                f"issuer={issuer} consumer={consumer} expected={expected}",
            )
        )
    return results


def minimum_role_parity(matrix: dict) -> list[CheckResult]:
    """Minimum-role parity across all 25 current/required pairs via the real guard."""
    results: list[CheckResult] = []
    for row in matrix["minimum_role_matrix"]:
        current = RoleType(row["current_role"])
        required = RoleType(row["required_role"])
        issuer = has_minimum_role(current, required)
        consumer = _consumer_requires_role(_ConsumerUser(current, False), required)
        expected = row["satisfied"]
        passed = issuer == consumer == expected
        results.append(
            CheckResult(
                f"minimum_role[{row['current_role']}>={row['required_role']}]",
                passed,
                f"issuer={issuer} consumer={consumer} expected={expected}",
            )
        )
    return results


def canonical_token_parity(matrix: dict) -> list[CheckResult]:
    """Prove each signed fixture token yields identical issuer/consumer decisions.

    Consistent tokens must validate and produce the canonical role/superuser
    decision on both sides; inconsistent tokens must be rejected identically
    (the issuer refuses to sign them, the consumer refuses to validate them),
    so a mismatched claim pair can never survive signing → validation.
    """
    validator = build_validator(matrix)
    results: list[CheckResult] = []
    for entry in matrix["canonical_jwt_fixtures"]["tokens"]:
        label = f"token[{entry['role']},is_superuser={entry['is_superuser']}]"
        declared_role = RoleType(entry["role"])
        issuer_superuser = has_superuser_privileges(
            declared_role, entry["is_superuser"]
        )
        try:
            payload = validator.validate_access_token(entry["jwt"])
        except InvalidToken:
            # Rejected by validation — must be a fixture flagged inconsistent.
            results.append(
                CheckResult(
                    label,
                    entry["consistent"] is False,
                    "rejected by consumer validation (invalid token)",
                )
            )
            continue
        user = _ConsumerUser(payload.role, payload.is_superuser)
        consumer_superuser = has_superuser_privileges(user.role, user.is_superuser)
        role_roundtrips = payload.role == declared_role
        superuser_parity = consumer_superuser == issuer_superuser
        # Requiring writer must agree between the two sides for this principal.
        writer_parity = _consumer_requires_role(user, RoleType.WRITER) == (
            has_minimum_role(payload.role, RoleType.WRITER)
        )
        passed = (
            entry["consistent"] is True
            and role_roundtrips
            and superuser_parity
            and writer_parity
        )
        results.append(
            CheckResult(
                label,
                passed,
                f"validated role={payload.role.value} "
                f"superuser(issuer={issuer_superuser},consumer={consumer_superuser}) "
                f"writer_parity={writer_parity}",
            )
        )
    return results


def _cache_client() -> RemoteRevocationClient:
    """A consumer revocation client with its bounded positive cache enabled."""
    return RemoteRevocationClient(
        introspection_url="http://auth:8000/user/private/v1/jti-status",
        private_api_secret="conformance-secret",  # nosec B106 - harness fixture
        cache_ttl=30,
    )


def generation_race(matrix: dict) -> list[CheckResult]:
    """Concurrent-login-during-downgrade generation race at the consumer seam.

    A downgrade advances the user's ``auth_generation`` watermark; any session
    minted against the superseded generation must never be served, in either
    interleaving, while a fresh session at the new generation is served.
    """
    events = matrix["session_revoked_events"]
    downgrade = events["v2_user_wide"]  # user-wide, auth_generation = 2
    user = downgrade["user_id"]
    new_gen = downgrade["auth_generation"]
    stale_gen = new_gen - 1
    results: list[CheckResult] = []

    # Interleaving A: the downgrade lands first; the racing stale-gen login's
    # positive result is refused by the cache (below the watermark).
    client = _cache_client()
    cache = client._cache
    assert cache is not None
    client.apply_session_revoked_event(downgrade)
    cache.put("race-after", user, stale_gen)
    results.append(
        CheckResult(
            "generation_race.stale_login_after_downgrade_refused",
            cache.get("race-after") is None and cache.is_superseded(user, stale_gen),
            f"stale gen {stale_gen} below watermark {new_gen}",
        )
    )

    # Interleaving B: the racing login caches first, then the downgrade evicts it.
    client = _cache_client()
    cache = client._cache
    assert cache is not None
    cache.put("race-before", user, stale_gen)
    seen_before = cache.get("race-before") is False
    client.apply_session_revoked_event(downgrade)
    results.append(
        CheckResult(
            "generation_race.stale_login_before_downgrade_evicted",
            seen_before and cache.get("race-before") is None,
            f"gen {stale_gen} entry evicted once watermark reached {new_gen}",
        )
    )

    # A fresh session minted at the new generation survives the downgrade.
    cache.put("fresh", user, new_gen)
    results.append(
        CheckResult(
            "generation_race.fresh_generation_login_served",
            cache.get("fresh") is False,
            f"gen {new_gen} entry served at/after watermark {new_gen}",
        )
    )
    return results


def outbox_propagation(matrix: dict) -> list[CheckResult]:
    """Durable-outbox propagation to consumer eviction, incl. the watermark rule.

    Exercises the ``<`` / ``==`` / ``>`` generation watermark rule with durable
    ``event_id`` dedup (v2) and conservative eviction (v1) as delivered by the
    outbox to the consumer's ``apply_session_revoked_event`` seam.
    """
    events = matrix["session_revoked_events"]
    user_wide = events["v2_user_wide"]  # gen 2, jti=None
    single = events["v2_single_session"]  # gen 1, jti set
    v1 = events["v1"]  # no generation
    user = user_wide["user_id"]
    results: list[CheckResult] = []

    # '>' : a higher-generation user-wide event applies and advances the
    # watermark, evicting every entry below it.
    client = _cache_client()
    cache = client._cache
    assert cache is not None
    cache.put(single["jti"], user, single["auth_generation"])
    cache.put("other", user, single["auth_generation"])
    client.apply_session_revoked_event(user_wide)
    results.append(
        CheckResult(
            "outbox.greater_generation_evicts_below",
            cache.get(single["jti"]) is None and cache.get("other") is None,
            f"gen {user_wide['auth_generation']} evicted gen "
            f"{single['auth_generation']} entries",
        )
    )

    # '==' : the same event redelivered (durable event_id) is deduplicated and
    # does not evict a fresh entry at the current generation (idempotent drain).
    cache.put("fresh-at-watermark", user, user_wide["auth_generation"])
    client.apply_session_revoked_event(user_wide)  # duplicate delivery
    results.append(
        CheckResult(
            "outbox.duplicate_event_id_is_deduplicated",
            cache.get("fresh-at-watermark") is False,
            "redelivered event_id did not re-evict at the same generation",
        )
    )

    # '<' : a stale lower-generation event is ignored and cannot evict a current
    # entry.
    cache.put("current", user, user_wide["auth_generation"])
    client.apply_session_revoked_event(single)  # gen 1 < watermark 2
    results.append(
        CheckResult(
            "outbox.stale_generation_event_ignored",
            cache.get("current") is False,
            f"gen {single['auth_generation']} event ignored below watermark "
            f"{user_wide['auth_generation']}",
        )
    )

    # v1 (no generation) : conservative user-wide eviction regardless of gen.
    client = _cache_client()
    cache = client._cache
    assert cache is not None
    cache.put("legacy", user, 5)
    client.apply_session_revoked_event(v1)
    results.append(
        CheckResult(
            "outbox.v1_event_conservative_user_eviction",
            cache.get("legacy") is None,
            "generation-less v1 event evicted the whole user",
        )
    )
    return results


def run_parity_matrix(matrix: dict) -> list[CheckResult]:
    """Run every parity check and return the flat result list."""
    results: list[CheckResult] = []
    results.extend(role_flag_superuser_parity(matrix))
    results.extend(minimum_role_parity(matrix))
    results.extend(canonical_token_parity(matrix))
    results.extend(generation_race(matrix))
    results.extend(outbox_propagation(matrix))
    return results
