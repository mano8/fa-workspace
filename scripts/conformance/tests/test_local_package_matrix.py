"""Unit tests for the local-package matrix resolver."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.conformance import ConformanceError
from scripts.conformance.local_package_matrix import (
    EXPECTED_FASTAPI_VERSION,
    EXPECTED_ISSUER_VERSION,
    EXPECTED_SDK_VERSION,
    _floor_for,
    _read_declared_version,
    resolve_local_package_matrix,
    specifier_admits,
    workspace_root,
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
            "sdk.resolves_version_identical",
            "fastapi.version",
            "fastapi.resolves_version_identical",
            "fastapi.sdk_floor_admits_installed_sdk",
            "issuer.version",
            "issuer.sdk_floor_admits_installed_sdk",
            "example.fastapi_floor_admits_installed_fastapi",
        ):
            self.assertIn(required, names)

    def test_intended_versions_track_the_repositories(self) -> None:
        """Guard against a version bump that forgets this harness.

        Read from each repository's own declaration rather than repeated
        literals: the literals are exactly what went stale at ``4.1.0`` and left
        the harness reporting RED on a correct stack.
        """
        root: Path = workspace_root()
        for constant, declaration in (
            (EXPECTED_SDK_VERSION, Path("auth-sdk-m8/auth_sdk_m8/__init__.py")),
            (EXPECTED_FASTAPI_VERSION, Path("fastapi-m8/fastapi_m8/_version.py")),
            (
                EXPECTED_ISSUER_VERSION,
                Path("fa-auth-m8/auth_user_service/__init__.py"),
            ),
        ):
            with self.subTest(declaration=declaration.as_posix()):
                self.assertEqual(constant, _read_declared_version(root / declaration))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
