"""Generate and validate the deterministic CycloneDX root-tooling inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any


SBOM_PATH = Path("sbom/root-tooling.cdx.json")
SOURCE_PATHS = (
    Path(".devcontainer/devcontainer-lock.json"),
    Path(".devcontainer/devcontainer.json"),
    Path(".devcontainer/setup.sh"),
    Path(".devcontainer/headroom.requirements.lock"),
    Path(".github/workflows/workspace-policy-lint.yml"),
    Path(".github/workflows/root-tooling.requirements.lock"),
)
ACTION_RE = re.compile(r"^\s*- uses:\s*(?P<name>[^@\s]+)@(?P<ref>[^\s#]+)\s+#\s+(?P<version>v\S+)\s*$")
REQUIREMENT_RE = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+(?:\[[^]]+\])?)==(?P<version>[^\s\\]+)")


class SbomError(ValueError):
    """Raised when the reviewed SBOM inputs or artifact are invalid."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _component(*, component_type: str, name: str, version: str, source: str, integrity: str | None = None) -> dict[str, Any]:
    reference = f"{component_type}:{name}@{version}"
    component: dict[str, Any] = {
        "bom-ref": reference,
        "type": component_type,
        "name": name,
        "version": version,
        "properties": [{"name": "m8:source", "value": source}],
    }
    if integrity:
        component["hashes"] = [{"alg": "SHA-256", "content": integrity.removeprefix("sha256:")}]
    return component


def build_sbom(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    raw_sources = {path.as_posix(): _sha256(workspace / path) for path in SOURCE_PATHS}
    lock = json.loads((workspace / ".devcontainer/devcontainer-lock.json").read_text(encoding="utf-8"))
    components: list[dict[str, Any]] = []
    components.append(_component(
        component_type="container", name=lock["base_image"]["reference"],
        version=lock["base_image"]["resolved"], source=".devcontainer/devcontainer-lock.json",
        integrity=lock["base_image"]["integrity"],
    ))
    for name, feature in sorted(lock["features"].items()):
        components.append(_component(
            component_type="container", name=name, version=feature["version"],
            source=".devcontainer/devcontainer-lock.json", integrity=feature["integrity"],
        ))
    for name, bootstrap in sorted(lock["bootstrap"].items()):
        components.append(_component(
            component_type="application", name=bootstrap["package"], version=bootstrap["version"],
            source=".devcontainer/devcontainer-lock.json",
            integrity=bootstrap.get("binary_sha256") or bootstrap.get("record_sha256"),
        ))
    for relative in (".devcontainer/headroom.requirements.lock", ".github/workflows/root-tooling.requirements.lock"):
        for line in (workspace / relative).read_text(encoding="utf-8").splitlines():
            match = REQUIREMENT_RE.match(line)
            if match:
                components.append(_component(
                    component_type="library", name=match["name"], version=match["version"], source=relative,
                ))
    for line in (workspace / ".github/workflows/workspace-policy-lint.yml").read_text(encoding="utf-8").splitlines():
        match = ACTION_RE.match(line)
        if match:
            components.append(_component(
            component_type="application", name=match["name"], version=match["version"],
            source=".github/workflows/workspace-policy-lint.yml",
            ))
    components.sort(key=lambda component: component["bom-ref"])
    digest = hashlib.sha256(json.dumps(raw_sources, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'm8-root-tooling:{digest}')}",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "name": "fa-workspace-root-tooling", "version": digest},
            "properties": [
                {"name": "m8:deterministic", "value": "true"},
                *[{"name": f"m8:source-sha256:{path}", "value": value} for path, value in sorted(raw_sources.items())],
            ],
        },
        "components": components,
    }


def canonical_bytes(workspace: Path) -> bytes:
    return (json.dumps(build_sbom(workspace), indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate_sbom(workspace: Path) -> None:
    path = workspace / SBOM_PATH
    try:
        actual = path.read_bytes()
        parsed = json.loads(actual)
    except (OSError, json.JSONDecodeError) as error:
        raise SbomError(f"cannot parse {SBOM_PATH}: {error}") from error
    if parsed.get("bomFormat") != "CycloneDX" or parsed.get("specVersion") != "1.6":
        raise SbomError("SBOM is not CycloneDX 1.6")
    if "timestamp" in parsed.get("metadata", {}):
        raise SbomError("SBOM metadata must not contain a nondeterministic timestamp")
    references = [component.get("bom-ref") for component in parsed.get("components", [])]
    if len(references) != len(set(references)) or any(not isinstance(reference, str) for reference in references):
        raise SbomError("SBOM component references must be unique strings")
    expected = canonical_bytes(workspace)
    if actual != expected:
        raise SbomError("SBOM is stale; regenerate it from the reviewed root-tooling inputs")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="verify the tracked SBOM is current")
    parser.add_argument("--write", action="store_true", help="write the canonical tracked SBOM")
    arguments = parser.parse_args()
    workspace = arguments.workspace.resolve()
    if arguments.check and arguments.write:
        parser.error("--check and --write are mutually exclusive")
    if arguments.check:
        validate_sbom(workspace)
        print("root-tooling SBOM validation passed")
    elif arguments.write:
        (workspace / SBOM_PATH).parent.mkdir(parents=True, exist_ok=True)
        (workspace / SBOM_PATH).write_bytes(canonical_bytes(workspace))
        print(f"wrote {SBOM_PATH}")
    else:
        sys.stdout.buffer.write(canonical_bytes(workspace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
