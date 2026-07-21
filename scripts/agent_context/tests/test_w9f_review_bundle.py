"""W9f self-contained exact-tree review-bundle fixtures."""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.review_bundle import (  # noqa: E402
    REQUIRED_CHECKS,
    ReviewBundleError,
    build_bundle,
    canonical_bytes,
    validate_bundle,
)


ROOT = Path(__file__).resolve().parents[3]


class W9fReviewBundleTests(unittest.TestCase):
    def _bundle(self) -> dict[str, object]:
        runtime = self.enterContext(__import__("tempfile").TemporaryDirectory())
        runtime_path = Path(runtime)
        (runtime_path / "session.json").write_text('{"state":"COMPLETED"}\n', encoding="utf-8")
        (runtime_path / "receipt.json").write_text('{"state":"COMPLETED"}\n', encoding="utf-8")
        checks = [{"id": item, "command": f"verify {item}", "exit_code": 0} for item in sorted(REQUIRED_CHECKS)]
        with (
            mock.patch("agent_context.review_bundle._git_identity", return_value={"commit": "a" * 40, "tree": "b" * 40}),
            mock.patch("agent_context.review_bundle._children", return_value=[{"id": "child", "path": "child", "commit": "c" * 40, "tree": "d" * 40, "agents_sha256": "e" * 64}]),
            mock.patch("agent_context.review_bundle.build_trust_identity", return_value={"trust_identity_sha256": "f" * 64}),
        ):
            return build_bundle(
                workspace=ROOT, live_runtime=runtime_path, checks=checks,
                codex_binary=Path(sys.executable), codex_version="fixture",
            )

    def _validate(self, bundle: dict[str, object]) -> None:
        with (
            mock.patch("agent_context.review_bundle._git_identity", return_value={"commit": "a" * 40, "tree": "b" * 40}),
            mock.patch("agent_context.review_bundle._children", return_value=[{"id": "child", "path": "child", "commit": "c" * 40, "tree": "d" * 40, "agents_sha256": "e" * 64}]),
        ):
            validate_bundle(bundle, workspace=ROOT)

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
        self.assertEqual(canonical_bytes(bundle), canonical_bytes(bundle))


if __name__ == "__main__":
    unittest.main()
