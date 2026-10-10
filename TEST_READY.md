# TEST READY: Google Ads Spy Intelligence Pipeline E2E Test Suite

## Status: READY FOR ACCEPTANCE & ESCALATION
The comprehensive 4-Tier Opaque-Box E2E test suite for Google Ads Spy is operational and available at:
`tests/test_spy_google_ads_e2e.py`

---

## 1. Test Execution Command
To execute the full test suite in the project environment:
```bash
source .venv/bin/activate
python3 -m unittest -v tests/test_spy_google_ads_e2e.py
```

---

## 2. Test Execution Summary

| Metric | Value |
| :--- | :--- |
| **Total Test Cases** | **19** |
| **Passing Tests** | **15** |
| **Failing Tests (Known Implementation Gaps)** | **4** |
| **Execution Time** | **~0.05 seconds** |
| **Test Framework** | Python `unittest` (Standard Library, zero dependencies) |

---

## 3. Tier Coverage Breakdown

### Tier 1: Feature Coverage (Core Capabilities)
- [x] `test_01_parse_unix_timestamp_to_iso_date` — **PASS**
  - Verified Unix timestamps `"6"."1"` (`1716439657` -> `2024-05-23`) and `"7"."1"` (`1791604392` -> `2026-10-10`) parse to ISO `YYYY-MM-DD`.
- [ ] `test_02_duration_days_formula_distinct_from_ad_count` — **FAIL (Bug Escalated)**
  - Expected: `duration_days = 31` (from 2025-01-01 to 2025-01-31).
  - Actual: `duration_days = 5` (equaled `ad_count`).
- [x] `test_03_all_time_filter_configuration` — **PASS**
  - Verified All-Time contract flag and crawler function callable.
- [x] `test_04_advertiser_metadata_enrichment_and_icon_cleaning` — **PASS**
  - Verified `_clean_text_line` correctly purges icon words (`videocam`, `image`, `đã xác minh`, `verified`).
- [x] `test_05_zero_ads_payload_standardization` — **PASS**
  - Verified 0-ads payload: `is_verified_zero: true`, `status: 'no_ads'`, counts = 0, empty advertisers list.

### Tier 2: Boundary & Corner Cases
- [x] `test_06_single_day_ad_boundary` — **PASS**
  - Verified `first_seen == last_shown` yields `duration_days = 1`.
- [x] `test_07_multi_year_ad_2024_to_2026` — **PASS**
  - Verified 911-day campaign across 2024-2026 and accurate 12-month boolean array for each year.
- [x] `test_08_leap_year_february_29_handling` — **PASS**
  - Verified Leap Year 2024 (Feb 28 to Mar 1 = 3 days, Feb 2024 = 29 days vs Feb 2025 = 28 days).
- [x] `test_09_missing_malformed_and_inverted_timestamps` — **PASS**
  - Verified inverted dates clamp to $\ge 1$ day without raising exceptions.
- [x] `test_10_domain_normalization_corner_cases` — **PASS**
  - Verified URLs with protocols, `www.`, subpaths, and whitespace normalize cleanly to domain keys.

### Tier 3: Cross-Feature Combinations
- [x] `test_11_tripartite_classification_with_monthly_activity` — **PASS**
  - Verified tripartite classifier: 🌲 Evergreen ($>60-90$ days across multi-year/seasons), 🍂 Seasonal (Q4 T10-T12 $\le 4$ mo), 🟡 New Test ($\le 30$ days).
- [x] `test_12_sqlite_sync_with_json_cache_interoperability` — **PASS**
  - Verified `update_store_spy_ads` synchronizes SQLite `stores` and `load_spy_data` falls back to DB for 0-ads stores.
- [x] `test_13_main_crm_store_spy_filtering` — **PASS**
  - Verified SQL conditions for `has_ads`, `no_ads`, `spied`, and `unspied` in main CRM store list.
- [ ] `test_18_monthly_activity_presence_in_sanitized_advertiser` — **FAIL (Bug Escalated)**
  - Expected: `adv` contains `monthly_activity: { "2024": [bool x 12], "2025": [...], "2026": [...] }`.
  - Actual: `monthly_activity` field is missing.
- [ ] `test_19_classification_field_in_sanitized_advertiser` — **FAIL (Bug Escalated)**
  - Expected: `adv` contains `classification: 'evergreen' | 'seasonal' | 'new_test'`.
  - Actual: `classification` field is missing.

### Tier 4: Real-World Workloads & Integrity
- [x] `test_14_binize_real_world_payload_structure` — **PASS**
  - Verified authentic benchmark file `data/spy_google_ads_binize.json`: 16 advertisers, 58 ads, multi-year history, duration > 100 days.
- [x] `test_15_multi_advertiser_workload_aggregation` — **PASS**
  - Verified aggregation of multi-advertiser payloads (3 advertisers, 32 total ads) without state leakage.
- [x] `test_16_sanitizer_pipeline_idempotency` — **PASS**
  - Verified multi-pass pipeline stability: Pass 1 == Pass 2 == Pass 3.
- [ ] `test_17_advertiser_name_ligature_sanitization` — **FAIL (Bug Escalated)**
  - Expected: `'videocam | TKTX Company'` sanitized to `'TKTX Company'`.
  - Actual: `name` remained `'videocam | TKTX Company'`.

---

## 4. Implementation Bugs Discovered & Escalated to M1 Worker (`worker_backend_m1`)

The following 4 defects must be resolved by `worker_backend_m1` in `backend/spy_ads.py` and `backend/spy_ads_worker.py`:

### Bug 1: `duration_days` Equals `ad_count` Instead of Date Math
- **Severity**: Critical (High Impact on UI)
- **Violated Requirement**: `PROJECT.md` Feature Inventory F3, `ORIGINAL_REQUEST.md` R1
- **File & Line**: `backend/spy_ads.py:360, 377`, `backend/spy_ads_worker.py:326, 341`
- **Observed Behavior**: `duration_days` is assigned the literal value of `ad_count`. An advertiser with 5 ads gets `duration_days = 5` even if running for 31 days.
- **Required Fix**: Compute `duration_days = max(1, (last_shown_dt - first_seen_dt).days + 1)`.

### Bug 2: Missing `monthly_activity` Array for 12-Month Strip
- **Severity**: High (Blocks Frontend 12-Month Strip R2)
- **Violated Requirement**: `PROJECT.md` Interface Contract line 90-92, `ORIGINAL_REQUEST.md` R2
- **File**: `backend/spy_ads.py:sanitize_spy_data`
- **Observed Behavior**: `adv.get("monthly_activity")` is missing (previously stripped by line 40 `adv.pop("multi_year", None)`).
- **Required Fix**: Generate `{ "2024": [bool x 12], "2025": [bool x 12], "2026": [bool x 12] }` representing whether ads were active in each month.

### Bug 3: Missing `classification` Tripartite Field
- **Severity**: High (Blocks Tripartite Badges R2)
- **Violated Requirement**: `PROJECT.md` Interface Contract line 82, Feature Inventory F10
- **File**: `backend/spy_ads.py:sanitize_spy_data`
- **Observed Behavior**: `adv` lacks `classification: 'evergreen' | 'seasonal' | 'new_test'`.
- **Required Fix**: Compute `classification` based on duration and monthly clustering (Evergreen for $\ge 60-90$ days/multi-year, Seasonal for peak clusters like Q4 T10-T12, New Test for $\le 30$ days).

### Bug 4: Incomplete Icon Ligature Stripping on Advertiser Names
- **Severity**: Medium
- **Violated Requirement**: `PROJECT.md` F4, `spec_miner_survey_data/handoff.md` § 11
- **File & Line**: `backend/spy_ads.py:48-53`
- **Observed Behavior**: `_clean_text_line` is applied to creative headlines and descriptions, but omitted for `adv["name"]` and `adv["legal_name"]`. Names starting with `"videocam | "` or `"đã xác minh | "` retain the icon text.
- **Required Fix**: Apply `name = _clean_text_line(name)` and `legal_name = _clean_text_line(legal_name)` in `sanitize_spy_data()`.
