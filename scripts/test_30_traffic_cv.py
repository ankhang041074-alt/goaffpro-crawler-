#!/usr/bin/env python3
"""
scripts/test_30_traffic_cv.py - Rigorous benchmark of Traffic.cv scraper vs. Tranco calibrated Zipf law
Runs an automated test across 30 stores from goaffpro.db:
- 10 Large Stores (traffic >= 100k)
- 10 Medium Stores (traffic 10k - 100k)
- 10 Small / Niche Stores (traffic_status == 'no_data')
Outputs a full comparative Markdown report.
"""

import sys
import os
import re
import time
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend import traffic_worker
from backend import traffic_cv_scraper


def get_test_sample() -> List[Dict[str, Any]]:
    """Select 30 distinct, real stores from the database."""
    conn = sqlite3.connect(str(BASE_DIR / "data" / "goaffpro.db"))
    c = conn.cursor()

    # Generic platform filter to ensure domain validity
    generic_domains = [
        "hostingersite.com", "myshopify.com", "wixsite.com", "wordpress.com",
        "amazon.", "etsy.com", "ebay.", "walmart.com", "target.com",
        "aliexpress.com", "tiktok.com", "instagram.com", "facebook.com",
        "twitter.com", "x.com", "youtube.com", "pinterest.com",
        "linktr.ee", "beacons.ai", "campsite.bio", "bit.ly", "tinyurl.com",
        "payhip.com", "digistore24.com", "gumroad.com", "wed2c.com",
        "clickbank.net", "stan.store", "stan.me"
    ]

    def is_clean_store(url: str) -> bool:
        if not url:
            return False
        clean = url.lower()
        return not any(g in clean for g in generic_domains)

    # 1. Ten Large Stores (traffic >= 100K)
    c.execute("""
        SELECT id, name, website_url, traffic_visits, traffic_raw_value, cookie_days
        FROM stores
        WHERE traffic_raw_value >= 100000 AND website_url != ''
        ORDER BY RANDOM() LIMIT 40
    """)
    raw_large = c.fetchall()
    large = []
    for r in raw_large:
        if is_clean_store(r[2]):
            large.append({
                "group": "1. Large (≥100K)",
                "id": r[0],
                "name": r[1],
                "url": r[2],
                "db_visits": r[3],
                "db_raw": r[4],
                "cookie_days": r[5]
            })
        if len(large) == 10:
            break

    # 2. Ten Medium Stores (10K - 100K)
    c.execute("""
        SELECT id, name, website_url, traffic_visits, traffic_raw_value, cookie_days
        FROM stores
        WHERE traffic_raw_value >= 10000 AND traffic_raw_value < 100000 AND website_url != ''
        ORDER BY RANDOM() LIMIT 40
    """)
    raw_medium = c.fetchall()
    medium = []
    for r in raw_medium:
        if is_clean_store(r[2]):
            medium.append({
                "group": "2. Medium (10K-100K)",
                "id": r[0],
                "name": r[1],
                "url": r[2],
                "db_visits": r[3],
                "db_raw": r[4],
                "cookie_days": r[5]
            })
        if len(medium) == 10:
            break

    # 3. Ten Small Stores (no_data)
    c.execute("""
        SELECT id, name, website_url, traffic_visits, traffic_raw_value, cookie_days
        FROM stores
        WHERE traffic_status = 'no_data' AND website_url != ''
        ORDER BY RANDOM() LIMIT 40
    """)
    raw_small = c.fetchall()
    small = []
    for r in raw_small:
        if is_clean_store(r[2]):
            small.append({
                "group": "3. Small (No Data)",
                "id": r[0],
                "name": r[1],
                "url": r[2],
                "db_visits": "0",
                "db_raw": 0,
                "cookie_days": r[5]
            })
        if len(small) == 10:
            break

    conn.close()
    return large + medium + small


def run_benchmark():
    print("=" * 80)
    print("🚀 BẮT ĐẦU KIỂM THỬ ĐỐI CHỨNG 30 WEBSITE (TRAFFIC.CV vs TRANCO ZIPF)")
    print("=" * 80)

    stores = get_test_sample()
    total = len(stores)
    print(f"-> Đã chọn {total} stores từ goaffpro.db (10 Large, 10 Medium, 10 Small)")

    domains = [traffic_worker.extract_domain(s["url"]) for s in stores]

    print("\n-> Đang khởi chạy Playwright Google Chrome persistent context...")
    t_start = time.time()

    # Run batch scrape
    cv_results = {}

    def progress_callback(current, total_count, item_res):
        domain = item_res.get("domain")
        status = item_res.get("status")
        visits = item_res.get("traffic_visits") or "no_data"
        grank = item_res.get("global_rank") or "-"
        print(f"[{current:02d}/{total_count:02d}] {domain:<28} | Status: {status:<8} | Traffic.cv: {visits:<8} | Rank: {grank}")

    scraped_list = traffic_cv_scraper.scrape_traffic_cv_batch(
        domains=domains,
        timeout_sec=15,
        delay_sec=1.5,
        on_progress=progress_callback
    )

    for item in scraped_list:
        cv_results[item.get("domain")] = item

    duration = time.time() - t_start
    print(f"\n-> Hoàn thành cào {len(scraped_list)}/{total} websites trong {duration:.1f}s ({duration/total:.2f}s/store)")

    # Comparative analysis
    print("\n" + "=" * 120)
    print(f"{'NHÓM':<18} | {'STORE / DOMAIN':<30} | {'TRANCO CALIB':<14} | {'TRAFFIC.CV':<12} | {'T.CV RANK':<10} | {'BOUNCE':<8} | {'STATUS'}")
    print("-" * 120)

    rows_report = []

    for s in stores:
        domain = traffic_worker.extract_domain(s["url"])
        cv = cv_results.get(domain, {})

        # Tranco calibrated estimation
        tranco_rank, _ = traffic_worker.fetch_domain_rank(domain)
        if tranco_rank:
            tranco_calib_raw = traffic_worker.rank_to_visits(tranco_rank)
            tranco_calib_str = traffic_worker.format_visits(tranco_calib_raw)
        else:
            tranco_calib_str = "no_data"
            tranco_calib_raw = 0

        cv_status = cv.get("status", "error")
        cv_visits = cv.get("traffic_visits") or ("0" if cv_status == "no_data" else cv_status)
        cv_grank = str(cv.get("global_rank") or "-")
        bounce = cv.get("bounce_rate") or "-"

        print(f"{s['group']:<18} | {domain:<30} | {tranco_calib_str:<14} | {cv_visits:<12} | {cv_grank:<10} | {bounce:<8} | {cv_status}")

        rows_report.append({
            "group": s["group"],
            "name": s["name"],
            "domain": domain,
            "url": s["url"],
            "cookie_days": s["cookie_days"],
            "tranco_rank": tranco_rank or "-",
            "tranco_calib": tranco_calib_str,
            "traffic_cv_visits": cv_visits,
            "traffic_cv_raw": cv.get("traffic_raw_value", 0),
            "traffic_cv_rank": cv_grank,
            "bounce_rate": bounce,
            "avg_duration": cv.get("avg_duration") or "-",
            "status": cv_status
        })

    # Summary statistics
    success_count = sum(1 for r in rows_report if r["status"] == "success")
    nodata_count = sum(1 for r in rows_report if r["status"] == "no_data")
    blocked_count = sum(1 for r in rows_report if r["status"] == "cf_blocked")
    error_count = sum(1 for r in rows_report if r["status"] == "error")

    print("=" * 120)
    print(f"TỔNG KẾT: Thành công: {success_count} | Dưới ngưỡng (no_data): {nodata_count} | Bị chặn Cloudflare: {blocked_count} | Lỗi: {error_count}")
    print("=" * 120)

    # Save Markdown report
    report_file = BASE_DIR / "data" / "benchmark_30_traffic_cv_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(rows_report, f, ensure_ascii=False, indent=2)
    print(f"-> Đã lưu báo cáo chi tiết vào: {report_file}")


if __name__ == "__main__":
    run_benchmark()
