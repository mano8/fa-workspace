"""Validate the frozen Phase 10 Step 10.1 remediation contract and register."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context import w2b1


REGISTER_PATH = PurePosixPath(".workspace/contracts/agent-context-w9a-findings.json")
CONTRACT_PATH = PurePosixPath(
    ".workspace/contracts/agent-context-w9a-remediation.contract.md"
)
TOP_FIELDS = {
    "schema_version",
    "register_id",
    "status",
    "frozen_at",
    "contract_path",
    "capability_ceiling",
    "source_inputs",
    "amendments",
    "findings",
    "input_limitations",
}
CAPABILITY_FIELDS = {
    "required_rows",
    "limited_rows",
    "unsupported_rows",
    "canonical_activation",
}
SOURCE_FIELDS = {
    "id",
    "classification",
    "path",
    "sha256",
    "required_in_clean_checkout",
}
AMENDMENT_FIELDS = {"id", "owner_step", "contract_section", "decision"}
FINDING_FIELDS = {
    "id",
    "severity",
    "title",
    "status",
    "blocking",
    "source_ids",
    "disposition",
    "remediation_step",
    "dependencies",
    "owner",
    "negative_tests",
    "closure_artifacts",
    "amendment_sections",
    "invalidation_triggers",
}
LIMITATION_FIELDS = FINDING_FIELDS - {"severity", "blocking"} | {"classification"}
EXPECTED_CAPABILITY_CEILING = {
    "required_rows": ["codex:devcontainer:non-interactive"],
    "limited_rows": [
        "claude:devcontainer:interactive",
        "claude:devcontainer:non-interactive",
        "codex:devcontainer:interactive",
    ],
    "unsupported_rows": [
        "claude:external-posix:interactive",
        "claude:external-posix:non-interactive",
        "claude:windows:interactive",
        "claude:windows:non-interactive",
        "codex:external-posix:interactive",
        "codex:external-posix:non-interactive",
        "codex:windows:interactive",
        "codex:windows:non-interactive",
    ],
    "canonical_activation": "disabled-until-10.2-through-10.8-pass",
}
EXPECTED_SOURCES = {
    "capability-evidence": (
        "tracked-normative-input",
        "scripts/agent_context/fixtures/evidence/capability-evidence-2026-07-19.md",
        "d921bcdbc26cb4e65ffc6f0ab642d191d543987594df5291cc904a01a4562e7b",
        True,
    ),
    "critical-audit-en": (
        "external-review-input",
        ".workspace/plans/fa-workspace/feedback/phase-9-5-critical-sign-off-audit-en.md",
        "f07be4be2bc39cad5cff72d741b9c84d4f6970b7a83d21d1afb74785d1109078",
        False,
    ),
    "critical-audit-fr": (
        "external-review-input",
        ".workspace/plans/fa-workspace/feedback/deep-research-report.md",
        "142bc1658704b1819a4310fb0b791f8cd1761fe2379b98cb854fbd18750132ff",
        False,
    ),
    "w2a-contract": (
        "tracked-normative-input",
        ".workspace/contracts/agent-context-w2a.contract.md",
        "c5400f05255cb71f1b7de39cbb50d7d6578783d9f05fa153732651e00fa094e6",
        True,
    ),
}
EXPECTED_AMENDMENTS = {
    "authorization": ("10.2", "4", "ed25519-signed-external-single-use-capability"),
    "handoff": ("10.3", "5", "durable-submission-started-with-terminal-ambiguity"),
    "lifecycle": ("10.6", "8", "start-resume-fresh-cleanup-no-compact"),
    "multi-repository": ("10.4", "6", "root-native-selected-children-injected"),
    "trust-identity": (
        "10.5",
        "7",
        "content-bound-clean-root-child-toolchain-identity",
    ),
}
EXPECTED_FINDINGS = {
    "C-1": ("critical", True, "10.2", ("10.1",)),
    "C-2": ("critical", True, "10.3", ("10.1", "10.2")),
    "H-1": ("high", True, "10.4", ("10.1", "10.3")),
    "H-2": ("high", True, "10.5", ("10.1",)),
    "H-3": ("high", True, "10.6", ("10.3", "10.5")),
    "M-1": ("medium", False, "10.7", ("10.5",)),
    "M-2": (
        "medium",
        False,
        "10.8",
        ("10.2", "10.3", "10.4", "10.5", "10.6", "10.7"),
    ),
    "M-3": (
        "medium",
        False,
        "10.9",
        ("10.2", "10.3", "10.4", "10.5", "10.6", "10.7", "10.8"),
    ),
    "M-4": ("medium", False, "10.5", ("10.1",)),
    "L-1": ("low", False, "10.10", ("10.5",)),
    "L-2": ("low", False, "10.11", ("10.5", "10.10")),
}
EXPECTED_FINDING_ORDER = tuple(EXPECTED_FINDINGS)
EXPECTED_CONTRACT_MARKERS = (
    "`IMPLEMENTED_PENDING_W9F_FINAL_REVIEW`",
    "Ed25519",
    "SUBMISSION_STARTED",
    "EXECUTION_AMBIGUOUS",
    "execution directory is the reviewed workspace root",
    "the sole native instruction source",
    "clean tracked-worktree and clean-index proof",
    "`start`",
    "`resume`",
    "`fresh`",
    "`compact`: unsupported",
)
FINDING_ID_RE = re.compile(r"^[CHML]-[1-9][0-9]*$")
OWNER_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STEP_RE = re.compile(r"^10\.(?:[1-9]|1[0-2])$")
TEST_RE = re.compile(
    r"^scripts\.agent_context\.tests\.test_[a-z0-9_]+\.[A-Za-z0-9_]+\.test_[a-z0-9_]+$"
)


class W9aContractError(ValueError):
    """Raised when the W9a contract or register is incomplete or inconsistent."""


@dataclass(frozen=True)
class W9aContractReport:
    finding_count: int
    blocking_count: int
    limitation_count: int
    named_negative_test_count: int
    named_closure_artifact_count: int


def _fail(message: str) -> NoReturn:
    raise W9aContractError(message)


def _closed(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{label} must be an object")
    missing = fields - set(value)
    unknown = set(value) - fields
    if missing:
        _fail(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        _fail(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    return value


def _canonical_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} must be a non-empty path")
    path = PurePosixPath(value)
    if path.is_absolute() or "\\" in value or "\x00" in value or "%" in value:
        _fail(f"{label} must be a canonical workspace-relative POSIX path")
    if any(part in {"", ".", ".."} for part in path.parts):
        _fail(f"{label} must be a canonical workspace-relative POSIX path")
    return value


def _unique_strings(
    value: Any, label: str, *, nonempty: bool = True, sorted_values: bool = True
) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        _fail(f"{label} must be {'a non-empty ' if nonempty else 'an '}array")
    if any(not isinstance(item, str) or not item for item in value):
        _fail(f"{label} entries must be non-empty strings")
    if len(value) != len(set(value)):
        _fail(f"{label} must not contain duplicates")
    if sorted_values and value != sorted(value):
        _fail(f"{label} must be sorted")
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        _fail(f"could not hash {path}: {error}")


def _read_register(path: Path) -> dict[str, Any]:
    try:
        value = w2b1.parse_strict_json(path.read_bytes())
    except (OSError, w2b1.AgentContextError) as error:
        _fail(f"invalid W9a finding register: {error}")
    return _closed(value, TOP_FIELDS, "W9a finding register")


def _validate_sources(workspace: Path, supplied: Any) -> set[str]:
    if not isinstance(supplied, list) or len(supplied) != len(EXPECTED_SOURCES):
        _fail("source_inputs must contain exactly the four frozen inputs")
    identifiers: list[str] = []
    for position, raw in enumerate(supplied):
        source = _closed(raw, SOURCE_FIELDS, f"source_inputs[{position}]")
        source_id = source["id"]
        if not isinstance(source_id, str):
            _fail(f"source_inputs[{position}].id must be a string")
        identifiers.append(source_id)
        expected = EXPECTED_SOURCES.get(source_id)
        if expected is None:
            _fail(f"unknown frozen source input: {source_id}")
        classification, path_text, digest, required = expected
        actual = (
            source["classification"],
            source["path"],
            source["sha256"],
            source["required_in_clean_checkout"],
        )
        if actual != expected:
            _fail(f"frozen source input changed: {source_id}")
        _canonical_path(path_text, f"source_inputs[{position}].path")
        path = workspace / path_text
        if required and not path.is_file():
            _fail(f"required tracked source input is missing: {path_text}")
        if path.exists() and _sha256(path) != digest:
            _fail(f"frozen source input hash changed: {source_id}")
        if classification == "external-review-input" and required:
            _fail("external review inputs cannot be required in a clean checkout")
    if identifiers != sorted(EXPECTED_SOURCES):
        _fail("source_inputs must be sorted by id")
    return set(identifiers)


def _validate_amendments(supplied: Any) -> set[str]:
    if not isinstance(supplied, list) or len(supplied) != len(EXPECTED_AMENDMENTS):
        _fail("amendments must contain exactly the five W9a decisions")
    identifiers: list[str] = []
    sections: set[str] = set()
    for position, raw in enumerate(supplied):
        amendment = _closed(raw, AMENDMENT_FIELDS, f"amendments[{position}]")
        amendment_id = amendment["id"]
        identifiers.append(amendment_id)
        expected = EXPECTED_AMENDMENTS.get(amendment_id)
        if expected is None or (
            amendment["owner_step"],
            amendment["contract_section"],
            amendment["decision"],
        ) != expected:
            _fail(f"frozen amendment changed: {amendment_id}")
        sections.add(amendment["contract_section"])
    if identifiers != sorted(EXPECTED_AMENDMENTS):
        _fail("amendments must be sorted by id")
    return sections


def _test_module_path(test_name: str) -> str:
    module = test_name.split(".", 5)[3]
    return f"scripts/agent_context/tests/{module}.py"


def _validate_item_lists(item: dict[str, Any], label: str) -> tuple[int, int, set[str]]:
    source_ids = _unique_strings(item["source_ids"], f"{label}.source_ids")
    if source_ids != ["critical-audit-en", "critical-audit-fr"]:
        _fail(f"{label} must cite both critical audits")
    dependencies = _unique_strings(
        item["dependencies"], f"{label}.dependencies", sorted_values=False
    )
    if any(STEP_RE.fullmatch(step) is None for step in dependencies):
        _fail(f"{label}.dependencies contains an invalid Phase 10 step")
    negative_tests = _unique_strings(item["negative_tests"], f"{label}.negative_tests")
    if any(TEST_RE.fullmatch(name) is None for name in negative_tests):
        _fail(f"{label}.negative_tests contains an invalid test name")
    artifacts = _unique_strings(item["closure_artifacts"], f"{label}.closure_artifacts")
    for position, artifact in enumerate(artifacts):
        _canonical_path(artifact, f"{label}.closure_artifacts[{position}]")
    for test_name in negative_tests:
        if _test_module_path(test_name) not in artifacts:
            _fail(f"{label} does not name the module for negative test {test_name}")
    section_list = _unique_strings(
        item["amendment_sections"],
        f"{label}.amendment_sections",
        sorted_values=False,
    )
    if any(not section.isdigit() for section in section_list) or section_list != sorted(
        section_list, key=int
    ):
        _fail(f"{label}.amendment_sections must be numerically sorted")
    sections = set(section_list)
    _unique_strings(item["invalidation_triggers"], f"{label}.invalidation_triggers")
    owner = item["owner"]
    if not isinstance(owner, str) or OWNER_RE.fullmatch(owner) is None:
        _fail(f"{label}.owner is invalid")
    if not isinstance(item["title"], str) or not item["title"].strip():
        _fail(f"{label}.title is required")
    if not isinstance(item["disposition"], str) or not item["disposition"]:
        _fail(f"{label}.disposition is required")
    if STEP_RE.fullmatch(item["remediation_step"]) is None:
        _fail(f"{label}.remediation_step is invalid")
    return len(negative_tests), len(artifacts), sections


def _validate_findings(supplied: Any) -> tuple[int, int, int, set[str]]:
    if not isinstance(supplied, list) or len(supplied) != len(EXPECTED_FINDINGS):
        _fail("findings must contain exactly the eleven reconciled findings")
    identifiers: list[str] = []
    blocking_count = 0
    test_count = 0
    artifact_count = 0
    used_sections: set[str] = set()
    for position, raw in enumerate(supplied):
        finding = _closed(raw, FINDING_FIELDS, f"findings[{position}]")
        finding_id = finding["id"]
        if not isinstance(finding_id, str) or FINDING_ID_RE.fullmatch(finding_id) is None:
            _fail(f"findings[{position}].id is invalid")
        identifiers.append(finding_id)
        expected = EXPECTED_FINDINGS.get(finding_id)
        if expected is None:
            _fail(f"unknown finding: {finding_id}")
        severity, blocking, step, dependencies = expected
        if (
            finding["severity"],
            finding["blocking"],
            finding["remediation_step"],
            tuple(finding["dependencies"]),
        ) != (severity, blocking, step, dependencies):
            _fail(f"frozen severity/blocking/step/dependency mapping changed: {finding_id}")
        if finding["status"] != "OPEN":
            _fail(f"W9a cannot close finding {finding_id}")
        if blocking:
            blocking_count += 1
        tests, artifacts, sections = _validate_item_lists(
            finding, f"finding {finding_id}"
        )
        test_count += tests
        artifact_count += artifacts
        used_sections.update(sections)
    if tuple(identifiers) != EXPECTED_FINDING_ORDER:
        _fail("findings must retain the frozen C/H/M/L order")
    return blocking_count, test_count, artifact_count, used_sections


def _validate_limitations(supplied: Any) -> tuple[int, int, set[str]]:
    if not isinstance(supplied, list) or len(supplied) != 1:
        _fail("input_limitations must contain exactly the ZIP limitation")
    limitation = _closed(supplied[0], LIMITATION_FIELDS, "input_limitations[0]")
    if (
        limitation["id"] != "zip-reproducibility"
        or limitation["classification"] != "non-finding-input-limitation"
        or limitation["status"] != "OPEN"
        or limitation["remediation_step"] != "10.12"
        or tuple(limitation["dependencies"])
        != tuple(f"10.{number}" for number in range(1, 12))
    ):
        _fail("the frozen ZIP limitation disposition changed")
    return _validate_item_lists(limitation, "ZIP input limitation")


def _validate_contract(workspace: Path, contract_path: str) -> None:
    if contract_path != CONTRACT_PATH.as_posix():
        _fail("contract_path does not name the frozen W9a contract")
    path = workspace / contract_path
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        _fail(f"could not read W9a contract: {error}")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        _fail("W9a contract must be UTF-8 without BOM, LF, and final newline")
    missing = [marker for marker in EXPECTED_CONTRACT_MARKERS if marker not in text]
    if missing:
        _fail(f"W9a contract is missing frozen markers: {', '.join(missing)}")


def validate_w9a_contract(workspace: Path) -> W9aContractReport:
    """Validate the exact W9a findings, decisions, provenance, and evidence names."""

    workspace = workspace.resolve()
    register = _read_register(workspace / REGISTER_PATH)
    if register["schema_version"] != 1:
        _fail("W9a register schema_version must be 1")
    if register["register_id"] != "w9a-2026-07-20":
        _fail("W9a register_id changed")
    if register["status"] != "FROZEN_W9A":
        _fail("W9a register status must remain FROZEN_W9A")
    try:
        w2b1._timestamp(register["frozen_at"], "W9a frozen_at")
    except w2b1.AgentContextError as error:
        _fail(str(error))
    _validate_contract(workspace, register["contract_path"])
    ceiling = _closed(register["capability_ceiling"], CAPABILITY_FIELDS, "capability_ceiling")
    if ceiling != EXPECTED_CAPABILITY_CEILING:
        _fail("W9a capability ceiling changed or expanded")
    source_ids = _validate_sources(workspace, register["source_inputs"])
    if source_ids != set(EXPECTED_SOURCES):
        _fail("W9a source input set changed")
    amendment_sections = _validate_amendments(register["amendments"])
    blocking, tests, artifacts, finding_sections = _validate_findings(register["findings"])
    limit_tests, limit_artifacts, limitation_sections = _validate_limitations(
        register["input_limitations"]
    )
    used_sections = finding_sections | limitation_sections
    if not amendment_sections.issubset(used_sections):
        _fail("one or more frozen amendment sections have no finding owner")
    return W9aContractReport(
        finding_count=len(register["findings"]),
        blocking_count=blocking,
        limitation_count=len(register["input_limitations"]),
        named_negative_test_count=tests + limit_tests,
        named_closure_artifact_count=artifacts + limit_artifacts,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        report = validate_w9a_contract(args.workspace)
    except W9aContractError as error:
        print(f"W9a contract validation failed: {error}", file=sys.stderr)
        return 1
    print(
        "W9a contract validation passed: "
        f"{report.finding_count} findings, {report.blocking_count} blocking, "
        f"{report.limitation_count} input limitation, "
        f"{report.named_negative_test_count} named negative tests, "
        f"{report.named_closure_artifact_count} named closure artifacts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
