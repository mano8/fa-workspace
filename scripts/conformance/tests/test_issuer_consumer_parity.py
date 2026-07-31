"""Unit tests for the issuer/consumer parity matrix."""

from __future__ import annotations

import unittest

from auth_sdk_m8.testing import load_authorization_fixture_matrix

from scripts.conformance.issuer_consumer_parity import (
    canonical_token_parity,
    generation_race,
    minimum_role_parity,
    outbox_propagation,
    role_flag_superuser_parity,
    run_parity_matrix,
)


class ParityMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = load_authorization_fixture_matrix()

    def _assert_all_pass(self, results) -> None:
        failures = [f"{r.name}: {r.detail}" for r in results if not r.passed]
        self.assertEqual(failures, [], f"parity failures: {failures}")

    def test_role_flag_superuser_parity_covers_every_row(self) -> None:
        results = role_flag_superuser_parity(self.matrix)
        self.assertEqual(len(results), len(self.matrix["role_flag_matrix"]))
        self._assert_all_pass(results)

    def test_minimum_role_parity_covers_every_pair(self) -> None:
        results = minimum_role_parity(self.matrix)
        self.assertEqual(len(results), len(self.matrix["minimum_role_matrix"]))
        self._assert_all_pass(results)

    def test_canonical_token_parity_validates_and_rejects(self) -> None:
        results = canonical_token_parity(self.matrix)
        self.assertEqual(
            len(results), len(self.matrix["canonical_jwt_fixtures"]["tokens"])
        )
        self._assert_all_pass(results)
        # Both consistent (validated) and inconsistent (rejected) fixtures exist,
        # so the parity proof spans valid and invalid claim combinations.
        rejected = [r for r in results if "rejected" in r.detail]
        validated = [r for r in results if "validated" in r.detail]
        self.assertTrue(rejected, "expected some inconsistent tokens to be rejected")
        self.assertTrue(validated, "expected some consistent tokens to validate")

    def test_generation_race(self) -> None:
        self._assert_all_pass(generation_race(self.matrix))

    def test_outbox_propagation(self) -> None:
        self._assert_all_pass(outbox_propagation(self.matrix))

    def test_full_matrix_is_green(self) -> None:
        results = run_parity_matrix(self.matrix)
        self._assert_all_pass(results)
        self.assertGreaterEqual(len(results), 50)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
