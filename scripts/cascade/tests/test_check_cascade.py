from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_cascade as cascade

SDK_SETTINGS = """
from typing import ClassVar
from pydantic import Field

class CommonSettings:
    ENV_FILE_DIR: ClassVar[str] = "x"
    required_fields = ["DOMAIN"]
    DOMAIN: str = Field(..., description="host")
    TOKEN_MODE: str = "stateless"
"""

FILES: dict[str, str] = {
    "auth-sdk-m8/pyproject.toml": '[project]\nname = "auth-sdk-m8"\nversion = "3.2.0"\n',
    "auth-sdk-m8/auth_sdk_m8/core/config.py": SDK_SETTINGS,
    "auth-sdk-m8/auth_sdk_m8/observability/settings.py": "class ObservabilitySettingsMixin:\n    METRICS_ENABLED: bool = False\n",
    "auth-sdk-m8/auth_sdk_m8/core/consumer.py": "class ConsumerAuthMixin:\n    INTROSPECTION_URL: str | None = None\n",
    "fastapi-m8/pyproject.toml": (
        '[project]\nname = "fastapi-m8"\nversion = "4.5.1"\n'
        'dependencies = ["auth-sdk-m8[config,security]>=3.2.0,<4.0.0"]\n'
    ),
    "fastapi-m8/fastapi_m8/_version.py": '__version__ = "4.5.1"\n',
    "fastapi-m8/fastapi_m8/_compat.py": 'COMPAT_MATRIX = {\n    "4.5": {"auth-sdk-m8": ">=3.2.0,<4.0.0"},\n}\n',
    "fastapi-m8/README.md": "## Compatibility\n\n| `4.5.1` | `>=3.2.0, <4.0.0` | 3.12 |\n",
    "fa-auth-m8/auth_user_service/__init__.py": '__version__ = "2.2.3"\n',
    "fa-auth-m8/examples/fastapi_full/__init__.py": '__version__ = "2.2.3"\n',
    "fa-auth-m8/examples/fastapi_minimal/__init__.py": '__version__ = "2.2.3"\n',
    "fa-auth-m8/auth_user_service/requirements_base.txt": "auth-sdk-m8>=3.2.0,<4.0.0\n",
    "fa-auth-m8/auth_user_service/requirements_prod.lock": "auth-sdk-m8==3.2.0 \\\n    --hash=sha256:00\n",
    "fa-auth-m8/auth_user_service/.env.example": "DOMAIN=changethis\n",
    "fa-auth-m8/examples/docker_compose/hardened_m8/docker-compose.yml": "    image: tepochtli/fa-auth-m8:2.2.3\n",
    "media-service-m8/media_service/__init__.py": '__version__ = "3.0.2"\n',
    "media-service-m8/media_service/requirements_base.txt": "fastapi-m8[db]>=4.5.1,<5.0.0\n",
    "media-service-m8/media_service/requirements_prod.lock": (
        "auth-sdk-m8[config]==3.2.0 \\\n    --hash=sha256:00\nfastapi-m8[db]==4.5.1 \\\n    --hash=sha256:00\n"
    ),
    "media-service-m8/README.md": "Set `TOKEN_MODE` to choose.\n",
    "astro-auth-m8/package.json": '{"version": "2.7.1"}\n',
    "astro-auth-m8/src/runtime/compatibility.ts": (
        'export const FA_AUTH_M8_TESTED_SERVICE_VERSION = "2.2.3";\n'
        'export const FA_AUTH_M8_MIN_SERVICE_VERSION = "2.0.0";\n'
        'export const FA_AUTH_M8_MAX_SERVICE_VERSION_EXCLUSIVE = "3.0.0";\n'
    ),
    "rpi_server/docente_reparto/docker-compose.yml": "    image: tepochtli/fa-auth-m8:2.2.3\n",
    "rpi_server/docente_reparto/auth.env": "DOMAIN=real-value\n",
    "rpi_server/docente_reparto/auth.env.example": "DOMAIN=changethis\n",
}


class CascadeWorkspace(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        for relative, text in FILES.items():
            self.write(relative, text)

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def messages(self, findings: list[cascade.Finding]) -> list[str]:
        return [f"{finding.path}: {finding.message}" for finding in findings]


class ConsistencyTests(CascadeWorkspace):
    def test_consistent_fleet_reports_nothing(self) -> None:
        self.assertEqual(cascade.consistency(self.root, {}), [])

    def test_planned_sdk_bump_lists_every_pin(self) -> None:
        found = self.messages(cascade.consistency(self.root, {"auth-sdk-m8": "3.3.0"}))
        self.assertIn("fastapi-m8/pyproject.toml: auth-sdk-m8 floor 3.2.0, target 3.3.0", found)
        self.assertIn(
            'fastapi-m8/fastapi_m8/_compat.py: COMPAT_MATRIX "4.5" floor 3.2.0, target 3.3.0', found
        )
        self.assertIn("fastapi-m8/README.md: Compatibility 4.5.x floor 3.2.0, target 3.3.0", found)
        self.assertIn(
            "fa-auth-m8/auth_user_service/requirements_prod.lock: auth-sdk-m8 lock pin 3.2.0, target 3.3.0",
            found,
        )
        self.assertIn(
            "media-service-m8/media_service/requirements_prod.lock: auth-sdk-m8 lock pin 3.2.0, target 3.3.0",
            found,
        )

    def test_new_fastapi_minor_needs_compat_rows(self) -> None:
        found = self.messages(cascade.consistency(self.root, {"fastapi-m8": "4.6.0"}))
        self.assertIn(
            'fastapi-m8/fastapi_m8/_compat.py: COMPAT_MATRIX has no "4.6" row (fails closed at startup)',
            found,
        )
        self.assertIn("fastapi-m8/README.md: Compatibility table has no 4.6.x row", found)
        self.assertIn("fastapi-m8/fastapi_m8/_version.py: version 4.5.1, target 4.6.0", found)

    def test_fa_auth_version_files_move_together(self) -> None:
        self.write("fa-auth-m8/examples/fastapi_minimal/__init__.py", '__version__ = "2.2.2"\n')
        found = self.messages(cascade.consistency(self.root, {}))
        self.assertEqual(
            found, ["fa-auth-m8/examples/fastapi_minimal/__init__.py: version 2.2.2, target 2.2.3"]
        )

    def test_image_tags_flag_operator_local_stacks(self) -> None:
        findings = cascade.consistency(self.root, {"fa-auth-m8": "2.2.4"})
        tags = [finding for finding in findings if finding.phase == "5"]
        self.assertEqual(len(tags), 2)
        local = {finding.path.split(":")[0]: finding.operator_local for finding in tags}
        self.assertTrue(local["rpi_server/docente_reparto/docker-compose.yml"])
        self.assertFalse(local["fa-auth-m8/examples/docker_compose/hardened_m8/docker-compose.yml"])

    def test_plugin_range_must_admit_the_service(self) -> None:
        found = self.messages(cascade.consistency(self.root, {"fa-auth-m8": "3.0.0"}))
        self.assertIn(
            "astro-auth-m8/src/runtime/compatibility.ts: FA_AUTH_M8_TESTED_SERVICE_VERSION 2.2.3, target fa-auth-m8 3.0.0",
            found,
        )
        self.assertIn(
            "astro-auth-m8/src/runtime/compatibility.ts: fa-auth-m8 3.0.0 is outside >=2.0.0 <3.0.0",
            found,
        )

    def test_conformance_matrix_and_ci_refs_track_targets(self) -> None:
        self.write(
            "scripts/conformance/local_package_matrix.py", 'EXPECTED_SDK_VERSION = "3.1.0"\n'
        )
        self.write(".github/workflows/cross-repo-conformance.yml", "env:\n  SDK_REF: v3.1.0\n")
        found = self.messages(cascade.check_conformance(self.root, {"auth-sdk-m8": "3.2.0"}))
        self.assertEqual(
            found,
            [
                "scripts/conformance/local_package_matrix.py: EXPECTED_SDK_VERSION 3.1.0, target 3.2.0",
                ".github/workflows/cross-repo-conformance.yml: SDK_REF 3.1.0, target 3.2.0",
            ],
        )

    def test_unknown_override_is_an_error(self) -> None:
        with self.assertRaises(cascade.CascadeError):
            cascade.consistency(self.root, {"not-a-repo": "1.0.0"})


class SettingsFieldTests(unittest.TestCase):
    def test_fields_skip_classvar_lowercase_and_description(self) -> None:
        fields = cascade.settings_fields(SDK_SETTINGS, "CommonSettings")
        self.assertEqual(sorted(fields), ["DOMAIN", "TOKEN_MODE"])
        self.assertEqual(fields["DOMAIN"].default, "Field(...)")
        self.assertTrue(cascade.is_required(fields["DOMAIN"]))
        self.assertFalse(cascade.is_required(fields["TOKEN_MODE"]))

    def test_real_env_files_are_never_templates(self) -> None:
        for name in (".env", "auth.env", ".env.local", ".env.production"):
            self.assertFalse(cascade.is_env_template(Path(name)), name)
        for name in (".env.example", "env.example", "auth.env.example", ".env.production.example"):
            self.assertTrue(cascade.is_env_template(Path(name)), name)


@unittest.skipIf(shutil.which("git") is None, "git is not available")
class EnvDiffTests(CascadeWorkspace):
    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.root / "auth-sdk-m8"), *args], check=True, capture_output=True
        )

    def test_added_required_and_removed_keys_are_located(self) -> None:
        self.git("init", "-q")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
        self.git("tag", "v3.2.0")
        self.write(
            "auth-sdk-m8/auth_sdk_m8/core/config.py",
            SDK_SETTINGS.replace('    TOKEN_MODE: str = "stateless"\n', "    ISSUER_URL: str\n"),
        )
        found = self.messages(
            cascade.env_diff(self.root, "auth-sdk-m8", "v3.2.0", cascade.WORKTREE)
        )
        self.assertIn(
            "auth-sdk-m8/auth_sdk_m8/core/config.py: CommonSettings.ISSUER_URL added (required)",
            found,
        )
        self.assertIn(
            "auth-sdk-m8/auth_sdk_m8/core/config.py: CommonSettings.TOKEN_MODE removed", found
        )
        self.assertIn(
            "fa-auth-m8/auth_user_service/.env.example: template lacks required CommonSettings.ISSUER_URL",
            found,
        )
        self.assertIn(
            "rpi_server/docente_reparto/auth.env.example: template lacks required CommonSettings.ISSUER_URL",
            found,
        )
        self.assertIn(
            "media-service-m8/README.md: still names removed CommonSettings.TOKEN_MODE", found
        )
        self.assertFalse(any("auth.env:" in message for message in found))


if __name__ == "__main__":
    unittest.main()
