"""Unit tests for the local-package matrix resolver."""

from __future__ import annotations

import unittest

from scripts.conformance import ConformanceError
from scripts.conformance.local_package_matrix import (
    EXPECTED_FASTAPI_VERSION,
    EXPECTED_ISSUER_VERSION,
    EXPECTED_SDK_VERSION,
    _floor_for,
    resolve_local_package_matrix,
    specifier_admits,
)


class SpecifierAdmitsTests(unittest.TestCase):
    def test_floor_and_ceiling_admits_inside_range(self) -> None:
        self.assertTrue(specifier_admits(">=3.1.0,<4.0.0", "3.1.0"))
        self.assertTrue(specifier_admits(">=3.1.0,<4.0.0", "3.9.9"))

    def test_below_floor_is_rejected(self) -> None:
        self.assertFalse(specifier_admits(">=3.1.0,<4.0.0", "3.0.0"))

    def test_at_or_above_ceiling_is_rejected(self) -> None:
        self.assertFalse(specifier_admits(">=3.1.0,<4.0.0", "4.0.0"))
        self.assertFalse(specifier_admits(">=4.1.0,<5.0.0", "5.1.0"))

    def test_exact_pin(self) -> None:
        self.assertTrue(specifier_admits("==3.0.0", "3.0.0"))
        self.assertFalse(specifier_admits("==3.0.0", "3.1.0"))

    def test_empty_specifier_fails_closed(self) -> None:
        with self.assertRaises(ConformanceError):
            specifier_admits("auth-sdk-m8", "3.1.0")


class FloorForTests(unittest.TestCase):
    def test_bare_requirement_line(self) -> None:
        text = "some-dep>=1.0\nauth-sdk-m8>=3.1.0,<4.0.0\nother==2\n"
        self.assertEqual(_floor_for("auth-sdk-m8", text), ">=3.1.0,<4.0.0")

    def test_quoted_indented_pyproject_line_with_extras(self) -> None:
        text = '    "auth-sdk-m8[config,security,fastapi]>=3.1.0,<4.0.0",\n'
        self.assertEqual(_floor_for("auth-sdk-m8", text), ">=3.1.0,<4.0.0")

    def test_missing_package_fails_closed(self) -> None:
        with self.assertRaises(ConformanceError):
            _floor_for("auth-sdk-m8", "nothing-here>=1.0\n")


class ResolveMatrixTests(unittest.TestCase):
    """End-to-end resolution against the installed local packages."""

    def setUp(self) -> None:
        self.results = resolve_local_package_matrix()

    def test_all_checks_pass(self) -> None:
        failures = [f"{r.name}: {r.detail}" for r in self.results if not r.passed]
        self.assertEqual(failures, [], f"local-package matrix failures: {failures}")

    def test_expected_named_checks_present(self) -> None:
        names = {r.name for r in self.results}
        for required in (
            "sdk.version",
            "sdk.resolves_in_workspace",
            "fastapi.version",
            "fastapi.resolves_in_workspace",
            "fastapi.sdk_floor_admits_installed_sdk",
            "issuer.version",
            "issuer.sdk_floor_admits_installed_sdk",
            "example.fastapi_floor_admits_installed_fastapi",
        ):
            self.assertIn(required, names)

    def test_intended_versions_are_the_current_matrix(self) -> None:
        # Guards against a silent version bump that forgets this harness.
        self.assertEqual(EXPECTED_SDK_VERSION, "3.1.0")
        self.assertEqual(EXPECTED_FASTAPI_VERSION, "4.1.0")
        self.assertEqual(EXPECTED_ISSUER_VERSION, "2.0.0")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
