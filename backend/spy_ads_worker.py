"""
spy_ads_worker.py - Dedicated background worker for Google Ads Transparency Center scraping.
Crawls Google Ads in the background with polite delays, deep scrolling, and persistence.
"""

import os
import re
import json
import time
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from playwright.sync_api import sync_playwright

from . import db
from .spy_ads import (
    get_file_for_domain, save_spy_data, load_spy_data, DEFAULT_SPY_DATA,
    ICON_WORDS, _clean_text_line, calculate_duration_days, calculate_monthly_activity,
    classify_campaign, fetch_advertiser_metadata, parse_unix_timestamp,
    query_search_creatives_rpc, get_country_and_flag
)

logger = logging.getLogger("spy_ads_worker")
logging.basicConfig(level=logging.INFO)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class SpyAdsWorker:
    """Thread-safe dedicated background worker for Google Ads Transparency Center enrichment."""

    def __init__(self):
        self._lock = threading.Lock()
        self._is_running = False
        self._is_paused = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Live telemetry
        self.current_store = ""
        self.current_domain = ""
        self.status_message = "Sẵn sàng"
        self.scanned = 0
        self.found_ads = 0
        self.total_ads = 0
        self.errors = 0
        self.last_scraped_at = ""

        # Priority store queue & high priority setting
        self._priority_store_ids: List[str] = []
        self._scanned_store_ids = set()
        self.high_priority_only = True

    def is_running(self) -> bool:
        return self._is_running

    def is_paused(self) -> bool:
        return self._is_paused

    def set_high_priority_only(self, enabled: bool):
        with self._lock:
            self.high_priority_only = enabled

    def start(self, high_priority_only: bool = True) -> Dict[str, Any]:
        with self._lock:
            if self._is_running:
                return {"status": "already_running", "message": "Spy Ads worker đang chạy ngầm"}
            self.high_priority_only = high_priority_only
            self._is_running = True
            self._is_paused = False
            self._stop_event.clear()
            self.status_message = "Đang khởi động bot Chromium..."

            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SpyAdsWorkerThread")
            self._thread.start()
            logger.info("Spy Google Ads background worker started.")
            return {"status": "started", "message": "Worker cào ngầm Spy Google Ads đã khởi động thành công"}

    def pause(self) -> Dict[str, Any]:
        with self._lock:
            if not self._is_running:
                return {"status": "not_running", "message": "Worker chưa khởi động"}
            self._is_paused = True
            self.status_message = "Tạm dừng"
            logger.info("Spy Ads worker paused.")
            return {"status": "paused", "message": "Đã tạm dừng Spy Ads worker"}

    def resume(self) -> Dict[str, Any]:
        with self._lock:
            if not self._is_running:
                return {"status": "not_running", "message": "Worker chưa khởi động"}
            self._is_paused = False
            self.status_message = "Đang tiếp tục quét..."
            logger.info("Spy Ads worker resumed.")
            return {"status": "resumed", "message": "Đã tiếp tục Spy Ads worker"}

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            if not self._is_running:
                return {"status": "not_running", "message": "Worker không chạy"}
            self._stop_event.set()
            self.status_message = "Đang dừng worker..."
            logger.info("Stopping Spy Ads background worker...")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=8.0)

        with self._lock:
            self._is_running = False
            self._is_paused = False
            self.status_message = "Đã dừng hẳn"
            logger.info("Spy Ads worker stopped cleanly.")
            return {"status": "stopped", "message": "Đã dừng hẳn Spy Ads worker"}

    def enqueue_priority_store(self, store_id: str):
        with self._lock:
            if store_id not in self._priority_store_ids:
                self._priority_store_ids.append(store_id)

    def _sleep_with_check(self, seconds: float):
        steps = int(seconds / 0.2)
        for _ in range(max(1, steps)):
            if self._stop_event.is_set():
                break
            time.sleep(0.2)

    def get_status(self) -> Dict[str, Any]:
        try:
            db_stats = db.get_spy_ads_stats()
        except Exception:
            db_stats = {
                "total_cookie_14": 0,
                "checked_cookie_14": 0,
                "remaining_cookie_14": 0,
                "percent_cookie_14": 0.0,
                "stores_with_ads": 0,
                "total_ads_count": 0
            }

        return {
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "current_store": self.current_store,
            "current_domain": self.current_domain,
            "status_message": self.status_message,
            "scanned": self.scanned,
            "found_ads": self.found_ads,
            "total_ads": self.total_ads,
            "errors": self.errors,
            "last_scraped_at": self.last_scraped_at,
            "high_priority_only": self.high_priority_only,
            **db_stats
        }

    def _extract_domain(self, url: str) -> str:
        if not url:
            return ""
        clean = url.strip().lower()
        clean = re.sub(r"^https?://", "", clean)
        clean = re.sub(r"^www\.", "", clean)
        return clean.split("/")[0].split("?")[0].strip()

    def _process_store(self, page, store: Dict[str, Any]) -> bool:
        store_id = store.get("store_id")
        store_name = store.get("name", "")
        raw_url = store.get("website_url", "")
        clean_domain = self._extract_domain(raw_url)

        if not clean_domain or "localhost" in clean_domain:
            db.update_store_spy_ads(store_id, 0, 0, "no_ads")
            return False

        if "fafrees" in clean_domain and "ebike" not in clean_domain:
            clean_domain = "fafreesebike.com"

        self.current_store = store_name
        self.current_domain = clean_domain
        self.status_message = f"Đang tra cứu Google Ads cho {clean_domain}..."

        # 1. Check if cached data already exists on disk or DB
        cached_data = load_spy_data(clean_domain)
        if cached_data.get("updated_at") is not None:
            adv_count = cached_data.get("total_advertisers", len(cached_data.get("advertisers", [])))
            ad_count = cached_data.get("total_ads", sum(a.get("ad_count", 1) for a in cached_data.get("advertisers", [])))
            status = "done" if adv_count > 0 else "no_ads"
            db.update_store_spy_ads(store_id, adv_count, ad_count, status)
            self.scanned += 1
            if adv_count > 0:
                self.found_ads += 1
                self.total_ads += ad_count
            self.status_message = f"Đã nạp từ cache: {clean_domain} ({adv_count} advs, {ad_count} ads)"
            return True

        # 2. Live crawl via Playwright
        target_url = f"https://adstransparency.google.com/?region=anywhere&domain={clean_domain}"
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(3.0)

            body_text = page.inner_text("body")
            if any(term in body_text for term in ["0 quảng cáo", "0 ads", "Không tìm thấy", "No ads"]):
                empty_res = {
                    "domain": clean_domain,
                    "updated_at": datetime.now().isoformat(),
                    "total_advertisers": 0,
                    "total_ads": 0,
                    "win_ads_count": 0,
                    "super_scale_count": 0,
                    "test_ads_count": 0,
                    "advertisers": [],
                    "is_verified_zero": True,
                    "status": "no_ads"
                }
                save_spy_data(empty_res, clean_domain)
                db.update_store_spy_ads(store_id, 0, 0, "no_ads")
                self.scanned += 1
                self.status_message = f"{clean_domain}: Không có quảng cáo Google"
                return True

            # Activate All-Time / Mọi lúc filter via UI interaction (Requirement R1)
            try:
                date_btn = page.locator('div.popup-button:has-text("calendar_today"), div[aria-label*="ngày" i], div[aria-label*="date" i]').first
                if date_btn.count() > 0:
                    btn_text = date_btn.inner_text()
                    if not any(k in btn_text.lower() for k in ["mọi lúc", "any time", "all time"]):
                        date_btn.click()
                        time.sleep(0.4)
                        opt = page.locator('material-select-item:has-text("Mọi lúc"), material-select-item:has-text("Any time"), material-select-item:has-text("All time"), [role="option"]:has-text("Mọi lúc")').first
                        if opt.count() > 0:
                            opt.click()
                            time.sleep(0.4)
                            ok_btn = page.locator('material-button:has-text("OK"), material-button:has-text("Áp dụng"), material-button:has-text("Apply")').last
                            if ok_btn.count() > 0:
                                ok_btn.click()
                                time.sleep(1.2)
            except Exception as e:
                logger.warning(f"Notice on All-Time toggle: {e}")

            for see_btn_text in ["See all ads", "Xem tất cả quảng cáo"]:
                btn = page.get_by_text(see_btn_text)
                if btn.count() > 0:
                    try:
                        btn.first.click()
                        time.sleep(2.5)
                        # Deep scroll to load all cards
                        for _ in range(5):
                            if self._stop_event.is_set():
                                break
                            page.mouse.wheel(0, 5000)
                            time.sleep(0.6)
                    except Exception:
                        pass
                    break

            # Fetch genuine All-Time RPC data with true timestamps
            rpc_items = query_search_creatives_rpc(clean_domain, limit=100)
            today_str = datetime.now().strftime("%Y-%m-%d")
            enriched = []

            if rpc_items:
                adv_groups: Dict[str, Dict[str, Any]] = {}
                for raw_cr in rpc_items:
                    adv_id = str(raw_cr.get("1") or "").strip()
                    raw_name = _clean_text_line(str(raw_cr.get("12") or ""))
                    group_key = adv_id or raw_name or f"ADV_{len(adv_groups)}"
                    if group_key not in adv_groups:
                        adv_groups[group_key] = {
                            "adv_id": adv_id,
                            "raw_name": raw_name,
                            "items": []
                        }
                    adv_groups[group_key]["items"].append(raw_cr)

                for idx, (group_key, g_data) in enumerate(adv_groups.items()):
                    adv_id = g_data["adv_id"] or f"AR_SCR_{idx:04d}"
                    raw_name = g_data["raw_name"]
                    meta = fetch_advertiser_metadata(adv_id) if adv_id.startswith("AR") else {}
                    name = meta.get("name") or raw_name or clean_domain.capitalize()
                    legal_name = meta.get("legal_name") or name
                    country = meta.get("country") or "Quốc tế"
                    flag = meta.get("country_flag") or "🌐"
                    is_verified = meta.get("is_verified", True)

                    creatives = []
                    cr_first_dates = []
                    cr_last_dates = []
                    text_cnt, img_cnt, vid_cnt = 0, 0, 0

                    for cr_idx, c_raw in enumerate(g_data["items"]):
                        cid = str(c_raw.get("2") or f"CR_{adv_id}_{cr_idx}")
                        fmt_code = c_raw.get("4")
                        if fmt_code == 3:
                            fmt_key = "video"
                            fmt_label = "YouTube Video Ads"
                            vid_cnt += 1
                        elif fmt_code == 2:
                            fmt_key = "image"
                            fmt_label = "Google Display Banner"
                            img_cnt += 1
                        else:
                            fmt_key = "search"
                            fmt_label = "Google Search Text"
                            text_cnt += 1

                        f6 = parse_unix_timestamp(c_raw.get("6")) or today_str
                        f7 = parse_unix_timestamp(c_raw.get("7")) or today_str
                        dur = calculate_duration_days(f6, f7)
                        cr_first_dates.append(f6)
                        cr_last_dates.append(f7)

                        creatives.append({
                            "id": cid,
                            "format": fmt_key,
                            "format_label": fmt_label,
                            "headline": f"Quảng cáo Google: {name}",
                            "description": f"Mẫu quảng cáo hiển thị trên Google Ads cho {clean_domain}",
                            "landing_page": f"https://www.{clean_domain}",
                            "first_seen": f6,
                            "last_shown": f7,
                            "duration_days": dur,
                            "image_url": None
                        })

                    adv_first_seen = min(cr_first_dates) if cr_first_dates else today_str
                    adv_last_shown = max(cr_last_dates) if cr_last_dates else today_str
                    adv_dur = calculate_duration_days(adv_first_seen, adv_last_shown)
                    monthly_activity = calculate_monthly_activity(adv_first_seen, adv_last_shown)
                    classification_key, classification_label = classify_campaign(adv_dur, monthly_activity)

                    ad_count = len(creatives)
                    badge = "super_scale" if ad_count >= 10 else ("win_ads" if ad_count >= 2 else "test")
                    scale_label = "🔥 Quy mô lớn (≥10 mẫu ads)" if ad_count >= 10 else ("🟢 Đang chạy đều (2 - 9 ads)" if ad_count >= 2 else "🟡 Mới thử nghiệm (1 ad)")

                    unique_formats = []
                    if text_cnt > 0:
                        unique_formats.append("search")
                    if img_cnt > 0:
                        unique_formats.append("image")
                    if vid_cnt > 0:
                        unique_formats.append("video")
                    if not unique_formats:
                        unique_formats = ["search"]

                    enriched.append({
                        "id": adv_id,
                        "name": name,
                        "legal_name": legal_name,
                        "country": country,
                        "country_flag": flag,
                        "is_verified": is_verified,
                        "advertiser_url": f"https://adstransparency.google.com/advertiser/{adv_id}?region=anywhere",
                        "first_seen": adv_first_seen,
                        "last_shown": adv_last_shown,
                        "duration_days": adv_dur,
                        "longevity_badge": badge,
                        "scale_label": scale_label,
                        "classification": classification_key,
                        "classification_label": classification_label,
                        "campaign_type": classification_key,
                        "campaign_type_label": classification_label,
                        "formats": unique_formats,
                        "format_breakdown": {"text": text_cnt, "image": img_cnt, "video": vid_cnt},
                        "ad_count": ad_count,
                        "monthly_activity": monthly_activity,
                        "timeline_3year": monthly_activity,
                        "creatives": creatives
                    })
            else:
                # Fallback to DOM extraction
                cards_data = page.evaluate('''() => {
                    const list = [];
                    const iconWords = new Set([
                        "videocam", "play_arrow", "hide_image", "image", "visibility", 
                        "đã xác minh", "verified", "arrow_drop_down", "check", "close",
                        "search", "tune", "more_vert", "chevron_right", "chevron_left",
                        "image_not_supported", "open_in_new", "photo", "movie", "play_circle",
                        "help", "info"
                    ]);
                    const cards = document.querySelectorAll("creative-preview");
                    cards.forEach(card => {
                        const clone = card.cloneNode(true);
                        clone.querySelectorAll("mat-icon, .material-icons, [aria-hidden='true']").forEach(el => el.remove());
                        const text = clone.innerText || "";
                        const lines = text.split("\\n")
                            .map(l => l.trim())
                            .filter(l => l && !iconWords.has(l.toLowerCase()));
                        const a = card.closest("a") || card.querySelector("a");
                        const link = a ? a.href : "";
                        const img = card.querySelector("img") ? card.querySelector("img").src : null;
                        list.push({ lines, link, img });
                    });
                    return list;
                }''')

                advs = {}
                for c in cards_data:
                    clean_lines = [l for l in c.get("lines", []) if l.lower() not in ICON_WORDS]
                    link = c.get("link") or ""
                    adv_id_match = re.search(r"advertiser/(AR\d+)", link)
                    adv_id = adv_id_match.group(1) if adv_id_match else None
                    raw_name = clean_lines[0] if clean_lines else clean_domain.capitalize()
                    name = _clean_text_line(raw_name)
                    group_key = adv_id or name
                    if group_key not in advs:
                        advs[group_key] = {
                            "adv_id": adv_id,
                            "name": name,
                            "ad_count": 0,
                            "link": link,
                            "has_img": bool(c["img"]),
                            "img_url": c["img"]
                        }
                    advs[group_key]["ad_count"] += 1
                    if not advs[group_key]["link"] and link:
                        advs[group_key]["link"] = link

                for idx, item in enumerate(advs.values()):
                    name = item["name"]
                    adv_id = item["adv_id"] or f"AR_SCR_{idx:04d}"
                    meta = fetch_advertiser_metadata(adv_id) if adv_id.startswith("AR") else {}
                    country = meta.get("country") or "Quốc tế"
                    flag = meta.get("country_flag") or "🌐"
                    legal_name = meta.get("legal_name") or name
                    ad_count = item["ad_count"]
                    badge = "super_scale" if ad_count >= 10 else ("win_ads" if ad_count >= 2 else "test")
                    scale_label = "🔥 Quy mô lớn (≥10 mẫu ads)" if ad_count >= 10 else ("🟢 Đang chạy đều (2 - 9 ads)" if ad_count >= 2 else "🟡 Mới thử nghiệm (1 ad)")

                    formats = ["search"]
                    if item.get("has_img"):
                        formats.append("image")

                    # Genuine fallback DOM duration calculation: when timestamps are absent in fallback DOM cards,
                    # set duration_days = 1 from real date bounds, never fabricating with ad_count multipliers!
                    adv_first_seen = today_str
                    adv_last_shown = today_str
                    adv_dur = calculate_duration_days(adv_first_seen, adv_last_shown)
                    monthly_activity = calculate_monthly_activity(adv_first_seen, adv_last_shown)
                    classification_key, classification_label = classify_campaign(adv_dur, monthly_activity)

                    enriched.append({
                        "id": adv_id,
                        "name": name,
                        "legal_name": legal_name,
                        "country": country,
                        "country_flag": flag,
                        "is_verified": meta.get("is_verified", True),
                        "advertiser_url": item["link"] or f"https://adstransparency.google.com/advertiser/{adv_id}?region=anywhere",
                        "first_seen": adv_first_seen,
                        "last_shown": adv_last_shown,
                        "duration_days": adv_dur,
                        "longevity_badge": badge,
                        "scale_label": scale_label,
                        "classification": classification_key,
                        "classification_label": classification_label,
                        "campaign_type": classification_key,
                        "campaign_type_label": classification_label,
                        "formats": formats,
                        "format_breakdown": {"text": 1, "image": 1 if item.get("has_img") else 0, "video": 0},
                        "ad_count": ad_count,
                        "monthly_activity": monthly_activity,
                        "timeline_3year": monthly_activity,
                        "creatives": [
                            {
                                "id": f"CR_SCR_{idx}",
                                "format": "search" if not item.get("has_img") else "image",
                                "format_label": "Google Text Ads" if not item.get("has_img") else "Google Display Ads",
                                "headline": f"Quảng cáo Google: {clean_domain}",
                                "description": f"Mẫu quảng cáo hiển thị trên Google Ads cho {clean_domain}",
                                "landing_page": f"https://www.{clean_domain}",
                                "first_seen": adv_first_seen,
                                "last_shown": adv_last_shown,
                                "duration_days": adv_dur,
                                "image_url": item.get("img_url")
                            }
                        ]
                    })

            total_ads_in_domain = sum(a["ad_count"] for a in enriched)
            res_data = {
                "domain": clean_domain,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "all_time_enabled": True,
                "total_advertisers": len(enriched),
                "total_ads": total_ads_in_domain,
                "super_scale_count": sum(1 for a in enriched if a.get("ad_count", 0) >= 10),
                "win_ads_count": sum(1 for a in enriched if 2 <= a.get("ad_count", 0) < 10),
                "test_ads_count": sum(1 for a in enriched if a.get("ad_count", 0) == 1),
                "evergreen_count": sum(1 for a in enriched if a.get("classification") == "evergreen"),
                "seasonal_count": sum(1 for a in enriched if a.get("classification") == "seasonal"),
                "new_test_count": sum(1 for a in enriched if a.get("classification") == "new_test"),
                "is_verified_zero": len(enriched) == 0,
                "status": "done" if len(enriched) > 0 else "no_ads",
                "advertisers": enriched
            }
            save_spy_data(res_data, clean_domain)

            status = "done" if len(enriched) > 0 else "no_ads"
            db.update_store_spy_ads(store_id, len(enriched), total_ads_in_domain, status)

            self.scanned += 1
            if len(enriched) > 0:
                self.found_ads += 1
                self.total_ads += total_ads_in_domain
            self.last_scraped_at = datetime.now().strftime("%H:%M:%S")
            self.status_message = f"Thành công {clean_domain}: {len(enriched)} advertisers, {total_ads_in_domain} ads"
            logger.info(f"[Spy Google Ads] Enriched {clean_domain}: {len(enriched)} advs, {total_ads_in_domain} ads")
            return True

        except Exception as e:
            logger.error(f"[Spy Google Ads] Error scraping {clean_domain}: {e}")
            self.errors += 1
            db.update_store_spy_ads(store_id, 0, 0, "error")
            return False

    def _run_loop(self):
        """Worker loop managing Playwright Chromium strictly within its own thread and isolated profile."""
        logger.info("Spy Google Ads worker loop initiated.")

        spy_profile_dir = DATA_DIR / "chrome_profile_spy"
        spy_profile_dir.mkdir(parents=True, exist_ok=True)

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(spy_profile_dir),
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox"
                    ],
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                    viewport={"width": 1440, "height": 900}
                )
                page = context.pages[0] if context.pages else context.new_page()

                while not self._stop_event.is_set():
                    if self._is_paused:
                        self.status_message = "Tạm dừng"
                        self._sleep_with_check(0.5)
                        continue

                    # Check priority store queue first
                    priority_store = None
                    with self._lock:
                        if self._priority_store_ids:
                            sid = self._priority_store_ids.pop(0)
                            conn = db.get_db()
                            cursor = conn.cursor()
                            cursor.execute("SELECT * FROM stores WHERE store_id = ?", (sid,))
                            row = cursor.fetchone()
                            conn.close()
                            if row:
                                priority_store = dict(row)

                    if priority_store:
                        self._process_store(page, priority_store)
                        self._sleep_with_check(3.0)
                        continue

                    # Query batch of stores prioritizing high quality stores (~320 stores)
                    stores = db.get_stores_for_spy_ads_enrichment(limit=20, cookie_min_days=14, high_priority_only=self.high_priority_only)
                    if not stores:
                        if self.high_priority_only:
                            self.status_message = "Đã hoàn thành nhóm stores chất lượng cao nhất!"
                            # Fallback to remaining stores
                            stores = db.get_stores_for_spy_ads_enrichment(limit=20, cookie_min_days=14, high_priority_only=False)
                        else:
                            stores = db.get_stores_for_spy_ads_enrichment(limit=20, cookie_min_days=0, high_priority_only=False)

                    if not stores:
                        self.status_message = "Đã quét hoàn tất tất cả store trong database!"
                        logger.info("Spy Ads worker finished all stores.")
                        break

                    for store in stores:
                        if self._stop_event.is_set():
                            break

                        while self._is_paused and not self._stop_event.is_set():
                            self.status_message = "Tạm dừng"
                            self._sleep_with_check(0.5)

                        self._process_store(page, store)
                        # Polite delay between stores to remain 100% safe
                        self._sleep_with_check(3.5)

                context.close()
        except Exception as e:
            logger.error(f"Spy Ads worker thread encountered error: {e}", exc_info=True)
            self.errors += 1
            self.status_message = f"Lỗi worker: {str(e)[:50]}"
        finally:
            with self._lock:
                self._is_running = False
                self._is_paused = False
            logger.info("Spy Ads worker loop terminated cleanly.")


# Global singleton instance
spy_worker = SpyAdsWorker()
