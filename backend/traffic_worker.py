import html
import json
import logging
import random
import re
import threading
import time
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse

import requests
from pytrends.request import TrendReq

from . import db

logger = logging.getLogger("TrafficWorker")
logging.basicConfig(level=logging.INFO)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


def extract_domain(url: str) -> str:
    """Extract clean domain name from URL."""
    if not url:
        return ""
    u = url.strip()
    if not u.startswith("http://") and not u.startswith("https://"):
        u = "https://" + u
    try:
        parsed = urlparse(u)
        host = (parsed.netloc or parsed.path).split("/")[0].split(":")[0].strip().lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def get_apex_domain(domain: str) -> str:
    """Extract apex/root domain if domain has common commerce subdomains."""
    parts = domain.lower().split(".")
    if len(parts) <= 2:
        return domain
    subdomain_prefixes = {
        "shop", "store", "app", "my", "us", "uk", "eu", "ca", "au",
        "fr", "de", "en", "m", "www", "checkout", "buy", "order", "portal"
    }
    if parts[0] in subdomain_prefixes:
        return ".".join(parts[1:])
    return domain

# In-memory cache for domain rankings to reduce API calls
_domain_rank_cache: Dict[str, Tuple[Optional[int], str]] = {}

# Google Trends cooldown timestamp to avoid spamming 429
_gt_cooldown_until: float = 0.0


def clean_brand_name(name: str, website_url: str = "") -> str:
    """Clean store name to create an effective query for Google Trends."""
    brand = html.unescape(name or "").strip()
    domain = extract_domain(website_url) if website_url else ""
    apex = get_apex_domain(domain) if domain else ""
    domain_stem = apex.split(".")[0] if apex else ""

    # If the name is an absolute URL or starts with http
    if brand.startswith("http://") or brand.startswith("https://") or "www." in brand:
        brand = domain_stem

    # Split on taglines/separators like ' - ', ' | ', ' : '
    for sep in [" - ", " | ", " : ", " – ", " — "]:
        if sep in brand:
            brand = brand.split(sep)[0].strip()
            break

    # Strip common trailing TLDs if present
    brand = re.sub(r"\.[a-z]{2,}(?:\.[a-z]{2,})?$", "", brand, flags=re.IGNORECASE)

    # Remove emojis and decorative icons (keep letters, digits, spaces, hyphens, apostrophes, &)
    brand = re.sub(r"[^\w\s\-\'’&]", " ", brand)
    brand = re.sub(r"\s+", " ", brand).strip()

    # Rule: If brand is too long (> 4 words) or looks like a slogan (e.g., "100% Plant Based..."),
    # fall back to domain_stem if domain is not a generic host (like myshopify.com)
    words = brand.split()
    generic_hosts = ["myshopify", "shopify", "wixsite", "wordpress", "hostingersite"]
    if len(words) > 4 and domain_stem and not any(h in domain for h in generic_hosts):
        brand = domain_stem

    # Rule: If brand is 1 word and domain has a compound brand (e.g. "Louis" + "louisskincare.com" -> "Louis Skincare")
    if len(words) == 1 and domain_stem and not any(h in domain for h in generic_hosts):
        if domain_stem.lower().startswith(brand.lower()) and len(domain_stem) > len(brand) + 2:
            remainder = domain_stem[len(brand):]
            brand = f"{brand} {remainder.capitalize()}"

    # If brand name is too generic or short, fallback to domain root
    if len(brand) < 2 and domain_stem:
        brand = domain_stem

    return brand.strip()


def _query_tranco(domain_to_check: str) -> Tuple[Optional[int], str]:
    """Single domain lookup on Tranco API with caching and retry on 429."""
    if domain_to_check in _domain_rank_cache:
        return _domain_rank_cache[domain_to_check]

    url = f"https://tranco-list.eu/api/ranks/domain/{domain_to_check}"
    ua = random.choice(USER_AGENTS)

    for attempt in range(2):
        try:
            resp = requests.get(
                url,
                timeout=8,
                headers={
                    "User-Agent": ua,
                    "Accept": "application/json",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                ranks = data.get("ranks", [])
                if ranks and len(ranks) > 0:
                    res = (int(ranks[0].get("rank")), "success")
                    _domain_rank_cache[domain_to_check] = res
                    return res
                res = (None, "no_data")
                _domain_rank_cache[domain_to_check] = res
                return res
            elif resp.status_code == 429:
                if attempt == 0:
                    time.sleep(2.0)
                    continue
                logger.warning(f"Tranco rate limit 429 for {domain_to_check}")
                return None, "error"
            elif resp.status_code == 404:
                res = (None, "no_data")
                _domain_rank_cache[domain_to_check] = res
                return res
            else:
                logger.warning(f"Tranco returned status {resp.status_code} for {domain_to_check}")
                return None, "error"
        except Exception as e:
            logger.warning(f"Domain rank lookup error for {domain_to_check}: {e}")
            return None, "error"

    return None, "error"


def fetch_domain_rank(domain: str) -> Tuple[Optional[int], str]:
    """
    Fetch global domain ranking from Tranco research dataset API.
    Returns (rank, status): status is 'success', 'no_data', or 'error'.
    STRICT: Network errors return 'error', not 'no_data'.
    """
    if not domain or len(domain) < 3:
        return None, "no_data"

    # Skip generic cloud, marketplaces, social platforms, and free hosting
    # These platforms have huge global traffic that does NOT belong to the individual affiliate store!
    generic_domains = [
        "hostingersite.com", "myshopify.com", "wixsite.com", "wordpress.com",
        "amazon.", "etsy.com", "ebay.", "walmart.com", "target.com",
        "aliexpress.com", "tiktok.com", "instagram.com", "facebook.com",
        "twitter.com", "x.com", "youtube.com", "pinterest.com",
        "linktr.ee", "beacons.ai", "campsite.bio"
    ]
    if any(h in domain for h in generic_domains):
        return None, "no_data"

    # Check given domain
    rank, status = _query_tranco(domain)
    if status == "success":
        return rank, "success"
    if status == "error":
        return None, "error"

    # If no data and domain has subdomain (e.g. shop.brand.com), check apex domain (brand.com)
    apex = get_apex_domain(domain)
    if apex != domain:
        time.sleep(1.2)
        rank_apex, status_apex = _query_tranco(apex)
        if status_apex == "success":
            return rank_apex, "success"
        if status_apex == "error":
            return None, "error"

    return None, "no_data"


def rank_to_visits(rank: int) -> int:
    """
    Zipf's Law web traffic estimation based on global domain rank.
    Rank 1: ~5B visits/mo
    Rank 10,000: ~790,000 visits/mo
    Rank 24,000 (Gymshark): ~340,000 visits/mo
    Rank 100,000: ~89,000 visits/mo
    Rank 500,000: ~19,000 visits/mo
    Rank 1,000,000: ~10,000 visits/mo
    """
    if not rank or rank <= 0:
        return 0

    try:
        visits = int(5.0e9 / (rank**0.95))
        if visits >= 1_000_000:
            return round(visits, -5)
        elif visits >= 100_000:
            return round(visits, -4)
        elif visits >= 10_000:
            return round(visits, -3)
        else:
            return round(visits, -2)
    except Exception:
        return 0


def format_visits(num: int) -> str:
    """Format traffic raw number into readable string."""
    if num >= 1_000_000:
        val = num / 1_000_000
        return f"{val:.1f}M".replace(".0M", "M")
    elif num >= 1_000:
        val = num / 1_000
        return f"{val:.1f}K".replace(".0K", "K")
    elif num > 0:
        return f"{num:,}"
    return ""


def fetch_google_trends(brand_name: str) -> Dict[str, Any]:
    """
    Fetch 5-year Google Trends search interest timeline for a brand.
    STRICT REQUIREMENT: NEVER FAKE OR INVENT NUMBERS.
    Returns status: 'success', 'no_data', or 'error'.
    """
    global _gt_cooldown_until

    if not brand_name or len(brand_name) < 2:
        return {"status": "no_data", "timeline": [], "peak_month": ""}

    # Check if Google Trends is currently in cooldown period due to 429
    now = time.time()
    if now < _gt_cooldown_until:
        rem = int(_gt_cooldown_until - now)
        return {
            "status": "pending",
            "cooldown": True,
            "error": f"rate_limited_cooldown ({rem}s)",
            "timeline": [],
            "peak_month": "",
        }

    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        # Note: retries must be 0 because urllib3 v2 removed method_whitelist which old pytrends uses
        pytrend = TrendReq(
            hl="en-US",
            tz=360,
            timeout=(10, 25),
            retries=0,
            requests_args={"headers": headers},
        )
        pytrend.build_payload(kw_list=[brand_name], timeframe="today 5-y")
        df = pytrend.interest_over_time()

        if df.empty or brand_name not in df.columns:
            return {"status": "no_data", "timeline": [], "peak_month": ""}

        # Count active non-zero weeks and total score
        non_zero_weeks = int((df[brand_name] > 0).sum())
        total_score = int(df[brand_name].sum())

        # STRICT RULE: A genuine search trend must have sustained interest over time.
        # If fewer than 6 active weeks across 5 years (262 weeks) or total score < 40,
        # it is isolated search noise. Mark as no_data to avoid misleading peak badges!
        if non_zero_weeks < 6 or total_score < 40:
            return {"status": "no_data", "timeline": [], "peak_month": ""}

        # Resample / group by month YYYY-MM
        df["month"] = df.index.strftime("%Y-%m")
        monthly = df.groupby("month")[brand_name].max().reset_index()

        # Count active calendar months with activity
        active_months = int((monthly[brand_name] > 0).sum())
        if active_months < 3:
            return {"status": "no_data", "timeline": [], "peak_month": ""}

        peak_idx = monthly[brand_name].idxmax()
        peak_row = monthly.iloc[peak_idx]
        peak_score = int(peak_row[brand_name])

        if peak_score < 5:
            return {"status": "no_data", "timeline": [], "peak_month": ""}

        peak_month = f"{peak_row['month']} ({peak_score} pts)"
        timeline = [
            {"month": r["month"], "value": int(r[brand_name])}
            for _, r in monthly.iterrows()
        ]

        return {
            "status": "success",
            "timeline": timeline,
            "peak_month": peak_month,
        }

    except Exception as e:
        err_msg = str(e).lower()
        if "429" in err_msg or "quota" in err_msg or "toomanyrequests" in err_msg:
            # Set 3-minute cooldown so we don't bombard Google
            _gt_cooldown_until = time.time() + 180.0
            logger.warning(f"Google Trends rate limited for '{brand_name}' -> cooling down 180s")
            return {"status": "error", "error": "rate_limited", "timeline": [], "peak_month": ""}
        logger.warning(f"Google Trends query failed for '{brand_name}': {e}")
        return {"status": "error", "error": str(e), "timeline": [], "peak_month": ""}


def enrich_store_data(store: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform real traffic & Google Trends enrichment for a single store record.
    Never invents numbers; returns real verified data or marks as 'no_data'.
    """
    global _gt_cooldown_until
    store_id = str(store.get("store_id") or "")
    name = str(store.get("name") or "")
    website_url = str(store.get("website_url") or "")

    domain = extract_domain(website_url)
    brand = clean_brand_name(name, website_url)

    # 1. Domain Traffic lookup
    traffic_raw = 0
    traffic_str = ""
    traffic_status = "no_data"

    if domain:
        rank, domain_status = fetch_domain_rank(domain)
        if domain_status == "success" and rank and rank > 0:
            traffic_raw = rank_to_visits(rank)
            traffic_str = format_visits(traffic_raw)
            traffic_status = "success"
        elif domain_status == "error":
            traffic_status = "error"
        else:
            traffic_status = "no_data"
    else:
        traffic_status = "no_data"

    # 2. Google Trends lookup
    now = time.time()
    existing_trend_status = store.get("trend_status") or "pending"
    existing_timeline_json = store.get("trend_timeline_json") or "[]"
    existing_peak = store.get("trend_peak_month") or ""

    if now < _gt_cooldown_until:
        # Currently in cooldown: keep pending status and do not query or mark as error
        trend_status = "pending" if existing_trend_status in ["", "error", "pending"] else existing_trend_status
        trend_timeline_json = existing_timeline_json
        trend_peak = existing_peak
    else:
        trend_res = fetch_google_trends(brand)
        t_status = trend_res.get("status", "no_data")
        if t_status == "success":
            trend_status = "success"
            trend_timeline = trend_res.get("timeline", [])
            trend_timeline_json = json.dumps(trend_timeline) if trend_timeline else "[]"
            trend_peak = trend_res.get("peak_month", "")
        elif t_status == "no_data":
            trend_status = "no_data"
            trend_timeline_json = "[]"
            trend_peak = ""
        elif t_status in ["pending", "cooldown"]:
            trend_status = "pending"
            trend_timeline_json = existing_timeline_json
            trend_peak = existing_peak
        else:
            trend_status = "error"
            trend_timeline_json = "[]"
            trend_peak = ""

    result = {
        "traffic_visits": traffic_str,
        "traffic_raw_value": traffic_raw,
        "traffic_status": traffic_status,
        "traffic_top_country": "Global",
        "trend_timeline_json": trend_timeline_json,
        "trend_peak_month": trend_peak,
        "trend_status": trend_status,
    }

    db.update_store_traffic_and_trends(store_id, result)
    return result


class TrafficWorker:
    """Background worker for enriching stores with traffic and Google Trends data."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._is_paused = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self.current_store = ""
        self.scanned = 0
        self.with_data = 0
        self.no_data = 0
        self.errors = 0

    def is_running(self) -> bool:
        return self._is_running

    def is_paused(self) -> bool:
        return self._is_paused

    def start(self) -> Dict[str, Any]:
        with self._lock:
            if self._is_running:
                if self._is_paused:
                    self._is_paused = False
                    return {"status": "resumed", "message": "Worker resumed"}
                return {"status": "already_running", "message": "Worker is already running"}

            self._is_running = True
            self._is_paused = False
            self._stop_event.clear()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            logger.info("Traffic & Google Trends background worker started.")
            return {"status": "started", "message": "Traffic background worker started"}

    def pause(self) -> Dict[str, Any]:
        with self._lock:
            if not self._is_running:
                return {"status": "not_running", "message": "Worker is not running"}
            self._is_paused = True
            return {"status": "paused", "message": "Worker paused"}

    def resume(self) -> Dict[str, Any]:
        with self._lock:
            if not self._is_running:
                return {"status": "not_running", "message": "Worker is not running"}
            self._is_paused = False
            return {"status": "resumed", "message": "Worker resumed"}

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            if not self._is_running:
                return {"status": "not_running", "message": "Worker is not running"}
            self._stop_event.set()
            self._is_paused = False
            logger.info("Stopping traffic background worker...")
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.5)
            self._is_running = False
            self.current_store = ""
            return {"status": "stopped", "message": "Traffic background worker stopped"}

    def get_status(self) -> Dict[str, Any]:
        global _gt_cooldown_until
        db_stats = db.get_traffic_stats()
        gt_cd = max(0, int(_gt_cooldown_until - time.time()))
        return {
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "current_store": self.current_store,
            "scanned": self.scanned,
            "with_data": db_stats.get("with_data", 0),
            "no_data": db_stats.get("no_data", 0),
            "errors": db_stats.get("errors", 0),
            "gt_cooldown_seconds": gt_cd,
            "remaining": db_stats.get("remaining_cookie_14_plus", 0),
            "total_cookie_14_plus": db_stats.get("total_cookie_14_plus", 0),
            "checked_cookie_14_plus": db_stats.get("checked_cookie_14_plus", 0),
            "above_10k": db_stats.get("above_10k", 0),
        }

    def _run_loop(self):
        try:
            while not self._stop_event.is_set():
                if self._is_paused:
                    self._stop_event.wait(0.5)
                    continue

                # Fetch stores prioritizing cookie_days >= 14
                stores = db.get_stores_for_traffic_enrichment(limit=25, cookie_min_days=14)
                if not stores:
                    # If all cookie >= 14 stores checked for traffic, check other stores
                    stores = db.get_stores_for_traffic_enrichment(limit=25, cookie_min_days=0)
                    if not stores:
                        # If all stores have traffic checked, check if Google Trends can be enriched for pending cookie >= 14 stores
                        if time.time() >= _gt_cooldown_until:
                            stores = db.get_stores_for_trend_enrichment(limit=25, cookie_min_days=14)
                        if not stores:
                            logger.info("All stores have been enriched with traffic data. Worker idle.")
                            break

                for store in stores:
                    if self._stop_event.is_set():
                        break

                    while self._is_paused and not self._stop_event.is_set():
                        self._stop_event.wait(0.5)

                    if self._stop_event.is_set():
                        break

                    store_name = store.get("name", "Unknown")
                    self.current_store = store_name

                    res = enrich_store_data(store)
                    self.scanned += 1

                    if res.get("traffic_status") == "success" or res.get("trend_status") == "success":
                        self.with_data += 1
                    elif res.get("traffic_status") == "error":
                        self.errors += 1
                        self._stop_event.wait(3.0)
                    elif res.get("trend_status") == "error":
                        self.errors += 1
                        self._stop_event.wait(3.0)
                    else:
                        self.no_data += 1

                    # Delay 2.5 to 4.0 seconds between stores to respect rate limits
                    delay = random.uniform(2.5, 4.0)
                    self._stop_event.wait(delay)

        except Exception as e:
            logger.error(f"Error in traffic worker loop: {e}", exc_info=True)
        finally:
            self._is_running = False
            self.current_store = ""
            logger.info("Traffic worker has stopped.")

    def refresh_single_store(self, store_id: str) -> Optional[Dict[str, Any]]:
        """Enrich or refresh a single store on demand."""
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stores WHERE store_id = ?", (store_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        store = dict(row)
        res = enrich_store_data(store)
        # Fetch updated store record
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stores WHERE store_id = ?", (store_id,))
        updated_row = cursor.fetchone()
        conn.close()

        return dict(updated_row) if updated_row else res


# Singleton instance
worker = TrafficWorker()
