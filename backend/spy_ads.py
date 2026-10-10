import os
import json
import re
import asyncio
import calendar
import urllib.request
import urllib.parse
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from . import db

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SPY_DATA_FILE = DATA_DIR / "spy_google_ads_binize.json"

ICON_WORDS = {
    "videocam", "play_arrow", "hide_image", "image", "visibility",
    "đã xác minh", "verified", "arrow_drop_down", "check", "close",
    "search", "tune", "more_vert", "chevron_right", "chevron_left",
    "image_not_supported", "open_in_new", "photo", "movie", "play_circle",
    "help", "info"
}

COUNTRY_MAP: Dict[str, Tuple[str, str]] = {
    "VN": ("Việt Nam", "🇻🇳"),
    "US": ("Hoa Kỳ", "🇺🇸"),
    "HK": ("Hồng Kông", "🇭🇰"),
    "CN": ("Trung Quốc", "🇨🇳"),
    "JP": ("Nhật Bản", "🇯🇵"),
    "GB": ("Vương quốc Anh", "🇬🇧"),
    "UK": ("Vương quốc Anh", "🇬🇧"),
    "IN": ("Ấn Độ", "🇮🇳"),
    "DE": ("Đức", "🇩🇪"),
    "FR": ("Pháp", "🇫🇷"),
    "SG": ("Singapore", "🇸🇬"),
    "AU": ("Úc", "🇦🇺"),
    "CA": ("Canada", "🇨🇦"),
    "AE": ("UAE", "🇦🇪"),
    "PK": ("Pakistan", "🇵🇰"),
    "TH": ("Thái Lan", "🇹🇭"),
    "MY": ("Malaysia", "🇲🇾"),
    "ID": ("Indonesia", "🇮🇩"),
    "PH": ("Philippines", "🇵🇭"),
    "KR": ("Hàn Quốc", "🇰🇷"),
    "TW": ("Đài Loan", "🇹🇼"),
    "NL": ("Hà Lan", "🇳🇱"),
    "IT": ("Ý", "🇮🇹"),
    "ES": ("Tây Ban Nha", "🇪🇸"),
    "BR": ("Brazil", "🇧🇷"),
    "MX": ("Mexico", "🇲🇽"),
    "RU": ("Nga", "🇷🇺"),
    "TR": ("Thổ Nhĩ Kỳ", "🇹🇷"),
    "SA": ("Saudi Arabia", "🇸🇦"),
    "IL": ("Israel", "🇮🇱"),
    "ZA": ("Nam Phi", "🇿🇦"),
    "NZ": ("New Zealand", "🇳🇿"),
    "IE": ("Ireland", "🇮🇪"),
    "CH": ("Thụy Sĩ", "🇨🇭"),
    "SE": ("Thụy Điển", "🇸🇪"),
    "NO": ("Na Uy", "🇳🇴"),
    "DK": ("Đan Mạch", "🇩🇰"),
    "FI": ("Phần Lan", "🇫🇮"),
    "PL": ("Ba Lan", "🇵🇱"),
}

_ADVERTISER_METADATA_CACHE: Dict[str, Dict[str, Any]] = {}

def _clean_text_line(txt: str) -> str:
    if not txt:
        return ""
    cleaned = txt.strip()
    for iw in ICON_WORDS:
        cleaned = re.sub(rf"^\s*{re.escape(iw)}\s*\|?\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned

def get_country_and_flag(country_code: str, fallback_country: str = "") -> Tuple[str, str]:
    """Resolve ISO country code to human Vietnamese name and flag emoji."""
    cc = (country_code or "").strip().upper()
    if cc in COUNTRY_MAP:
        return COUNTRY_MAP[cc]
    if len(cc) == 2 and cc.isalpha():
        flag = "".join(chr(127397 + ord(c)) for c in cc)
        return cc, flag
    if fallback_country:
        fc_lower = fallback_country.lower()
        for code, (cname, cflag) in COUNTRY_MAP.items():
            if cname.lower() in fc_lower:
                return cname, cflag
        return fallback_country, "🌐"
    return "Quốc tế", "🌐"

def parse_unix_timestamp(ts: Any) -> Optional[str]:
    """Parse Google Transparency Unix timestamp string/int into YYYY-MM-DD.
    Returns None for invalid, empty, or pre-2001 timestamps (including '0' and 0)
    to prevent date explosions back to Unix epoch 1970-01-01.
    """
    if not ts or ts == "0" or ts == 0:
        return None
    if isinstance(ts, dict):
        ts = ts.get("1")
        if not ts or ts == "0" or ts == 0:
            return None
    try:
        sec = int(ts)
        if sec > 10**11:  # Milliseconds
            sec = sec // 1000
        # Google Ads launched in late 2000; timestamps <= 0 or < 1000000000 (pre-2001) are invalid
        if sec < 1000000000:
            return None
        return datetime.fromtimestamp(sec, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return None

def calculate_duration_days(first_seen_str: str, last_shown_str: str) -> int:
    """Calculate actual elapsed running days: max(1, (last_shown - first_seen).days + 1)."""
    try:
        d1 = datetime.strptime(first_seen_str, "%Y-%m-%d").date()
        d2 = datetime.strptime(last_shown_str, "%Y-%m-%d").date()
        return max(1, (d2 - d1).days + 1)
    except Exception:
        return 1

def calculate_monthly_activity(first_seen_str: str, last_shown_str: str, years: Tuple[int, ...] = (2024, 2025, 2026)) -> Dict[str, List[bool]]:
    """
    Compute 12-month boolean activity for each year (2024..2026).
    A month is active (True) iff [first_seen, last_shown] overlaps with [month_start, month_end].
    Enforces d_start <= d_end to prevent false positive month illumination when dates are inverted.
    """
    try:
        d_start = datetime.strptime(first_seen_str, "%Y-%m-%d").date()
        d_end = datetime.strptime(last_shown_str, "%Y-%m-%d").date()
    except Exception:
        return {str(y): [False] * 12 for y in years}

    if d_start > d_end:
        return {str(y): [False] * 12 for y in years}

    activity: Dict[str, List[bool]] = {}
    for y in years:
        months_active: List[bool] = []
        for m in range(1, 13):
            last_day = calendar.monthrange(y, m)[1]
            m_start = date(y, m, 1)
            m_end = date(y, m, last_day)
            is_active = (d_start <= m_end) and (d_end >= m_start)
            months_active.append(is_active)
        activity[str(y)] = months_active
    return activity

def classify_campaign(duration_days: int, monthly_activity: Optional[Dict[str, List[bool]]] = None) -> Tuple[str, str]:
    """
    Tripartite classification based on duration and monthly distribution:
    - new_test: '🟡 Mới Chạy (New Test)' (duration <= 30 days)
    - seasonal: '🍂 Chạy Theo Mùa (Seasonal)' (clustered in specific peak months/quarters e.g. Q4 <= 4 months)
    - evergreen: '🌲 Chạy Quanh Năm (Evergreen)' (active across majority of months >= 6-7 months/year, total >= 8, or continuous >= 180 days)
    """
    if duration_days <= 30:
        return "new_test", "🟡 Mới Chạy (New Test)"

    total_active_months = sum(sum(1 for m in flags if m) for flags in monthly_activity.values()) if monthly_activity else 0
    max_year_active = max((sum(1 for m in flags if m) for flags in monthly_activity.values()), default=0) if monthly_activity else 0
    years_with_activity = sum(1 for flags in monthly_activity.values() if any(flags)) if monthly_activity else 0

    # If monthly activity is not available / all False, fallback to duration thresholds
    if total_active_months == 0:
        if duration_days >= 90:
            return "evergreen", "🌲 Chạy Quanh Năm (Evergreen)"
        return "seasonal", "🍂 Chạy Theo Mùa (Seasonal)"

    # High active months across calendar
    if max_year_active >= 7 or total_active_months >= 8:
        return "evergreen", "🌲 Chạy Quanh Năm (Evergreen)"

    # Seasonal cluster: concentrated in <= 4 months in any year (e.g. Q4 T10-T12 = 3 months / 92 days)
    if (years_with_activity == 1 and total_active_months <= 4) or (max_year_active <= 4 and total_active_months <= 6):
        return "seasonal", "🍂 Chạy Theo Mùa (Seasonal)"

    # Long-running continuous multi-quarter/multi-year campaigns
    if duration_days >= 180:
        return "evergreen", "🌲 Chạy Quanh Năm (Evergreen)"

    if duration_days >= 90 and (max_year_active >= 5 or total_active_months >= 6):
        return "evergreen", "🌲 Chạy Quanh Năm (Evergreen)"

    return "seasonal", "🍂 Chạy Theo Mùa (Seasonal)"

classify_advertiser = classify_campaign

def fetch_advertiser_metadata(adv_id: str) -> Dict[str, Any]:
    """Query Google Ads LookupService/GetAdvertiserById for legal name, country, and verification status."""
    if not adv_id or not adv_id.startswith("AR"):
        return {}
    if adv_id in _ADVERTISER_METADATA_CACHE:
        return _ADVERTISER_METADATA_CACHE[adv_id]

    url = "https://adstransparency.google.com/anji/_/rpc/LookupService/GetAdvertiserById?authuser="
    req_data = {"1": adv_id, "3": {"1": 1}}
    post_body = urllib.parse.urlencode({"f.req": json.dumps(req_data)}).encode("utf-8")
    req = urllib.request.Request(url, data=post_body, headers={
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "x-same-domain": "1",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = resp.read().decode("utf-8")
            if raw.startswith(")]}'"):
                raw = raw[raw.find("\n") + 1:]
            res_json = json.loads(raw).get("1", {})
            name = _clean_text_line(res_json.get("2", ""))
            legal = res_json.get("9", {}).get("2") if isinstance(res_json.get("9"), dict) else name
            legal = _clean_text_line(legal or name)
            cc = res_json.get("3") or res_json.get("11") or ""
            cname, flag = get_country_and_flag(cc)
            is_ver = bool(res_json.get("15"))
            meta = {
                "name": name,
                "legal_name": legal or name,
                "country": cname,
                "country_code": cc,
                "country_flag": flag,
                "is_verified": is_ver
            }
            _ADVERTISER_METADATA_CACHE[adv_id] = meta
            return meta
    except Exception:
        return {}

def query_search_creatives_rpc(domain: str, limit: int = 100) -> Optional[List[Dict[str, Any]]]:
    """Direct All-Time RPC query without date bounding filter.
    Returns:
    - List of creative dicts (can be empty list if Google confirms 0 ads) on success.
    - None if a network, HTTP, or timeout error occurs.
    """
    clean = domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if clean.startswith("www."):
        clean = clean[4:]
    url = "https://adstransparency.google.com/anji/_/rpc/SearchService/SearchCreatives?authuser="
    req_data = {"2": limit, "3": {"12": {"1": clean, "2": True}}, "7": {"1": 1, "2": 0, "3": 2704}}
    post_body = urllib.parse.urlencode({"f.req": json.dumps(req_data)}).encode("utf-8")
    req = urllib.request.Request(url, data=post_body, headers={
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "x-same-domain": "1",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8")
            if raw.startswith(")]}'"):
                raw = raw[raw.find("\n") + 1:]
            data = json.loads(raw)
            return data.get("1", [])
    except Exception as e:
        print(f"[Spy Google Ads] SearchCreatives RPC error for {domain}: {e}")
        return None


def sanitize_spy_data(data: Dict[str, Any], domain: str = "") -> Dict[str, Any]:
    """Sanitize and standardize spy data: real duration calculation, 12-month activity, and tripartite badges."""
    clean_domain = (domain or data.get("domain", "")).strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if clean_domain.startswith("www."):
        clean_domain = clean_domain[4:]

    advs = data.get("advertisers", [])
    clean_advs = []
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for adv in advs:
        adv_id = str(adv.get("id") or "").strip()
        name = str(adv.get("name") or "").strip()
        legal_name = str(adv.get("legal_name") or "").strip()

        # Clean icon words from names
        name = _clean_text_line(name)
        legal_name = _clean_text_line(legal_name)
        if not name or name.lower() in ICON_WORDS:
            name = legal_name if (legal_name and legal_name.lower() not in ICON_WORDS) else (clean_domain.capitalize() if clean_domain else "Advertiser")
        if not legal_name or legal_name.lower() in ICON_WORDS:
            legal_name = name

        adv["name"] = name
        adv["legal_name"] = legal_name

        # Clean country and flag
        country_code = adv.get("country_code") or ""
        country = adv.get("country") or ""
        cname, flag = get_country_and_flag(country_code, fallback_country=country)
        adv["country"] = cname
        adv["country_flag"] = flag

        # Clean creatives and determine date boundaries
        clean_creatives = []
        cr_first_dates = []
        cr_last_dates = []
        text_cnt, img_cnt, vid_cnt = 0, 0, 0

        for idx, cr in enumerate(adv.get("creatives", [])):
            hl = _clean_text_line(cr.get("headline", ""))
            desc = _clean_text_line(cr.get("description", ""))
            fmt = str(cr.get("format") or "search").lower()
            if "video" in fmt or "youtube" in fmt:
                fmt_key = "video"
                vid_cnt += 1
            elif "image" in fmt or "display" in fmt or "banner" in fmt:
                fmt_key = "image"
                img_cnt += 1
            else:
                fmt_key = "search"
                text_cnt += 1

            cr_first = cr.get("first_seen") or adv.get("first_seen") or today_str
            cr_last = cr.get("last_shown") or adv.get("last_shown") or today_str
            cr_dur = calculate_duration_days(cr_first, cr_last)

            cr_first_dates.append(cr_first)
            cr_last_dates.append(cr_last)

            clean_creatives.append({
                "id": str(cr.get("id") or f"CR_{adv_id}_{idx}"),
                "format": fmt_key,
                "format_label": cr.get("format_label") or ("Google Text Ads" if fmt_key == "search" else ("Google Display Banner" if fmt_key == "image" else "YouTube Video Ads")),
                "headline": hl or f"Quảng cáo Google: {clean_domain}",
                "description": desc or f"Mẫu quảng cáo hiển thị trên Google Ads cho {clean_domain}",
                "landing_page": cr.get("landing_page") or f"https://www.{clean_domain}",
                "first_seen": cr_first,
                "last_shown": cr_last,
                "duration_days": cr_dur,
                "image_url": cr.get("image_url")
            })

        # Calculate genuine advertiser-level dates and duration (NOT ad_count!)
        adv_first_seen = min(cr_first_dates) if cr_first_dates else (adv.get("first_seen") or today_str)
        adv_last_shown = max(cr_last_dates) if cr_last_dates else (adv.get("last_shown") or today_str)
        adv_dur = calculate_duration_days(adv_first_seen, adv_last_shown)

        adv["first_seen"] = adv_first_seen
        adv["last_shown"] = adv_last_shown
        adv["duration_days"] = adv_dur

        # 12-Month activity and Tripartite Classification (R1, R2)
        monthly_activity = calculate_monthly_activity(adv_first_seen, adv_last_shown)
        adv["monthly_activity"] = monthly_activity
        adv["timeline_3year"] = monthly_activity

        classification_key, classification_label = classify_campaign(adv_dur, monthly_activity)
        adv["classification"] = classification_key
        adv["classification_label"] = classification_label
        adv["campaign_type"] = classification_key
        adv["campaign_type_label"] = classification_label

        # Authentic scale badges:
        # 🔥 Quy mô lớn (≥10 mẫu ads), 🟢 Đang chạy đều (2 - 9 ads), 🟡 Mới thử nghiệm (1 ad)
        ad_count = int(adv.get("ad_count") or len(clean_creatives) or 1)
        adv["ad_count"] = ad_count
        if ad_count >= 10:
            adv["longevity_badge"] = "super_scale"
            adv["scale_label"] = "🔥 Quy mô lớn (≥10 mẫu ads)"
        elif ad_count >= 2:
            adv["longevity_badge"] = "win_ads"
            adv["scale_label"] = "🟢 Đang chạy đều (2 - 9 ads)"
        else:
            adv["longevity_badge"] = "test"
            adv["scale_label"] = "🟡 Mới thử nghiệm (1 ad)"

        # Formats list and breakdown
        unique_formats = []
        if text_cnt > 0:
            unique_formats.append("search")
        if img_cnt > 0:
            unique_formats.append("image")
        if vid_cnt > 0:
            unique_formats.append("video")
        if not unique_formats:
            unique_formats = ["search"]
        adv["formats"] = unique_formats
        adv["format_breakdown"] = {"text": text_cnt, "image": img_cnt, "video": vid_cnt}

        adv["creatives"] = clean_creatives
        clean_advs.append(adv)

    data["domain"] = clean_domain or data.get("domain", "binize.com")
    data["all_time_enabled"] = True
    data["advertisers"] = clean_advs
    data["total_advertisers"] = len(clean_advs)
    data["total_ads"] = sum(a["ad_count"] for a in clean_advs)
    data["super_scale_count"] = sum(1 for a in clean_advs if a["ad_count"] >= 10)
    data["win_ads_count"] = sum(1 for a in clean_advs if 2 <= a["ad_count"] < 10)
    data["test_ads_count"] = sum(1 for a in clean_advs if a["ad_count"] == 1)
    data["evergreen_count"] = sum(1 for a in clean_advs if a.get("classification") == "evergreen")
    data["seasonal_count"] = sum(1 for a in clean_advs if a.get("classification") == "seasonal")
    data["new_test_count"] = sum(1 for a in clean_advs if a.get("classification") == "new_test")

    if len(clean_advs) == 0:
        data["is_verified_zero"] = True
        data["status"] = "no_ads"
    else:
        data["is_verified_zero"] = False
        data["status"] = "done"

    data.pop("evergreen_percent", None)
    return data

def _load_default_spy_data() -> Dict[str, Any]:
    if SPY_DATA_FILE.exists():
        try:
            with open(SPY_DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return sanitize_spy_data(raw, "binize.com")
        except Exception:
            pass
    return {
        "domain": "binize.com",
        "updated_at": "2026-10-10T11:45:00",
        "total_advertisers": 16,
        "total_ads": 58,
        "super_scale_count": 1,
        "win_ads_count": 15,
        "test_ads_count": 0,
        "advertisers": []
    }

DEFAULT_SPY_DATA = _load_default_spy_data()

def get_file_for_domain(domain: str) -> Path:
    clean = (domain or "binize.com").strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if clean.startswith("www."):
        clean = clean[4:]
    if "fafrees" in clean:
        return DATA_DIR / "spy_google_ads_fafreesebike_com.json"
    if "letbricks" in clean:
        return DATA_DIR / "spy_google_ads_letbricks_com.json"
    if "binize" in clean:
        p = DATA_DIR / "spy_google_ads_binize.json"
        if p.exists():
            return p
        return DATA_DIR / "spy_google_ads_binize_com.json"
    clean_fname = clean.replace(".", "_")
    return DATA_DIR / f"spy_google_ads_{clean_fname}.json"

def load_spy_data(domain: str = "binize.com", store_id: Optional[str] = None) -> Dict[str, Any]:
    """Load cached spy data for specific domain from disk with DB verification fallback."""
    clean_domain = (domain or "binize.com").strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if clean_domain.startswith("www."):
        clean_domain = clean_domain[4:]

    file_path = get_file_for_domain(clean_domain)
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return sanitize_spy_data(data, clean_domain)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    # Fallback to default for binize if available
    if "binize" in clean_domain:
        return sanitize_spy_data(DEFAULT_SPY_DATA, clean_domain)

    # Check database to see if store was verified as having 0 ads
    try:
        conn = db.get_db()
        cursor = conn.cursor()
        if store_id:
            cursor.execute("""
            SELECT store_id, name, website_url, spy_ads_status, spy_adv_count, spy_ads_count, spy_updated_at, crawled_at
            FROM stores
            WHERE store_id = ?
            LIMIT 1
            """, (store_id,))
        else:
            cursor.execute("""
            SELECT store_id, name, website_url, spy_ads_status, spy_adv_count, spy_ads_count, spy_updated_at, crawled_at
            FROM stores
            WHERE website_url LIKE ? OR website_url LIKE ?
            LIMIT 1
            """, (f"%://{clean_domain}%", f"%://www.{clean_domain}%"))
        row = cursor.fetchone()
        conn.close()
        if row and row["spy_ads_status"] in ("no_ads", "done"):
            ad_count = row["spy_ads_count"] or 0
            adv_count = row["spy_adv_count"] or 0
            if ad_count == 0:
                return {
                    "domain": clean_domain,
                    "updated_at": row["spy_updated_at"] or row["crawled_at"] or datetime.now().isoformat(),
                    "total_advertisers": 0,
                    "total_ads": 0,
                    "win_ads_count": 0,
                    "super_scale_count": 0,
                    "test_ads_count": 0,
                    "is_verified_zero": True,
                    "status": "no_ads",
                    "advertisers": []
                }
    except Exception as e:
        print(f"Error querying DB for spy fallback: {e}")

    return {
        "domain": clean_domain,
        "updated_at": None,
        "total_advertisers": 0,
        "total_ads": 0,
        "win_ads_count": 0,
        "super_scale_count": 0,
        "test_ads_count": 0,
        "advertisers": [],
        "is_empty": True
    }

def save_spy_data(data: Dict[str, Any], domain: str = "binize.com"):
    """Persist spy data to disk for a domain."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sanitized = sanitize_spy_data(data, domain)
    file_path = get_file_for_domain(domain or sanitized.get("domain", "binize.com"))
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sanitized, f, ensure_ascii=False, indent=2)

async def crawl_google_ads_transparency(domain: str = "binize.com") -> Dict[str, Any]:
    """
    Live scraper that queries Google Ads Transparency Center in All-Time mode.
    Extracts actual Unix timestamps ("6"."1" -> first_seen, "7"."1" -> last_shown),
    computes genuine duration_days, 12-month activity timeline matrix (2024..2026),
    tripartite classification (evergreen / seasonal / new_test), and full advertiser metadata.
    """
    clean_domain = domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if clean_domain.startswith("www."):
        clean_domain = clean_domain[4:]
    if "fafrees" in clean_domain and "ebike" not in clean_domain:
        clean_domain = "fafreesebike.com"

    target_url = f"https://adstransparency.google.com/?region=anywhere&domain={clean_domain}"
    captured_rpc_items: List[Dict[str, Any]] = []
    is_zero_confirmed = False
    browser_navigated = False
    browser_error = None

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900}
            )

            # Intercept raw JSON responses from SearchCreatives to extract genuine Unix timestamps
            async def handle_response(response):
                nonlocal captured_rpc_items
                if "SearchCreatives" in response.url and response.status == 200:
                    try:
                        body_txt = await response.text()
                        if body_txt.startswith(")]}'"):
                            body_txt = body_txt[body_txt.find("\n") + 1:]
                        payload = json.loads(body_txt)
                        items = payload.get("1", [])
                        if items:
                            captured_rpc_items.extend(items)
                    except Exception:
                        pass

            page.on("response", handle_response)

            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2500)
                browser_navigated = True
            except Exception as e:
                browser_error = str(e)
                print(f"[Spy Google Ads] Page navigation notice: {e}")

            # Verify if store genuinely has 0 ads
            if browser_navigated:
                try:
                    body_text = await page.inner_text("body")
                    if any(term in body_text for term in ["0 quảng cáo", "0 ads", "Không tìm thấy", "Không tìm thấy", "No ads found"]):
                        is_zero_confirmed = True
                except Exception:
                    pass

            # Activate All-Time / Mọi lúc filter via UI interaction (Requirement R1)
            if browser_navigated and not is_zero_confirmed:
                try:
                    date_btn = page.locator('div.popup-button:has-text("calendar_today"), div[aria-label*="ngày" i], div[aria-label*="date" i]').first
                    if await date_btn.count() > 0:
                        btn_text = await date_btn.inner_text()
                        if not any(k in btn_text.lower() for k in ["mọi lúc", "any time", "all time"]):
                            await date_btn.click()
                            await page.wait_for_timeout(400)
                            opt = page.locator('material-select-item:has-text("Mọi lúc"), material-select-item:has-text("Any time"), material-select-item:has-text("All time"), [role="option"]:has-text("Mọi lúc")').first
                            if await opt.count() > 0:
                                await opt.click()
                                await page.wait_for_timeout(400)
                                ok_btn = page.locator('material-button:has-text("OK"), material-button:has-text("Áp dụng"), material-button:has-text("Apply")').last
                                if await ok_btn.count() > 0:
                                    await ok_btn.click()
                                    await page.wait_for_timeout(1200)
                except Exception as e:
                    print(f"[Spy Google Ads] Notice on All-Time date toggle: {e}")

            # Expand and scroll if ads are present
            if browser_navigated and not is_zero_confirmed:
                try:
                    for see_btn_text in ["See all ads", "Xem tất cả quảng cáo"]:
                        btn = page.get_by_text(see_btn_text)
                        if await btn.count() > 0:
                            await btn.first.click()
                            await page.wait_for_timeout(2000)
                            for _ in range(4):
                                await page.mouse.wheel(0, 5000)
                                await page.wait_for_timeout(600)
                            break
                except Exception:
                    pass

            await browser.close()
    except Exception as e:
        browser_error = str(e)
        print(f"[Spy Google Ads] Playwright browser execution note: {e}")

    # Fallback to direct All-Time RPC query if network interception didn't capture items
    rpc_items = None
    rpc_error = None
    if not is_zero_confirmed and not captured_rpc_items:
        try:
            rpc_items = query_search_creatives_rpc(clean_domain, limit=100)
            if rpc_items is not None and len(rpc_items) > 0:
                captured_rpc_items = rpc_items
        except Exception as e:
            rpc_error = str(e)

    # Differentiate between verified zero ads vs network / timeout error
    if not captured_rpc_items:
        # Google Ads Transparency explicitly verified 0 ads via page text or successful RPC with 0 items
        if is_zero_confirmed or (browser_navigated and rpc_items is not None and len(rpc_items) == 0):
            empty_res = {
                "domain": clean_domain,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "all_time_enabled": True,
                "total_advertisers": 0,
                "total_ads": 0,
                "win_ads_count": 0,
                "super_scale_count": 0,
                "test_ads_count": 0,
                "evergreen_count": 0,
                "seasonal_count": 0,
                "new_test_count": 0,
                "advertisers": [],
                "is_verified_zero": True,
                "status": "no_ads"
            }
            save_spy_data(empty_res, clean_domain)
            return empty_res

        # Network/timeout error: do NOT overwrite cache or claim verified zero ads
        error_msg = browser_error or rpc_error or "Network timeout or connection error reaching Google Ads Transparency"
        error_res = {
            "domain": clean_domain,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "all_time_enabled": True,
            "total_advertisers": 0,
            "total_ads": 0,
            "win_ads_count": 0,
            "super_scale_count": 0,
            "test_ads_count": 0,
            "evergreen_count": 0,
            "seasonal_count": 0,
            "new_test_count": 0,
            "advertisers": [],
            "is_verified_zero": False,
            "status": "error",
            "error": error_msg
        }
        return error_res

    # Deduplicate and group creatives by advertiser
    adv_groups: Dict[str, Dict[str, Any]] = {}
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for raw_cr in captured_rpc_items:
        adv_id = str(raw_cr.get("1") or "").strip()
        raw_name = _clean_text_line(str(raw_cr.get("12") or ""))
        group_key = adv_id or raw_name or f"ADV_{len(adv_groups)}"

        if group_key not in adv_groups:
            adv_groups[group_key] = {
                "adv_id": adv_id,
                "raw_name": raw_name,
                "creatives_raw": []
            }
        adv_groups[group_key]["creatives_raw"].append(raw_cr)

    enriched_advertisers = []
    for idx, (group_key, group_data) in enumerate(adv_groups.items()):
        adv_id = group_data["adv_id"] or f"AR_SCR_{idx:04d}"
        raw_name = group_data["raw_name"]

        # Fetch authentic advertiser legal info and country
        meta = fetch_advertiser_metadata(adv_id) if adv_id.startswith("AR") else {}
        name = meta.get("name") or raw_name or clean_domain.capitalize()
        legal_name = meta.get("legal_name") or name
        country = meta.get("country") or "Quốc tế"
        flag = meta.get("country_flag") or "🌐"
        is_verified = meta.get("is_verified", True)

        # Extract creatives and timestamps
        creatives = []
        cr_first_dates = []
        cr_last_dates = []
        text_cnt, img_cnt, vid_cnt = 0, 0, 0

        for cr_idx, c_raw in enumerate(group_data["creatives_raw"]):
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

            # Parse genuine Unix timestamps ("6"."1" -> start, "7"."1" -> end)
            f6 = parse_unix_timestamp(c_raw.get("6")) or today_str
            f7 = parse_unix_timestamp(c_raw.get("7")) or today_str
            dur = calculate_duration_days(f6, f7)

            cr_first_dates.append(f6)
            cr_last_dates.append(f7)

            # Extract image preview URL if available
            img_url = None
            raw_3 = c_raw.get("3")
            if isinstance(raw_3, dict):
                inner_3 = raw_3.get("3")
                if isinstance(inner_3, dict) and "2" in inner_3:
                    m = re.search(r'src=["\'](https?://[^"\']+)["\']', inner_3["2"])
                    if m:
                        img_url = m.group(1)

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
                "image_url": img_url
            })

        # Calculate genuine advertiser-level dates and duration (NOT ad_count!)
        adv_first_seen = min(cr_first_dates) if cr_first_dates else today_str
        adv_last_shown = max(cr_last_dates) if cr_last_dates else today_str
        adv_duration = calculate_duration_days(adv_first_seen, adv_last_shown)

        # Compute 12-Month activity and Tripartite Classification (R1, R2)
        monthly_activity = calculate_monthly_activity(adv_first_seen, adv_last_shown)
        classification_key, classification_label = classify_campaign(adv_duration, monthly_activity)

        ad_count = len(creatives)
        if ad_count >= 10:
            longevity_badge = "super_scale"
            scale_label = "🔥 Quy mô lớn (≥10 mẫu ads)"
        elif ad_count >= 2:
            longevity_badge = "win_ads"
            scale_label = "🟢 Đang chạy đều (2 - 9 ads)"
        else:
            longevity_badge = "test"
            scale_label = "🟡 Mới thử nghiệm (1 ad)"

        unique_formats = []
        if text_cnt > 0:
            unique_formats.append("search")
        if img_cnt > 0:
            unique_formats.append("image")
        if vid_cnt > 0:
            unique_formats.append("video")
        if not unique_formats:
            unique_formats = ["search"]

        enriched_advertisers.append({
            "id": adv_id,
            "name": name,
            "legal_name": legal_name,
            "country": country,
            "country_flag": flag,
            "is_verified": is_verified,
            "advertiser_url": f"https://adstransparency.google.com/advertiser/{adv_id}?region=anywhere",
            "first_seen": adv_first_seen,
            "last_shown": adv_last_shown,
            "duration_days": adv_duration,
            "longevity_badge": longevity_badge,
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

    total_ads_count = sum(a["ad_count"] for a in enriched_advertisers)
    res_data = {
        "domain": clean_domain,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "all_time_enabled": True,
        "total_advertisers": len(enriched_advertisers),
        "total_ads": total_ads_count,
        "super_scale_count": sum(1 for a in enriched_advertisers if a["ad_count"] >= 10),
        "win_ads_count": sum(1 for a in enriched_advertisers if 2 <= a["ad_count"] < 10),
        "test_ads_count": sum(1 for a in enriched_advertisers if a["ad_count"] == 1),
        "evergreen_count": sum(1 for a in enriched_advertisers if a.get("classification") == "evergreen"),
        "seasonal_count": sum(1 for a in enriched_advertisers if a.get("classification") == "seasonal"),
        "new_test_count": sum(1 for a in enriched_advertisers if a.get("classification") == "new_test"),
        "is_verified_zero": False,
        "status": "done" if len(enriched_advertisers) > 0 else "no_ads",
        "advertisers": enriched_advertisers
    }

    save_spy_data(res_data, clean_domain)
    return res_data
