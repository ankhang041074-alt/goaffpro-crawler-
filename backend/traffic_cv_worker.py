"""
traffic_cv_worker.py - Dedicated background worker for Traffic.cv (Similarweb) enrichment.
Targets stores prioritizing cookie_days >= 14 (~5,243 stores).
Implements 3 core defense tiers against Cloudflare Turnstile:
  - Tier 1: Auto-pass with persistent profile & anti-automation flags
  - Tier 2: Audible chime & on-screen move with 90s human resolution gate
  - Tier 3: Smart fallback to calibrated Tranco Zipf formula
Runs completely in the background off-screen (-2500, -2500) without taking user focus.
Fully thread-safe with single-thread Playwright affinity and graceful self-healing.
"""

import os
import re
import time
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Set

from playwright.sync_api import sync_playwright

from . import db
from .traffic_worker import extract_domain, fetch_domain_rank, rank_to_visits, format_visits
from .traffic_cv_scraper import parse_traffic_cv_text, get_profile_dir

logger = logging.getLogger("TrafficCVWorker")
logging.basicConfig(level=logging.INFO)


class TrafficCVWorker:
    """Thread-safe dedicated worker for automated Traffic.cv (Similarweb) store enrichment."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._is_paused = False
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._lock = threading.Lock()

        # Thread-safe window positioning request (True = on screen, False = off screen)
        self._target_window_bounds: Optional[bool] = None

        # Playwright session objects (strictly managed within the worker thread)
        self._pw = None
        self._context = None
        self._page = None
        self._cdp = None

        # Worker state
        self.current_store: str = ""
        self.current_domain: str = ""
        self.status_message: str = "Sẵn sàng"
        self.waiting_turnstile: bool = False
        self.turnstile_remaining_sec: int = 0
        self.window_is_on_screen: bool = False

        # Counters
        self.scanned: int = 0
        self.with_data: int = 0
        self.no_data: int = 0
        self.tranco_fallbacks: int = 0
        self.errors: int = 0
        self._scanned_store_ids: Set[str] = set()
        self._priority_store_ids: List[str] = []

    def is_running(self) -> bool:
        return self._is_running

    def is_paused(self) -> bool:
        return self._is_paused

    def enqueue_priority_store(self, store_id: str) -> threading.Event:
        """Enqueue a store ID for immediate on-demand enrichment using active browser session."""
        with self._lock:
            if not hasattr(self, "_priority_events"):
                self._priority_events = {}
            event = threading.Event()
            self._priority_events[store_id] = event
            if store_id not in self._priority_store_ids:
                self._priority_store_ids.insert(0, store_id)
            self._wake_event.set()
            return event

    def start(self) -> Dict[str, Any]:
        with self._lock:
            if self._is_running:
                if self._is_paused:
                    self._is_paused = False
                    self.status_message = "Đã tiếp tục tiến trình quét Traffic.cv"
                    self._wake_event.set()
                    return {"status": "resumed", "message": "Worker resumed"}
                return {"status": "already_running", "message": "Traffic.cv worker is already running"}

            self._is_running = True
            self._is_paused = False
            self._stop_event.clear()
            self._wake_event.clear()
            self._target_window_bounds = None
            self.status_message = "Đang khởi động trình duyệt Traffic.cv ngầm..."

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            logger.info("Traffic.cv enrichment worker started successfully.")
            return {"status": "started", "message": "Traffic.cv worker started in background"}

    def pause(self) -> Dict[str, Any]:
        with self._lock:
            if not self._is_running:
                return {"status": "not_running", "message": "Worker is not running"}
            self._is_paused = True
            self.status_message = "Tạm dừng"
            self._wake_event.set()
            return {"status": "paused", "message": "Traffic.cv worker paused"}

    def resume(self) -> Dict[str, Any]:
        with self._lock:
            if not self._is_running:
                return {"status": "not_running", "message": "Worker is not running"}
            self._is_paused = False
            self.status_message = "Đang quét Traffic.cv..."
            self._wake_event.set()
            return {"status": "resumed", "message": "Traffic.cv worker resumed"}

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            if not self._is_running:
                return {"status": "not_running", "message": "Worker is not running"}
            self._stop_event.set()
            self._is_paused = False
            self.status_message = "Đang dừng worker..."
            self._wake_event.set()
            logger.info("Signaling Traffic.cv background worker to stop...")
            t = self._thread

        # Wait for worker thread to perform its own clean Playwright shutdown
        if t and t.is_alive():
            t.join(timeout=6.0)

        with self._lock:
            self._is_running = False
            self.current_store = ""
            self.current_domain = ""
            self.waiting_turnstile = False
            self.status_message = "Đã dừng hẳn"
            return {"status": "stopped", "message": "Traffic.cv worker stopped"}

    def get_status(self) -> Dict[str, Any]:
        stats = db.get_traffic_cv_stats()
        return {
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "current_store": self.current_store,
            "current_domain": self.current_domain,
            "status_message": self.status_message,
            "waiting_turnstile": self.waiting_turnstile,
            "turnstile_remaining_sec": self.turnstile_remaining_sec,
            "window_is_on_screen": self.window_is_on_screen,
            "scanned": self.scanned,
            "with_data": self.with_data,
            "no_data": self.no_data,
            "tranco_fallbacks": self.tranco_fallbacks,
            "errors": self.errors,
            "cookie_14_stats": {
                "total": stats.get("total_cookie_14", 0),
                "enriched": stats.get("enriched_cookie_14", 0),
                "remaining": stats.get("remaining_cookie_14", 0),
                "percent": stats.get("percent_cookie_14", 0.0),
            },
            "all_stats": {
                "total": stats.get("total_stores", 0),
                "enriched": stats.get("total_enriched", 0),
                "tranco": stats.get("total_tranco", 0),
                "with_data": stats.get("with_data", 0),
                "no_data": stats.get("no_data", 0),
            }
        }

    def bring_to_front(self) -> Dict[str, Any]:
        """Move browser window to screen (100, 100) for user manual inspection or Turnstile check."""
        self._target_window_bounds = True
        self.window_is_on_screen = True
        self._wake_event.set()
        return {"status": "success", "message": "Đã đưa cửa sổ trình duyệt ra màn hình chính"}

    def send_to_back(self) -> Dict[str, Any]:
        """Minimize browser window completely so it disappears from the desktop."""
        self._target_window_bounds = False
        self.window_is_on_screen = False
        self._wake_event.set()
        return {"status": "success", "message": "Đã thu nhỏ và ẩn hoàn toàn cửa sổ trình duyệt xuống Dock"}

    # -------------------------------------------------------------------------
    # Internal Playwright operations (executed strictly on worker thread)
    # -------------------------------------------------------------------------

    def _apply_pending_window_bounds(self):
        """Execute CDP window bounds adjustment safely on the worker thread."""
        if self._target_window_bounds is not None and self._cdp:
            on_screen = self._target_window_bounds
            self._target_window_bounds = None
            self._set_window_bounds(on_screen=on_screen)

    def _set_window_bounds(self, on_screen: bool):
        """Move browser window using Chrome DevTools Protocol (CDP)."""
        if not self._cdp:
            return
        try:
            target_info = self._cdp.send("Target.getTargetInfo")
            target_id = target_info["targetInfo"]["targetId"]
            win_info = self._cdp.send("Browser.getWindowForTarget", {"targetId": target_id})
            win_id = win_info["windowId"]

            if on_screen:
                self._cdp.send("Browser.setWindowBounds", {
                    "windowId": win_id,
                    "bounds": {"left": 100, "top": 100, "width": 1280, "height": 800, "windowState": "normal"}
                })
                self.window_is_on_screen = True
                logger.info("Moved browser window ON-SCREEN to (100, 100)")
                try:
                    subprocess.Popen(
                        ["osascript", "-e", 'tell application "Google Chrome" to activate'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                except Exception:
                    pass
            else:
                self._cdp.send("Browser.setWindowBounds", {
                    "windowId": win_id,
                    "bounds": {"windowState": "minimized"}
                })
                self.window_is_on_screen = False
                logger.info("Minimized browser window completely off screen (Dock/Hidden)")
        except Exception as e:
            logger.warning(f"Error adjusting window bounds via CDP: {e}")

    def _sleep_with_check(self, seconds: float):
        """High-responsiveness sleep slicing into 100ms intervals."""
        deadline = time.time() + seconds
        while time.time() < deadline and not self._stop_event.is_set():
            if self._wake_event.is_set():
                self._wake_event.clear()
            self._apply_pending_window_bounds()
            if self._is_paused:
                break
            time.sleep(0.1)

    def _play_alert_sound(self):
        """Play audible chime on macOS for Tier 2 human intervention alert."""
        sound_path = "/System/Library/Sounds/Glass.aiff"
        if os.path.exists(sound_path):
            try:
                subprocess.Popen(["afplay", sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def _is_cloudflare_challenge(self) -> bool:
        """Check if active page is displaying a Cloudflare Turnstile challenge."""
        if not self._page:
            return False
        try:
            title = (self._page.title() or "").lower()
            if any(w in title for w in ["just a moment", "chờ", "checking your browser", "cloudflare", "attention required"]):
                return True

            # Quick DOM inspect for Turnstile challenge iframe / widget
            html = self._page.content().lower()[:2000]
            if "cf-turnstile" in html or "challenges.cloudflare.com" in html:
                if "verify you are human" in html or "xác minh bạn là con người" in html:
                    return True
        except Exception:
            pass
        return False

    def _init_browser(self) -> bool:
        """Initialize single persistent browser session running off-screen."""
        profile_dir = get_profile_dir()
        try:
            self._pw = sync_playwright().start()
            launch_kwargs = {
                "user_data_dir": str(profile_dir),
                "headless": False,
                "ignore_default_args": ["--enable-automation"],
                "viewport": {"width": 1280, "height": 800},
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-session-crashed-bubble",
                    "--no-restore-session-state",
                    "--disable-infobars",
                    "--window-position=-2500,-2500",
                    "--window-size=1280,800"
                ]
            }
            if Path("/Applications/Google Chrome.app").exists():
                launch_kwargs["channel"] = "chrome"

            self._context = self._pw.chromium.launch_persistent_context(**launch_kwargs)
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            self._cdp = self._context.new_cdp_session(self._page)
            self.window_is_on_screen = False
            self._set_window_bounds(on_screen=False)
            logger.info("Persistent Chrome session initialized and minimized off-screen.")
            return True
        except Exception as e:
            logger.error(f"Failed to launch Chrome for Traffic.cv worker: {e}")
            self._close_browser()
            return False

    def _ensure_browser(self) -> bool:
        """Self-healing browser session check: revive if crashed or closed."""
        if self._context and self._page and not self._page.is_closed():
            try:
                _ = self._page.title()
                return True
            except Exception:
                pass
        logger.warning("Browser context lost or disconnected. Re-launching Chrome session...")
        self._close_browser()
        return self._init_browser()

    def _close_browser(self):
        """Safely close browser and teardown Playwright session strictly on worker thread."""
        try:
            if self._cdp:
                self._cdp.detach()
        except Exception:
            pass
        self._cdp = None

        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        self._context = None
        self._page = None

        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._pw = None

    def _apply_tranco_fallback(self, store: Dict[str, Any], clean_domain: str):
        """Tier 3 Fallback: Calibrated Tranco Zipf formula if Turnstile is unresolved."""
        store_id = store.get("store_id") or ""
        logger.warning(f"Tier 3 Fallback: Fetching Tranco rank for {clean_domain}...")
        rank, domain_status = fetch_domain_rank(clean_domain)

        if domain_status == "success" and rank and rank > 0:
            traffic_raw = rank_to_visits(rank)
            traffic_str = format_visits(traffic_raw)
            traffic_status = "success"
        elif domain_status == "error":
            traffic_raw = 0
            traffic_str = ""
            traffic_status = "error"
        else:
            traffic_raw = 0
            traffic_str = ""
            traffic_status = "no_data"

        db.update_store_traffic_cv(store_id, {
            "traffic_visits": traffic_str,
            "traffic_raw_value": traffic_raw,
            "traffic_status": traffic_status,
            "traffic_source": "tranco",
            "traffic_bounce_rate": "",
            "traffic_avg_duration": "",
            "traffic_global_rank": rank or 0,
            "traffic_country_rank": 0,
            "traffic_pages_per_visit": "",
        })

        self.tranco_fallbacks += 1
        self.scanned += 1
        if traffic_raw > 0:
            self.with_data += 1
        else:
            self.no_data += 1

    def _process_single_store(self, store: Dict[str, Any]) -> bool:
        """Enrich a single store record through the 3-Tier Traffic.cv pipeline."""
        self._apply_pending_window_bounds()

        store_id = store.get("store_id") or ""
        name = store.get("name") or "Unknown"
        website_url = store.get("website_url") or ""

        self.current_store = name
        domain = extract_domain(website_url)
        if not domain:
            domain = extract_domain(store.get("portal_url") or "")

        clean_domain = domain.strip().lower()
        clean_domain = re.sub(r"^https?://", "", clean_domain).rstrip("/")
        clean_domain = clean_domain.split("/")[0]

        self.current_domain = clean_domain

        if not clean_domain:
            # Store has no website or domain
            db.update_store_traffic_cv(store_id, {
                "traffic_visits": "",
                "traffic_raw_value": 0,
                "traffic_status": "no_data",
                "traffic_source": "traffic_cv",
                "traffic_bounce_rate": "",
                "traffic_avg_duration": "",
                "traffic_global_rank": 0,
                "traffic_country_rank": 0,
                "traffic_pages_per_visit": "",
            })
            self.no_data += 1
            self.scanned += 1
            return True

        target_url = f"https://traffic.cv/{clean_domain}"
        self.status_message = f"Đang tra cứu Similarweb: {clean_domain}"
        logger.info(f"Navigating to {target_url} for store {name}")

        try:
            self._page.goto(target_url, timeout=20000, wait_until="domcontentloaded")
        except Exception as e:
            logger.warning(f"Navigation timeout for {clean_domain}: {e}")
            pass

        # ------------------------------------------------------------------
        # Tier 1 Defense: Auto-pass check (Wait up to 4s for automatic pass)
        # ------------------------------------------------------------------
        is_cf = False
        for _ in range(4):
            if self._stop_event.is_set():
                return False
            self._apply_pending_window_bounds()
            if self._is_cloudflare_challenge():
                is_cf = True
                time.sleep(1.0)
            else:
                is_cf = False
                break

        # ------------------------------------------------------------------
        # Tier 2 Defense: Alert & Human Gate (Window to (100,100) + Sound + 90s)
        # ------------------------------------------------------------------
        if is_cf:
            logger.warning(f"Cloudflare Turnstile challenge active on {clean_domain}. Triggering Tier 2 Human Gate...")
            self.waiting_turnstile = True
            self.status_message = f"Cần giải Cloudflare Turnstile cho: {clean_domain}"
            self._set_window_bounds(on_screen=True)
            self._play_alert_sound()

            passed = False
            turnstile_timeout = 90
            start_wait = time.time()

            while (time.time() - start_wait) < turnstile_timeout:
                if self._stop_event.is_set():
                    self.waiting_turnstile = False
                    return False

                self._apply_pending_window_bounds()
                remaining = int(turnstile_timeout - (time.time() - start_wait))
                self.turnstile_remaining_sec = max(0, remaining)
                self.status_message = f"Đang chờ người dùng bấm giải Turnstile... còn {remaining}s"

                if not self._is_cloudflare_challenge():
                    logger.info("Cloudflare Turnstile passed successfully by user!")
                    passed = True
                    break
                time.sleep(1.0)

            self.waiting_turnstile = False
            self.turnstile_remaining_sec = 0

            if passed:
                self._set_window_bounds(on_screen=False)
                self.status_message = "Turnstile đã vượt qua! Đang bóc tách dữ liệu..."
                time.sleep(2.0)
            else:
                # ------------------------------------------------------------------
                # Tier 3 Defense: Smart Fallback to calibrated Tranco formula
                # ------------------------------------------------------------------
                logger.warning(f"Turnstile not solved within 90s for {clean_domain}. Activating Tier 3 Fallback to Tranco!")
                self._set_window_bounds(on_screen=False)
                self.status_message = f"Hết 90s: Áp dụng Tier 3 Tranco Fallback cho {clean_domain}"
                self._apply_tranco_fallback(store, clean_domain)
                return True

        # Extract page metrics from Traffic.cv
        time.sleep(1.5)
        self._apply_pending_window_bounds()
        try:
            body_text = self._page.inner_text("body")
        except Exception:
            body_text = ""

        parsed = parse_traffic_cv_text(body_text)

        if parsed["traffic_raw_value"] > 0 or parsed["global_rank"] > 0:
            db.update_store_traffic_cv(store_id, {
                "traffic_visits": parsed["total_visits_str"],
                "traffic_raw_value": parsed["traffic_raw_value"],
                "traffic_status": "success",
                "traffic_source": "traffic_cv",
                "traffic_bounce_rate": parsed["bounce_rate"],
                "traffic_avg_duration": parsed["avg_duration"],
                "traffic_global_rank": parsed["global_rank"],
                "traffic_country_rank": parsed["country_rank"],
                "traffic_pages_per_visit": parsed["pages_per_visit"],
            })
            self.with_data += 1
            logger.info(f"Enriched {clean_domain}: {parsed['total_visits_str']} visits, Rank #{parsed['global_rank']}")
        else:
            # Website has no Similarweb report (traffic < 5k)
            db.update_store_traffic_cv(store_id, {
                "traffic_visits": "",
                "traffic_raw_value": 0,
                "traffic_status": "no_data",
                "traffic_source": "traffic_cv",
                "traffic_bounce_rate": "",
                "traffic_avg_duration": "",
                "traffic_global_rank": 0,
                "traffic_country_rank": 0,
                "traffic_pages_per_visit": "",
            })
            self.no_data += 1
            logger.info(f"No Similarweb report for {clean_domain} (<5k visits)")

        self.scanned += 1
        return True

    def _run_loop(self):
        """Main background loop executing cleanly on its own thread."""
        logger.info("Traffic.cv worker loop initiated.")
        if not self._init_browser():
            self._is_running = False
            self.status_message = "Lỗi khởi động trình duyệt Chrome"
            return

        try:
            while not self._stop_event.is_set():
                self._apply_pending_window_bounds()

                if self._is_paused:
                    self.status_message = "Tạm dừng"
                    self._sleep_with_check(0.5)
                    continue

                if not self._ensure_browser():
                    logger.error("Failed to maintain browser session. Sleeping 5s before retry...")
                    self._sleep_with_check(5.0)
                    continue

                # Check if there is an on-demand priority store
                priority_store = None
                sid = None
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
                    try:
                        self._process_single_store(priority_store)
                    except Exception as e:
                        logger.error(f"Error on priority store {priority_store.get('name')}: {e}")
                        self.errors += 1
                    finally:
                        with self._lock:
                            if hasattr(self, "_priority_events") and sid and sid in self._priority_events:
                                self._priority_events[sid].set()
                    continue

                # Fetch stores prioritizing cookie_days >= 14, un-enriched by Traffic.cv or fallback
                stores = db.get_stores_for_traffic_cv_enrichment(
                    limit=30,
                    cookie_min_days=14,
                    exclude_store_ids=list(self._scanned_store_ids)[-200:] if self._scanned_store_ids else None
                )

                if not stores:
                    self.status_message = "Đã hoàn thành 100% toàn bộ store trong hệ thống!"
                    logger.info("All stores have been enriched with Similarweb! Stopping worker cleanly...")
                    break

                processed_in_batch = 0
                for store in stores:
                    if self._stop_event.is_set():
                        break

                    while self._is_paused and not self._stop_event.is_set():
                        self.status_message = "Tạm dừng"
                        self._sleep_with_check(0.5)

                    if self._stop_event.is_set():
                        break

                    store_id = store.get("store_id")
                    if store_id in self._scanned_store_ids:
                        continue
                    self._scanned_store_ids.add(store_id)
                    processed_in_batch += 1

                    try:
                        self._process_single_store(store)
                    except Exception as e:
                        logger.error(f"Error processing store {store.get('name')}: {e}")
                        self.errors += 1
                        # Save error status to prevent getting stuck
                        db.update_store_traffic_cv(store_id, {
                            "traffic_visits": "",
                            "traffic_raw_value": 0,
                            "traffic_status": "error",
                            "traffic_source": "traffic_cv_error"
                        })

                    # Polite 1.2s delay between store queries
                    if not self._stop_event.is_set():
                        self._sleep_with_check(1.2)

                # If all items in this batch were already in self._scanned_store_ids, wait politely
                if processed_in_batch == 0 and not self._stop_event.is_set():
                    self._sleep_with_check(2.0)

        except Exception as loop_err:
            logger.error(f"Traffic.cv worker loop error: {loop_err}", exc_info=True)
            self.status_message = f"Lỗi vòng lặp: {loop_err}"
        finally:
            self._close_browser()
            self._is_running = False
            self.waiting_turnstile = False
            self.current_store = ""
            self.current_domain = ""
            logger.info("Traffic.cv worker stopped cleanly.")


# Singleton instance
cv_worker = TrafficCVWorker()
