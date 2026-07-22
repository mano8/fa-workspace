"""Validate root CI supply-chain pins without running child CI."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ACTION_RE = re.compile(
    r"^\s*- uses:\s*(?P<name>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(?P<ref>[^\s#]+)"
    r"\s+#\s+(?P<version>v\S+)\s*$"
)
REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[^\s\\]+)\s*\\?\s*$"
)
HASH_RE = re.compile(r"^\s+--hash=sha256:(?P<hash>[0-9a-f]{64})\s*$")
HEADROOM_REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+(?:\[[^]]+\])?)==(?P<version>\S+)"
    r"\s+--hash=sha256:(?P<hash>[0-9a-f]{64})$"
)


def _fail(message: str) -> None:
    raise SystemExit(f"supply-chain validation failed: {message}")


def validate_supply_chain(workspace: Path) -> None:
    workflow = workspace / ".github/workflows/workspace-policy-lint.yml"
    lock = workspace / ".github/workflows/root-tooling.requirements.lock"
    workflow_lines = workflow.read_text(encoding="utf-8").splitlines()
    action_count = 0
    for line_number, line in enumerate(workflow_lines, 1):
        if "uses:" not in line:
            continue
        match = ACTION_RE.match(line)
        if match is None or not re.fullmatch(r"[0-9a-f]{40}", match["ref"]):
            _fail(f"{workflow.relative_to(workspace)}:{line_number} has an unreviewed Action ref")
        action_count += 1
    if action_count == 0:
        _fail("root workflow contains no pinned Actions")

    packages: dict[str, tuple[str, set[str]]] = {}
    pending_name: str | None = None
    pending_version: str | None = None
    for line_number, line in enumerate(lock.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = REQUIREMENT_RE.match(line)
        if requirement:
            pending_name = requirement["name"].lower().replace("_", "-")
            pending_version = requirement["version"]
            packages[pending_name] = (pending_version, set())
            continue
        hash_match = HASH_RE.match(line)
        if hash_match and pending_name is not None:
            packages[pending_name][1].add(hash_match["hash"])
            continue
        _fail(f"{lock.relative_to(workspace)}:{line_number} has malformed lock content")
    required = {"ruff": "0.15.22", "cryptography": "49.0.0", "cffi": "2.1.0", "pycparser": "3.0"}
    if set(packages) != set(required):
        _fail("tooling lock package set is not the reviewed root set")
    for name, version in required.items():
        actual_version, hashes = packages[name]
        if actual_version != version or not hashes:
            _fail(f"{name} is not pinned with at least one SHA-256 hash")
    if "--require-hashes" not in "\n".join(workflow_lines):
        _fail("workflow does not require pip hash verification")

    headroom_lock = workspace / ".devcontainer/headroom.requirements.lock"
    bootstrap_lock = workspace / ".devcontainer/bootstrap-lock.json"
    feature_lock = workspace / ".devcontainer/devcontainer-lock.json"
    devcontainer = json.loads(
        (workspace / ".devcontainer/devcontainer.json").read_text(encoding="utf-8")
    )
    setup = (workspace / ".devcontainer/setup.sh").read_text(encoding="utf-8")
    compose = (workspace / ".devcontainer/docker-compose.devcontainer.yml").read_text(encoding="utf-8")
    dockerfile = (workspace / ".devcontainer/Dockerfile").read_text(encoding="utf-8")
    locked = json.loads(bootstrap_lock.read_text(encoding="utf-8"))
    locked_features = json.loads(feature_lock.read_text(encoding="utf-8"))
    bootstrap = locked["bootstrap"]
    headroom_lines = [
        line for line in headroom_lock.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    parsed = [HEADROOM_REQUIREMENT_RE.fullmatch(line) for line in headroom_lines]
    if len(parsed) < 2 or any(match is None for match in parsed):
        _fail("Headroom transitive lock is absent or contains an unhashed requirement")
    names = [match["name"].split("[", 1)[0].lower().replace("_", "-") for match in parsed if match]
    if len(names) != len(set(names)) or "headroom-ai" not in names:
        _fail("Headroom transitive lock has duplicate packages or lacks Headroom")
    lock_sha256 = hashlib.sha256(headroom_lock.read_bytes()).hexdigest()
    if bootstrap["headroom"].get("requirements_sha256") != lock_sha256:
        _fail("Headroom lock digest does not match bootstrap-lock.json")
    if not all(token in setup for token in ("--only-binary=:all:", "--require-hashes", "--no-deps")):
        _fail("Headroom setup does not enforce the complete hashed wheel lock")
    root_lock_sha256 = hashlib.sha256(lock.read_bytes()).hexdigest()
    if bootstrap["root_tooling"].get("record_sha256") != root_lock_sha256:
        _fail("root-tooling lock digest does not match bootstrap-lock.json")
    if "/workspace/.github/workflows/root-tooling.requirements.lock" not in setup:
        _fail("shared root venv is not installed from the hashed root-tooling lock")
    child_requirements = (
        "fa-auth-m8/auth_user_service/requirements_dev.txt",
        "imgtools_m8/requirements.txt",
        "media-service-m8/media_service/requirements_dev.txt",
    )
    if any(value in setup for value in child_requirements):
        _fail("root bootstrap must not install floating child-owned requirements")
    proxy = bootstrap["headroom_proxy"]
    if proxy.get("resolved") not in compose or proxy.get("binary_sha256") not in proxy.get("resolved", ""):
        _fail("Headroom proxy image is not pinned to the reviewed digest")
    base_image = locked["base_image"]
    python_image = locked.get("runtime_images", {}).get("python", {})
    if base_image.get("resolved") not in dockerfile:
        _fail("Dev Container base image is not pinned to the reviewed digest in Dockerfile")
    if python_image.get("resolved") not in dockerfile:
        _fail("Python runtime image is not pinned to the reviewed digest in Dockerfile")
    if bootstrap["python_runtime"].get("resolved") != python_image.get("resolved"):
        _fail("Python bootstrap identity differs from its reviewed runtime image")
    if any("devcontainers/features/python" in feature for feature in devcontainer.get("features", {})):
        _fail("Python must come from the content-addressed runtime image, not a source-building feature")
    if any("anthropics/devcontainer-features/claude-code" in feature for feature in devcontainer.get("features", {})):
        _fail("Claude Code must come from the exact hash-verified bootstrap, not a floating feature")
    runtime_features = {
        "node_runtime": "ghcr.io/devcontainers/features/node:2",
    }
    for runtime, feature in runtime_features.items():
        version = bootstrap[runtime]["version"]
        if devcontainer.get("features", {}).get(feature, {}).get("version") != version:
            _fail(f"{runtime} feature option is not exact or differs from its lock")
        if locked["feature_options"][feature].get("version") != version:
            _fail(f"{runtime} devcontainer lock option differs from bootstrap identity")
    reviewed_options = {
        "ghcr.io/devcontainers/features/node:2": {
            "pnpmVersion": "none", "nvmVersion": "0.40.6",
        },
        "ghcr.io/devcontainers/features/docker-outside-of-docker:1": {
            "version": "29.6.1", "moby": False,
            "dockerDashComposeVersion": "none", "installDockerBuildx": False,
        },
    }
    if set(locked_features) != {"features"}:
        _fail("Dev Container lock must contain only the canonical features object")
    if set(locked_features["features"]) != set(reviewed_options):
        _fail("Dev Container feature lock differs from the reviewed feature set")
    if set(locked.get("feature_options", {})) != set(reviewed_options):
        _fail("bootstrap feature options differ from the reviewed feature set")
    for feature, expected in reviewed_options.items():
        actual = devcontainer.get("features", {}).get(feature, {})
        if any(actual.get(name) != value for name, value in expected.items()):
            _fail(f"{feature} options are not the reviewed deterministic set")
        locked_feature = locked_features["features"].get(feature)
        if not isinstance(locked_feature, dict) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", locked_feature.get("integrity", ""),
        ):
            _fail(f"{feature} is not content-bound by the Dev Container lock")
        feature_resource = feature.rsplit(":", 1)[0]
        if locked_feature.get("resolved") != f"{feature_resource}@{locked_feature['integrity']}":
            _fail(f"{feature} resolved digest differs from its integrity lock")
        locked_options = locked["feature_options"][feature]
        if any(locked_options.get(name) != value for name, value in expected.items()):
            _fail(f"{feature} lock options differ from the reviewed deterministic set")
    enforced = (
        bootstrap["claude"], bootstrap["codex"], bootstrap["headroom"], bootstrap["node_runtime"],
        bootstrap["python_runtime"], bootstrap["root_tooling"],
        bootstrap["apt_ca_certificates"], bootstrap["apt_curl"], bootstrap["apt_git"],
        bootstrap["apt_jq"],
    )
    for item in enforced:
        for value in (item["version"], item.get("binary_sha256") or item.get("record_sha256")):
            if value is not None and value not in setup:
                _fail(f"bootstrap setup does not enforce {item['package']} identity")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    arguments = parser.parse_args()
    validate_supply_chain(arguments.workspace.resolve())
    print("supply-chain validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
