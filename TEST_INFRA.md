# Test Infrastructure: Google Ads Spy Intelligence Pipeline

## 1. Overview & Purpose
This document defines the testing architecture and test runner specifications for the **Google Ads Transparency Spy All-Time & 12-Month Timeline** standardization feature.
The test suite validates data extraction, calendar mathematics, tripartite classification, multi-year monthly timeline arrays, SQLite persistence, and UI synchronization contracts.

---

## 2. Test Architecture & Directory Layout

```
/Users/trankhang/Downloads/tool goaff/
├── backend/
│   ├── spy_ads.py                 # Core crawler, sanitization, JSON cache
│   ├── spy_ads_worker.py          # Background worker
│   ├── api.py                     # FastAPI endpoints (/api/spy/google-ads, crawl)
│   └── db.py                      # SQLite database queries & store updates
├── data/
│   ├── goaffpro.db                # Production SQLite database (protected)
│   └── spy_google_ads_binize.json # Authentic benchmark dataset (58 ads, multi-year)
├── tests/
│   └── test_spy_google_ads_e2e.py # 4-Tier Opaque-Box E2E Test Suite (19 tests)
├── TEST_INFRA.md                  # Test runner & architecture documentation (this file)
└── TEST_READY.md                  # Test readiness & defect escalation report
```

---

## 3. Test Runner Commands

The test suite is built on Python's standard `unittest` framework to guarantee zero external dependency overhead and 100% deterministic reproducibility.

### Primary Command (Virtual Environment)
```bash
source .venv/bin/activate
python3 -m unittest tests/test_spy_google_ads_e2e.py
```

### Verbose Mode with Detailed Execution Trace
```bash
source .venv/bin/activate
python3 -m unittest -v tests/test_spy_google_ads_e2e.py
```

### Single Tier / Test Method Execution
```bash
# Run only Tier 1 Feature Coverage
python3 -m unittest tests.test_spy_google_ads_e2e.TestGoogleAdsSpyTier1FeatureCoverage

# Run only Tier 2 Boundary Cases
python3 -m unittest tests.test_spy_google_ads_e2e.TestGoogleAdsSpyTier2BoundaryCornerCases

# Run only Tier 3 Cross-Feature Combinations
python3 -m unittest tests.test_spy_google_ads_e2e.TestGoogleAdsSpyTier3CrossFeatureCombinations

# Run only Tier 4 Real-World Workloads
python3 -m unittest tests.test_spy_google_ads_e2e.TestGoogleAdsSpyTier4RealWorldWorkloads
```

---

## 4. 4-Tier Test Design Matrix

| Tier | Category | Test Method | Covered Requirements | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | Feature Coverage | `test_01_parse_unix_timestamp_to_iso_date` | F2, R1 | Parses Unix timestamps (`1716439657` -> `2024-05-23`) from RPC `"6"."1"` and `"7"."1"`. |
| **Tier 1** | Feature Coverage | `test_02_duration_days_formula_distinct_from_ad_count` | F3, R1 | Verifies `duration_days = max(1, (last_shown - first_seen).days + 1)` is computed from dates, NOT `ad_count`. |
| **Tier 1** | Feature Coverage | `test_03_all_time_filter_configuration` | F1, R1 | Validates All-Time mode contract and verifies unconstrained date range in Transparency RPC. |
| **Tier 1** | Feature Coverage | `test_04_advertiser_metadata_enrichment_and_icon_cleaning` | F4, R1 | Verifies advertiser fields and tests `_clean_text_line` removing icon ligatures (`videocam`, `image`, etc.). |
| **Tier 1** | Feature Coverage | `test_05_zero_ads_payload_standardization` | F7, R3 | Verifies payload for 0-ads store: `is_verified_zero: true`, `status: 'no_ads'`, counts = 0, empty list. |
| **Tier 2** | Boundary & Corner | `test_06_single_day_ad_boundary` | F3 | When `first_seen == last_shown`, duration MUST equal 1 (never 0 or negative). |
| **Tier 2** | Boundary & Corner | `test_07_multi_year_ad_2024_to_2026` | F11, R2 | Multi-year campaign spanning 2024..2026 (911 days), verifying 12-month boolean array per year. |
| **Tier 2** | Boundary & Corner | `test_08_leap_year_february_29_handling` | F3 | 2024 leap year math: Feb 28 to Mar 1 = 3 days, Feb 2024 = 29 days, Feb 2025 = 28 days. |
| **Tier 2** | Boundary & Corner | `test_09_missing_malformed_and_inverted_timestamps` | F3 | Clamps duration $\ge 1$ when timestamps are inverted or dates are anomalous. |
| **Tier 2** | Boundary & Corner | `test_10_domain_normalization_corner_cases` | F6 | Normalizes URLs with protocols (`https://`), `www.`, paths, and trailing slashes. |
| **Tier 3** | Cross-Feature | `test_11_tripartite_classification_with_monthly_activity` | F10, R2 | Tests classification: 🌲 Evergreen, 🍂 Seasonal (e.g. Q4 T10-T12), 🟡 New Test ($\le 30$ days). |
| **Tier 3** | Cross-Feature | `test_12_sqlite_sync_with_json_cache_interoperability` | F5, F7, R3 | Updates SQLite `stores` table and tests `load_spy_data` DB fallback for missing 0-ads cache. |
| **Tier 3** | Cross-Feature | `test_13_main_crm_store_spy_filtering` | F5, R3 | Verifies CRM store filters (`has_ads`, `no_ads`, `spied`, `unspied`) against SQLite database. |
| **Tier 4** | Real-World Workload | `test_14_binize_real_world_payload_structure` | F14, AC 1 | Validates authentic benchmark dataset in `data/spy_google_ads_binize.json` against contracts. |
| **Tier 4** | Real-World Workload | `test_15_multi_advertiser_workload_aggregation` | F4, F6 | Verifies domain with multiple advertisers (evergreen + seasonal + test) aggregates correctly. |
| **Tier 4** | Real-World Workload | `test_16_sanitizer_pipeline_idempotency` | F6 | Multi-pass sanitization stability: Pass 1 == Pass 2 == Pass 3 without data degradation. |
| **Tier 4** | Boundary & Edge | `test_17_advertiser_name_ligature_sanitization` | F4 | Validates whether `sanitize_spy_data` purges icon ligatures from advertiser names. |
| **Tier 3** | Interface Contract | `test_18_monthly_activity_presence_in_sanitized_advertiser` | F6, F9, R2 | Verifies presence of `monthly_activity` (`{ "2024": [bool x 12], "2025": [...], "2026": [...] }`). |
| **Tier 3** | Interface Contract | `test_19_classification_field_in_sanitized_advertiser` | F10, R2 | Verifies presence of `classification` (`'evergreen' \| 'seasonal' \| 'new_test'`) on advertiser. |

---

## 5. Test Isolation & Data Protection Strategy
To ensure production databases and live caches remain completely untouched:
1. **Isolated SQLite Database**: Tests in `TestGoogleAdsSpyTier3CrossFeatureCombinations` instantiate a temporary SQLite database using `tempfile.TemporaryDirectory()`, monkeypatching `db.DB_PATH` during `setUp()` and restoring `_orig_db_path` in `tearDown()`. Production `data/goaffpro.db` is never modified.
2. **Deterministic Timezone**: Date parsing test cases strictly use UTC (`timezone.utc`) to ensure tests produce identical outputs regardless of host server timezone (Vietnam, UTC, US).
3. **Read-Only Ingestion**: Real-world workload tests inspect `data/spy_google_ads_binize.json` in read-only mode without overwriting or deleting production cache files.

---

## 6. Authoritative Expected Output Derivation
All expected outputs are derived from authoritative specifications in:
- `PROJECT.md` § Interface Contracts & § Feature Inventory
- `ORIGINAL_REQUEST.md` § Requirements (R1, R2, R3) and Acceptance Criteria
- `spec_miner_survey_data/handoff.md` (DOM and RPC response schema)
- `explorer_survey_crawler/handoff.md` (Unix timestamp extraction parameters)
