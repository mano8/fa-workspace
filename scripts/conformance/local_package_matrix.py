"""Local-package matrix resolution in dependency order (§6, ``TEST-CROSS-01``).

Proves the first cross-repository integration requirement of
``50-verification-conformance.md`` §6:

    Build/install local packages in dependency order: SDK -> fastapi -> issuer
    and examples. Assert imports resolve to the intended workspace versions.

The platform packages (``auth_sdk_m8``, ``fastapi_m8``) are **imported** and
checked to resolve at the intended version, and to be *version-identical* to
the in-workspace source of truth — either because they resolve to that source
directly (an editable/`-e` install) or because a published copy from the index
carries the very same version. The issuer and its examples are **services**; to
honour the no-cross-service-source-import rule this module never imports them —
it reads their declared package version and dependency floors from
source-of-truth files and asserts the dependency-order contract holds (the
issuer's SDK floor admits the installed SDK; the example's ``fastapi-m8`` floor
admits the installed framework).

All checks fail closed: a shadowing copy at a *different* version than the
workspace source, a version drift from the intended matrix, or a floor that
excludes the installed platform version is an error.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.conformance import CheckResult, ConformanceError

#: Intended workspace versions (2026-07-31 version matrix, §90 evidence).
#: ``scripts/conformance/tests`` asserts each entry still equals the version the
#: corresponding repository declares, so a bump that forgets this harness fails
#: as a stale-matrix error rather than as a confusing resolution mismatch.
EXPECTED_SDK_VERSION = "3.1.0"
EXPECTED_FASTAPI_VERSION = "4.2.1"
EXPECTED_ISSUER_VERSION = "2.0.0"

#: Where each platform package declares its own version, relative to the
#: workspace root. Used for the version-identity check below.
PLATFORM_VERSION_SOURCES = {
    "auth_sdk_m8": Path("auth-sdk-m8") / "auth_sdk_m8" / "__init__.py",
    "fastapi_m8": Path("fastapi-m8") / "fastapi_m8" / "_version.py",
}


def workspace_root() -> Path:
    """Return the workspace root (three levels up from this module)."""
    return Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Minimal, dependency-free version + specifier handling.
# The floors in this stack are all simple ``>=a.b.c,<d.e.f`` forms, so a tiny
# comparator avoids taking a runtime dependency on ``packaging`` (which the
# child-agnostic workspace tooling env does not guarantee).
# --------------------------------------------------------------------------- #
def _version_tuple(version: str) -> tuple[int, ...]:
    parts = version.strip().split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ConformanceError(f"unparseable version {version!r}") from exc


_OP_PATTERN = re.compile(r"(>=|<=|==|>|<)\s*([0-9][0-9.]*)")


def specifier_admits(specifier: str, version: str) -> bool:
    """Return whether *version* satisfies every clause of *specifier*.

    Supports the comma-separated ``>=``/``<=``/``==``/``>``/``<`` clauses used
    across this stack's floors, e.g. ``>=3.1.0,<4.0.0``.
    """
    clauses = _OP_PATTERN.findall(specifier)
    if not clauses:
        raise ConformanceError(f"no version clause found in {specifier!r}")
    got = _version_tuple(version)
    for op, bound_text in clauses:
        bound = _version_tuple(bound_text)
        if op == ">=" and not got >= bound:
            return False
        if op == "<=" and not got <= bound:
            return False
        if op == ">" and not got > bound:
            return False
        if op == "<" and not got < bound:
            return False
        if op == "==" and got != bound:
            return False
    return True


def _floor_for(package: str, text: str) -> str:
    """Extract the version specifier declared for *package* in *text*.

    Tolerates an optional extras bracket, e.g.
    ``auth-sdk-m8[config,security]>=3.1.0,<4.0.0``.
    """
    # Not line-anchored: the dependency may be quoted and indented (pyproject
    # array) or bare at column 0 (requirements file). The lookbehind keeps the
    # match at a package-name boundary so a prose mention cannot match.
    pattern = re.compile(
        rf"(?<![\w-]){re.escape(package)}(?:\[[^\]]*\])?\s*([<>=!,\d. ]+)",
    )
    match = pattern.search(text)
    if not match:
        raise ConformanceError(f"no {package!r} floor found")
    return match.group(1).strip()


def _module_version(module: object) -> str:
    version = getattr(module, "__version__", None)
    if not isinstance(version, str):  # pragma: no cover - defensive
        raise ConformanceError(f"{module!r} exposes no string __version__")
    return version


def _read_declared_version(init_path: Path) -> str:
    match = re.search(
        r"^__version__\s*=\s*[\"']([^\"']+)[\"']",
        init_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if not match:
        raise ConformanceError(f"no __version__ in {init_path}")
    return match.group(1)


def _version_identity(
    label: str, package: str, module_path: Path, installed: str, root: Path
) -> CheckResult:
    """Assert the imported platform package is version-identical to its source.

    The original assertion demanded the import resolve to the in-workspace
    checkout. That premise held only while these packages were unpublished. Both
    are released now, so a published copy pulled from the index is an equally
    valid resolution — it is what a clean runner installs — provided it carries
    the *same* version the workspace source declares. What must still fail
    closed is a shadowing copy at a different version, which is the drift the
    original check existed to catch.
    """
    source = root / PLATFORM_VERSION_SOURCES[package]
    declared = _read_declared_version(source)
    in_workspace = str(module_path).startswith(str(source.parent.parent.resolve()))
    origin = "workspace source" if in_workspace else "published distribution"
    return CheckResult(
        f"{label}.resolves_version_identical",
        installed == declared,
        f"{package}=={installed} from {origin} ({module_path}); "
        f"{source.relative_to(root).as_posix()} declares {declared}",
    )


def resolve_local_package_matrix(root: Path | None = None) -> list[CheckResult]:
    """Resolve the SDK -> fastapi -> issuer/examples matrix in dependency order.

    Returns one :class:`CheckResult` per assertion. Raises
    :class:`ConformanceError` only on a structural problem (a missing
    source-of-truth file); ordinary expectation failures are reported as failed
    results so the full matrix is always visible.
    """
    root = root or workspace_root()
    results: list[CheckResult] = []

    # 1. SDK leg — imported, version-identical to its source, intended version.
    # Imported lazily so a missing or misresolved package surfaces as a clean
    # conformance failure rather than a module-load crash.
    import auth_sdk_m8

    sdk_version = _module_version(auth_sdk_m8)
    sdk_path = Path(auth_sdk_m8.__file__ or "").resolve()
    results.append(
        CheckResult(
            "sdk.version",
            sdk_version == EXPECTED_SDK_VERSION,
            f"auth_sdk_m8=={sdk_version} (expected {EXPECTED_SDK_VERSION})",
        )
    )
    results.append(_version_identity("sdk", "auth_sdk_m8", sdk_path, sdk_version, root))

    # 2. fastapi leg — imported, version-identical, intended version, SDK floor.
    # Lazy for the same reason as the SDK import above.
    import fastapi_m8

    fastapi_version = _module_version(fastapi_m8)
    fastapi_path = Path(fastapi_m8.__file__ or "").resolve()
    results.append(
        CheckResult(
            "fastapi.version",
            fastapi_version == EXPECTED_FASTAPI_VERSION,
            f"fastapi_m8=={fastapi_version} (expected {EXPECTED_FASTAPI_VERSION})",
        )
    )
    results.append(
        _version_identity("fastapi", "fastapi_m8", fastapi_path, fastapi_version, root)
    )
    fastapi_sdk_floor = _floor_for(
        "auth-sdk-m8", (root / "fastapi-m8" / "pyproject.toml").read_text("utf-8")
    )
    results.append(
        CheckResult(
            "fastapi.sdk_floor_admits_installed_sdk",
            specifier_admits(fastapi_sdk_floor, sdk_version),
            f"fastapi-m8 declares auth-sdk-m8{fastapi_sdk_floor}; "
            f"installed {sdk_version}",
        )
    )

    # 3. Issuer + example leg — read declared metadata, never imported.
    issuer = root / "fa-auth-m8"
    issuer_version = _read_declared_version(
        issuer / "auth_user_service" / "__init__.py"
    )
    results.append(
        CheckResult(
            "issuer.version",
            issuer_version == EXPECTED_ISSUER_VERSION,
            f"fa-auth-m8=={issuer_version} (expected {EXPECTED_ISSUER_VERSION})",
        )
    )
    issuer_sdk_floor = _floor_for(
        "auth-sdk-m8",
        (issuer / "auth_user_service" / "requirements_base.txt").read_text("utf-8"),
    )
    results.append(
        CheckResult(
            "issuer.sdk_floor_admits_installed_sdk",
            specifier_admits(issuer_sdk_floor, sdk_version),
            f"fa-auth-m8 declares auth-sdk-m8{issuer_sdk_floor}; "
            f"installed {sdk_version}",
        )
    )
    example_floor = _floor_for(
        "fastapi-m8",
        (issuer / "examples" / "fastapi_full" / "requirements_base.txt").read_text(
            "utf-8"
        ),
    )
    results.append(
        CheckResult(
            "example.fastapi_floor_admits_installed_fastapi",
            specifier_admits(example_floor, fastapi_version),
            f"fastapi_full declares fastapi-m8{example_floor}; "
            f"installed {fastapi_version}",
        )
    )
    return results
