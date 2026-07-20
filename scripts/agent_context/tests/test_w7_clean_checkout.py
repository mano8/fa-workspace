from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]


class W7CleanCheckoutTests(unittest.TestCase):
    def test_preferred_budget_gate_passes_from_a_clean_root_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            clone = Path(temporary) / "workspace"
            completed = subprocess.run(
                ["git", "clone", "--no-local", "--quiet", str(WORKSPACE), str(clone)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse((clone / "auth-sdk-m8").exists())
            verified = subprocess.run(
                [
                    sys.executable,
                    "scripts/agent_context/budget_promotion.py",
                    "--workspace",
                    ".",
                    "--enforce-preferred",
                ],
                cwd=clone,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(verified.returncode, 0, verified.stderr)
