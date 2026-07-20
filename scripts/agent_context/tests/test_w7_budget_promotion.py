from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import budget_promotion
from agent_context.measure_w4_context import build_report


WORKSPACE = Path(__file__).resolve().parents[3]


class W7BudgetPromotionTests(unittest.TestCase):
    def test_reviewed_baseline_matches_two_independent_root_only_runs(self) -> None:
        snapshot = budget_promotion.verify(WORKSPACE, enforce_preferred=True)
        self.assertEqual(
            [fixture["fixture_id"] for fixture in snapshot["fixtures"]],
            list(budget_promotion.PROMOTION_FIXTURE_IDS),
        )

    def test_hard_overflow_fails_before_or_after_preferred_promotion(self) -> None:
        snapshot = budget_promotion.report_snapshot(build_report(WORKSPACE, "1970-01-01T00:00:00Z"))
        overflow = copy.deepcopy(snapshot)
        overflow["fixtures"][0]["model_visible_total"] = overflow["fixtures"][0]["effective_hard_limit"] + 1
        for enforce_preferred in (False, True):
            with self.subTest(enforce_preferred=enforce_preferred):
                with self.assertRaisesRegex(budget_promotion.BudgetPromotionError, "hard context budget overflow"):
                    budget_promotion._validate_limits(overflow, enforce_preferred=enforce_preferred)

    def test_preferred_enforcement_is_reversible_without_weakening_hard_limit(self) -> None:
        snapshot = budget_promotion.report_snapshot(build_report(WORKSPACE, "1970-01-01T00:00:00Z"))
        warning_only = copy.deepcopy(snapshot)
        warning_only["fixtures"][0]["model_visible_total"] = warning_only["fixtures"][0]["preferred_ceiling"] + 1
        budget_promotion._validate_limits(warning_only, enforce_preferred=False)
        with self.assertRaisesRegex(budget_promotion.BudgetPromotionError, "preferred context budget overflow"):
            budget_promotion._validate_limits(warning_only, enforce_preferred=True)
