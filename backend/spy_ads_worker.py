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
from .spy_ads import get_file_for_domain, save_spy_data, load_spy_data, DEFAULT_SPY_DATA, ICON_WORDS, _clean_text_line

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

            for see_btn_text in ["See all ads", "Xem tất cả quảng cáo"]:
                btn = page.get_by_text(see_btn_text)
                if btn.count() > 0:
                    try:
                        btn.first.click()
                        time.sleep(3.0)
                        # Deep scroll to load all cards
                        for _ in range(5):
                            if self._stop_event.is_set():
                                break
                            page.mouse.wheel(0, 5000)
                            time.sleep(0.8)
                    except Exception:
                        pass
                    break

            # Robust DOM extraction: clone node and remove icon elements before taking innerText
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

                raw_name = clean_lines[0] if clean_lines else ""
                if not raw_name or raw_name.lower() in ICON_WORDS:
                    raw_name = clean_domain.capitalize()
                name = raw_name.strip()

                group_key = adv_id or name
                if group_key not in advs:
                    advs[group_key] = {
                        "adv_id": adv_id,
                        "name": name,
                        "ad_count": 0,
                        "link": link,
                        "has_img": bool(c["img"]),
                        "img_url": c["img"],
                        "lines": clean_lines
                    }
                else:
                    if name != clean_domain.capitalize() and advs[group_key]["name"] == clean_domain.capitalize():
                        advs[group_key]["name"] = name
                    if not advs[group_key]["img_url"] and c["img"]:
                        advs[group_key]["img_url"] = c["img"]
                        advs[group_key]["has_img"] = True
                advs[group_key]["ad_count"] += 1
                if not advs[group_key]["link"] and link:
                    advs[group_key]["link"] = link

            enriched = []
            today_str = datetime.now().strftime("%Y-%m-%d")
            for idx, item in enumerate(advs.values()):
                name = item["name"]
                is_vn = any(k in name.upper() for k in [
                    "NGUYỄN", "TRẦN", "LÊ", "PHẠM", "HOÀNG", "ĐẶNG", "BÙI", 
                    "ĐỖ", "HỒ", "NGÔ", "DƯƠNG", "LÝ", "VŨ", "ĐINH", "TRỊNH", 
                    "CÔNG TY", "TNHH", "MEDIA", "DIGITAL"
                ])
                country = "Việt Nam" if is_vn else ("Trung Quốc" if any(c in name for c in ["深圳", "Ruixin", "Guangzhou"]) else "Quốc tế")
                flag = "🇻🇳" if country == "Việt Nam" else ("🇨🇳" if country == "Trung Quốc" else "🌐")
                
                ad_count = item["ad_count"]
                badge = "super_scale" if ad_count >= 10 else ("win_ads" if ad_count >= 2 else "test")
                scale_label = f"🔥 Quy mô lớn (≥10 mẫu ads)" if ad_count >= 10 else (f"🟢 Đang chạy đều (2 - 9 ads)" if ad_count >= 2 else "🟡 Mới thử nghiệm (1 ad)")
                adv_id = item["adv_id"] or f"AR_SCR_{idx:04d}"

                formats = ["search"]
                if item.get("has_img"):
                    formats.append("image")

                card_lines = item.get("lines", [])
                headline = _clean_text_line(card_lines[1] if len(card_lines) > 1 else f"Quảng cáo Google: {clean_domain}")
                description = _clean_text_line(" | ".join(card_lines[2:4]) if len(card_lines) > 2 else f"Mẫu quảng cáo hiển thị trên Google Ads cho {clean_domain}")

                creatives = [
                    {
                        "id": f"CR_SCR_{idx}",
                        "format": "search" if not item.get("has_img") else "image",
                        "format_label": "Google Text Ads" if not item.get("has_img") else "Google Display Ads",
                        "headline": headline or f"Quảng cáo Google: {clean_domain}",
                        "description": description or f"Mẫu quảng cáo hiển thị trên Google Ads cho {clean_domain}",
                        "landing_page": f"https://www.{clean_domain}",
                        "last_shown": today_str,
                        "duration_days": ad_count,
                        "image_url": item.get("img_url")
                    }
                ]

                enriched.append({
                    "id": adv_id,
                    "name": name,
                    "legal_name": name,
                    "country": country,
                    "country_flag": flag,
                    "is_verified": True,
                    "advertiser_url": item["link"] or f"https://adstransparency.google.com/advertiser/{adv_id}?region=anywhere",
                    "first_seen": today_str,
                    "last_shown": today_str,
                    "duration_days": ad_count,
                    "longevity_badge": badge,
                    "scale_label": scale_label,
                    "formats": formats,
                    "ad_count": ad_count,
                    "creatives": creatives
                })

            total_ads_in_domain = sum(a["ad_count"] for a in enriched)
            res_data = {
                "domain": clean_domain,
                "updated_at": datetime.now().isoformat(),
                "total_advertisers": len(enriched),
                "total_ads": total_ads_in_domain,
                "super_scale_count": sum(1 for a in enriched if a.get("ad_count", 0) >= 10),
                "win_ads_count": sum(1 for a in enriched if 2 <= a.get("ad_count", 0) < 10),
                "test_ads_count": sum(1 for a in enriched if a.get("ad_count", 0) == 1),
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
