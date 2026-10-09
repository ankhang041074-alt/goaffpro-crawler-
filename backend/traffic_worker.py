import html
import json
import logging
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import quote, urlparse
import urllib.request

import requests
try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

from pytrends.request import TrendReq

from . import db
from .categorizer import extract_meta_tags, classify_store

logger = logging.getLogger("TrafficWorker")
logging.basicConfig(level=logging.INFO)

EXPANDED_USER_AGENTS = [
    # macOS Chrome
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Windows Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # macOS Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Windows Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.2478.80",
    # iOS Safari (iPad / iPhone)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    # Linux Chrome
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]
USER_AGENTS = EXPANDED_USER_AGENTS


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

# Google Trends cooldown timestamp and backoff counter
_gt_cooldown_until: float = 0.0
_gt_consecutive_429: int = 0
TRENDS_COOKIE_FILE: Path = Path(__file__).resolve().parent.parent / "data" / "trends_cookies.json"


# VPN is completely disabled per user preference for network stability and zero interruption
ENABLE_VPN = False


def find_expressvpn_bin() -> Optional[str]:
    """VPN disabled: always returns None."""
    return None


logger.info("⚡ Chế độ trực tiếp: Đã TẮT hoàn toàn VPN. Tool chạy trực tiếp bằng mạng máy tính mượt mà, không lo bị đơ hay gián đoạn mạng.")


def rotate_vpn_region() -> bool:
    """VPN rotation is completely disabled."""
    return False



def clean_brand_name(name: str, website_url: str = "", site_title: str = "") -> str:
    """Clean store name to create an effective query for Google Trends."""
    brand = html.unescape(name or "").strip()
    domain = extract_domain(website_url) if website_url else ""
    apex = get_apex_domain(domain) if domain else ""
    domain_stem = apex.split(".")[0] if apex else ""

    # If the name is an absolute URL or starts with http or is raw domain stem
    if brand.startswith("http://") or brand.startswith("https://") or "www." in brand or (domain_stem and brand.lower().replace(" ", "") == domain_stem.lower()):
        # Try extracting human brand name from site_title if available
        extracted_from_title = ""
        if site_title:
            for sep in [" – ", " - ", " | ", " — "]:
                if sep in site_title:
                    parts = [p.strip() for p in site_title.split(sep) if p.strip()]
                    for p in [parts[-1], parts[0]]:
                        clean_p = p.replace(" ", "").lower()
                        if domain_stem and (domain_stem in clean_p or clean_p in domain_stem) and len(p.split()) <= 4:
                            extracted_from_title = p
                            break
                if extracted_from_title:
                    break
        brand = extracted_from_title if extracted_from_title else domain_stem

    # If brand contains the apex domain (e.g. HALOorodje.si ...), strip TLD or reduce to domain stem
    if apex and apex.lower() in brand.lower():
        brand = re.sub(re.escape(apex), domain_stem, brand, flags=re.IGNORECASE)

    # Split on taglines/separators like ' - ', ' | ', ' : '
    for sep in [" - ", " | ", " : ", " – ", " — "]:
        if sep in brand:
            brand = brand.split(sep)[0].strip()
            break

    # Strip common trailing TLDs if present
    brand = re.sub(r"\.[a-z]{2,}(?:\.[a-z]{2,})?$", "", brand, flags=re.IGNORECASE)

    # Strip common international store descriptors (e.g. 'spletna trgovina', 'online store', 'webshop')
    intnl_store_stops = [
        r"\bspletna\s+trgovina\b", r"\bonline\s+store\b", r"\bofficial\s+store\b",
        r"\bweb\s*shop\b", r"\be-?shop\b", r"\btrgovina\b", r"\bboutique\b"
    ]
    for stop_pattern in intnl_store_stops:
        brand = re.sub(stop_pattern, "", brand, flags=re.IGNORECASE).strip()

    # Strip country code and platform suffixes with hyphen/underscore like -UK, -US, -DE, -EU, -CA, -FR, -ES, -IT, -AU, -NL, -store, -shop
    brand = re.sub(r"[-_](?:uk|us|de|eu|ca|fr|es|it|au|nl|jp|kr|br|vn|store|shop|online|official)$", "", brand, flags=re.IGNORECASE)
    # Strip affiliate words like "Affiliate", "Affiliates"
    brand = re.sub(r"\baffiliates?\b", "", brand, flags=re.IGNORECASE).strip()

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
    # But DO NOT append common generic additions like cases, kits, store, shop, etc.
    compound_stops = {"cases", "kits", "store", "shop", "online", "gear", "direct", "apparel", "wear", "supply", "supplies"}
    if len(words) == 1 and domain_stem and not any(h in domain for h in generic_hosts):
        if domain_stem.lower().startswith(brand.lower()) and len(domain_stem) > len(brand) + 2:
            remainder = domain_stem[len(brand):].lower()
            if remainder not in compound_stops:
                brand = f"{brand} {remainder.capitalize()}"
                words = brand.split()

    suffixes = {
        "australia", "usa", "us", "uk", "canada", "ca", "france", "fr", "germany", "de",
        "eu", "es", "it", "nl", "jp", "kr", "in", "official", "store", "shop", "online",
        "club", "co", "website", "global", "international", "inc", "llc", "ltd", "corp",
        "app", "io", "com"
    }
    if len(words) >= 2 and words[-1].lower() in suffixes and domain_stem:
        if domain_stem.lower().startswith(words[0].lower()):
            brand = " ".join(words[:-1])
            words = brand.split()

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
        "linktr.ee", "beacons.ai", "campsite.bio", "bit.ly", "tinyurl.com",
        "payhip.com", "digistore24.com", "gumroad.com", "wed2c.com",
        "clickbank.net", "stan.store", "stan.me"
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
    Zipf's Law web traffic estimation based on global domain rank,
    calibrated to Similarweb / Traffic.cv visits scale.
    Rank 10,000: ~2.5M visits/mo
    Rank 24,000 (Gymshark): ~1.1M visits/mo
    Rank 100,000: ~285,000 visits/mo
    Rank 142,511 (Makeblock): ~204,000 visits/mo (Traffic.cv: 204.37K)
    Rank 500,000: ~62,000 visits/mo
    Rank 1,000,000: ~32,000 visits/mo
    """
    if not rank or rank <= 0:
        return 0

    try:
        visits = int(1.6e10 / (rank**0.95))
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


class GoogleTrendsSessionManager:
    """
    Manages resilient HTTP session for Google Trends API requests.
    Supports curl_cffi with HTTP/2 and Chrome 124 TLS/JA3 impersonation as primary engine,
    with persistent disk-based cookie caching (trends_cookies.json) and automatic session recycling.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._cffi_session: Optional[Any] = None
        self._session: Optional[requests.Session] = None
        self._user_agent: str = random.choice(EXPANDED_USER_AGENTS)
        self._request_count: int = 0
        self._last_warmup_time: float = 0.0

    def get_cffi_session(self) -> Optional[Any]:
        if not HAS_CURL_CFFI:
            return None
        with self._lock:
            if self._cffi_session is None:
                self._init_cffi_session_locked()
            self._request_count += 1
            return self._cffi_session

    def get_session(self) -> requests.Session:
        with self._lock:
            if self._session is None:
                self._init_session_locked()
            self._request_count += 1
            return self._session

    def recycle_session(self):
        with self._lock:
            self._init_cffi_session_locked(force_new=True)
            if self._session is not None:
                try:
                    self._session.close()
                except Exception:
                    pass
                self._session = None

    def save_cookies(self):
        with self._lock:
            self._save_cookies_locked()

    def _save_cookies_locked(self):
        try:
            c_dict = {}
            if self._cffi_session is not None:
                for k, v in self._cffi_session.cookies.items():
                    c_dict[k] = v
            elif self._session is not None:
                c_dict = self._session.cookies.get_dict()
            if c_dict:
                TRENDS_COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(TRENDS_COOKIE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"updated_at": time.time(), "cookies": c_dict}, f)
        except Exception as e:
            logger.debug(f"Could not persist trends cookies: {e}")

    def _load_cached_cookies_dict(self) -> Dict[str, str]:
        try:
            if TRENDS_COOKIE_FILE.exists():
                with open(TRENDS_COOKIE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Valid if less than 180 days old (Google NID cookies are valid for 6 months)
                if time.time() - data.get("updated_at", 0) < 180 * 86400:
                    c = data.get("cookies", {})
                    if c and "NID" in c:
                        return c
        except Exception as e:
            logger.debug(f"Could not load cached trends cookies: {e}")
        return {}

    def _init_cffi_session_locked(self, force_new: bool = False):
        if not HAS_CURL_CFFI:
            return
        if self._cffi_session is not None:
            try:
                self._cffi_session.close()
            except Exception:
                pass

        self._user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        self._cffi_session = cffi_requests.Session(impersonate="chrome124")
        self._cffi_session.headers.update({
            "User-Agent": self._user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Referer": "https://trends.google.com/trends/explore",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        })
        self._cffi_session.cookies.set("SOCS", "CAESHAgCEhJnd3NfMjAyNDA1MjgtMF9SQzEaAmVuIAEaBgiA_L20Bg", domain=".google.com")
        self._cffi_session.cookies.set("CONSENT", "PENDING+999", domain=".google.com")

        cached = self._load_cached_cookies_dict()
        if cached and not force_new:
            for k, v in cached.items():
                self._cffi_session.cookies.set(k, v, domain=".google.com")
            logger.info(f"Loaded {len(cached)} cached Google Trends cookies into curl_cffi session.")
        
        # Warm up with landing page to guarantee live NID cookies
        try:
            r_warm = self._cffi_session.get("https://trends.google.com/", timeout=6)
            if r_warm.status_code == 200:
                self._save_cookies_locked()
                logger.info("curl_cffi session warmed up successfully with live Google cookies.")
        except Exception as e:
            logger.debug(f"curl_cffi warmup notice: {e}")

    def _load_cached_cookies_locked(self) -> bool:
        try:
            cached = self._load_cached_cookies_dict()
            if cached and self._session is not None:
                for k, v in cached.items():
                    self._session.cookies.set(k, v, domain=".google.com")
                logger.info(f"Loaded {len(cached)} cached Google Trends cookies from disk.")
                return True
        except Exception as e:
            logger.debug(f"Could not load cached trends cookies: {e}")
        return False

    def _init_session_locked(self, force_new: bool = False):
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass

        self._session = requests.Session()
        self._request_count = 0
        self._user_agent = random.choice(EXPANDED_USER_AGENTS)

        # Standard modern browser headers
        self._session.headers.update({
            "User-Agent": self._user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://trends.google.com/trends/explore",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        })

        # Pre-seed consent cookies across Google domain
        self._session.cookies.set("SOCS", "CAESHAgCEhJnd3NfMjAyNDA1MjgtMF9SQzEaAmVuIAEaBgiA_L20Bg", domain=".google.com")
        self._session.cookies.set("CONSENT", "PENDING+999", domain=".google.com")

        # Attempt to load persistent cookies if not forcing a clean reset
        if not force_new:
            self._load_cached_cookies_locked()

        # Warm up session by visiting Google Trends landing page to acquire or refresh live cookies
        try:
            resp = self._session.get(
                "https://trends.google.com/",
                headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                timeout=(3.0, 5.0),
            )
            if resp.status_code == 200:
                self._last_warmup_time = time.time()
                self._save_cookies_locked()
                logger.info("Google Trends session warmed up successfully with live cookies.")
            elif resp.status_code == 429:
                logger.warning("Google Trends landing page returned 429 during session warmup.")
        except Exception as e:
            logger.warning(f"Google Trends session warmup notice: {e}")


trends_session_mgr = GoogleTrendsSessionManager()


class OptimizedTrendReq(TrendReq):
    """
    Subclass of pytrends TrendReq that leverages our persistent, recycled Google session
    with live NID/SOCS cookies and browser headers, avoiding recreating unauthenticated sessions.
    """

    def __init__(self, session_mgr: GoogleTrendsSessionManager, hl="en-US", tz=360, timeout=(10, 25)):
        self.session_mgr = session_mgr
        self.managed_session = self.session_mgr.get_session()
        super().__init__(
            hl=hl,
            tz=tz,
            timeout=timeout,
            retries=0,
            requests_args={"headers": {"User-Agent": self.managed_session.headers.get("User-Agent", "")}},
        )

    def GetGoogleCookie(self) -> Dict[str, str]:
        # Return cookies from our managed pre-warmed session
        return dict(self.managed_session.cookies)

    def _get_data(self, url, method=TrendReq.GET_METHOD, trim_chars=0, **kwargs):
        s = self.managed_session
        # Do not override session's live cookie jar with static snapshot
        if method == TrendReq.POST_METHOD:
            response = s.post(url, timeout=self.timeout, **kwargs, **self.requests_args)
        else:
            response = s.get(url, timeout=self.timeout, **kwargs, **self.requests_args)

        if response.status_code == 200 and any(
            t in response.headers.get("Content-Type", "")
            for t in ["application/json", "application/javascript", "text/javascript"]
        ):
            content = response.text[trim_chars:].strip()
            self.session_mgr.save_cookies()
            return json.loads(content)
        elif response.status_code == 429:
            from pytrends.exceptions import TooManyRequestsError
            raise TooManyRequestsError.from_response(response)
        else:
            from pytrends.exceptions import ResponseError
            raise ResponseError.from_response(response)


def _handle_gt_429_cooldown(brand_name: str) -> Dict[str, Any]:
    """Helper to register 429 cooldown with exponential backoff and randomized jitter."""
    global _gt_consecutive_429, _gt_cooldown_until
    _gt_consecutive_429 += 1
    # Smooth adaptive backoff: 1st ~18-24s, 2nd ~30-36s, 3rd ~50-60s, max 120s
    base_cooldown = min(120.0, 18.0 * (1.6 ** min(_gt_consecutive_429 - 1, 3)))
    cooldown_time = base_cooldown + random.uniform(2.0, 5.0)
    _gt_cooldown_until = time.time() + cooldown_time
    trends_session_mgr.recycle_session()
    logger.info(
        f"⏳ Google Trends chạm ngưỡng 429 cho '{brand_name}' (lần {_gt_consecutive_429}). Tự động giãn cách {int(cooldown_time)}s riêng cho Trends. "
        f"Traffic Tranco và bóc tách Website tiếp tục chạy 100% bằng mạng bình thường."
    )
    return {
        "status": "pending",
        "cooldown": True,
        "error": "rate_limited_cooldown",
        "timeline": [],
        "peak_month": ""
    }


def fetch_google_trends_direct(brand_name: str) -> Optional[Dict[str, Any]]:
    """
    Direct Google Trends API query using curl_cffi with HTTP/2 and Chrome 124 TLS/JA3 impersonation.
    STRICT ZERO-FAKE-DATA POLICY: 100% genuine data or marked as no_data.
    Returns Dict result if handled, or None if fallback to pytrends is desired.
    """
    global _gt_consecutive_429

    s = trends_session_mgr.get_cffi_session()
    if s is None:
        return None

    referer = f"https://trends.google.com/trends/explore?geo=&q={quote(brand_name)}"
    req_headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": None,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Referer": referer,
    }

    # Step 1: Explore API with encoded comparisonItem (POST method required by Google)
    req_param = json.dumps({
        "comparisonItem": [{"keyword": brand_name, "time": "today 5-y", "geo": ""}],
        "category": 0,
        "property": ""
    })
    explore_url = "https://trends.google.com/trends/api/explore"
    explore_params = {"hl": "en-US", "tz": 360, "req": req_param}

    r1 = None
    for attempt in range(2):
        try:
            r1 = s.get(explore_url, params=explore_params, headers=req_headers, timeout=12)
            if r1.status_code == 429 and attempt == 0:
                trends_session_mgr.recycle_session()
                s = trends_session_mgr.get_cffi_session()
                time.sleep(1.0)
                continue
            break
        except Exception as e:
            if attempt == 0:
                time.sleep(1.0)
                continue
            logger.warning(f"curl_cffi explore request failed for '{brand_name}': {e}")
            return None

    if r1 is None or r1.status_code == 429:
        logger.info(f"curl_cffi explore returned 429 for '{brand_name}', falling back to pytrends")
        return None

    if r1.status_code != 200:
        logger.warning(f"Google Trends explore returned status {r1.status_code} for '{brand_name}'")
        return None

    text = r1.text
    if text.startswith(")]}',\n") or text.startswith(")]}'"):
        text = text[text.find("{"):]
    try:
        data = json.loads(text)
    except Exception as e:
        logger.warning(f"Failed to parse explore JSON for '{brand_name}': {e}")
        return None

    token = None
    w_req = None
    for w in data.get("widgets", []):
        if w.get("id") == "TIMESERIES":
            token = w.get("token")
            w_req = json.dumps(w.get("request"))
            break

    if not token or not w_req:
        return {"status": "no_data", "timeline": [], "peak_month": ""}

    # Step 2: Widget Multiline API
    multi_url = "https://trends.google.com/trends/api/widgetdata/multiline"
    multi_params = {"hl": "en-US", "tz": 360, "req": w_req, "token": token}

    r2 = None
    for attempt in range(2):
        try:
            r2 = s.get(multi_url, params=multi_params, headers=req_headers, timeout=12)
            if r2.status_code == 429 and attempt == 0:
                time.sleep(1.5)
                continue
            break
        except Exception as e:
            if attempt == 0:
                time.sleep(1.0)
                continue
            logger.warning(f"curl_cffi multiline request failed for '{brand_name}': {e}")
            return None

    if r2 is None or r2.status_code == 429:
        logger.info(f"curl_cffi multiline returned 429 for '{brand_name}', falling back to pytrends")
        return None

    if r2.status_code != 200:
        logger.warning(f"Google Trends multiline returned status {r2.status_code} for '{brand_name}'")
        return None

    m_text = r2.text
    if m_text.startswith(")]}',\n") or m_text.startswith(")]}'"):
        m_text = m_text[m_text.find("{"):]
    try:
        m_data = json.loads(m_text)
    except Exception as e:
        logger.warning(f"Failed to parse multiline JSON for '{brand_name}': {e}")
        return None

    points = m_data.get("default", {}).get("timelineData", [])
    if not points:
        return {"status": "no_data", "timeline": [], "peak_month": ""}

    # Successful response! Save session cookies to disk and reset 429 counter
    trends_session_mgr.save_cookies()
    _gt_consecutive_429 = 0

    # Step 3: Validate and aggregate genuine 5-year trend
    non_zero_weeks = 0
    total_score = 0
    monthly_max = defaultdict(int)

    for p in points:
        vals = p.get("value", [])
        raw_val = vals[0] if vals else 0
        if isinstance(raw_val, str) and "<" in raw_val:
            val = 0
        else:
            try:
                val = int(raw_val)
            except (ValueError, TypeError):
                val = 0

        if val > 0:
            non_zero_weeks += 1
            total_score += val
        t = int(p.get("time", 0))
        m = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m")
        if val > monthly_max[m]:
            monthly_max[m] = val

    # STRICT RULE: A genuine search trend must have sustained interest over time.
    # If fewer than 6 active weeks across 5 years (262 weeks) or total score < 40,
    # it is isolated search noise. Mark as no_data to avoid misleading peak badges!
    if non_zero_weeks < 6 or total_score < 40:
        return {"status": "no_data", "timeline": [], "peak_month": ""}

    active_months = sum(1 for v in monthly_max.values() if v > 0)
    if active_months < 3:
        return {"status": "no_data", "timeline": [], "peak_month": ""}

    timeline = [{"month": m, "value": monthly_max[m]} for m in sorted(monthly_max.keys())]
    peak_item = max(timeline, key=lambda x: x["value"])
    peak_score = peak_item["value"]

    if peak_score < 5:
        return {"status": "no_data", "timeline": [], "peak_month": ""}

    peak_month = f"{peak_item['month']} ({peak_score} pts)"
    is_steady = db.calculate_is_steady_trend(timeline)

    return {
        "status": "success",
        "timeline": timeline,
        "peak_month": peak_month,
        "is_steady": is_steady,
    }


def fetch_google_trends(brand_name: str, bypass_cooldown: bool = False) -> Dict[str, Any]:
    """
    Fetch 5-year Google Trends search interest timeline for a brand.
    STRICT REQUIREMENT: NEVER FAKE OR INVENT NUMBERS.
    Uses ultra-fast curl_cffi HTTP/2 Chrome TLS impersonation direct to Google Explore & Multiline APIs,
    with automatic fallback to pytrends.
    Returns status: 'success', 'no_data', or 'error'.
    """
    global _gt_cooldown_until, _gt_consecutive_429

    if not brand_name or len(brand_name) < 2:
        return {"status": "no_data", "timeline": [], "peak_month": ""}

    # Check if Google Trends is currently in cooldown period due to 429
    now = time.time()
    if now < _gt_cooldown_until and not bypass_cooldown:
        rem = int(_gt_cooldown_until - now)
        return {
            "status": "pending",
            "cooldown": True,
            "error": f"rate_limited_cooldown ({rem}s)",
            "timeline": [],
            "peak_month": "",
        }

    # 1. Primary Engine: Ultra-fast curl_cffi with HTTP/2 and Chrome 124 TLS/JA3 impersonation
    if HAS_CURL_CFFI:
        try:
            direct_res = fetch_google_trends_direct(brand_name)
            if direct_res is not None:
                return direct_res
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "quota" in err_msg or "toomanyrequests" in err_msg:
                return _handle_gt_429_cooldown(brand_name)
            logger.warning(f"curl_cffi direct failed for '{brand_name}', falling back to pytrends: {e}")

    # 2. Resilient Fallback: Optimized pytrends TrendReq
    try:
        pytrend = OptimizedTrendReq(
            session_mgr=trends_session_mgr,
            hl="en-US",
            tz=360,
            timeout=(10, 25),
        )
        pytrend.build_payload(kw_list=[brand_name], timeframe="today 5-y")
        df = pytrend.interest_over_time()

        # Success! Reset consecutive 429 counter
        _gt_consecutive_429 = 0

        if df.empty or brand_name not in df.columns:
            return {"status": "no_data", "timeline": [], "peak_month": ""}

        # Count active non-zero weeks and total score
        non_zero_weeks = int((df[brand_name] > 0).sum())
        total_score = int(df[brand_name].sum())

        if non_zero_weeks < 6 or total_score < 40:
            return {"status": "no_data", "timeline": [], "peak_month": ""}

        # Resample / group by month YYYY-MM
        df["month"] = df.index.strftime("%Y-%m")
        monthly = df.groupby("month")[brand_name].max().reset_index()

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
        is_steady = db.calculate_is_steady_trend(timeline)

        return {
            "status": "success",
            "timeline": timeline,
            "peak_month": peak_month,
            "is_steady": is_steady,
        }

    except Exception as e:
        err_msg = str(e).lower()
        if "429" in err_msg or "quota" in err_msg or "toomanyrequests" in err_msg:
            return _handle_gt_429_cooldown(brand_name)
        logger.warning(f"Google Trends query failed for '{brand_name}': {e}")
        return {"status": "error", "error": str(e), "timeline": [], "peak_month": ""}


def fetch_website_metadata(website_url: str) -> Tuple[str, str, str]:
    """Fetch website HTML header (up to 40KB) and extract title, description, and keywords."""
    if not website_url or not website_url.startswith("http"):
        return "", "", ""
    try:
        req = urllib.request.Request(
            website_url,
            headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            chunk = resp.read(40000).decode("utf-8", errors="ignore")
            return extract_meta_tags(chunk)
    except Exception:
        return "", "", ""


def enrich_store_data(
    store: Dict[str, Any],
    require_min_traffic_for_trends: int = 10000,
    force_refresh_traffic: bool = False,
    use_traffic_cv: bool = False
) -> Dict[str, Any]:
    """
    Perform real traffic & Google Trends enrichment for a single store record.
    Never invents numbers; returns real verified data or marks as 'no_data'.
    Prioritizes Google Trends queries for stores with traffic >= require_min_traffic_for_trends.
    Supports high-precision Similarweb extraction via traffic.cv with Tranco Zipf fallback.
    """
    global _gt_cooldown_until
    store_id = str(store.get("store_id") or "")
    name = str(store.get("name") or "")
    website_url = str(store.get("website_url") or "")

    domain = extract_domain(website_url)
    if not domain:
        domain = extract_domain(str(store.get("portal_url") or ""))
    brand = clean_brand_name(name, website_url, str(store.get("site_title") or ""))

    # 1. Domain Traffic lookup
    existing_traffic_status = str(store.get("traffic_status") or "no_data")
    existing_traffic_raw = int(store.get("traffic_raw_value") or 0)

    traffic_raw = existing_traffic_raw
    traffic_str = str(store.get("traffic_visits") or "")
    traffic_status = existing_traffic_status
    traffic_source = str(store.get("traffic_source") or "")
    traffic_bounce_rate = str(store.get("traffic_bounce_rate") or "")
    traffic_avg_duration = str(store.get("traffic_avg_duration") or "")
    traffic_global_rank = int(store.get("traffic_global_rank") or 0)
    traffic_country_rank = int(store.get("traffic_country_rank") or 0)
    traffic_pages_per_visit = str(store.get("traffic_pages_per_visit") or "")

    # If requested, attempt Similarweb direct extraction from traffic.cv first
    if use_traffic_cv and domain:
        try:
            from . import traffic_cv_scraper
            cv_res = traffic_cv_scraper.scrape_traffic_cv(domain)
            if cv_res.get("status") == "success":
                traffic_raw = cv_res.get("traffic_raw_value", 0)
                traffic_str = cv_res.get("traffic_visits", "")
                traffic_status = "success"
                traffic_source = "traffic_cv"
                traffic_bounce_rate = cv_res.get("bounce_rate", "")
                traffic_avg_duration = cv_res.get("avg_duration", "")
                traffic_global_rank = cv_res.get("global_rank", 0)
                traffic_country_rank = cv_res.get("country_rank", 0)
                traffic_pages_per_visit = cv_res.get("pages_per_visit", "")
            elif cv_res.get("status") == "no_data":
                traffic_raw = 0
                traffic_str = ""
                traffic_status = "no_data"
                traffic_source = "traffic_cv"
                traffic_bounce_rate = ""
                traffic_avg_duration = ""
                traffic_global_rank = 0
                traffic_country_rank = 0
                traffic_pages_per_visit = ""
        except Exception as e:
            logger.warning(f"traffic_cv lookup error for {domain}: {e}")

    # Fallback to Tranco if traffic_status is not success and not traffic_cv
    if traffic_status != "success" and traffic_source != "traffic_cv":
        if not force_refresh_traffic and existing_traffic_status in ["success", "no_data"] and existing_traffic_raw > 0:
            traffic_raw = existing_traffic_raw
            traffic_str = str(store.get("traffic_visits") or format_visits(traffic_raw))
            traffic_status = str(existing_traffic_status)
        elif domain:
            rank, domain_status = fetch_domain_rank(domain)
            if domain_status == "success" and rank and rank > 0:
                traffic_raw = rank_to_visits(rank)
                traffic_str = format_visits(traffic_raw)
                traffic_status = "success"
                traffic_source = "tranco"
            elif domain_status == "error":
                traffic_status = "error"
                traffic_raw = 0
                traffic_str = ""
            else:
                traffic_status = "no_data"
                traffic_raw = 0
                traffic_str = ""
        else:
            traffic_status = "no_data"
            traffic_raw = 0
            traffic_str = ""

    # 2. Google Trends lookup (Always active when force_refresh_traffic is True)
    now = time.time()
    existing_trend_status = store.get("trend_status") or "pending"
    existing_timeline_json = store.get("trend_timeline_json") or "[]"
    existing_peak = store.get("trend_peak_month") or ""
    existing_is_steady = int(store.get("trend_is_steady") or 0)

    # Always initialize trend variables with safe defaults so no branch raises UnboundLocalError
    trend_status = existing_trend_status
    trend_timeline_json = existing_timeline_json
    trend_peak = existing_peak
    trend_is_steady = existing_is_steady
    trends_queried = False

    should_query_trends = True
    if not force_refresh_traffic:
        if require_min_traffic_for_trends > 0 and traffic_raw < require_min_traffic_for_trends:
            should_query_trends = False

    if not brand:
        trend_status = "no_data"
        trend_timeline_json = "[]"
        trend_peak = ""
        trend_is_steady = 0
    elif not should_query_trends:
        # Keep existing trend data if already succeeded, otherwise leave pending to save rate-limit quota
        trend_status = existing_trend_status if existing_trend_status == "success" else "pending"
        trend_timeline_json = existing_timeline_json
        trend_peak = existing_peak
        trend_is_steady = existing_is_steady
    elif now < _gt_cooldown_until and not force_refresh_traffic:
        # Currently in cooldown: keep pending status during background crawl
        trend_status = "pending" if existing_trend_status in ["", "error", "pending"] else existing_trend_status
        trend_timeline_json = existing_timeline_json
        trend_peak = existing_peak
        trend_is_steady = existing_is_steady
    else:
        trends_queried = True
        trend_res = fetch_google_trends(brand, bypass_cooldown=force_refresh_traffic)
        t_status = trend_res.get("status", "no_data")
        if t_status == "success":
            trend_status = "success"
            trend_timeline = trend_res.get("timeline", [])
            trend_timeline_json = json.dumps(trend_timeline) if trend_timeline else "[]"
            trend_peak = trend_res.get("peak_month", "")
            trend_is_steady = 1 if trend_res.get("is_steady", False) else 0
        elif t_status == "no_data":
            trend_status = "no_data"
            trend_timeline_json = "[]"
            trend_peak = ""
            trend_is_steady = 0
        elif t_status in ["pending", "cooldown"]:
            trend_status = "pending"
            trend_timeline_json = existing_timeline_json
            trend_peak = existing_peak
            trend_is_steady = existing_is_steady
        else:
            trend_status = "error"
            trend_timeline_json = "[]"
            trend_peak = ""
            trend_is_steady = 0

    result = {
        "traffic_visits": traffic_str,
        "traffic_raw_value": traffic_raw,
        "traffic_status": traffic_status,
        "traffic_top_country": "Global",
        "traffic_source": traffic_source,
        "traffic_bounce_rate": traffic_bounce_rate,
        "traffic_avg_duration": traffic_avg_duration,
        "traffic_global_rank": traffic_global_rank,
        "traffic_country_rank": traffic_country_rank,
        "traffic_pages_per_visit": traffic_pages_per_visit,
        "trend_timeline_json": trend_timeline_json,
        "trend_peak_month": trend_peak,
        "trend_status": trend_status,
        "trend_is_steady": trend_is_steady,
        "trends_queried": trends_queried,
    }

    db.update_store_traffic_and_trends(store_id, result)

    # 3. Intelligent Website Categorization (Multi-Niche & 18+ Handling)
    existing_cat = str(store.get("category") or "General")
    existing_site_desc = str(store.get("site_description") or "")
    if existing_cat == "General" or not existing_site_desc:
        t, d, k = fetch_website_metadata(website_url)
        cat_result = classify_store(title=t, description=d, keywords=k, name=name, url=website_url)
        db.update_store_categorization(
            store_id=store_id,
            primary_category=cat_result["primary_category"],
            categories_json=json.dumps(cat_result["categories"]),
            site_title=cat_result["site_title"],
            site_description=cat_result["site_description"],
            is_adult=cat_result["is_adult"]
        )

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
            "trend_checked_cookie_14": db_stats.get("trend_checked_cookie_14", 0),
            "trend_10k_done": db_stats.get("trend_10k_done", 0),
            "total_stores": db_stats.get("total_stores", 0),
            "total_traffic_checked": db_stats.get("total_traffic_checked", 0),
            "above_10k": db_stats.get("above_10k", 0),
            "vpn_available": False,
            "vpn_enabled": False,
        }

    def _run_loop(self):
        try:
            while not self._stop_event.is_set():
                if self._is_paused:
                    self._stop_event.wait(0.5)
                    continue

                stores = []
                is_low_traffic_trend_phase = False

                # PRIORITY 1: High-traffic stores (Traffic >= 10k) waiting for Google Trends!
                if time.time() >= _gt_cooldown_until:
                    stores = db.get_stores_for_trend_enrichment(limit=25, cookie_min_days=0, min_traffic=10000)

                # PRIORITY 2: Stores with cookie_days >= 14 that haven't had their Traffic checked yet
                if not stores:
                    stores = db.get_stores_for_traffic_enrichment(limit=25, cookie_min_days=14)

                # PRIORITY 3: Stores with cookie_days >= 14 waiting for Google Trends!
                # (User's primary target - progress bar tracks trend_checked_cookie_14)
                if not stores and time.time() >= _gt_cooldown_until:
                    stores = db.get_stores_for_trend_enrichment(limit=25, cookie_min_days=14, min_traffic=0)
                    if stores:
                        is_low_traffic_trend_phase = True

                # PRIORITY 4: Remaining stores in database (cookie_days < 14) for Traffic & Category
                if not stores:
                    stores = db.get_stores_for_traffic_enrichment(limit=25, cookie_min_days=0)

                # PRIORITY 5: Remaining stores (cookie_days < 14) for Google Trends
                if not stores and time.time() >= _gt_cooldown_until:
                    stores = db.get_stores_for_trend_enrichment(limit=25, cookie_min_days=0, min_traffic=0)
                    if stores:
                        is_low_traffic_trend_phase = True

                if not stores:
                    if time.time() < _gt_cooldown_until:
                        wait_sec = min(5.0, max(1.0, _gt_cooldown_until - time.time()))
                        self._stop_event.wait(wait_sec)
                        continue
                    logger.info("All stores have been enriched with traffic and trends data. Worker idle.")
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

                    try:
                        # Only check Trends for stores with traffic >= 10k during normal run,
                        # unless in Phase 3 where all >= 10k stores are completed.
                        min_traffic_req = 0 if is_low_traffic_trend_phase else 10000
                        res = enrich_store_data(store, require_min_traffic_for_trends=min_traffic_req)
                        self.scanned += 1

                        t_status = res.get("trend_status", "")
                        tr_status = res.get("traffic_status", "")

                        if tr_status == "success" or t_status == "success":
                            self.with_data += 1
                        elif tr_status == "error" or t_status == "error":
                            self.errors += 1
                        else:
                            self.no_data += 1

                        # High-speed adaptive delay powered by curl_cffi HTTP/2:
                        # - If trends query was executed: safe 1.2s - 1.8s delay to respect Google's quota
                        # - If in cooldown/pending: snappy 0.5s - 0.9s delay
                        # - If error: 1.2s - 1.8s delay
                        # - If only Tranco domain traffic was checked: ultra-fast 0.3s - 0.6s delay
                        if res.get("trends_queried"):
                            delay = random.uniform(1.2, 1.8)
                        elif t_status == "pending":
                            delay = random.uniform(0.5, 0.9)
                        elif t_status == "error" or tr_status == "error":
                            delay = random.uniform(1.2, 1.8)
                        else:
                            delay = random.uniform(0.3, 0.6)

                        self._stop_event.wait(delay)
                    except Exception as store_err:
                        logger.error(f"Error enriching store '{store_name}': {store_err}", exc_info=True)
                        self.errors += 1
                        self._stop_event.wait(1.0)

        except Exception as e:
            logger.error(f"Error in traffic worker loop: {e}", exc_info=True)
        finally:
            self._is_running = False
            self.current_store = ""
            logger.info("Traffic worker has stopped.")

    def refresh_single_store(self, store_id: str, use_traffic_cv: bool = True) -> Optional[Dict[str, Any]]:
        """Enrich or refresh a single store on demand with high-precision Similarweb data."""
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stores WHERE store_id = ?", (store_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        store = dict(row)
        res = enrich_store_data(
            store,
            require_min_traffic_for_trends=0,
            force_refresh_traffic=True,
            use_traffic_cv=use_traffic_cv
        )
        # Fetch updated store record
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stores WHERE store_id = ?", (store_id,))
        updated_row = cursor.fetchone()
        conn.close()

        return dict(updated_row) if updated_row else res


# Singleton instance
worker = TrafficWorker()
