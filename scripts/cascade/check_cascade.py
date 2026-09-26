"""Report every place the auth-sdk-m8 / fastapi-m8 release cascade disagrees.

The graph, touchpoints and phase order are owned by
``.workspace/context/dependency-cascade.md``; this module is its executable
mirror. When that file gains a pin, stack, plugin or settings base, this module
changes in the same commit.

Two modes:

* Consistency (default): every touchpoint is compared with the target version
  of the package it names. A target defaults to the package's working-tree
  version (read the way ``version-sources.md`` documents) and can be overridden
  with ``--set repo=version`` to preview what a planned bump has to move.
* ``--env-diff REPO FROM TO``: diff the env-settings fields a platform package
  declares between two Git refs (``WORKTREE`` for the checkout), then list the
  env templates and docs of each inheriting service that the diff affects.

Operator tooling only: it reads tracked source files in child working trees
(and ``git show`` for ``--env-diff``). It never runs child CI, tests, compose or
delivery, never reads a registry, and never opens a real env file — only
``*.example`` templates. It prints paths and key names, never values.

Exit codes: 0 nothing to report, 1 drift found, 2 usage or read error.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

WORKTREE = "WORKTREE"
SKIP_DIRS = frozenset(
    {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", "data"}
)

# Authoritative version source per repository (version-sources.md).
# Each entry lists every file that must carry the same version.
PYPROJECT = "pyproject"
DUNDER = "dunder"
PACKAGE_JSON = "package.json"
VERSION_FILES: dict[str, tuple[tuple[str, str], ...]] = {
    "auth-sdk-m8": ((PYPROJECT, "pyproject.toml"),),
    "fastapi-m8": ((PYPROJECT, "pyproject.toml"), (DUNDER, "fastapi_m8/_version.py")),
    "fa-auth-m8": (
        (DUNDER, "auth_user_service/__init__.py"),
        (DUNDER, "examples/fastapi_full/__init__.py"),
        (DUNDER, "examples/fastapi_minimal/__init__.py"),
    ),
    "media-service-m8": ((DUNDER, "media_service/__init__.py"),),
    "media-worker-m8": ((DUNDER, "worker/__init__.py"),),
    "prompt-engine-m8": ((DUNDER, "promt_engine_service/__init__.py"),),
    "reparto-docente-m8": ((DUNDER, "reparto_service/__init__.py"),),
    "astro-auth-m8": ((PACKAGE_JSON, "package.json"),),
    "astro-media-m8": ((PACKAGE_JSON, "package.json"),),
    "astro-prompt-m8": ((PACKAGE_JSON, "package.json"),),
    "astro-reparto-m8": ((PACKAGE_JSON, "package.json"),),
}

CONSUMER_PACKAGES = {
    "media-service-m8": "media_service",
    "prompt-engine-m8": "promt_engine_service",
    "reparto-docente-m8": "reparto_service",
}
SERVICE_IMAGES = (
    "fa-auth-m8",
    "media-service-m8",
    "media-worker-m8",
    "prompt-engine-m8",
    "reparto-docente-m8",
)
# Directories whose files may state a service image tag. rpi_server is
# operator-local (gitignored by the workspace); its findings are flagged so.
IMAGE_TAG_ROOTS = (
    "fa-auth-m8/examples/docker_compose",
    "fa-ui-m8/docker_compose",
    "media-service-m8/docker_compose",
    "media-worker-m8/docker_compose",
    "prompt-engine-m8/docker_compose",
    "reparto-docente-m8/docker_compose",
    "rpi_server",
)
IMAGE_TAG_FILES = ("fa-auth-m8/README.md", "fa-auth-m8/DOCKERHUB.md")
OPERATOR_LOCAL = ("rpi_server",)
PLUGIN_BACKENDS = {
    "astro-auth-m8": ("fa-auth-m8", "FA_AUTH_M8_"),
    "astro-media-m8": ("media-service-m8", "MEDIA_SERVICE_M8_"),
    "astro-prompt-m8": ("prompt-engine-m8", "PROMPT_ENGINE_M8_"),
    "astro-reparto-m8": ("reparto-docente-m8", "REPARTO_"),
}

# Env-settings bases a platform package declares, and who inherits them.
ISSUER = ("fa-auth-m8",)
CONSUMERS = tuple(CONSUMER_PACKAGES)
SETTINGS_BASES: dict[str, tuple[tuple[str, str, tuple[str, ...]], ...]] = {
    "auth-sdk-m8": (
        ("CommonSettings", "auth_sdk_m8/core/config.py", ISSUER + CONSUMERS),
        (
            "ObservabilitySettingsMixin",
            "auth_sdk_m8/observability/settings.py",
            ISSUER + CONSUMERS,
        ),
        ("ConsumerAuthMixin", "auth_sdk_m8/core/consumer.py", ("fastapi-m8",) + CONSUMERS),
    ),
    "fastapi-m8": (
        ("ConsumerServiceSettings", "fastapi_m8/config.py", ("fastapi-m8",) + CONSUMERS),
    ),
}
# Operator-local env templates, by the service they configure.
OPERATOR_ENV_PREFIXES = {
    "fa-auth-m8": "rpi_server/docente_reparto/auth.env",
    "media-service-m8": "rpi_server/docente_reparto/media.env",
    "prompt-engine-m8": "rpi_server/docente_reparto/prompt.env",
    "reparto-docente-m8": "rpi_server/docente_reparto/reparto.env",
}

DUNDER_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


class CascadeError(Exception):
    """Raised when a required source cannot be read or parsed."""


@dataclass(frozen=True)
class Finding:
    """One touchpoint that disagrees with its target."""

    phase: str
    repo: str
    path: str
    message: str
    operator_local: bool = False


@dataclass(frozen=True)
class Field:
    """One env-settings field as declared on a settings class."""

    annotation: str
    default: str | None


# ---------------------------------------------------------------- utilities


def version_key(version: str) -> tuple[int, int, int]:
    """Return the numeric (major, minor, patch) of a version string."""
    match = SEMVER_RE.match(version)
    if match is None:
        raise CascadeError(f"not a semantic version: {version!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def minor_of(version: str) -> str:
    """Return ``major.minor`` of a version string."""
    major, minor, _ = version_key(version)
    return f"{major}.{minor}"


def read_text(path: Path) -> str:
    """Read a UTF-8 source file or raise a CascadeError naming it."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise CascadeError(f"cannot read {path}: {error}") from error


def rel(workspace: Path, path: Path) -> str:
    """Return a workspace-relative POSIX path for display."""
    return path.relative_to(workspace).as_posix()


def walk_files(root: Path) -> Iterator[Path]:
    """Yield files under root, skipping dependency and build directories."""
    if not root.is_dir():
        return
    for path in sorted(root.iterdir()):
        if path.is_dir():
            if path.name not in SKIP_DIRS:
                yield from walk_files(path)
        elif path.is_file():
            yield path


def is_env_template(path: Path) -> bool:
    """Return True for a tracked env template; never for a real env file."""
    name = path.name
    return name.endswith(".example") and (
        name in {".env.example", "env.example"}
        or name.endswith(".env.example")
        or name.startswith(".env.")
    )


# ---------------------------------------------------------------- versions


def read_version(kind: str, path: Path) -> str:
    """Read one version source the way version-sources.md documents it."""
    text = read_text(path)
    if kind == PYPROJECT:
        version = tomllib.loads(text).get("project", {}).get("version")
        if not isinstance(version, str):
            raise CascadeError(f"{path}: no [project] version literal")
        return version
    if kind == PACKAGE_JSON:
        version = json.loads(text).get("version")
        if not isinstance(version, str):
            raise CascadeError(f"{path}: no version")
        return version
    match = DUNDER_RE.search(text)
    if match is None:
        raise CascadeError(f"{path}: no __version__")
    return match.group(1)


def working_tree_versions(workspace: Path) -> dict[str, str]:
    """Return each present repository's primary working-tree version."""
    versions: dict[str, str] = {}
    for repo, sources in VERSION_FILES.items():
        kind, relative = sources[0]
        path = workspace / repo / relative
        if path.is_file():
            versions[repo] = read_version(kind, path)
    return versions


def check_version_files(workspace: Path, targets: dict[str, str]) -> list[Finding]:
    """Every version file of a repository carries that repository's target."""
    findings: list[Finding] = []
    for repo, sources in VERSION_FILES.items():
        target = targets.get(repo)
        if target is None:
            continue
        for kind, relative in sources:
            path = workspace / repo / relative
            if not path.is_file():
                continue
            found = read_version(kind, path)
            if found != target:
                findings.append(
                    Finding(
                        "version", repo, rel(workspace, path), f"version {found}, target {target}"
                    )
                )
    return findings


# ---------------------------------------------------------------- pins


def floor_of(text: str, package: str) -> list[str]:
    """Return every ``>=`` floor declared for package (extras allowed)."""
    pattern = rf"{re.escape(package)}(?:\[[^\]]*\])?\s*>=\s*([0-9][0-9A-Za-z.+-]*)"
    return re.findall(pattern, text)


def lock_pin_of(text: str, package: str) -> list[str]:
    """Return every ``==`` pin of package at the start of a lock line."""
    pattern = rf"^{re.escape(package)}(?:\[[^\]]*\])?==([^\s\\]+)"
    return re.findall(pattern, text, flags=re.MULTILINE)


def check_pin(
    workspace: Path,
    phase: str,
    repo: str,
    relative: str,
    package: str,
    target: str | None,
    *,
    lock: bool,
) -> list[Finding]:
    """Compare every floor or lock pin of package in one file with target."""
    path = workspace / repo / relative
    if target is None or not path.is_file():
        return []
    text = read_text(path)
    found = lock_pin_of(text, package) if lock else floor_of(text, package)
    kind = "lock pin" if lock else "floor"
    if not found:
        return [Finding(phase, repo, rel(workspace, path), f"no {package} {kind} found")]
    return [
        Finding(phase, repo, rel(workspace, path), f"{package} {kind} {value}, target {target}")
        for value in found
        if value != target
    ]


def check_fastapi(workspace: Path, targets: dict[str, str]) -> list[Finding]:
    """Phase 2: fastapi-m8's SDK floor, COMPAT_MATRIX row and README table."""
    repo = "fastapi-m8"
    sdk = targets.get("auth-sdk-m8")
    own = targets.get(repo)
    findings = check_pin(workspace, "2", repo, "pyproject.toml", "auth-sdk-m8", sdk, lock=False)
    if own is None or sdk is None:
        return findings
    minor = minor_of(own)

    compat = workspace / repo / "fastapi_m8/_compat.py"
    if compat.is_file():
        rows = dict(
            re.findall(
                r'"(\d+\.\d+)"\s*:\s*\{\s*"auth-sdk-m8"\s*:\s*">=([^,"]+),',
                read_text(compat),
            )
        )
        if minor not in rows:
            findings.append(
                Finding(
                    "2",
                    repo,
                    rel(workspace, compat),
                    f'COMPAT_MATRIX has no "{minor}" row (fails closed at startup)',
                )
            )
        elif rows[minor] != sdk:
            findings.append(
                Finding(
                    "2",
                    repo,
                    rel(workspace, compat),
                    f'COMPAT_MATRIX "{minor}" floor {rows[minor]}, target {sdk}',
                )
            )

    readme = workspace / repo / "README.md"
    if readme.is_file():
        rows = re.findall(
            r"^\|\s*`(\d+\.\d+)\.[^`]*`\s*\|\s*`>=\s*([^,`]+),",
            read_text(readme),
            flags=re.MULTILINE,
        )
        floors = [floor for row_minor, floor in rows if row_minor == minor]
        if not floors:
            findings.append(
                Finding(
                    "2", repo, rel(workspace, readme), f"Compatibility table has no {minor}.x row"
                )
            )
        elif sdk not in floors:
            findings.append(
                Finding(
                    "2",
                    repo,
                    rel(workspace, readme),
                    f"Compatibility {minor}.x floor {floors[0]}, target {sdk}",
                )
            )
    return findings


def check_services(workspace: Path, targets: dict[str, str]) -> list[Finding]:
    """Phase 3: issuer and consumer floors and hashed-lock pins."""
    sdk = targets.get("auth-sdk-m8")
    framework = targets.get("fastapi-m8")
    findings: list[Finding] = []

    issuer = "fa-auth-m8"
    findings += check_pin(
        workspace,
        "3",
        issuer,
        "auth_user_service/requirements_base.txt",
        "auth-sdk-m8",
        sdk,
        lock=False,
    )
    findings += check_pin(
        workspace,
        "3",
        issuer,
        "auth_user_service/requirements_prod.lock",
        "auth-sdk-m8",
        sdk,
        lock=True,
    )
    findings += check_pin(
        workspace,
        "3",
        issuer,
        "examples/fastapi_full/requirements_base.txt",
        "fastapi-m8",
        framework,
        lock=False,
    )
    findings += check_pin(
        workspace,
        "3",
        issuer,
        "examples/fastapi_full/requirements_prod.lock",
        "fastapi-m8",
        framework,
        lock=True,
    )
    findings += check_pin(
        workspace,
        "3",
        issuer,
        "examples/fastapi_full/requirements_prod.lock",
        "auth-sdk-m8",
        sdk,
        lock=True,
    )
    findings += check_pin(
        workspace,
        "3",
        issuer,
        ".github/workflows/database-integration.yaml",
        "fastapi-m8",
        framework,
        lock=False,
    )

    for repo, package in CONSUMER_PACKAGES.items():
        findings += check_pin(
            workspace,
            "3",
            repo,
            f"{package}/requirements_base.txt",
            "fastapi-m8",
            framework,
            lock=False,
        )
        findings += check_pin(
            workspace,
            "3",
            repo,
            f"{package}/requirements_prod.lock",
            "fastapi-m8",
            framework,
            lock=True,
        )
        findings += check_pin(
            workspace, "3", repo, f"{package}/requirements_prod.lock", "auth-sdk-m8", sdk, lock=True
        )
    return findings


def image_tag_files(workspace: Path) -> Iterator[Path]:
    """Yield every compose, env-template and doc file that may state a tag."""
    for root in IMAGE_TAG_ROOTS:
        for path in walk_files(workspace / root):
            if path.name == "CHANGELOG.md":
                continue
            if path.suffix in {".yml", ".yaml", ".md"} or is_env_template(path):
                yield path
    for relative in IMAGE_TAG_FILES:
        path = workspace / relative
        if path.is_file():
            yield path


def check_image_tags(workspace: Path, targets: dict[str, str]) -> list[Finding]:
    """Phase 5: every stated service image tag equals the service's target."""
    names = "|".join(re.escape(name) for name in SERVICE_IMAGES)
    pattern = re.compile(rf"tepochtli/({names}):(\d[0-9A-Za-z.+-]*)")
    findings: list[Finding] = []
    for path in image_tag_files(workspace):
        shown = rel(workspace, path)
        local = shown.split("/", 1)[0] in OPERATOR_LOCAL
        for number, line in enumerate(read_text(path).splitlines(), start=1):
            for image, tag in pattern.findall(line):
                target = targets.get(image)
                if target is not None and tag != target:
                    findings.append(
                        Finding(
                            "5", image, f"{shown}:{number}", f"tag {tag}, target {target}", local
                        )
                    )
    return findings


def check_plugins(workspace: Path, targets: dict[str, str]) -> list[Finding]:
    """Phase 6: tested service version and the supported range per plugin."""
    findings: list[Finding] = []
    for plugin, (service, prefix) in PLUGIN_BACKENDS.items():
        path = workspace / plugin / "src/runtime/compatibility.ts"
        target = targets.get(service)
        if target is None or not path.is_file():
            continue
        text = read_text(path)
        constants = dict(
            re.findall(rf'export const {re.escape(prefix)}(\w+)\s*=\s*"([^"]+)"', text)
        )
        shown = rel(workspace, path)
        tested = constants.get("TESTED_SERVICE_VERSION")
        if tested != target:
            findings.append(
                Finding(
                    "6",
                    plugin,
                    shown,
                    f"{prefix}TESTED_SERVICE_VERSION {tested}, target {service} {target}",
                )
            )
        low = constants.get("MIN_SERVICE_VERSION")
        high = constants.get("MAX_SERVICE_VERSION_EXCLUSIVE")
        if low is None or high is None:
            findings.append(
                Finding("6", plugin, shown, "service-version range constants not found")
            )
        elif not version_key(low) <= version_key(target) < version_key(high):
            findings.append(
                Finding("6", plugin, shown, f"{service} {target} is outside >={low} <{high}")
            )
    return findings


def check_version_matrix(workspace: Path, targets: dict[str, str]) -> list[Finding]:
    """Phase 7: version-sources.md map and published table name each target."""
    path = workspace / ".workspace/context/version-sources.md"
    if not path.is_file():
        return []
    text = read_text(path)
    shown = rel(workspace, path)
    map_section = text.split("## Published release vs working-tree version", 1)[0]
    findings: list[Finding] = []
    for repo, target in targets.items():
        mapped = re.search(
            rf"`{re.escape(repo)}`(?: \(`[^`]+`\))? (\d[0-9A-Za-z.+-]*)", map_section
        )
        if mapped is None:
            findings.append(
                Finding("7", repo, shown, "mechanism map has no version for this repository")
            )
        elif mapped.group(1) != target:
            findings.append(
                Finding("7", repo, shown, f"mechanism map {mapped.group(1)}, target {target}")
            )
        row = re.search(
            rf"^\| `{re.escape(repo)}` \| ([^|]+) \| ([^|]+) \|", text, flags=re.MULTILINE
        )
        if row is None:
            findings.append(
                Finding("7", repo, shown, "published table has no row for this repository")
            )
        elif row.group(2).strip() != target:
            findings.append(
                Finding(
                    "7",
                    repo,
                    shown,
                    f"published table working tree {row.group(2).strip()}, target {target}",
                )
            )
    return findings


CONFORMANCE_PINS = {
    "auth-sdk-m8": ("EXPECTED_SDK_VERSION", "SDK_REF"),
    "fastapi-m8": ("EXPECTED_FASTAPI_VERSION", "FASTAPI_REF"),
    "fa-auth-m8": ("EXPECTED_ISSUER_VERSION", "ISSUER_REF"),
}


def check_conformance(workspace: Path, targets: dict[str, str]) -> list[Finding]:
    """Phase 7: the workspace conformance harness's pinned platform matrix."""
    matrix = workspace / "scripts/conformance/local_package_matrix.py"
    workflow = workspace / ".github/workflows/cross-repo-conformance.yml"
    findings: list[Finding] = []
    for repo, (constant, ref) in CONFORMANCE_PINS.items():
        target = targets.get(repo)
        if target is None:
            continue
        for path, name, pattern in (
            (matrix, constant, rf'^{constant}\s*=\s*"([^"]+)"'),
            (workflow, ref, rf"^\s*{ref}:\s*v?(\S+)"),
        ):
            if not path.is_file():
                continue
            found = re.search(pattern, read_text(path), flags=re.MULTILINE)
            shown = rel(workspace, path)
            if found is None:
                findings.append(Finding("7", repo, shown, f"{name} not found"))
            elif found.group(1) != target:
                findings.append(
                    Finding("7", repo, shown, f"{name} {found.group(1)}, target {target}")
                )
    return findings


def consistency(workspace: Path, overrides: dict[str, str]) -> list[Finding]:
    """Run every phase check against working-tree versions plus overrides."""
    targets = working_tree_versions(workspace)
    unknown = sorted(set(overrides) - set(VERSION_FILES))
    if unknown:
        raise CascadeError(f"unknown repository in --set: {', '.join(unknown)}")
    for version in overrides.values():
        version_key(version)
    targets.update(overrides)
    return (
        check_version_files(workspace, targets)
        + check_fastapi(workspace, targets)
        + check_services(workspace, targets)
        + check_image_tags(workspace, targets)
        + check_plugins(workspace, targets)
        + check_version_matrix(workspace, targets)
        + check_conformance(workspace, targets)
    )


# ---------------------------------------------------------------- env diff


def without_description(value: ast.expr) -> ast.expr:
    """Drop a call's ``description=`` keyword: prose is not an env change."""
    if not isinstance(value, ast.Call):
        return value
    keywords = [keyword for keyword in value.keywords if keyword.arg != "description"]
    return ast.Call(func=value.func, args=value.args, keywords=keywords)


def settings_fields(source: str, class_name: str) -> dict[str, Field]:
    """Return the uppercase, non-ClassVar annotated fields of one class."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            fields: dict[str, Field] = {}
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(
                    statement.target, ast.Name
                ):
                    continue
                name = statement.target.id
                annotation = ast.unparse(statement.annotation)
                if not name.isupper() or annotation.startswith(("ClassVar", "typing.ClassVar")):
                    continue
                default = (
                    None
                    if statement.value is None
                    else ast.unparse(without_description(statement.value))
                )
                fields[name] = Field(annotation, default)
            return fields
    raise CascadeError(f"class {class_name} not found")


def is_required(field: Field) -> bool:
    """A field with no default, or ``Field(...)``, must be set in the env."""
    if field.default is None:
        return True
    return re.match(r"^(?:\w+\.)?Field\(\s*\.\.\.", field.default) is not None


def source_at(workspace: Path, repo: str, ref: str, relative: str) -> str:
    """Return a file's text at a Git ref, or from the working tree."""
    if ref == WORKTREE:
        return read_text(workspace / repo / relative)
    result = subprocess.run(
        ["git", "-C", str(workspace / repo), "show", f"{ref}:{relative}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise CascadeError(f"git show {ref}:{relative} in {repo} failed: {result.stderr.strip()}")
    return result.stdout


def repo_env_templates(workspace: Path, repo: str) -> list[Path]:
    """Return a repository's env templates plus its operator-local ones."""
    templates = [path for path in walk_files(workspace / repo) if is_env_template(path)]
    prefix = OPERATOR_ENV_PREFIXES.get(repo)
    if prefix is not None:
        parent = (workspace / prefix).parent
        stem = Path(prefix).name
        templates += [
            path
            for path in walk_files(parent)
            if path.name.startswith(stem) and path.name.endswith(".example")
        ]
    return templates


def repo_docs(workspace: Path, repo: str) -> list[Path]:
    """Return a repository's README files, excluding dependency trees."""
    return [path for path in walk_files(workspace / repo) if path.name == "README.md"]


def env_diff(workspace: Path, repo: str, before: str, after: str) -> list[Finding]:
    """Diff a platform package's settings fields and locate affected files."""
    bases = SETTINGS_BASES.get(repo)
    if bases is None:
        raise CascadeError(f"--env-diff supports {', '.join(SETTINGS_BASES)}, not {repo}")
    findings: list[Finding] = []
    for class_name, relative, inheritors in bases:
        old = settings_fields(source_at(workspace, repo, before, relative), class_name)
        new = settings_fields(source_at(workspace, repo, after, relative), class_name)
        where = f"{repo}/{relative}"
        added = sorted(set(new) - set(old))
        removed = sorted(set(old) - set(new))
        changed = sorted(name for name in set(old) & set(new) if old[name] != new[name])
        for name in added:
            state = "required" if is_required(new[name]) else f"default {new[name].default}"
            findings.append(Finding("4", repo, where, f"{class_name}.{name} added ({state})"))
        for name in removed:
            findings.append(Finding("4", repo, where, f"{class_name}.{name} removed"))
        for name in changed:
            findings.append(
                Finding(
                    "4",
                    repo,
                    where,
                    f"{class_name}.{name} changed: {old[name].annotation} = {old[name].default} -> {new[name].annotation} = {new[name].default}",
                )
            )
        must_template = [name for name in added if is_required(new[name])]
        must_template += [
            name for name in changed if is_required(new[name]) and not is_required(old[name])
        ]
        for inheritor in inheritors:
            findings += locate_keys(workspace, inheritor, class_name, must_template, removed)
    return findings


def locate_keys(
    workspace: Path, repo: str, class_name: str, required: Iterable[str], removed: Iterable[str]
) -> list[Finding]:
    """List templates missing a required key and files still naming a removed one."""
    findings: list[Finding] = []
    templates = repo_env_templates(workspace, repo)
    for name in required:
        line = re.compile(rf"^\s*#?\s*{re.escape(name)}\s*=", re.MULTILINE)
        for path in templates:
            if not line.search(read_text(path)):
                shown = rel(workspace, path)
                findings.append(
                    Finding(
                        "4",
                        repo,
                        shown,
                        f"template lacks required {class_name}.{name}",
                        shown.startswith(OPERATOR_LOCAL),
                    )
                )
    for name in removed:
        word = re.compile(rf"\b{re.escape(name)}\b")
        for path in templates + repo_docs(workspace, repo):
            if word.search(read_text(path)):
                shown = rel(workspace, path)
                findings.append(
                    Finding(
                        "4",
                        repo,
                        shown,
                        f"still names removed {class_name}.{name}",
                        shown.startswith(OPERATOR_LOCAL),
                    )
                )
    return findings


# ---------------------------------------------------------------- CLI


def parse_set(values: list[str]) -> dict[str, str]:
    """Parse repeated ``repo=version`` overrides."""
    overrides: dict[str, str] = {}
    for value in values:
        repo, separator, version = value.partition("=")
        if not separator or not repo or not version:
            raise CascadeError(f"--set expects repo=version, got {value!r}")
        overrides[repo] = version
    return overrides


def render(findings: list[Finding]) -> str:
    """Format findings grouped by phase for a terminal."""
    if not findings:
        return "cascade consistent: nothing to report"
    lines = [f"{len(findings)} finding(s)"]
    for finding in sorted(findings, key=lambda item: (item.phase, item.repo, item.path)):
        local = " [operator-local]" if finding.operator_local else ""
        lines.append(
            f"  phase {finding.phase:<7} {finding.repo:<18} {finding.path}: {finding.message}{local}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the requested mode and return the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--set", action="append", default=[], metavar="REPO=VERSION", help="target override"
    )
    parser.add_argument(
        "--env-diff", nargs=3, metavar=("REPO", "FROM", "TO"), help=f"TO may be {WORKTREE}"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    workspace: Path = args.workspace.resolve()
    try:
        if args.env_diff:
            repo, before, after = args.env_diff
            findings = env_diff(workspace, repo, before, after)
        else:
            findings = consistency(workspace, parse_set(args.set))
    except CascadeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    else:
        print(render(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
