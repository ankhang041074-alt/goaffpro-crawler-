"""
traffic_cv_scraper.py - High-precision Playwright scraper for Traffic.cv (Similarweb traffic data).
Supports automatic Cloudflare Turnstile bypass with Google Chrome persistent profile,
clean metric extraction (Visits, Global Rank, Country Rank, Bounce Rate, Duration),
batch scraping with single persistent browser session, and Tranco Zipf fallback.
"""

import os
import re
import json
import time
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Callable

from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BROWSER_PROFILE_DIR = DATA_DIR / "chrome_profile_traffic_cv"

logger = logging.getLogger("TrafficCVScraper")
logging.basicConfig(level=logging.INFO)

_browser_lock = threading.Lock()
verification_window_closed = threading.Event()
verification_should_close = False


def get_profile_dir() -> Path:
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return BROWSER_PROFILE_DIR


def parse_traffic_number(traffic_text: str) -> Tuple[int, str]:
    """
    Parses traffic text like '204.37K', '1.5M', '301.38K', '45,000', '< 5,000', '< 5K' into (raw_int, formatted_str).
    """
    if not traffic_text or not isinstance(traffic_text, str):
        return 0, ""

    clean = traffic_text.strip().replace(",", "")
    if clean in ["0", "–", "-", "n/a", "none"]:
        return 0, ""

    # Similarweb displays '< 5,000' or '< 5K' for domains with small traffic
    if "<" in clean:
        m_small = re.search(r"<\s*([\d\.]+)\s*([KMBkmb])?", clean)
        if m_small:
            try:
                num = float(m_small.group(1))
                unit = (m_small.group(2) or "").upper()
                if unit == "K":
                    raw = int(num * 500)  # midpoint for <5K is ~2500
                elif not unit and num <= 5000:
                    raw = int(num / 2)
                else:
                    raw = int(num)
                formatted = f"< {m_small.group(1)}{unit}" if unit else f"< {int(num):,}"
                return max(1, raw), formatted
            except ValueError:
                return 2500, "< 5K"
        return 2500, "< 5K"

    m = re.search(r"([\d\.]+)\s*([KMBkmb])?", clean)
    if not m:
        return 0, ""

    try:
        num_val = float(m.group(1))
    except ValueError:
        return 0, ""

    unit = (m.group(2) or "").upper()

    if unit == "M":
        raw = int(num_val * 1_000_000)
    elif unit == "B":
        raw = int(num_val * 1_000_000_000)
    elif unit == "K":
        raw = int(num_val * 1_000)
    else:
        raw = int(num_val)

    formatted = f"{num_val:.2f}{unit}".rstrip("0").rstrip(".") if unit else f"{raw:,}"
    return raw, formatted


def _extract_rank_num(text_line: str) -> int:
    """Extract integer rank value stripping '#', commas, and whitespace."""
    if not text_line:
        return 0
    clean = re.sub(r"[#,\s]", "", text_line)
    return int(clean) if clean.isdigit() else 0


def parse_traffic_cv_text(text: str) -> Dict[str, Any]:
    """
    Parse innerText of a traffic.cv report page into structured metrics.
    Structured layout from traffic.cv:
      [Rank Number]
      GLOBAL RANK
      [Rank Number]
      COUNTRY RANK
      TOTAL VISITS
      [Visits e.g. 204.37K or 0]
      AVG. DURATION
      [Duration e.g. 00:01:36]
      PAGES PER VISIT
      [Pages e.g. 3.16]
      BOUNCE RATE
      [Rate e.g. 38.66%]
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    data = {
        "total_visits_str": "",
        "traffic_raw_value": 0,
        "global_rank": 0,
        "country_rank": 0,
        "bounce_rate": "",
        "avg_duration": "",
        "pages_per_visit": "",
        "has_report": False,
    }

    for i, line in enumerate(lines):
        upper = line.upper()

        if upper == "TRAFFIC REPORT":
            data["has_report"] = True

        elif upper == "TOTAL VISITS" and i + 1 < len(lines):
            raw_v_text = lines[i + 1]
            raw_val, formatted_val = parse_traffic_number(raw_v_text)
            data["total_visits_str"] = formatted_val
            data["traffic_raw_value"] = raw_val

        elif upper == "GLOBAL RANK":
            # Check previous line first, then next line to support all DOM layouts
            rank = 0
            if i - 1 >= 0:
                rank = _extract_rank_num(lines[i - 1])
            if rank == 0 and i + 1 < len(lines):
                rank = _extract_rank_num(lines[i + 1])
            data["global_rank"] = rank

        elif upper == "COUNTRY RANK":
            rank = 0
            if i - 1 >= 0:
                rank = _extract_rank_num(lines[i - 1])
            if rank == 0 and i + 1 < len(lines):
                rank = _extract_rank_num(lines[i + 1])
            data["country_rank"] = rank

        elif upper == "BOUNCE RATE" and i + 1 < len(lines):
            data["bounce_rate"] = lines[i + 1]

        elif upper in ["AVG. DURATION", "AVG DURATION"] and i + 1 < len(lines):
            data["avg_duration"] = lines[i + 1]

        elif upper == "PAGES PER VISIT" and i + 1 < len(lines):
            data["pages_per_visit"] = lines[i + 1]

    return data


def open_traffic_cv_verification_window(target_url: str = "https://traffic.cv/www.makeblock.com") -> Dict[str, Any]:
    """
    Opens a Google Chrome browser window using the persistent profile
    so the user can pass Cloudflare Turnstile once. Cookies are permanently saved to disk.
    """
    global verification_should_close, verification_window_closed
    profile_dir = get_profile_dir()
    verification_should_close = False
    verification_window_closed.clear()

    def _run():
        global verification_window_closed
        try:
            with sync_playwright() as p:
                launch_kwargs = {
                    "user_data_dir": str(profile_dir),
                    "headless": False,
                    "ignore_default_args": ["--enable-automation"],
                    "viewport": {"width": 1280, "height": 850},
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-session-crashed-bubble",
                        "--no-restore-session-state",
                        "--disable-infobars"
                    ]
                }
                # Use real installed Google Chrome on macOS if available
                if Path("/Applications/Google Chrome.app").exists():
                    launch_kwargs["channel"] = "chrome"

                context = p.chromium.launch_persistent_context(**launch_kwargs)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
                logger.info(f"Opened Traffic.cv verification window at {target_url}")

                while len(context.pages) > 0 and not verification_should_close:
                    time.sleep(1)

                context.close()
        except Exception as e:
            logger.error(f"Error in Traffic.cv verification window: {e}")
        finally:
            verification_window_closed.set()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {
        "status": "opened",
        "message": "Cửa sổ trình duyệt Traffic.cv đã được mở. Hãy kiểm tra xác nhận Cloudflare Turnstile để lưu phiên!",
        "target_url": target_url
    }


def _extract_page_metrics(page, domain: str) -> Dict[str, Any]:
    """Helper to extract metrics from an active Playwright page."""
    # Check title for Cloudflare Turnstile challenge
    for _ in range(6):
        title = page.title()
        if "chờ" not in title.lower() and "moment" not in title.lower() and "just a moment" not in title.lower():
            break
        time.sleep(1.0)

    title = page.title()
    if "chờ" in title.lower() or "moment" in title.lower():
        return {
            "status": "cf_blocked",
            "domain": domain,
            "message": "Cloudflare Turnstile challenge active. Cần bấm mở xác minh 1 lần!"
        }

    # Retrieve page text
    try:
        text = page.inner_text("body")
    except Exception:
        text = ""

    parsed = parse_traffic_cv_text(text)

    # Check for empty / no data cases
    if parsed["traffic_raw_value"] == 0 and parsed["global_rank"] == 0:
        return {
            "status": "no_data",
            "domain": domain,
            "traffic_visits": "",
            "traffic_raw_value": 0,
            "global_rank": 0,
            "country_rank": 0,
            "bounce_rate": "",
            "avg_duration": "",
            "pages_per_visit": "",
            "message": "Website nhỏ hoặc mới lập, chưa có lưu lượng truy cập đủ ngưỡng Similarweb (<5K visits)"
        }

    return {
        "status": "success",
        "domain": domain,
        "traffic_visits": parsed["total_visits_str"],
        "traffic_raw_value": parsed["traffic_raw_value"],
        "global_rank": parsed["global_rank"],
        "country_rank": parsed["country_rank"],
        "bounce_rate": parsed["bounce_rate"],
        "avg_duration": parsed["avg_duration"],
        "pages_per_visit": parsed["pages_per_visit"]
    }


def scrape_traffic_cv(domain: str, timeout_sec: int = 15) -> Dict[str, Any]:
    """
    Scrapes a single domain from traffic.cv using the persistent Playwright profile.
    """
    clean_domain = domain.strip().lower()
    clean_domain = re.sub(r"^https?://", "", clean_domain).rstrip("/")
    clean_domain = clean_domain.split("/")[0]

    profile_dir = get_profile_dir()
    target_url = f"https://traffic.cv/{clean_domain}"

    with _browser_lock:
        try:
            with sync_playwright() as p:
                launch_kwargs = {
                    "user_data_dir": str(profile_dir),
                    "headless": False,
                    "ignore_default_args": ["--enable-automation"],
                    "viewport": {"width": 1280, "height": 800},
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--window-position=0,0",
                        "--window-size=1280,800"
                    ]
                }
                if Path("/Applications/Google Chrome.app").exists():
                    launch_kwargs["channel"] = "chrome"

                context = p.chromium.launch_persistent_context(**launch_kwargs)
                page = context.pages[0] if context.pages else context.new_page()

                try:
                    page.goto(target_url, timeout=timeout_sec * 1000, wait_until="domcontentloaded")
                except Exception as e:
                    context.close()
                    return {"status": "error", "domain": clean_domain, "error": f"Navigation timeout: {e}"}

                time.sleep(2.0)
                res = _extract_page_metrics(page, clean_domain)
                context.close()
                return res

        except Exception as e:
            return {"status": "error", "domain": clean_domain, "error": str(e)}


def scrape_traffic_cv_batch(
    domains: List[str],
    timeout_sec: int = 15,
    delay_sec: float = 1.2,
    on_progress: Optional[Callable[[int, int, Dict[str, Any]], None]] = None
) -> List[Dict[str, Any]]:
    """
    High-efficiency batch scraper: opens a SINGLE persistent browser context
    and processes all domains sequentially, saving time and keeping Turnstile session warm.
    """
    profile_dir = get_profile_dir()
    results = []

    with _browser_lock:
        try:
            with sync_playwright() as p:
                launch_kwargs = {
                    "user_data_dir": str(profile_dir),
                    "headless": False,
                    "ignore_default_args": ["--enable-automation"],
                    "viewport": {"width": 1280, "height": 800},
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--window-position=0,0",
                        "--window-size=1280,800"
                    ]
                }
                if Path("/Applications/Google Chrome.app").exists():
                    launch_kwargs["channel"] = "chrome"

                context = p.chromium.launch_persistent_context(**launch_kwargs)
                page = context.pages[0] if context.pages else context.new_page()

                total = len(domains)
                for idx, domain in enumerate(domains):
                    clean_domain = domain.strip().lower()
                    clean_domain = re.sub(r"^https?://", "", clean_domain).rstrip("/")
                    clean_domain = clean_domain.split("/")[0]

                    target_url = f"https://traffic.cv/{clean_domain}"
                    logger.info(f"[{idx+1}/{total}] Scraping Traffic.cv for: {clean_domain}")

                    try:
                        page.goto(target_url, timeout=timeout_sec * 1000, wait_until="domcontentloaded")
                        time.sleep(2.0)
                        item_res = _extract_page_metrics(page, clean_domain)
                    except Exception as e:
                        item_res = {"status": "error", "domain": clean_domain, "error": str(e)}

                    results.append(item_res)

                    if on_progress:
                        try:
                            on_progress(idx + 1, total, item_res)
                        except Exception:
                            pass

                    # Small delay between stores
                    if idx < total - 1:
                        time.sleep(delay_sec)

                context.close()
        except Exception as e:
            logger.error(f"Batch scraper encountered error: {e}")

    return results
