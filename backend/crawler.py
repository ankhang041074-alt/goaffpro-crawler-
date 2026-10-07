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


def clean_profile_session():
    """
    Remove stale Chromium session restore files and mark exit_type as Normal.
    This guarantees Chromium will never restore old crashed tabs (like https://goaffpro.com/stores 404).
    """
    profile_dir = get_profile_dir()
    default_dir = profile_dir / "Default"
    sessions_dir = default_dir / "Sessions"
    if sessions_dir.exists():
        try:
            import shutil
            shutil.rmtree(sessions_dir, ignore_errors=True)
        except Exception:
            pass
    for fname in ["Current Session", "Current Tabs", "Last Session", "Last Tabs"]:
        fpath = default_dir / fname
        if fpath.exists():
            try:
                fpath.unlink(missing_ok=True)
            except Exception:
                pass
    pref_file = default_dir / "Preferences"
    if pref_file.exists():
        try:
            with open(pref_file, "r", encoding="utf-8") as f:
                pref = json.load(f)
            if "profile" in pref and isinstance(pref["profile"], dict):
                pref["profile"]["exit_type"] = "Normal"
                pref["profile"]["exited_cleanly"] = True
            if "session" in pref and isinstance(pref["session"], dict):
                pref["session"]["restore_on_startup"] = 5
            with open(pref_file, "w", encoding="utf-8") as f:
                json.dump(pref, f)
        except Exception:
            pass


# Global flag to signal login window to close gracefully
login_window_should_close = False
login_window_closed_event = threading.Event()
login_window_closed_event.set()

def _force_kill_browser_processes():
    import subprocess
    try:
        if os.name != 'nt':
            subprocess.run(["pkill", "-f", "browser_profile"], check=False)
        time.sleep(0.5)
    except Exception as e:
        print(f"Error killing existing browser: {e}")

def close_login_window_gracefully():
    global login_window_should_close
    if not login_window_closed_event.is_set():
        print("[Crawler] Signaling login window to close...")
        login_window_should_close = True
        login_window_closed_event.wait(timeout=10)
    _force_kill_browser_processes()


def open_login_window(url: str = "https://goaffpro.com/login") -> Dict[str, Any]:
    """
    Launch a persistent Chromium window for the user to manually log in to GoAffPro.
    Cookies and session tokens will be permanently saved to BROWSER_PROFILE_DIR.
    Never restores old 404 tabs or allows https://goaffpro.com/stores.
    """
    global login_window_should_close
    login_window_should_close = False
    login_window_closed_event.clear()

    # Sanitize URL: never allow 404 URL https://goaffpro.com/stores
    target_url = (url or "").strip()
    if not target_url or ("goaffpro.com/stores" in target_url.lower() and "affiliate" not in target_url.lower()):
        target_url = "https://goaffpro.com/login"

    # Clean stale session files to avoid reopening old 404 tabs
    clean_profile_session()
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
                        "--no-sandbox",
                        "--disable-session-crashed-bubble",
                        "--no-restore-session-state",
                        "--disable-features=InfiniteSessionRestore",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-infobars"
                    ]
                )
                # Close any extra restored tabs
                for p_extra in list(context.pages)[1:]:
                    try:
                        p_extra.close()
                    except Exception:
                        pass

                page = context.pages[0] if context.pages else context.new_page()
                page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                
                print(f"[GoAffPro Browser] Opened login browser at {target_url}. Preserving session in {profile_dir}")
                
                # Keep open until user closes browser window or signaled to close
                while len(context.pages) > 0 and not login_window_should_close:
                    time.sleep(1)
                    
                context.close()
        except Exception as e:
            print(f"[GoAffPro Browser] Error or closed: {e}")
        finally:
            login_window_closed_event.set()

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
    portal_url = item.get("portal_url") or item.get("affiliate_url") or item.get("signup_url") or item.get("affiliatePortal") or ""
    logo_url = item.get("logo") or item.get("icon") or item.get("logo_url") or item.get("image") or ""

    # Commission rate
    comm = item.get("commission") or item.get("commission_rate") or item.get("rate") or item.get("default_commission") or ""
    if isinstance(comm, dict):
        comm_amount = comm.get("amount") or comm.get("rate") or comm.get("value") or 0
        comm_type = str(comm.get("type", "percentage")).lower()
        if "percent" in comm_type:
            comm_str = f"{comm_amount}%"
            comm_val = float(comm_amount)
        else:
            comm_str = f"${comm_amount}"
            comm_val = float(comm_amount)
    elif isinstance(comm, (int, float)):
        comm_str = f"{comm}%"
        comm_val = float(comm)
    else:
        comm_str = str(comm).strip()
        comm_val = db.parse_commission_numeric(comm_str)

    # Cookie duration
    cookie_days = 30
    cookie_raw = item.get("cookieDuration") or item.get("cookie_duration") or item.get("cookie_days") or item.get("cookie_period") or 30
    try:
        raw_int = int(re.search(r"\d+", str(cookie_raw)).group())
        # If in seconds (e.g., 604800s -> 7 days)
        if raw_int > 1000:
            cookie_days = max(1, raw_int // 86400)
        else:
            cookie_days = raw_int
    except Exception:
        cookie_days = 30

    # Currency
    currency = item.get("currency") or item.get("payout_currency") or "USD"

    category = item.get("category") or item.get("niche") or item.get("industry") or "General"
    description = item.get("description") or item.get("about") or item.get("bio") or ""
    instant = item.get("areRegistrationsOpen") or item.get("isApprovedAutomatically") or item.get("auto_approve") or item.get("instant_access") or item.get("instant_join") or True

    return {
        "store_id": store_id,
        "name": name,
        "website_url": str(website_url),
        "portal_url": str(portal_url),
        "logo_url": str(logo_url),
        "currency": str(currency),
        "commission_rate": comm_str,
        "commission_value": comm_val,
        "cookie_days": cookie_days,
        "category": str(category),
        "description": str(description),
        "instant_access": bool(instant)
    }


def parse_dom_stores(page) -> List[Dict[str, Any]]:
    """Extract stores rendered directly in the GoAffPro DOM."""
    discovered = []
    try:
        cards_data = page.evaluate(r"""
            () => {
                const results = [];
                const allDivs = Array.from(document.querySelectorAll('div'));
                
                // Pick leaf-like containers that contain "Store ID:" and "Commission"
                const cards = allDivs.filter(el => {
                    const text = el.innerText || '';
                    return text.includes('Store ID:') && text.includes('Commission') && 
                           !Array.from(el.children).some(child => child.innerText && child.innerText.includes('Store ID:') && child.innerText.includes('Commission'));
                });

                cards.forEach(card => {
                    const text = card.innerText || '';
                    
                    // Store ID
                    const idMatch = text.match(/Store ID:\s*([0-9a-zA-Z_-]+)/i);
                    const storeId = idMatch ? idMatch[1] : '';

                    // Currency
                    const currMatch = text.match(/Currency\s*([A-Z]{3})/i);
                    const currency = currMatch ? currMatch[1].toUpperCase() : 'USD';

                    // Commission
                    const commMatch = text.match(/Commission\s*([0-9.]+\s*%?)/i);
                    const commission = commMatch ? commMatch[1] : '0%';

                    // Cookie Duration
                    const cookieMatch = text.match(/Cookie Duration\s*([0-9]+)\s*day/i);
                    const cookieDays = cookieMatch ? parseInt(cookieMatch[1]) : 30;

                    // Links and Name
                    const links = Array.from(card.querySelectorAll('a'));
                    let website = '';
                    for (const a of links) {
                        const href = a.href || '';
                        const aText = (a.innerText || '').trim();
                        if (aText && !aText.toLowerCase().includes('view program') && !aText.toLowerCase().includes('enroll')) {
                            if (!website && (href.startsWith('http') || aText.includes('.'))) {
                                website = aText.includes('.') ? aText : href;
                            }
                        }
                    }

                    // Logo
                    const img = card.querySelector('img');
                    const logo = img ? img.src : '';

                    // Name
                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                    const nonLabels = lines.filter(l => 
                        !l.includes('Store ID:') && 
                        !l.includes('Currency') && 
                        !l.includes('Commission') && 
                        !l.includes('Cookie Duration') &&
                        !l.includes('Registration Open') &&
                        !l.includes('Instant Access') &&
                        !l.includes('View program') &&
                        !l.includes('Enroll') &&
                        !l.includes('USD') &&
                        !l.includes('%')
                    );
                    
                    let name = nonLabels.length > 0 ? nonLabels[0] : '';
                    if (!website && nonLabels.length > 1 && nonLabels[1].includes('.')) {
                        website = nonLabels[1];
                    }

                    if (storeId || name) {
                        results.push({
                            store_id: storeId || name.toLowerCase().replace(/[^a-z0-9]/g, '_'),
                            name: name || ('Store ' + storeId),
                            website_url: website.startsWith('http') ? website : (website ? 'https://' + website : ''),
                            portal_url: website.startsWith('http') ? website : (website ? 'https://' + website : ''),
                            logo_url: logo,
                            currency: currency,
                            commission_rate: commission,
                            cookie_days: cookieDays,
                            description: text.slice(0, 300)
                        });
                    }
                });
                return results;
            }
        """)

        for c in cards_data:
            comm_rate = c.get("commission_rate", "0%")
            discovered.append({
                "store_id": c.get("store_id"),
                "name": c.get("name"),
                "website_url": c.get("website_url", ""),
                "portal_url": c.get("portal_url", ""),
                "logo_url": c.get("logo_url", ""),
                "currency": c.get("currency", "USD"),
                "commission_rate": comm_rate,
                "commission_value": db.parse_commission_numeric(comm_rate),
                "cookie_days": c.get("cookie_days", 30),
                "category": "General",
                "description": c.get("description", ""),
                "instant_access": True
            })
    except Exception as e:
        print(f"[DOM Scraper] Error extracting DOM elements: {e}")

    return discovered


def handle_cloudflare(page, db=None, job_id: Optional[str] = None):
    """Wait for manual Cloudflare challenge solving if encountered."""
    for _ in range(60):  # wait up to 2 minutes
        try:
            title = page.title().lower()
            content_start = page.content()[:1000].lower()
            if "just a moment" in title or "cloudflare" in title or "turnstile" in content_start:
                if db and job_id:
                    db.update_crawl_job(
                        job_id,
                        status="running",
                        message="Phát hiện Cloudflare! Vui lòng xác minh trên cửa sổ trình duyệt..."
                    )
                print("[Crawler] Cloudflare challenge detected, waiting for user verification...")
                time.sleep(2)
            else:
                break
        except Exception:
            break


def navigate_to_available_stores(page, db=None, job_id: Optional[str] = None, start_url: Optional[str] = None) -> bool:
    """
    Executes the required GoAffPro browser navigation flow:
    1. Go to https://goaffpro.com/login (or check if logged in via /main) and handle login / CF challenge.
    2. On dashboard selection screen ("Welcome back" / "Choose your dashboard"), click "I am an affiliate".
    3. Navigate to Stores / click "Stores" on the sidebar (it opens "My Stores").
    4. Click the "Available Stores" tab (which is at https://goaffpro.com/affiliate/stores/search or click tab Available Stores).
    5. Only then start scraping the stores from the "Available Stores" page.
    NEVER navigate to https://goaffpro.com/stores because it returns a 404 error!
    """
    # 0. Sanitize start URL: never allow 404 URL https://goaffpro.com/stores
    target_url = (start_url or "").strip()
    if not target_url or ("goaffpro.com/stores" in target_url.lower() and "affiliate" not in target_url.lower()):
        target_url = "https://goaffpro.com/login"

    if db and job_id:
        db.update_crawl_job(job_id, message=f"Đang mở trang bắt đầu: {target_url}...")

    print(f"[Crawler Flow] Step 1: Navigating to {target_url}...")
    page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    handle_cloudflare(page, db, job_id)

    # If already on Available Stores search page, we are ready!
    if "stores/search" in page.url.lower():
        print("[Crawler Flow] Already on Available Stores search page.")
        if db and job_id:
            db.update_crawl_job(job_id, message="Đã sẵn sàng trên trang Available Stores!")
        return True

    # If page landed on a 404 stores page from prior session, navigate away
    if "goaffpro.com/stores" in page.url.lower() and "affiliate" not in page.url.lower():
        print("[Crawler Flow] Currently on 404 stores URL, navigating to https://goaffpro.com/main...")
        page.goto("https://goaffpro.com/main", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

    # When target was login, check if user already has an active session by navigating to /main
    if "login" in target_url.lower() or "login" in page.url.lower():
        is_already_on_dash = False
        try:
            if page.locator("a[href='/affiliate']").is_visible(timeout=500) or page.locator("text=Available Stores").is_visible(timeout=500):
                is_already_on_dash = True
        except Exception:
            pass

        if not is_already_on_dash:
            try:
                page.goto("https://goaffpro.com/main", wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
                handle_cloudflare(page, db, job_id)
            except Exception:
                pass

    # Check if user needs to login
    def check_is_on_login():
        u = page.url.lower()
        if "login" in u or "sign_in" in u:
            return True
        try:
            if page.locator("input[type='password']").is_visible(timeout=500):
                return True
        except Exception:
            pass
        return False

    if check_is_on_login():
        if db and job_id:
            db.update_crawl_job(
                job_id,
                status="waiting_login",
                message="Cần đăng nhập tài khoản GoAffPro trước khi cào! Vui lòng đăng nhập trên cửa sổ trình duyệt..."
            )
        print("[Crawler Flow] Step 1: Waiting for user to complete login (up to 3 minutes)...")
        for _ in range(90):
            time.sleep(2)
            handle_cloudflare(page, db, job_id)
            if not check_is_on_login():
                break
            try:
                if (page.locator("a[href='/affiliate']").is_visible(timeout=500) or
                    page.locator("text=I am an affiliate").is_visible(timeout=500) or
                    page.locator("text=Available Stores").is_visible(timeout=500) or
                    page.locator("text=Stores").is_visible(timeout=500)):
                    break
            except Exception:
                pass

        if db and job_id:
            db.update_crawl_job(job_id, status="running", message="Đăng nhập thành công! Đang tiếp tục điều hướng...")
        page.wait_for_timeout(3000)

    # If already on Available Stores search page, we are ready!
    if "stores/search" in page.url.lower():
        print("[Crawler Flow] Already on Available Stores search page.")
        if db and job_id:
            db.update_crawl_job(job_id, message="Đã sẵn sàng trên trang Available Stores!")
        return True

    # Step 2: On dashboard selection screen ("Welcome back" / "Choose your dashboard"), click "I am an affiliate"
    if "affiliate" not in page.url.lower() or "goaffpro.com/main" in page.url.lower():
        print("[Crawler Flow] Step 2: Checking for 'I am an affiliate'...")
        if db and job_id:
            db.update_crawl_job(job_id, message="Đang kiểm tra và chọn 'I am an affiliate'...")

        affiliate_selectors = [
            "a[href='/affiliate']",
            "a[href*='/affiliate']:has-text('I am an affiliate')",
            "text=I am an affiliate",
            "a:has-text('I am an affiliate')",
            "button:has-text('I am an affiliate')",
            "div:has-text('I am an affiliate')",
            "[role='button']:has-text('I am an affiliate')",
            "text=Affiliate Portal",
        ]
        affiliate_clicked = False
        for sel in affiliate_selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1500):
                    print(f"[Crawler Flow] Step 2: Clicking affiliate option with selector: {sel}")
                    loc.click()
                    affiliate_clicked = True
                    page.wait_for_timeout(3000)
                    break
            except Exception:
                continue

        if affiliate_clicked:
            print(f"[Crawler Flow] Step 2 completed. Current URL: {page.url}")

    # Check if already on Available Stores
    if "stores/search" in page.url.lower():
        print("[Crawler Flow] Landed on Available Stores page after selecting affiliate.")
        return True

    # Step 3: Navigate to Stores / click "Stores" on sidebar (it opens "My Stores")
    if "affiliate/stores" not in page.url.lower():
        print("[Crawler Flow] Step 3: Navigating to Stores sidebar...")
        if db and job_id:
            db.update_crawl_job(job_id, message="Đang mở mục Stores trên thanh menu sidebar...")

        stores_clicked = False
        sidebar_selectors = [
            "a[href='/affiliate/stores']",
            "nav a:has-text('Stores')",
            "aside a:has-text('Stores')",
            ".sidebar a:has-text('Stores')",
            "a:has-text('Stores')",
            "button:has-text('Stores')",
            "[role='navigation'] a:has-text('Stores')",
            "text=Stores",
        ]
        for sel in sidebar_selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=2000):
                    print(f"[Crawler Flow] Step 3: Clicking sidebar Stores with selector: {sel}")
                    loc.click()
                    stores_clicked = True
                    page.wait_for_timeout(3000)
                    break
            except Exception:
                continue

        if not stores_clicked and "affiliate/stores" not in page.url.lower():
            print("[Crawler Flow] Step 3: Sidebar Stores not found or not clickable, navigating to https://goaffpro.com/affiliate/stores...")
            page.goto("https://goaffpro.com/affiliate/stores", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

    # Check if already on Available Stores
    if "stores/search" in page.url.lower():
        print("[Crawler Flow] Landed on Available Stores search page.")
        return True

    # Step 4: Click the "Available Stores" tab (which is at https://goaffpro.com/affiliate/stores/search or click tab Available Stores)
    print("[Crawler Flow] Step 4: Clicking 'Available Stores' tab...")
    if db and job_id:
        db.update_crawl_job(job_id, message="Đang chọn tab Available Stores...")

    available_clicked = False
    available_selectors = [
        "a[href='/affiliate/stores/search']",
        "a[href*='stores/search']",
        "a:has-text('Available Stores')",
        "button:has-text('Available Stores')",
        "[role='tab']:has-text('Available Stores')",
        "text=Available Stores",
        "a:has-text('Available')",
        "button:has-text('Available')",
    ]
    for sel in available_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                print(f"[Crawler Flow] Step 4: Clicking Available Stores tab with selector: {sel}")
                loc.click()
                available_clicked = True
                page.wait_for_timeout(3000)
                break
        except Exception:
            continue

    # Fallback if tab click didn't navigate
    if "stores/search" not in page.url.lower():
        print("[Crawler Flow] Step 4: Not yet on stores/search, navigating to https://goaffpro.com/affiliate/stores/search...")
        page.goto("https://goaffpro.com/affiliate/stores/search", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

    # Step 5: Ready to scrape
    print(f"[Crawler Flow] Step 5: Navigation complete! Current URL: {page.url}")
    if db and job_id:
        db.update_crawl_job(job_id, message="Đã vào trang Available Stores. Bắt đầu cào dữ liệu...")
    page.wait_for_timeout(2000)
    return True


def run_crawl_job(job_id: str, max_pages: int = 50, start_url: Optional[str] = None):
    """
    Main crawling worker. Navigates pages, intercepts API responses,
    parses DOM cards, and updates database continuously.
    """
    close_login_window_gracefully()
    clean_profile_session()
    profile_dir = get_profile_dir()
    db.update_crawl_job(job_id, status="running", message="Khởi động trình duyệt Playwright...")

    # Sanitize start_url to prevent 404
    if not start_url or ("goaffpro.com/stores" in start_url.lower() and "affiliate" not in start_url.lower()):
        target_url = "https://goaffpro.com/login"
    else:
        target_url = start_url.strip()

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,  # Headful so user can observe or solve unexpected challenges
                viewport={"width": 1280, "height": 850},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-session-crashed-bubble",
                    "--no-restore-session-state",
                    "--disable-features=InfiniteSessionRestore",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-infobars"
                ]
            )
            # Close any extra restored tabs
            for p_extra in list(context.pages)[1:]:
                try:
                    p_extra.close()
                except Exception:
                    pass

            page = context.pages[0] if context.pages else context.new_page()

            captured_api_stores: List[Dict[str, Any]] = []

            # Response listener: capture JSON responses containing store lists
            def handle_response(response):
                try:
                    ct = response.headers.get("content-type", "")
                    if "application/json" in ct:
                        # Check if URL seems related to stores, marketplace, or sites API
                        url_low = response.url.lower()
                        if any(k in url_low for k in ["store", "merchant", "marketplace", "program", "affiliate", "sites"]):
                            body = response.json()
                            items = []
                            if isinstance(body, list):
                                items = body
                            elif isinstance(body, dict):
                                items = body.get("stores") or body.get("sites") or body.get("data") or body.get("items") or body.get("results") or []
                            
                            if isinstance(items, list):
                                for item in items:
                                    parsed = parse_store_from_json(item)
                                    if parsed:
                                        captured_api_stores.append(parsed)
                except Exception:
                    pass

            page.on("response", handle_response)

            # Perform the exact 5-step navigation to Available Stores
            navigate_to_available_stores(page, db=db, job_id=job_id, start_url=target_url)

            total_saved = 0
            current_page = 1

            # Try to set items per page to 100
            try:
                # Find the correct select using Playwright locators to ensure React/Vue bindings trigger
                selects = page.locator("select").all()
                for select in selects:
                    options_text = select.inner_text().lower()
                    if "10" in options_text and "100" in options_text:
                        opts = select.locator("option").all()
                        for opt in opts:
                            if "100" in opt.inner_text():
                                val = opt.get_attribute("value")
                                if val:
                                    select.select_option(value=val)
                                else:
                                    select.select_option(label=opt.inner_text())
                                break
                        break
                print("[Crawler] Attempted to set 100 items per page natively.")
                page.wait_for_timeout(3000)
            except Exception as e:
                print(f"[Crawler] Failed to set 100 items per page: {e}")

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
                
                try:
                    # Strategy 1: Look for button/link/div with exact text "Next"
                    next_btn = page.locator('button:has-text("Next"), a:has-text("Next"), [role="button"]:has-text("Next"), .page-next, .pagination-next').last
                    if next_btn.is_visible(timeout=2000) and not next_btn.is_disabled():
                        next_btn.click()
                        next_clicked = True
                        page.wait_for_timeout(3000)
                    else:
                        # Strategy 2: Find any visible element with exact text Next
                        all_next = page.get_by_text("Next", exact=True).all()
                        for el in all_next:
                            if el.is_visible() and not el.is_disabled():
                                el.click()
                                next_clicked = True
                                page.wait_for_timeout(3000)
                                break
                except Exception as e:
                    print(f"[Crawler] Error clicking next button: {e}")

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
