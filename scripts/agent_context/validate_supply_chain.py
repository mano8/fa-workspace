"""Validate root CI supply-chain pins without running child CI."""

from __future__ import annotations

import argparse
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    arguments = parser.parse_args()
    validate_supply_chain(arguments.workspace.resolve())
    print("supply-chain validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
