import os
import sys
import json
import time
import re
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from . import db

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BROWSER_PROFILE_DIR = DATA_DIR / "browser_profile"

active_crawl_threads: Dict[str, threading.Thread] = {}
active_browsers: Dict[str, Any] = {}


def get_profile_dir() -> Path:
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return BROWSER_PROFILE_DIR


def open_login_window(url: str = "https://goaffpro.com/login") -> Dict[str, Any]:
    """
    Launch a persistent Chromium window for the user to manually log in to GoAffPro.
    Cookies and session tokens will be permanently saved to BROWSER_PROFILE_DIR.
    """
    profile_dir = get_profile_dir()

    def _run():
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    viewport={"width": 1280, "height": 850},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox"
                    ]
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                print(f"[GoAffPro Browser] Opened login browser at {url}. Preserving session in {profile_dir}")
                
                # Keep open until user closes browser window
                while len(context.pages) > 0:
                    time.sleep(1)
                context.close()
        except Exception as e:
            print(f"[GoAffPro Browser] Error or closed: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {
        "status": "opened",
        "profile_dir": str(profile_dir),
        "message": "Trình duyệt đã được mở. Hãy đăng nhập tài khoản GoAffPro của bạn và mở mục Stores / Available Stores!"
    }


def parse_store_from_json(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Helper to extract normalized store fields from varied GoAffPro API payloads."""
    if not isinstance(item, dict):
        return None

    name = item.get("name") or item.get("store_name") or item.get("title") or item.get("shop_name") or ""
    if not name or len(str(name).strip()) < 2:
        return None

    name = str(name).strip()
    store_id = str(item.get("id") or item.get("store_id") or item.get("handle") or name).strip().lower()

    website_url = item.get("website") or item.get("store_url") or item.get("url") or item.get("shop_url") or ""
    portal_url = item.get("portal_url") or item.get("affiliate_url") or item.get("signup_url") or ""
    logo_url = item.get("logo") or item.get("icon") or item.get("logo_url") or item.get("image") or ""

    # Commission rate
    comm = item.get("commission") or item.get("commission_rate") or item.get("rate") or item.get("default_commission") or ""
    if isinstance(comm, (int, float)):
        comm_str = f"{comm}%"
        comm_val = float(comm)
    else:
        comm_str = str(comm).strip()
        comm_val = db.parse_commission_numeric(comm_str)

    # Cookie duration
    cookie_days = 30
    cookie_raw = item.get("cookie_duration") or item.get("cookie_days") or item.get("cookie_period") or 30
    try:
        cookie_days = int(re.search(r"\d+", str(cookie_raw)).group())
    except Exception:
        cookie_days = 30

    category = item.get("category") or item.get("niche") or item.get("industry") or "General"
    description = item.get("description") or item.get("about") or item.get("bio") or ""
    instant = item.get("auto_approve") or item.get("instant_access") or item.get("instant_join") or True

    return {
        "store_id": store_id,
        "name": name,
        "website_url": str(website_url),
        "portal_url": str(portal_url),
        "logo_url": str(logo_url),
        "commission_rate": comm_str,
        "commission_value": comm_val,
        "cookie_days": cookie_days,
        "category": str(category),
        "description": str(description),
        "instant_access": bool(instant)
    }


def parse_dom_stores(page) -> List[Dict[str, Any]]:
    """Fallback: extract stores rendered directly in the DOM / HTML cards."""
    discovered = []
    try:
        # Evaluate in page context to grab all store cards/items
        cards_data = page.evaluate("""
            () => {
                const results = [];
                // Look for cards, list items, or table rows
                const cardSelectors = [
                    '.store-card', '.merchant-card', '[data-testid="store-item"]',
                    '.marketplace-item', '.card', '.list-group-item', 'tr.store-row'
                ];
                let elements = [];
                for (const sel of cardSelectors) {
                    const found = document.querySelectorAll(sel);
                    if (found && found.length > 2) {
                        elements = Array.from(found);
                        break;
                    }
                }
                
                // Fallback: look for generic containers with links and commission keywords
                if (elements.length === 0) {
                    const allDivs = document.querySelectorAll('div, tr');
                    elements = Array.from(allDivs).filter(el => {
                        const text = el.innerText || '';
                        return (text.includes('%') || text.includes('commission') || text.includes('Cookie')) && el.querySelector('a');
                    }).slice(0, 50);
                }

                elements.forEach(el => {
                    const text = el.innerText || '';
                    const titleEl = el.querySelector('h1, h2, h3, h4, h5, .title, .name, strong, b');
                    const linkEl = el.querySelector('a[href]');
                    const imgEl = el.querySelector('img');

                    const name = titleEl ? titleEl.innerText.trim() : (linkEl ? linkEl.innerText.trim() : '');
                    const link = linkEl ? linkEl.href : '';
                    const logo = imgEl ? imgEl.src : '';

                    if (name && name.length > 2 && !name.toLowerCase().includes('stores') && !name.toLowerCase().includes('filter')) {
                        results.push({
                            name: name,
                            text: text,
                            link: link,
                            logo: logo
                        });
                    }
                });
                return results;
            }
        """)

        for c in cards_data:
            c_text = c.get("text", "")
            name = c.get("name", "")
            
            # Find commission in card text
            comm_match = re.search(r"(\d+(?:\.\d+)?\s*%\s*(?:commission|per sale|rev share)?)", c_text, re.IGNORECASE)
            comm_rate = comm_match.group(1) if comm_match else "10%"
            
            # Find cookie days in text
            cookie_match = re.search(r"(\d+)\s*(?:day|days)\s*cookie", c_text, re.IGNORECASE)
            cookie_days = int(cookie_match.group(1)) if cookie_match else 30

            # Find category if present
            cat_match = re.search(r"(?:Category|Niche):\s*([A-Za-z\s&]+)", c_text, re.IGNORECASE)
            category = cat_match.group(1).strip() if cat_match else "General"

            discovered.append({
                "store_id": name.lower().replace(" ", "_"),
                "name": name,
                "website_url": c.get("link", ""),
                "portal_url": c.get("link", ""),
                "logo_url": c.get("logo", ""),
                "commission_rate": comm_rate,
                "commission_value": db.parse_commission_numeric(comm_rate),
                "cookie_days": cookie_days,
                "category": category,
                "description": c_text[:200],
                "instant_access": True
            })
    except Exception as e:
        print(f"[DOM Scraper] Error extracting DOM elements: {e}")

    return discovered


def run_crawl_job(job_id: str, max_pages: int = 50, start_url: Optional[str] = None):
    """
    Main crawling worker. Navigates pages, intercepts API responses,
    parses DOM cards, and updates database continuously.
    """
    profile_dir = get_profile_dir()
    db.update_crawl_job(job_id, status="running", message="Khởi động trình duyệt Playwright...")

    target_url = start_url or "https://goaffpro.com/stores"

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,  # Headful so user can observe or solve unexpected challenges
                viewport={"width": 1280, "height": 850},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox"
                ]
            )
            page = context.pages[0] if context.pages else context.new_page()

            captured_api_stores: List[Dict[str, Any]] = []

            # Response listener: capture JSON responses containing store lists
            def handle_response(response):
                try:
                    ct = response.headers.get("content-type", "")
                    if "application/json" in ct:
                        # Check if URL seems related to stores or marketplace
                        url_low = response.url.lower()
                        if any(k in url_low for k in ["store", "merchant", "marketplace", "program", "affiliate"]):
                            body = response.json()
                            items = []
                            if isinstance(body, list):
                                items = body
                            elif isinstance(body, dict):
                                items = body.get("stores") or body.get("data") or body.get("items") or body.get("results") or []
                            
                            if isinstance(items, list):
                                for item in items:
                                    parsed = parse_store_from_json(item)
                                    if parsed:
                                        captured_api_stores.append(parsed)
                except Exception:
                    pass

            page.on("response", handle_response)

            db.update_crawl_job(job_id, message=f"Đang điều hướng đến {target_url}...")
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # Check if redirected to login page
            current_url = page.url.lower()
            if "login" in current_url or "sign_in" in current_url:
                db.update_crawl_job(
                    job_id,
                    status="waiting_login",
                    message="Cần đăng nhập tài khoản GoAffPro trước khi cào! Vui lòng đăng nhập trên cửa sổ trình duyệt..."
                )
                # Wait up to 3 minutes for user to log in
                for _ in range(90):
                    time.sleep(2)
                    if "login" not in page.url.lower() and "sign_in" not in page.url.lower():
                        break

            total_saved = 0
            current_page = 1

            while current_page <= max_pages:
                db.update_crawl_job(
                    job_id,
                    current_page=current_page,
                    total_pages=max_pages,
                    message=f"Đang cào dữ liệu trang {current_page}..."
                )

                # Scroll smoothly to trigger lazy-load images & stores
                for i in range(3):
                    page.mouse.wheel(0, 1000)
                    page.wait_for_timeout(1000)

                # Extract from intercepted API + fallback DOM
                dom_stores = parse_dom_stores(page)
                batch = captured_api_stores + dom_stores

                if batch:
                    # Deduplicate in batch
                    unique_batch = {}
                    for s in batch:
                        sid = s["store_id"]
                        if sid not in unique_batch:
                            unique_batch[sid] = s
                    
                    saved_count = db.save_stores_batch(list(unique_batch.values()))
                    total_saved += saved_count
                    captured_api_stores.clear()

                    db.update_crawl_job(
                        job_id,
                        total_stores=total_saved,
                        message=f"Đã cào xong trang {current_page}, thu thập {total_saved} stores..."
                    )

                # Check if there is a 'Next' button or pagination
                next_clicked = False
                next_selectors = [
                    'button:has-text("Next")', 'button:has-text("Sau")',
                    'a:has-text("Next")', 'a:has-text("Sau")',
                    '[aria-label="Next"]', '.pagination-next', '.page-next'
                ]
                for n_sel in next_selectors:
                    try:
                        next_btn = page.query_selector(n_sel)
                        if next_btn and next_btn.is_visible() and not next_btn.is_disabled():
                            next_btn.click()
                            next_clicked = True
                            page.wait_for_timeout(3000)
                            break
                    except Exception:
                        pass

                if not next_clicked:
                    # Check for page number button (e.g. current_page + 1)
                    try:
                        page_btn = page.query_selector(f'button:has-text("{current_page + 1}"), a:has-text("{current_page + 1}")')
                        if page_btn and page_btn.is_visible():
                            page_btn.click()
                            next_clicked = True
                            page.wait_for_timeout(3000)
                    except Exception:
                        pass

                if not next_clicked:
                    print(f"[GoAffPro Crawler] Reached end of pagination at page {current_page}")
                    break

                current_page += 1

            db.update_crawl_job(
                job_id,
                status="completed",
                current_page=current_page,
                total_stores=total_saved,
                message=f"Hoàn thành xuất sắc! Đã cào được {total_saved} stores từ GoAffPro."
            )
            context.close()
    except Exception as e:
        print(f"[GoAffPro Crawler] Error during job {job_id}: {e}")
        db.update_crawl_job(
            job_id,
            status="failed",
            message=f"Lỗi khi cào dữ liệu: {str(e)}"
        )


def start_background_crawl(job_id: str, max_pages: int = 50, start_url: Optional[str] = None):
    """Spawn crawl job in a separate daemon thread."""
    t = threading.Thread(target=run_crawl_job, args=(job_id, max_pages, start_url), daemon=True)
    active_crawl_threads[job_id] = t
    t.start()
    return job_id
