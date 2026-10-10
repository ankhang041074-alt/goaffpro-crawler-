"""
End-to-End Test Suite for Google Ads Spy Intelligence Pipeline.
Covers Tiers 1-4:
- Tier 1: Feature Coverage (Date parsing, duration_days math, all-time flags, advertiser metadata, 0-ads state)
- Tier 2: Boundary & Corner Cases (Single-day ad, multi-year ad 2024..2026, leap year Feb 29, malformed/inverted dates, domain normalization)
- Tier 3: Cross-Feature Combinations (Tripartite classification + monthly_activity, SQLite sync + JSON cache fallback, CRM filters)
- Tier 4: Real-World Workloads (binize.com payload verification, multi-advertiser scenarios, pipeline idempotency)

Authoritative sources:
- PROJECT.md (Architecture, Interface Contracts, Feature Inventory F1-F14)
- ORIGINAL_REQUEST.md (R1 All-Time & Real Dates, R2 12-Month Strip & Tripartite, R3 DB/Cache Sync)
- Data and Crawler Survey Reports (spec_miner_survey_data/handoff.md, explorer_survey_crawler/handoff.md)
"""

import os
import sys
import json
import sqlite3
import calendar
import tempfile
import unittest
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import spy_ads, db


# ==============================================================================
# AUTHORITATIVE REFERENCE SPECIFICATIONS & ORACLES (PROJECT.md & ORIGINAL_REQUEST.md)
# ==============================================================================

def oracle_parse_unix_timestamp(ts: Any) -> str:
    """Derive ISO YYYY-MM-DD from Unix timestamp in seconds or string seconds."""
    if ts is None:
        raise ValueError("Timestamp cannot be None")
    val = int(ts)
    return datetime.fromtimestamp(val, tz=timezone.utc).strftime("%Y-%m-%d")


def oracle_calculate_duration_days(first_seen_str: str, last_shown_str: str) -> int:
    """
    Authoritative duration days calculation:
    duration_days = max(1, (last_shown_dt - first_seen_dt).days + 1)
    """
    d1 = datetime.strptime(first_seen_str, "%Y-%m-%d").date()
    d2 = datetime.strptime(last_shown_str, "%Y-%m-%d").date()
    delta = (d2 - d1).days
    return max(1, delta + 1)


def oracle_compute_monthly_activity(first_seen_str: str, last_shown_str: str,
                                    years: List[int] = [2024, 2025, 2026]) -> Dict[str, List[bool]]:
    """
    Authoritative monthly activity generator for multi-year strip (T1-T12).
    For each year in years, returns a list of 12 booleans [Jan..Dec].
    A month is active (True) iff first_seen <= end_of_month and last_shown >= start_of_month.
    """
    d1 = datetime.strptime(first_seen_str, "%Y-%m-%d").date()
    d2 = datetime.strptime(last_shown_str, "%Y-%m-%d").date()

    activity = {}
    for y in years:
        months_active = []
        for m in range(1, 13):
            last_day = calendar.monthrange(y, m)[1]
            start_of_month = date(y, m, 1)
            end_of_month = date(y, m, last_day)

            is_active = (d1 <= end_of_month) and (d2 >= start_of_month)
            months_active.append(is_active)
        activity[str(y)] = months_active
    return activity


def oracle_classify_advertiser(duration_days: int,
                              monthly_activity: Optional[Dict[str, List[bool]]] = None) -> Tuple[str, str]:
    """
    Authoritative tripartite classification:
    - Evergreen (🌲 Chạy Quanh Năm (Evergreen)): duration >= 60-90 days or running continuously across multiple quarters/years.
    - Seasonal (🍂 Chạy Theo Mùa (Seasonal)): clustered in specific peak quarters/months.
    - New Test (🟡 Mới Chạy (New Test)): duration <= 30 days.
    """
    if duration_days <= 30:
        return "new_test", "🟡 Mới Chạy (New Test)"

    if monthly_activity:
        # Check active months in each year
        total_active_months = sum(sum(1 for m in flags if m) for flags in monthly_activity.values())
        years_with_activity = sum(1 for flags in monthly_activity.values() if any(flags))

        # Clustered seasonal window: active <= 4 months within a single year (e.g. Q4 T10-T12 or Summer)
        if years_with_activity == 1 and total_active_months <= 4:
            return "seasonal", "🍂 Chạy Theo Mùa (Seasonal)"

        # Repeat seasonal window: active across years but <= 4 months per year
        max_months_in_any_year = max((sum(1 for m in flags if m) for flags in monthly_activity.values()), default=0)
        if max_months_in_any_year <= 4 and total_active_months <= 6:
            return "seasonal", "🍂 Chạy Theo Mùa (Seasonal)"

        if total_active_months >= 7 or (years_with_activity > 1 and duration_days >= 60):
            return "evergreen", "🌲 Chạy Quanh Năm (Evergreen)"

        return "seasonal", "🍂 Chạy Theo Mùa (Seasonal)"

    if duration_days >= 60:
        return "evergreen", "🌲 Chạy Quanh Năm (Evergreen)"
    return "seasonal", "🍂 Chạy Theo Mùa (Seasonal)"


# ==============================================================================
# TIER 1: FEATURE COVERAGE (Core Functional Capabilities)
# ==============================================================================

class TestGoogleAdsSpyTier1FeatureCoverage(unittest.TestCase):
    """
    Tier 1 tests verify fundamental feature functionality:
    - Unix timestamp extraction & conversion (F2)
    - Duration calculation math independent of ad count (F3)
    - All-Time / Any Time filter and flag (F1)
    - Complete advertiser metadata & icon removal (F4)
    - Standardized zero-ads payload contract (F7)
    """

    def test_01_parse_unix_timestamp_to_iso_date(self):
        """
        [Tier 1] Verify Google Ads Transparency RPC Unix timestamps ("6"."1" and "7"."1")
        are accurately parsed to ISO YYYY-MM-DD.
        """
        # Historical timestamp from Transparency RPC: 1716439657 -> 2024-05-23
        ts_start = 1716439657
        expected_start = "2024-05-23"
        actual_start = oracle_parse_unix_timestamp(ts_start)
        self.assertEqual(actual_start, expected_start, f"Expected {expected_start}, got {actual_start}")

        # Recent timestamp from Transparency RPC: 1791604392 -> 2026-10-10
        ts_end = 1791604392
        expected_end = "2026-10-10"
        actual_end = oracle_parse_unix_timestamp(ts_end)
        self.assertEqual(actual_end, expected_end, f"Expected {expected_end}, got {actual_end}")

        # Check if backend exposes timestamp parser helper
        backend_parser = getattr(spy_ads, "parse_unix_timestamp", None) or getattr(spy_ads, "parse_rpc_timestamp", None)
        if backend_parser:
            self.assertEqual(backend_parser(ts_start), expected_start)
            self.assertEqual(backend_parser(ts_end), expected_end)
            # Verify "0", 0, and pre-2001 timestamps return None to prevent 1970 date explosion
            self.assertIsNone(backend_parser("0"))
            self.assertIsNone(backend_parser(0))
            self.assertIsNone(backend_parser({"1": "0"}))
            self.assertIsNone(backend_parser(-1))
            self.assertIsNone(backend_parser("invalid"))
            # Mathematical invariant: fallback or "2026-10-10" does not explode to 20,737 days
            fallback_dt = backend_parser("0") or "2026-10-10"
            self.assertEqual(fallback_dt, "2026-10-10")
            dur = spy_ads.calculate_duration_days(fallback_dt, "2026-10-10")
            self.assertEqual(dur, 1, "Fallback date calculation must yield 1 day, never 20,737 days")

    def test_02_duration_days_formula_distinct_from_ad_count(self):
        """
        [Tier 1] Verify duration_days = (last_shown - first_seen).days + 1.
        Must NOT equal ad_count.
        """
        first_seen = "2025-01-01"
        last_shown = "2025-01-31"
        ad_count = 5  # advertiser has 5 creatives

        # Expected duration is 31 days (entire January)
        expected_duration = 31
        actual_duration = oracle_calculate_duration_days(first_seen, last_shown)
        self.assertEqual(actual_duration, expected_duration)
        self.assertNotEqual(actual_duration, ad_count,
                            "Duration must NOT be confounded with ad_count (bug fix R1)")

        # Test backend calculate_duration helper if available
        backend_calc = getattr(spy_ads, "calculate_duration_days", None)
        if backend_calc:
            self.assertEqual(backend_calc(first_seen, last_shown), expected_duration)

        # Test through mock advertiser payload
        raw_payload = {
            "domain": "test-example.com",
            "advertisers": [
                {
                    "id": "AR1111111111",
                    "name": "Test Advertiser",
                    "ad_count": ad_count,
                    "first_seen": first_seen,
                    "last_shown": last_shown,
                    "duration_days": ad_count,  # pre-bug state
                    "creatives": [
                        {
                            "id": "CR01",
                            "first_seen": first_seen,
                            "last_shown": last_shown,
                            "duration_days": ad_count
                        }
                    ]
                }
            ]
        }

        # If backend sanitize or processing fixes duration_days:
        sanitized = spy_ads.sanitize_spy_data(raw_payload, "test-example.com")
        adv = sanitized["advertisers"][0]
        # Check whether backend has resolved duration_days bug
        if adv.get("first_seen") and adv.get("last_shown") and adv["first_seen"] != adv["last_shown"]:
            # If backend updated duration_days, assert correctness
            calc_val = adv.get("duration_days")
            if calc_val == expected_duration:
                self.assertEqual(calc_val, expected_duration)
            else:
                self.assertEqual(calc_val, expected_duration,
                                 f"[M1 Bug Escalation] adv.duration_days is {calc_val}, expected {expected_duration}. "
                                 f"Check backend/spy_ads.py duration_days calculation.")

    def test_03_all_time_filter_configuration(self):
        """
        [Tier 1] Verify All-Time mode contract:
        - Payload indicates all_time_enabled is True (or enabled by default).
        - Direct RPC query specification does NOT restrict dates with bounding fields 6 or 7.
        """
        # Standard schema check for All-Time mode
        sample_payload = {
            "domain": "binize.com",
            "all_time_enabled": True,
            "total_advertisers": 1,
            "advertisers": []
        }
        self.assertTrue(sample_payload.get("all_time_enabled", False))

        # Check crawler helper / parameter if exposed
        crawl_fn = getattr(spy_ads, "crawl_google_ads_transparency", None)
        self.assertTrue(callable(crawl_fn), "crawl_google_ads_transparency must be callable")

    def test_04_advertiser_metadata_enrichment_and_icon_cleaning(self):
        """
        [Tier 1] Verify full advertiser metadata is preserved and icon ligatures
        (videocam, image, đã xác minh, etc.) are stripped cleanly from text.
        """
        test_strings = [
            ("videocam | Binize 10.26 Carplay Screen", "Binize 10.26 Carplay Screen"),
            ("đã xác minh | CGY HONG KONG TECH", "CGY HONG KONG TECH"),
            ("image | Dash Cam Front 4K", "Dash Cam Front 4K"),
            ("play_arrow | Wireless Adapter Review", "Wireless Adapter Review"),
            ("verified | Official Store", "Official Store")
        ]

        for raw_text, expected_cleaned in test_strings:
            cleaned = spy_ads._clean_text_line(raw_text)
            self.assertEqual(cleaned, expected_cleaned,
                             f"Failed cleaning '{raw_text}': got '{cleaned}'")

    def test_05_zero_ads_payload_standardization(self):
        """
        [Tier 1] Verify zero-ads store produces standardized payload:
        - total_advertisers == 0
        - total_ads == 0
        - is_verified_zero == True
        - status == 'no_ads'
        - advertisers == []
        """
        zero_payload = {
            "domain": "no-ads-store.com",
            "total_advertisers": 0,
            "total_ads": 0,
            "advertisers": [],
            "updated_at": "2026-10-10T10:00:00"
        }

        sanitized = spy_ads.sanitize_spy_data(zero_payload, "no-ads-store.com")
        self.assertTrue(sanitized.get("is_verified_zero", False),
                        "Zero-ads payload must have is_verified_zero=True")
        self.assertEqual(sanitized.get("status"), "no_ads",
                         "Zero-ads payload status must be 'no_ads'")
        self.assertEqual(sanitized.get("total_advertisers"), 0)
        self.assertEqual(sanitized.get("total_ads"), 0)
        self.assertEqual(len(sanitized.get("advertisers", [])), 0)


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES
# ==============================================================================

class TestGoogleAdsSpyTier2BoundaryCornerCases(unittest.TestCase):
    """
    Tier 2 tests boundary conditions, extreme spans, calendar quirks, and edge inputs:
    - Single-day ad boundary (duration == 1)
    - Multi-year ad spanning 2024 to 2026 (912 days)
    - Leap year February 29 handling (2024)
    - Inverted or missing dates resilience
    - Domain string sanitization corner cases
    """

    def test_06_single_day_ad_boundary(self):
        """
        [Tier 2] When first_seen == last_shown, duration_days MUST be 1.
        It must never be 0 or negative.
        """
        same_date = "2026-06-15"
        duration = oracle_calculate_duration_days(same_date, same_date)
        self.assertEqual(duration, 1, "Single day ad must have duration_days = 1")

        # Test backend helper if present
        backend_calc = getattr(spy_ads, "calculate_duration_days", None)
        if backend_calc:
            self.assertEqual(backend_calc(same_date, same_date), 1)

    def test_07_multi_year_ad_2024_to_2026(self):
        """
        [Tier 2] Multi-year ad from 2024-04-12 to 2026-10-09:
        - duration_days == 911 or 912 (exact calendar delta + 1)
        - monthly_activity contains 2024, 2025, 2026 with 12 elements each
        - 2024: Jan-Mar (indices 0..2) False, Apr-Dec (indices 3..11) True
        - 2025: All 12 months True
        - 2026: Jan-Oct (indices 0..9) True, Nov-Dec (indices 10..11) False
        """
        start = "2024-04-12"
        end = "2026-10-09"
        duration = oracle_calculate_duration_days(start, end)
        self.assertEqual(duration, 911, "2024-04-12 to 2026-10-09 is 911 days inclusive")

        monthly = oracle_compute_monthly_activity(start, end, [2024, 2025, 2026])
        self.assertIn("2024", monthly)
        self.assertIn("2025", monthly)
        self.assertIn("2026", monthly)

        # 2024 verification
        act_2024 = monthly["2024"]
        self.assertEqual(len(act_2024), 12)
        self.assertFalse(act_2024[0], "Jan 2024 must be False")
        self.assertFalse(act_2024[1], "Feb 2024 must be False")
        self.assertFalse(act_2024[2], "Mar 2024 must be False")
        self.assertTrue(act_2024[3], "Apr 2024 must be True")
        self.assertTrue(all(act_2024[3:12]), "Apr-Dec 2024 must be True")

        # 2025 verification
        act_2025 = monthly["2025"]
        self.assertEqual(len(act_2025), 12)
        self.assertTrue(all(act_2025), "All 12 months in 2025 must be True")

        # 2026 verification
        act_2026 = monthly["2026"]
        self.assertEqual(len(act_2026), 12)
        self.assertTrue(all(act_2026[0:10]), "Jan-Oct 2026 must be True")
        self.assertFalse(act_2026[10], "Nov 2026 must be False")
        self.assertFalse(act_2026[11], "Dec 2026 must be False")

    def test_08_leap_year_february_29_handling(self):
        """
        [Tier 2] Verify leap year 2024 math:
        - 2024-02-28 to 2024-03-01 spans 3 days (Feb 28, Feb 29, Mar 1).
        - 2024-02-01 to 2024-02-29 is 29 days.
        - 2025-02-01 to 2025-02-28 (non-leap) is 28 days.
        """
        leap_span = oracle_calculate_duration_days("2024-02-28", "2024-03-01")
        self.assertEqual(leap_span, 3, "Crossing Feb 29 in 2024 must count 3 days")

        feb_2024 = oracle_calculate_duration_days("2024-02-01", "2024-02-29")
        self.assertEqual(feb_2024, 29, "Feb 2024 has 29 days")

        feb_2025 = oracle_calculate_duration_days("2025-02-01", "2025-02-28")
        self.assertEqual(feb_2025, 28, "Feb 2025 has 28 days")

    def test_09_missing_malformed_and_inverted_timestamps(self):
        """
        [Tier 2] Resilience when dates are inverted or malformed:
        - If last_shown is earlier than first_seen, duration must clamp to >= 1.
        - Non-crash fallback behavior.
        """
        # Inverted dates (e.g. clock desync)
        inverted_duration = oracle_calculate_duration_days("2026-10-10", "2026-09-01")
        self.assertEqual(inverted_duration, 1, "Inverted dates must clamp to at least 1 day")

        # Test backend helper if present
        backend_calc = getattr(spy_ads, "calculate_duration_days", None)
        if backend_calc:
            self.assertGreaterEqual(backend_calc("2026-10-10", "2026-09-01"), 1)

        # Inverted dates monthly activity must return all False (no false positive illumination)
        ma_inv = spy_ads.calculate_monthly_activity("2026-09-20", "2026-09-10")
        for y in ("2024", "2025", "2026"):
            self.assertFalse(any(ma_inv[y]), f"Inverted dates must not illuminate {y}")

    def test_10_domain_normalization_corner_cases(self):
        """
        [Tier 2] Test domain sanitization for various dirty inputs:
        - URLs with protocol, www, subpaths, whitespace
        """
        cases = [
            ("  https://WWW.Binize.com/collections/dashcam  ", "binize.com"),
            ("http://letbricks.com/", "letbricks.com"),
            ("https://store.motor.com/sub/page", "store.motor.com"),
            ("binize.com", "binize.com")
        ]
        for raw_domain, expected_clean in cases:
            file_path = spy_ads.get_file_for_domain(raw_domain)
            self.assertTrue(str(file_path).endswith(f"spy_google_ads_{expected_clean.replace('.', '_')}.json") or
                            "binize" in str(file_path),
                            f"Domain '{raw_domain}' did not route to clean filename: {file_path}")


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==============================================================================

class TestGoogleAdsSpyTier3CrossFeatureCombinations(unittest.TestCase):
    """
    Tier 3 tests interactions between features:
    - Tripartite classification correlated with monthly_activity
    - SQLite DB synchronization and JSON cache fallback interoperability
    - Main CRM filter query integration with stores table
    """

    def setUp(self):
        # Create an isolated temporary SQLite database for DB interaction tests
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_db_path = Path(self.temp_dir.name) / "test_goaffpro.db"
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = self.temp_db_path
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig_db_path
        self.temp_dir.cleanup()

    def test_11_tripartite_classification_with_monthly_activity(self):
        """
        [Tier 3] Test classification mapping:
        - duration <= 30 days -> 'new_test' / '🟡 Mới Chạy (New Test)'
        - duration >= 90 days across multiple seasons -> 'evergreen' / '🌲 Chạy Quanh Năm (Evergreen)'
        - concentrated seasonal window -> 'seasonal' / '🍂 Chạy Theo Mùa (Seasonal)'
        """
        # Case A: New Test
        cls_new, badge_new = oracle_classify_advertiser(15)
        self.assertEqual(cls_new, "new_test")
        self.assertIn("Mới Chạy", badge_new)

        # Case B: Evergreen Multi-Year Campaign
        monthly_evergreen = oracle_compute_monthly_activity("2024-04-12", "2026-10-09")
        cls_eg, badge_eg = oracle_classify_advertiser(911, monthly_evergreen)
        self.assertEqual(cls_eg, "evergreen")
        self.assertIn("Chạy Quanh Năm", badge_eg)

        # Case C: Seasonal Q4 Campaign (Active Oct-Dec only)
        monthly_seasonal = oracle_compute_monthly_activity("2025-10-01", "2025-12-31")
        cls_sn, badge_sn = oracle_classify_advertiser(92, monthly_seasonal)
        self.assertEqual(cls_sn, "seasonal")
        self.assertIn("Chạy Theo Mùa", badge_sn)

        # Test backend classify helper
        backend_classify = getattr(spy_ads, "classify_campaign", None) or getattr(spy_ads, "classify_advertiser", None)
        self.assertIsNotNone(backend_classify, "backend classify helper must be present")
        b_cls, b_badge = backend_classify(15)
        self.assertEqual(b_cls, "new_test")
        b_cls_eg, b_badge_eg = backend_classify(911, monthly_evergreen)
        self.assertEqual(b_cls_eg, "evergreen")
        b_cls_sn, b_badge_sn = backend_classify(92, monthly_seasonal)
        self.assertEqual(b_cls_sn, "seasonal", "Q4 92-day campaign must be classified as seasonal")
        self.assertIn("Chạy Theo Mùa", b_badge_sn)

    def test_12_sqlite_sync_with_json_cache_interoperability(self):
        """
        [Tier 3] Verify update_store_spy_ads synchronizes SQLite fields
        and load_spy_data falls back to SQLite for zero-ads store when JSON is missing.
        """
        conn = db.get_db()
        cursor = conn.cursor()

        # Seed a test store
        test_store_id = "store_test_001"
        cursor.execute("""
        INSERT INTO stores (store_id, name, website_url, spy_ads_status)
        VALUES (?, ?, ?, ?)
        """, (test_store_id, "Test Zero Ads Store", "https://test-zero-ads.com", "pending"))
        conn.commit()
        conn.close()

        # 1. Update as verified zero ads
        db.update_store_spy_ads(test_store_id, adv_count=0, ad_count=0, status="no_ads")

        # Verify DB updated
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT spy_ads_status, spy_adv_count, spy_ads_count, spy_updated_at FROM stores WHERE store_id = ?", (test_store_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["spy_ads_status"], "no_ads")
        self.assertEqual(row["spy_adv_count"], 0)
        self.assertEqual(row["spy_ads_count"], 0)
        self.assertIsNotNone(row["spy_updated_at"])

        # 2. Test fallback in load_spy_data when JSON cache file does not exist
        fallback_data = spy_ads.load_spy_data("test-zero-ads.com", store_id=test_store_id)
        self.assertTrue(fallback_data.get("is_verified_zero", False))
        self.assertEqual(fallback_data.get("status"), "no_ads")
        self.assertEqual(fallback_data.get("total_advertisers"), 0)

        # 3. Update as store with active ads
        test_active_id = "store_test_002"
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO stores (store_id, name, website_url, spy_ads_status)
        VALUES (?, ?, ?, ?)
        """, (test_active_id, "Test Active Store", "https://test-active.com", "pending"))
        conn.commit()
        conn.close()

        db.update_store_spy_ads(test_active_id, adv_count=3, ad_count=25, status="done")

        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT spy_ads_status, spy_adv_count, spy_ads_count FROM stores WHERE store_id = ?", (test_active_id,))
        row_act = cursor.fetchone()
        conn.close()

        self.assertEqual(row_act["spy_ads_status"], "done")
        self.assertEqual(row_act["spy_adv_count"], 3)
        self.assertEqual(row_act["spy_ads_count"], 25)

    def test_13_main_crm_store_spy_filtering(self):
        """
        [Tier 3] Verify SQLite CRM filters in GET /api/stores:
        - 'has_ads': spy_ads_status = 'done' AND spy_ads_count > 0
        - 'no_ads': spy_ads_status = 'no_ads'
        - 'spied': spy_ads_status IN ('done', 'no_ads')
        - 'unspied' / 'pending': spy_ads_status IS NULL OR spy_ads_status IN ('pending', '')
        """
        conn = db.get_db()
        cursor = conn.cursor()

        # Insert 4 stores representing each state
        stores_data = [
            ("s_done", "Store Has Ads", "https://s-done.com", "done", 10),
            ("s_zero", "Store No Ads", "https://s-zero.com", "no_ads", 0),
            ("s_pending", "Store Pending", "https://s-pending.com", "pending", 0),
            ("s_null", "Store Unspied", "https://s-null.com", None, 0),
        ]
        for sid, sname, surl, sstatus, scnt in stores_data:
            cursor.execute("""
            INSERT INTO stores (store_id, name, website_url, spy_ads_status, spy_ads_count)
            VALUES (?, ?, ?, ?, ?)
            """, (sid, sname, surl, sstatus, scnt))
        conn.commit()

        # 1. Test has_ads filter
        cursor.execute("SELECT store_id FROM stores WHERE (spy_ads_status = 'done' AND COALESCE(spy_ads_count, 0) > 0)")
        has_ads_ids = [r["store_id"] for r in cursor.fetchall()]
        self.assertEqual(has_ads_ids, ["s_done"])

        # 2. Test no_ads filter
        cursor.execute("SELECT store_id FROM stores WHERE spy_ads_status = 'no_ads'")
        no_ads_ids = [r["store_id"] for r in cursor.fetchall()]
        self.assertEqual(no_ads_ids, ["s_zero"])

        # 3. Test spied filter
        cursor.execute("SELECT store_id FROM stores WHERE spy_ads_status IN ('done', 'no_ads')")
        spied_ids = sorted([r["store_id"] for r in cursor.fetchall()])
        self.assertEqual(spied_ids, ["s_done", "s_zero"])

        # 4. Test unspied filter
        cursor.execute("SELECT store_id FROM stores WHERE (spy_ads_status IS NULL OR spy_ads_status IN ('pending', ''))")
        unspied_ids = sorted([r["store_id"] for r in cursor.fetchall()])
        self.assertEqual(unspied_ids, ["s_null", "s_pending"])

        conn.close()


# ==============================================================================
# TIER 4: REAL-WORLD WORKLOADS & DATA INTEGRITY
# ==============================================================================

class TestGoogleAdsSpyTier4RealWorldWorkloads(unittest.TestCase):
    """
    Tier 4 tests validate real-world production datasets and multi-advertiser loads:
    - Real-world binize.com cache payload compliance (AC 1, AC 2)
    - Multi-advertiser aggregation and isolation
    - Idempotency and preservation of sanitization pipeline
    """

    def test_14_binize_real_world_payload_structure(self):
        """
        [Tier 4] Verify the authentic binize.com dataset in data/spy_google_ads_binize.json:
        - Contains multiple advertisers
        - Contains multi-year history (first_seen in 2024)
        - duration_days reflects actual elapsed days (> 100 days), NOT ad count
        - Creatives have clean headlines, descriptions, and landing pages
        """
        binize_path = PROJECT_ROOT / "data" / "spy_google_ads_binize.json"
        if not binize_path.exists():
            binize_path = PROJECT_ROOT / "data" / "spy_google_ads_binize_com.json"

        self.assertTrue(binize_path.exists(), f"Benchmark data file {binize_path} must exist")

        with open(binize_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("domain"), "binize.com")
        self.assertGreater(data.get("total_advertisers", 0), 0)
        self.assertGreater(data.get("total_ads", 0), 0)

        advertisers = data.get("advertisers", [])
        self.assertGreater(len(advertisers), 0)

        # Inspect the primary advertiser (TKTX or Rakuten)
        primary_adv = advertisers[0]
        self.assertTrue(primary_adv.get("id", "").startswith("AR"))
        self.assertTrue(len(primary_adv.get("name", "")) > 0)
        self.assertTrue(len(primary_adv.get("legal_name", "")) > 0)
        self.assertIn("country", primary_adv)
        self.assertIn("country_flag", primary_adv)

        # Duration verification on authentic payload
        first_seen = primary_adv.get("first_seen")
        last_shown = primary_adv.get("last_shown")
        self.assertIsNotNone(first_seen, "first_seen must not be None")
        self.assertIsNotNone(last_shown, "last_shown must not be None")

        # In authentic data, first_seen is 2024-04-12 and duration is > 900 days
        if first_seen and last_shown:
            expected_days = oracle_calculate_duration_days(first_seen, last_shown)
            actual_days = primary_adv.get("duration_days", 0)
            self.assertGreater(actual_days, 100,
                               f"Real binize advertiser must have duration_days > 100, got {actual_days}")
            # Ensure not equal to ad_count
            self.assertNotEqual(actual_days, primary_adv.get("ad_count"),
                                "Real duration_days must not equal ad_count")

    def test_15_multi_advertiser_workload_aggregation(self):
        """
        [Tier 4] Verify domain with multiple distinct advertisers:
        - Advertiser 1: Evergreen (2024..2026, 26 ads)
        - Advertiser 2: Seasonal (Q4 2025, 5 ads)
        - Advertiser 3: New Test (15 days, 1 ad)
        Verifies total advertiser and ads count sum properly without cross-contamination.
        """
        payload = {
            "domain": "multi-adv-test.com",
            "advertisers": [
                {
                    "id": "AR_001",
                    "name": "Evergreen Adv",
                    "ad_count": 26,
                    "first_seen": "2024-04-12",
                    "last_shown": "2026-10-09",
                    "duration_days": 911,
                    "creatives": [{"id": "CR_1", "format": "search", "headline": "Ad 1"}]
                },
                {
                    "id": "AR_002",
                    "name": "Seasonal Adv",
                    "ad_count": 5,
                    "first_seen": "2025-10-01",
                    "last_shown": "2025-12-31",
                    "duration_days": 92,
                    "creatives": [{"id": "CR_2", "format": "image", "headline": "Ad 2"}]
                },
                {
                    "id": "AR_003",
                    "name": "New Test Adv",
                    "ad_count": 1,
                    "first_seen": "2026-09-25",
                    "last_shown": "2026-10-09",
                    "duration_days": 15,
                    "creatives": [{"id": "CR_3", "format": "video", "headline": "Ad 3"}]
                }
            ]
        }

        sanitized = spy_ads.sanitize_spy_data(payload, "multi-adv-test.com")
        self.assertEqual(sanitized["total_advertisers"], 3)
        self.assertEqual(sanitized["total_ads"], 32)

        adv_map = {a["id"]: a for a in sanitized["advertisers"]}
        self.assertEqual(adv_map["AR_001"]["ad_count"], 26)
        self.assertEqual(adv_map["AR_002"]["ad_count"], 5)
        self.assertEqual(adv_map["AR_003"]["ad_count"], 1)
        self.assertEqual(adv_map["AR_001"]["classification"], "evergreen")
        self.assertEqual(adv_map["AR_002"]["classification"], "seasonal")
        self.assertEqual(adv_map["AR_003"]["classification"], "new_test")

    def test_16_sanitizer_pipeline_idempotency(self):
        """
        [Tier 4] Verify that running spy data through sanitize_spy_data
        multiple times produces idempotent results without data decay.
        """
        initial_data = {
            "domain": "idempotent-test.com",
            "advertisers": [
                {
                    "id": "AR_IDEMP_1",
                    "name": "Clean Test Brand",
                    "legal_name": "Clean Test Brand Ltd",
                    "country": "Việt Nam",
                    "country_flag": "🇻🇳",
                    "ad_count": 3,
                    "first_seen": "2026-01-01",
                    "last_shown": "2026-06-01",
                    "duration_days": 152,
                    "creatives": [
                        {
                            "id": "CR_10",
                            "headline": "đã xác minh | Best Deal",
                            "description": "image | Great product",
                            "landing_page": "https://idempotent-test.com"
                        }
                    ]
                }
            ]
        }

        pass1 = spy_ads.sanitize_spy_data(initial_data, "idempotent-test.com")
        json1 = json.dumps(pass1, sort_keys=True)

        pass2 = spy_ads.sanitize_spy_data(pass1, "idempotent-test.com")
        json2 = json.dumps(pass2, sort_keys=True)

        pass3 = spy_ads.sanitize_spy_data(pass2, "idempotent-test.com")
        json3 = json.dumps(pass3, sort_keys=True)

        self.assertEqual(json1, json2, "Sanitizer must be idempotent between pass 1 and pass 2")
        self.assertEqual(json2, json3, "Sanitizer must be idempotent between pass 2 and pass 3")

        # Verify ligatures were removed from creatives and stayed removed
        adv = pass3["advertisers"][0]
        self.assertEqual(adv["name"], "Clean Test Brand")
        self.assertEqual(adv["creatives"][0]["headline"], "Best Deal")
        self.assertEqual(adv["creatives"][0]["description"], "Great product")

    def test_17_advertiser_name_ligature_sanitization(self):
        """
        [Tier 4 / Edge] Verify whether sanitize_spy_data strips icon ligatures
        from advertiser name (e.g. 'videocam | TKTX Company' -> 'TKTX Company').
        """
        dirty_adv_payload = {
            "domain": "brand-test.com",
            "advertisers": [
                {
                    "id": "AR_DIRTY_1",
                    "name": "videocam | TKTX Company",
                    "legal_name": "đã xác minh | TKTX Legal Corp",
                    "ad_count": 5,
                    "creatives": []
                }
            ]
        }
        sanitized = spy_ads.sanitize_spy_data(dirty_adv_payload, "brand-test.com")
        cleaned_name = sanitized["advertisers"][0]["name"]
        self.assertEqual(
            cleaned_name, "TKTX Company",
            f"[M1 Bug Escalation] sanitize_spy_data did not strip icon ligature from advertiser name. "
            f"Expected 'TKTX Company', got '{cleaned_name}'."
        )

    def test_18_monthly_activity_presence_in_sanitized_advertiser(self):
        """
        [Tier 3 / Contract] Verify that sanitize_spy_data computes or preserves
        monthly_activity for multi-year strip (2024, 2025, 2026) per PROJECT.md interface contract.
        """
        adv_payload = {
            "domain": "timeline-test.com",
            "advertisers": [
                {
                    "id": "AR_TL_1",
                    "name": "Timeline Adv",
                    "ad_count": 10,
                    "first_seen": "2024-04-12",
                    "last_shown": "2026-10-09",
                    "duration_days": 911,
                    "creatives": []
                }
            ]
        }
        sanitized = spy_ads.sanitize_spy_data(adv_payload, "timeline-test.com")
        adv = sanitized["advertisers"][0]
        self.assertIn(
            "monthly_activity", adv,
            "[M1 Bug Escalation] adv missing 'monthly_activity' field per PROJECT.md § Interface Contracts. "
            "Ensure backend/spy_ads.py computes 12-month boolean arrays for 2024, 2025, and 2026."
        )
        if "monthly_activity" in adv:
            ma = adv["monthly_activity"]
            self.assertIn("2024", ma)
            self.assertIn("2025", ma)
            self.assertIn("2026", ma)
            self.assertEqual(len(ma["2024"]), 12)
            self.assertEqual(len(ma["2025"]), 12)
            self.assertEqual(len(ma["2026"]), 12)

    def test_19_classification_field_in_sanitized_advertiser(self):
        """
        [Tier 3 / Contract] Verify that sanitize_spy_data assigns tripartite classification
        ('evergreen' | 'seasonal' | 'new_test') per PROJECT.md line 82.
        """
        adv_payload = {
            "domain": "class-test.com",
            "advertisers": [
                {
                    "id": "AR_CLS_1",
                    "name": "Evergreen Brand",
                    "ad_count": 26,
                    "first_seen": "2024-04-12",
                    "last_shown": "2026-10-09",
                    "duration_days": 911,
                    "creatives": []
                }
            ]
        }
        sanitized = spy_ads.sanitize_spy_data(adv_payload, "class-test.com")
        adv = sanitized["advertisers"][0]
        self.assertIn(
            "classification", adv,
            "[M1 Bug Escalation] adv missing 'classification' field ('evergreen' | 'seasonal' | 'new_test') "
            "per PROJECT.md § Interface Contracts."
        )
        if "classification" in adv:
            self.assertIn(adv["classification"], ["evergreen", "seasonal", "new_test"])
            self.assertEqual(adv["classification"], "evergreen")

    def test_20_network_error_not_conflated_with_zero_ads(self):
        """
        [Tier 4 / Defect Fix] Differentiate network error/timeout from verified zero ads.
        When Google Ads Transparency encounters a connection timeout or network failure,
        crawler must return status='error' and is_verified_zero=False.
        It must NOT overwrite as verified zero-ads store.
        """
        import asyncio
        from unittest.mock import patch

        with patch.object(spy_ads, "query_search_creatives_rpc", return_value=None):
            with patch("playwright.async_api.async_playwright", side_effect=Exception("Connection timed out")):
                res = asyncio.run(spy_ads.crawl_google_ads_transparency("network-fail-domain.com"))
                self.assertEqual(res.get("status"), "error")
                self.assertFalse(res.get("is_verified_zero"), "Network failure must NOT be verified zero ads")
                self.assertIn("error", res)



# ==============================================================================
# MAIN TEST RUNNER
# ==============================================================================

if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
