"""W9e L-1 immutable root supply-chain fixtures."""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context.validate_supply_chain import validate_supply_chain


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = Path(".github/workflows/workspace-policy-lint.yml")
LOCK = Path(".github/workflows/root-tooling.requirements.lock")


class W9eSupplyChainTests(unittest.TestCase):
    def test_actions_use_full_commit_sha_with_version_comment(self) -> None:
        lines = (ROOT / WORKFLOW).read_text(encoding="utf-8").splitlines()
        actions = [line for line in lines if "uses:" in line]
        self.assertGreaterEqual(len(actions), 2)
        for line in actions:
            self.assertRegex(line, r"@[0-9a-f]{40}\s+#\s+v\S+$")

    def test_python_inputs_are_hash_verified(self) -> None:
        workflow = (ROOT / WORKFLOW).read_text(encoding="utf-8")
        lock = (ROOT / LOCK).read_text(encoding="utf-8")
        self.assertIn("--require-hashes --no-deps", workflow)
        requirements = [line for line in lock.splitlines() if re.match(r"^[A-Za-z0-9_.-]+==", line)]
        hashes = [line for line in lock.splitlines() if "--hash=sha256:" in line]
        self.assertEqual(len(requirements), len(hashes))
        headroom_lock = (ROOT / ".devcontainer/headroom.requirements.lock").read_text(encoding="utf-8")
        headroom_requirements = [
            line for line in headroom_lock.splitlines() if line and not line.startswith("#")
        ]
        self.assertGreater(len(headroom_requirements), 1)
        self.assertTrue(all(" --hash=sha256:" in line for line in headroom_requirements))
        setup = (ROOT / ".devcontainer/setup.sh").read_text(encoding="utf-8")
        devcontainer = (ROOT / ".devcontainer/devcontainer.json").read_text(encoding="utf-8")
        dockerfile = (ROOT / ".devcontainer/Dockerfile").read_text(encoding="utf-8")
        self.assertIn(".github/workflows/root-tooling.requirements.lock", setup)
        self.assertNotIn("fa-auth-m8/auth_user_service/requirements_dev.txt", setup)
        self.assertNotIn("imgtools_m8/requirements.txt", setup)
        self.assertNotIn("media-service-m8/media_service/requirements_dev.txt", setup)
        self.assertNotIn("devcontainers/features/python", devcontainer)
        self.assertNotIn("anthropics/devcontainer-features/claude-code", devcontainer)
        self.assertIn('"pnpmVersion": "none"', devcontainer)
        self.assertIn('"nvmVersion": "0.40.6"', devcontainer)
        self.assertIn('"dockerDashComposeVersion": "none"', devcontainer)
        self.assertIn('"installDockerBuildx": false', devcontainer)
        self.assertIn('@anthropic-ai/claude-code@${CLAUDE_VERSION}', setup)
        self.assertIn(
            "python@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b",
            dockerfile,
        )
        validate_supply_chain(ROOT)

    def test_unreviewed_dependency_refresh_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in (WORKFLOW, LOCK):
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            workflow = root / WORKFLOW
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
                    "actions/checkout@v4",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SystemExit, "unreviewed Action ref"):
                validate_supply_chain(root)


if __name__ == "__main__":
    unittest.main()
