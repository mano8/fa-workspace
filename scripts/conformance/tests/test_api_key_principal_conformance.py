"""Unit tests for the API-key principal conformance checks (§3.12)."""

from __future__ import annotations

import unittest

from auth_sdk_m8.testing import load_authorization_fixture_matrix

from scripts.conformance.api_key_principal_conformance import (
    capability_audience_policy_matrix,
    capability_ceiling_and_no_superuser,
    downgrade_denies_next_request,
    forged_keys_indistinguishable,
    local_remote_principal_equivalence,
    no_positive_caching,
    remote_status_and_fail_closed,
    route_audit_forbids_bare_key_deps,
    run_api_key_conformance,
)


class ApiKeyPrincipalConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = load_authorization_fixture_matrix()

    def _assert_all_pass(self, results) -> None:
        failures = [f"{r.name}: {r.detail}" for r in results if not r.passed]
        self.assertEqual(failures, [], f"conformance failures: {failures}")

    def test_local_remote_principal_equivalence(self) -> None:
        results = local_remote_principal_equivalence(self.matrix)
        self.assertEqual(
            len(results), len(self.matrix["local_remote_principal_equivalence"])
        )
        self._assert_all_pass(results)

    def test_capability_audience_policy_matrix_covers_every_row(self) -> None:
        results = capability_audience_policy_matrix(self.matrix)
        self.assertEqual(
            len(results), len(self.matrix["audience_and_capability_policy_matrix"])
        )
        self._assert_all_pass(results)
        # The matrix spans both the ceiling denials and ordinary role decisions.
        self.assertTrue(any("ceiling" in r.name for r in results))
        self.assertTrue(any(r.name.startswith("policy[") for r in results))

    def test_remote_status_and_fail_closed(self) -> None:
        self._assert_all_pass(remote_status_and_fail_closed(self.matrix))

    def test_no_positive_caching(self) -> None:
        self._assert_all_pass(no_positive_caching(self.matrix))

    def test_downgrade_denies_next_request(self) -> None:
        self._assert_all_pass(downgrade_denies_next_request(self.matrix))

    def test_forged_keys_indistinguishable(self) -> None:
        self._assert_all_pass(forged_keys_indistinguishable(self.matrix))

    def test_capability_ceiling_and_no_superuser(self) -> None:
        self._assert_all_pass(capability_ceiling_and_no_superuser(self.matrix))

    def test_route_audit_forbids_bare_key_deps(self) -> None:
        self._assert_all_pass(route_audit_forbids_bare_key_deps())

    def test_full_api_key_conformance_is_green(self) -> None:
        results = run_api_key_conformance(self.matrix)
        self._assert_all_pass(results)
        # 10 equivalence + 62 policy + 7 status + 2 caching + 1 downgrade
        # + 2 indistinguishable + 4 ceiling + 1 route-audit.
        self.assertGreaterEqual(len(results), 80)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
