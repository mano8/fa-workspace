"""Cross-repository authorization conformance harness (fa-workspace owned).

This package realises the Phase 5 controller bullet *"Run local-package matrix
in dependency order and prove issuer/consumer parity for all valid and invalid
claim combinations, including the concurrent-login-during-downgrade generation
race and the durable-outbox propagation"* from
``.workspace/plans/stack/todo/auth-role-superuser-consistency/00-execution.md``
(canonical verification owner: ``50-verification-conformance.md`` §6
*Cross-repository integration*, ``TEST-CROSS-01``).

Ownership boundary (``.workspace/architecture.md``):

* ``fa-workspace`` owns cross-repository architecture and workspace-only CI, so
  the aggregate cross-repo proof lives here rather than inside any child.
* The harness imports **platform** packages only — ``auth_sdk_m8`` (the
  canonical decision owner the issuer uses) and ``fastapi_m8`` (the consumer
  framework). It never imports a **service** (``fa-auth-m8``) source module, so
  ``ARCH-LAYER-DIRECTION`` and the no-cross-service-source-import rule of
  ``policies/tasks/cross-repository.md`` hold: the issuer and consumer *halves*
  are each independently proven inside their own repositories' fixture-matrix
  contract suites; this harness proves the two halves resolve **identically**.
* All expectations are read from the SDK-owned checksum-verified fixture matrix
  (``FIXTURE-01``); the harness never invents local expectations.

It is intentionally **not** wired into ``workspace-policy-lint`` (which stays
child-agnostic and installs no platform packages). It runs in its own opt-in
``cross-repo-conformance`` workflow and locally against the shared venv.
"""

from __future__ import annotations

__all__ = [
    "ConformanceError",
    "CheckResult",
]


class ConformanceError(RuntimeError):
    """Raised when a conformance check fails closed.

    The harness follows the fail-closed posture of the authorization contracts:
    any unproven or drifted expectation is an error, never a silent pass.
    """


class CheckResult:
    """One named conformance check outcome.

    Kept deliberately tiny (no third-party model dependency) so the harness has
    the same minimal footprint as the rest of ``scripts/`` workspace tooling.
    """

    __slots__ = ("name", "passed", "detail")

    def __init__(self, name: str, passed: bool, detail: str) -> None:
        self.name = name
        self.passed = passed
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        status = "PASS" if self.passed else "FAIL"
        return f"<CheckResult {status} {self.name!r}: {self.detail}>"
