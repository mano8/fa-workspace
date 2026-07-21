"""W9f self-contained exact-tree review-bundle fixtures."""

from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.review_bundle import (  # noqa: E402
    CHECK_COMMANDS,
    ReviewBundleError,
    build_bundle,
    canonical_bytes,
    validate_bundle,
)


ROOT = Path(__file__).resolve().parents[3]
ROOT_IDENTITY = {"commit": "a" * 40, "tree": "b" * 40}
CHILDREN = [{
    "id": "child", "path": "child", "commit": "c" * 40,
    "tree": "d" * 40, "agents_sha256": "e" * 64,
}]
TRUST = {"children": [{"path": "child"}], "trust_identity_sha256": "f" * 64}
CLOSURE = {
    "artifacts": [{"path": "tracked", "sha256": "1" * 64}],
    "negative_tests": ["module.Class.test_negative"],
}
FINDINGS = [{
    "id": "C-1", "severity": "critical",
    "status": "CLOSED_BY_REPLAYED_W9F_EVIDENCE",
    "negative_tests": ["module.Class.test_negative"],
    "closure_artifacts": ["tracked"],
}]
LIMITATION = {"id": "zip-reproducibility", "status": "REPLACED_BY_REPLAYED_EXACT_TREE_BUNDLE"}


def _checks() -> list[dict[str, object]]:
    return [{
        "id": check_id, "command": list(command), "exit_code": 0,
        "stdout_sha256": "2" * 64, "stderr_sha256": "3" * 64,
    } for check_id, command in sorted(CHECK_COMMANDS.items())]


class W9fReviewBundleTests(unittest.TestCase):
    def _patches(self, *, check_results: list[dict[str, object]] | None = None) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(mock.patch("agent_context.review_bundle._git_identity", return_value=ROOT_IDENTITY))
        stack.enter_context(mock.patch("agent_context.review_bundle._children", return_value=CHILDREN))
        stack.enter_context(mock.patch("agent_context.review_bundle._closure_inventory", return_value=CLOSURE))
        stack.enter_context(mock.patch(
            "agent_context.review_bundle._finding_dispositions", return_value=(FINDINGS, LIMITATION),
        ))
        stack.enter_context(mock.patch("agent_context.review_bundle.build_trust_identity", return_value=TRUST))
        stack.enter_context(mock.patch("agent_context.review_bundle._validate_live_receipt"))
        if check_results is not None:
            stack.enter_context(mock.patch("agent_context.review_bundle.run_checks", return_value=check_results))
        return stack

    def _bundle(self) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as runtime, self._patches(check_results=_checks()):
            runtime_path = Path(runtime)
            (runtime_path / "session.json").write_text('{"state":"COMPLETED"}\n', encoding="utf-8")
            (runtime_path / "receipt.json").write_text('{"state":"COMPLETED"}\n', encoding="utf-8")
            return build_bundle(
                workspace=ROOT, live_runtime=runtime_path,
                codex_binary=Path(sys.executable), codex_version="fixture",
            )

    def _validate(self, bundle: dict[str, object]) -> None:
        with self._patches():
            validate_bundle(
                bundle, workspace=ROOT, codex_binary=Path(sys.executable),
                codex_version="fixture", check_runner=lambda _root: _checks(),
            )

    def test_bundle_rejects_missing_child_or_git_identity(self) -> None:
        bundle = self._bundle()
        bundle["children"] = bundle["children"][:-1]  # type: ignore[index]
        with self.assertRaisesRegex(ReviewBundleError, "child Git"):
            self._validate(bundle)

    def test_bundle_rejects_missing_finding_evidence(self) -> None:
        bundle = self._bundle()
        bundle["findings"] = bundle["findings"][:-1]  # type: ignore[index]
        with self.assertRaisesRegex(ReviewBundleError, "finding evidence"):
            self._validate(bundle)

    def test_bundle_rejects_parent_tree_or_dirty_proof(self) -> None:
        bundle = self._bundle()
        changed = deepcopy(bundle)
        changed["reviewed_root"]["tree"] = "0" * 40  # type: ignore[index]
        with self.assertRaisesRegex(ReviewBundleError, "root commit/tree"):
            self._validate(changed)

    def test_self_contained_bundle_replays_minimum_checks(self) -> None:
        bundle = self._bundle()
        self._validate(bundle)
        changed = deepcopy(bundle)
        changed["checks"][0]["stdout_sha256"] = "4" * 64  # type: ignore[index]
        with self.assertRaisesRegex(ReviewBundleError, "check replay"):
            self._validate(changed)
        self.assertEqual(canonical_bytes(bundle), canonical_bytes(bundle))


if __name__ == "__main__":
    unittest.main()
