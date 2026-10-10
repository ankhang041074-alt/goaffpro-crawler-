"""
Adversarial Stress Test Suite for Milestone M1 (Challenger 1).
Attacks:
- Leap year (2024 Feb 29)
- Multi-year spans crossing 2024 to 2026
- Inverted dates (first_seen > last_shown)
- Future dates (late 2026, 2027)
- Missing and malformed timestamps (None, '0', empty, invalid string)
- Boundary durations (1, 30, 31, 89, 90, 1000 days)
- Tripartite classification boundaries & badges
- Monthly activity boolean matrix invariants
- Property-based fuzzing with 1,000 randomized date pairs
"""

import sys
import random
import calendar
import unittest
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import spy_ads


class TestChallengerM1DateAndClassificationStress(unittest.TestCase):
    """Adversarial challenge test suite for M1 date math and categorization."""

    # --------------------------------------------------------------------------
    # 1. LEAP YEAR STRESS TESTS
    # --------------------------------------------------------------------------
    def test_01_leap_year_february_29_boundaries(self):
        """Stress test 2024 leap year calculations."""
        # A single-day ad exactly on Leap Day
        dur_leap_single = spy_ads.calculate_duration_days("2024-02-29", "2024-02-29")
        self.assertEqual(dur_leap_single, 1, "Single leap day must be 1 day")

        ma_leap = spy_ads.calculate_monthly_activity("2024-02-29", "2024-02-29")
        self.assertTrue(ma_leap["2024"][1], "Feb 2024 must be active for leap day")
        self.assertFalse(ma_leap["2024"][0], "Jan 2024 must be inactive")
        self.assertFalse(ma_leap["2024"][2], "Mar 2024 must be inactive")
        self.assertFalse(any(ma_leap["2025"]), "2025 must be all inactive")
        self.assertFalse(any(ma_leap["2026"]), "2026 must be all inactive")

        # Crossing Feb 29 in 2024 (Feb 28 to Mar 1 = 3 days: Feb 28, Feb 29, Mar 1)
        dur_cross_2024 = spy_ads.calculate_duration_days("2024-02-28", "2024-03-01")
        self.assertEqual(dur_cross_2024, 3, "2024-02-28 to 2024-03-01 must span 3 days")

        # Crossing Feb 28 in 2025 (non-leap: Feb 28 to Mar 1 = 2 days: Feb 28, Mar 1)
        dur_cross_2025 = spy_ads.calculate_duration_days("2025-02-28", "2025-03-01")
        self.assertEqual(dur_cross_2025, 2, "2025-02-28 to 2025-03-01 must span 2 days")

        # Full February in 2024 (29 days)
        dur_feb_2024 = spy_ads.calculate_duration_days("2024-02-01", "2024-02-29")
        self.assertEqual(dur_feb_2024, 29, "Feb 2024 must be 29 days")

        # Full February in 2025 (28 days)
        dur_feb_2025 = spy_ads.calculate_duration_days("2025-02-01", "2025-02-28")
        self.assertEqual(dur_feb_2025, 28, "Feb 2025 must be 28 days")

    def test_02_invalid_leap_day_non_leap_year(self):
        """Passing 2025-02-29 (invalid date) must fail gracefully without unhandled exception."""
        dur = spy_ads.calculate_duration_days("2025-02-29", "2025-03-01")
        self.assertEqual(dur, 1, "Invalid date must fallback to 1 without crashing")

        ma = spy_ads.calculate_monthly_activity("2025-02-29", "2025-03-01")
        self.assertEqual(len(ma["2025"]), 12)
        self.assertFalse(any(ma["2025"]), "Invalid date monthly activity must return all False")

    # --------------------------------------------------------------------------
    # 2. MULTI-YEAR SPANS CROSSING 2024 TO 2026
    # --------------------------------------------------------------------------
    def test_03_multi_year_crossing_spans(self):
        """Stress test long running campaigns crossing from 2024 through 2026."""
        # 1. Full 3-year span: 2024-01-01 to 2026-12-31
        # 366 (leap 2024) + 365 (2025) + 365 (2026) = 1096 days
        dur_3yr = spy_ads.calculate_duration_days("2024-01-01", "2026-12-31")
        self.assertEqual(dur_3yr, 1096, "Full 3-year span (2024-2026) must be exactly 1096 days")

        ma_3yr = spy_ads.calculate_monthly_activity("2024-01-01", "2026-12-31")
        self.assertTrue(all(ma_3yr["2024"]), "All 12 months in 2024 must be True")
        self.assertTrue(all(ma_3yr["2025"]), "All 12 months in 2025 must be True")
        self.assertTrue(all(ma_3yr["2026"]), "All 12 months in 2026 must be True")

        cls_key, cls_label = spy_ads.classify_campaign(dur_3yr, ma_3yr)
        self.assertEqual(cls_key, "evergreen")
        self.assertIn("Chạy Quanh Năm", cls_label)

        # 2. Mid-2024 to early 2026 (e.g., 2024-11-15 to 2026-02-10)
        # Expected: 2024 Nov-Dec (2), 2025 All (12), 2026 Jan-Feb (2) -> 16 active months
        d_start = "2024-11-15"
        d_end = "2026-02-10"
        delta_days = (date(2026, 2, 10) - date(2024, 11, 15)).days + 1
        dur_mid = spy_ads.calculate_duration_days(d_start, d_end)
        self.assertEqual(dur_mid, delta_days)

        ma_mid = spy_ads.calculate_monthly_activity(d_start, d_end)
        # 2024 check: months 1..10 False, months 11..12 True
        self.assertFalse(any(ma_mid["2024"][:10]))
        self.assertTrue(all(ma_mid["2024"][10:]))
        # 2025 check: all True
        self.assertTrue(all(ma_mid["2025"]))
        # 2026 check: months 1..2 True, months 3..12 False
        self.assertTrue(all(ma_mid["2026"][:2]))
        self.assertFalse(any(ma_mid["2026"][2:]))

    # --------------------------------------------------------------------------
    # 3. BOUNDARY DURATIONS & TRIPARTITE CLASSIFICATION
    # --------------------------------------------------------------------------
    def test_04_exact_boundary_durations(self):
        """Stress test exact classification boundary thresholds: 1, 30, 31, 89, 90, 1000 days."""
        boundaries = [
            (1, "new_test", "🟡 Mới Chạy (New Test)"),
            (15, "new_test", "🟡 Mới Chạy (New Test)"),
            (30, "new_test", "🟡 Mới Chạy (New Test)"),
            (31, "seasonal", "🍂 Chạy Theo Mùa (Seasonal)"),
            (60, "seasonal", "🍂 Chạy Theo Mùa (Seasonal)"),
            (89, "seasonal", "🍂 Chạy Theo Mùa (Seasonal)"),
            (90, "evergreen", "🌲 Chạy Quanh Năm (Evergreen)"),
            (91, "evergreen", "🌲 Chạy Quanh Năm (Evergreen)"),
            (1000, "evergreen", "🌲 Chạy Quanh Năm (Evergreen)"),
        ]

        dummy_ma = {"2024": [False] * 12, "2025": [False] * 12, "2026": [False] * 12}
        for days, expected_key, expected_label in boundaries:
            key, label = spy_ads.classify_campaign(days, dummy_ma)
            self.assertEqual(key, expected_key, f"Failed at {days} days: expected {expected_key}, got {key}")
            self.assertEqual(label, expected_label, f"Failed label at {days} days: expected {expected_label}, got {label}")

    def test_05_high_active_month_evergreen_overrides(self):
        """Verify that max_year_active >= 7 or total_active_months >= 8 triggers evergreen."""
        # Case A: exactly 7 active months in a single year (even if duration parameter is passed low)
        ma_7_months = {
            "2024": [True] * 7 + [False] * 5,
            "2025": [False] * 12,
            "2026": [False] * 12,
        }
        key, label = spy_ads.classify_campaign(45, ma_7_months)
        self.assertEqual(key, "evergreen", "max_year_active >= 7 must classify as evergreen")

        # Case B: total active months >= 8 distributed across years (4 in 2024, 4 in 2025)
        ma_8_total = {
            "2024": [True] * 4 + [False] * 8,
            "2025": [True] * 4 + [False] * 8,
            "2026": [False] * 12,
        }
        key, label = spy_ads.classify_campaign(50, ma_8_total)
        self.assertEqual(key, "evergreen", "total_active_months >= 8 must classify as evergreen")

        # Case C: 6 total months and max 4 in any year -> seasonal
        ma_6_total = {
            "2024": [True] * 3 + [False] * 9,
            "2025": [True] * 3 + [False] * 9,
            "2026": [False] * 12,
        }
        key, label = spy_ads.classify_campaign(50, ma_6_total)
        self.assertEqual(key, "seasonal", "Low month count and duration < 90 must classify as seasonal")

    # --------------------------------------------------------------------------
    # 4. INVERTED DATES STRESS TESTS
    # --------------------------------------------------------------------------
    def test_06_inverted_dates_handling(self):
        """Stress test behavior when first_seen > last_shown due to remote clock/data corruption."""
        # 1. Inverted across months
        dur_inv_cross = spy_ads.calculate_duration_days("2026-10-10", "2026-09-01")
        self.assertEqual(dur_inv_cross, 1, "Inverted dates must clamp duration to 1")

        ma_inv_cross = spy_ads.calculate_monthly_activity("2026-10-10", "2026-09-01")
        self.assertFalse(any(ma_inv_cross["2024"]), "2024 must be all False")
        self.assertFalse(any(ma_inv_cross["2025"]), "2025 must be all False")
        self.assertFalse(any(ma_inv_cross["2026"]), "2026 must be all False")

        # 2. Inverted within the same month
        dur_inv_same = spy_ads.calculate_duration_days("2026-09-20", "2026-09-10")
        self.assertEqual(dur_inv_same, 1, "Inverted dates in same month must clamp duration to 1")

        # 3. Inverted by multi-year
        dur_inv_yr = spy_ads.calculate_duration_days("2026-10-10", "2024-01-01")
        self.assertEqual(dur_inv_yr, 1, "Inverted dates across years must clamp duration to 1")

    # --------------------------------------------------------------------------
    # 5. FUTURE AND OFF-WINDOW DATES
    # --------------------------------------------------------------------------
    def test_07_future_and_past_off_window_dates(self):
        """Test dates in late 2026, future 2027+, and pre-2024."""
        # Late 2026: 2026-11-01 to 2026-12-31 (61 days, seasonal)
        dur_late = spy_ads.calculate_duration_days("2026-11-01", "2026-12-31")
        self.assertEqual(dur_late, 61)
        ma_late = spy_ads.calculate_monthly_activity("2026-11-01", "2026-12-31")
        self.assertFalse(any(ma_late["2024"]))
        self.assertFalse(any(ma_late["2025"]))
        self.assertEqual(ma_late["2026"][:10], [False] * 10)
        self.assertEqual(ma_late["2026"][10:], [True, True])

        # Beyond 2026 (e.g. 2027)
        dur_2027 = spy_ads.calculate_duration_days("2027-01-01", "2027-06-01")
        self.assertEqual(dur_2027, 152)
        ma_2027 = spy_ads.calculate_monthly_activity("2027-01-01", "2027-06-01")
        self.assertFalse(any(ma_2027["2024"]))
        self.assertFalse(any(ma_2027["2025"]))
        self.assertFalse(any(ma_2027["2026"]))

        # Before 2024 (e.g. 2023)
        dur_2023 = spy_ads.calculate_duration_days("2023-01-01", "2023-12-31")
        self.assertEqual(dur_2023, 365)
        ma_2023 = spy_ads.calculate_monthly_activity("2023-01-01", "2023-12-31")
        self.assertFalse(any(ma_2023["2024"]))
        self.assertFalse(any(ma_2023["2025"]))
        self.assertFalse(any(ma_2023["2026"]))

    # --------------------------------------------------------------------------
    # 6. MISSING AND MALFORMED TIMESTAMPS
    # --------------------------------------------------------------------------
    def test_08_missing_and_malformed_timestamps(self):
        """Stress test timestamp parser and date functions with invalid/edge inputs."""
        # parse_unix_timestamp
        self.assertIsNone(spy_ads.parse_unix_timestamp(None))
        self.assertIsNone(spy_ads.parse_unix_timestamp(""))
        self.assertIsNone(spy_ads.parse_unix_timestamp("   "))
        self.assertIsNone(spy_ads.parse_unix_timestamp("invalid_text"))
        self.assertIsNone(spy_ads.parse_unix_timestamp(0))  # int 0 is falsy -> None

        # calculate_duration_days resilience
        self.assertEqual(spy_ads.calculate_duration_days("", "2026-10-10"), 1)
        self.assertEqual(spy_ads.calculate_duration_days(None, "2026-10-10"), 1)
        self.assertEqual(spy_ads.calculate_duration_days("2026-10-10", None), 1)
        self.assertEqual(spy_ads.calculate_duration_days(None, None), 1)
        self.assertEqual(spy_ads.calculate_duration_days("bad-date-1", "bad-date-2"), 1)

        # calculate_monthly_activity resilience
        ma_none = spy_ads.calculate_monthly_activity(None, None)
        self.assertEqual(len(ma_none), 3)
        for y in ("2024", "2025", "2026"):
            self.assertEqual(len(ma_none[y]), 12)
            self.assertFalse(any(ma_none[y]))

    # --------------------------------------------------------------------------
    # 7. MONTHLY ACTIVITY MATRIX STRUCTURAL INVARIANTS
    # --------------------------------------------------------------------------
    def test_09_monthly_activity_matrix_structure(self):
        """Verify monthly_activity strictly conforms to the PROJECT.md TypeScript interface."""
        ma = spy_ads.calculate_monthly_activity("2024-06-01", "2025-06-01")
        # Must be dict with string keys "2024", "2025", "2026"
        self.assertIsInstance(ma, dict)
        self.assertEqual(set(ma.keys()), {"2024", "2025", "2026"})

        for yr_key, month_list in ma.items():
            self.assertIsInstance(yr_key, str)
            self.assertIsInstance(month_list, list)
            self.assertEqual(len(month_list), 12, f"Year {yr_key} must contain exactly 12 elements")
            for idx, val in enumerate(month_list):
                # Must be strictly Python bool (True or False), not None or integer 1/0
                self.assertIsInstance(val, bool, f"Element {idx} of {yr_key} must be bool, got {type(val)}")

    # --------------------------------------------------------------------------
    # 8. PROPERTY-BASED FUZZING (1,000 RANDOMIZED INTERVALS)
    # --------------------------------------------------------------------------
    def test_10_property_based_stress_fuzzing(self):
        """
        Fuzzing test running 1,000 randomly generated (start, end) date pairs.
        Asserts fundamental mathematical invariants:
        1. duration_days >= 1 always.
        2. If start == end, duration_days == 1.
        3. If start <= end, duration_days == (end - start).days + 1.
        4. calculate_monthly_activity never crashes and returns exactly 3 years x 12 bools.
        5. For all months wholly before start or wholly after end, monthly_activity is False.
        6. classify_campaign always returns one of ('new_test', 'seasonal', 'evergreen').
        """
        random.seed(42)  # Deterministic seed for reproducible tests
        base_date = date(2023, 1, 1)
        max_days = 365 * 5  # Span across 2023-2027

        for iteration in range(1000):
            offset1 = random.randint(0, max_days)
            offset2 = random.randint(0, max_days)
            d1 = base_date + timedelta(days=offset1)
            d2 = base_date + timedelta(days=offset2)

            d1_str = d1.strftime("%Y-%m-%d")
            d2_str = d2.strftime("%Y-%m-%d")

            # 1. Test duration math
            dur = spy_ads.calculate_duration_days(d1_str, d2_str)
            self.assertGreaterEqual(dur, 1, f"Iteration {iteration}: duration must be >= 1 for {d1_str} -> {d2_str}")

            if d1 == d2:
                self.assertEqual(dur, 1, f"Iteration {iteration}: identical date must yield duration 1")
            elif d1 < d2:
                expected_dur = (d2 - d1).days + 1
                self.assertEqual(dur, expected_dur, f"Iteration {iteration}: {d1_str} -> {d2_str} duration mismatch")
            else:
                self.assertEqual(dur, 1, f"Iteration {iteration}: inverted dates must clamp to 1")

            # 2. Test monthly activity
            ma = spy_ads.calculate_monthly_activity(d1_str, d2_str)
            self.assertEqual(len(ma), 3)
            for y_str in ("2024", "2025", "2026"):
                y_int = int(y_str)
                self.assertEqual(len(ma[y_str]), 12)
                for m_idx in range(12):
                    m_num = m_idx + 1
                    is_active = ma[y_str][m_idx]
                    self.assertIsInstance(is_active, bool)

                    # Mathematical oracle check for valid non-inverted intervals:
                    if d1 <= d2:
                        last_day = calendar.monthrange(y_int, m_num)[1]
                        m_start = date(y_int, m_num, 1)
                        m_end = date(y_int, m_num, last_day)

                        expected_overlap = (d1 <= m_end) and (d2 >= m_start)
                        self.assertEqual(
                            is_active, expected_overlap,
                            f"Iteration {iteration}: Month {y_str}-{m_num:02d} overlap mismatch for [{d1_str}, {d2_str}]"
                        )

            # 3. Test classification
            c_key, c_label = spy_ads.classify_campaign(dur, ma)
            self.assertIn(c_key, ("new_test", "seasonal", "evergreen"))
            self.assertTrue(len(c_label) > 0)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestChallengerM1DateAndClassificationStress)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
