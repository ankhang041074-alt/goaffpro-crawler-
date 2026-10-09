import sqlite3
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "goaffpro.db"


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def parse_commission_numeric(rate_str: str) -> float:
    """Extract highest numeric commission percentage from text, e.g. '15%', '10% - 25%' -> 25.0"""
    if not rate_str:
        return 0.0
    try:
        # Search for percentages
        pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", rate_str)
        if pcts:
            return max(float(p) for p in pcts)
        
        # Search for currency amounts or numbers
        nums = re.findall(r"(\d+(?:\.\d+)?)", rate_str)
        if nums:
            return float(nums[0])
    except Exception:
        pass
    return 0.0


def calculate_is_steady_trend(timeline: List[Dict[str, Any]]) -> bool:
    """
    Evaluate if a store's Google Trends search interest is steady / evergreen
    rather than an isolated seasonal spike or noise.
    
    Criteria:
    - Timeline has sustained non-zero activity (active in >= 18 months or >= 65% for <= 24 mo; >= 60% for > 24 mo, min 12 active months)
    - No long dormant dead gaps (max consecutive zeroes <= 6 months)
    - Average monthly search interest >= 5.0 points
    - Multi-year activity across recorded timeline with regular non-zero interest in each recorded year (>= 3 active months in full years)
    - No single extreme outlier spike dominating the entire history (> 40% of the sum)
    """
    if not timeline or len(timeline) < 6:
        return False
    try:
        vals = []
        months = []
        for p in timeline:
            if not isinstance(p, dict):
                continue
            m = str(p.get("month") or "").strip()
            raw_v = p.get("value")
            try:
                v = int(float(raw_v)) if raw_v is not None else 0
            except (ValueError, TypeError):
                v = 0
            vals.append(max(0, v))
            months.append(m)

        total_months = len(vals)
        if total_months < 6:
            return False

        active_months = sum(1 for v in vals if v > 0)
        if active_months < 12:
            return False

        active_ratio = active_months / total_months
        avg_score = sum(vals) / total_months
        if avg_score < 5.0:
            return False

        # For shorter timelines (<= 24 months), require >= 18 active months or >= 65%
        # For full multi-year timelines (> 24 months, e.g. 5-year 61 months), require sustained active ratio >= 60%
        if total_months <= 24:
            if not (active_months >= 18 or active_ratio >= 0.65):
                return False
        else:
            if active_ratio < 0.60:
                return False

        # Prevent dormant dead streaks: steady traffic should not be dead for > 6 consecutive months
        max_zeros = 0
        cur_zeros = 0
        for v in vals:
            if v == 0:
                cur_zeros += 1
                if cur_zeros > max_zeros:
                    max_zeros = cur_zeros
            else:
                cur_zeros = 0
        if max_zeros > 6:
            return False

        years: Dict[str, List[int]] = {}
        for m, v in zip(months, vals):
            yr = m.split("-")[0] if "-" in m else "unknown"
            years.setdefault(yr, []).append(v)

        active_years = sum(1 for yr_vals in years.values() if any(v > 0 for v in yr_vals))
        if len(years) >= 2 and active_years < 2:
            return False

        # For full calendar years recorded (>= 10 months in that year), require regular activity (>= 3 active months)
        for yr, yr_vals in years.items():
            if len(yr_vals) >= 10:
                yr_act = sum(1 for v in yr_vals if v > 0)
                if yr_act < 3:
                    return False

        total_sum = sum(vals)
        if total_sum > 0 and (max(vals) / total_sum) > 0.40:
            return False

        return True
    except Exception:
        return False



def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        website_url TEXT DEFAULT '',
        portal_url TEXT DEFAULT '',
        logo_url TEXT DEFAULT '',
        currency TEXT DEFAULT 'USD',
        commission_rate TEXT DEFAULT '',
        commission_value REAL DEFAULT 0.0,
        cookie_days INTEGER DEFAULT 30,
        category TEXT DEFAULT 'General',
        description TEXT DEFAULT '',
        instant_access INTEGER DEFAULT 1,
        status TEXT DEFAULT 'available',
        is_favorite INTEGER DEFAULT 0,
        notes TEXT DEFAULT '',
        crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crawl_jobs (
        job_id TEXT PRIMARY KEY,
        status TEXT DEFAULT 'pending',
        current_page INTEGER DEFAULT 0,
        total_pages INTEGER DEFAULT 0,
        total_stores INTEGER DEFAULT 0,
        new_stores INTEGER DEFAULT 0,
        message TEXT DEFAULT '',
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Indices for high-performance searching and sorting
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_name ON stores(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_category ON stores(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_currency ON stores(currency)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_cookie ON stores(cookie_days)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_commission ON stores(commission_value)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_favorite ON stores(is_favorite)")

    # Ensure traffic and Google Trends columns exist
    cursor.execute("PRAGMA table_info(stores)")
    existing_cols = {row["name"] for row in cursor.fetchall()}

    traffic_cols = [
        ("traffic_visits", "TEXT DEFAULT ''"),
        ("traffic_raw_value", "INTEGER DEFAULT 0"),
        ("traffic_status", "TEXT DEFAULT 'pending'"),
        ("traffic_top_country", "TEXT DEFAULT ''"),
        ("trend_timeline_json", "TEXT DEFAULT ''"),
        ("trend_peak_month", "TEXT DEFAULT ''"),
        ("trend_status", "TEXT DEFAULT 'pending'"),
        ("trend_is_steady", "INTEGER DEFAULT 0"),
        ("traffic_updated_at", "DATETIME DEFAULT NULL"),
        ("categories_json", "TEXT DEFAULT '[]'"),
        ("site_title", "TEXT DEFAULT ''"),
        ("site_description", "TEXT DEFAULT ''"),
        ("is_adult", "INTEGER DEFAULT 0"),
        ("traffic_source", "TEXT DEFAULT ''"),
        ("traffic_bounce_rate", "TEXT DEFAULT ''"),
        ("traffic_avg_duration", "TEXT DEFAULT ''"),
        ("traffic_global_rank", "INTEGER DEFAULT 0"),
        ("traffic_country_rank", "INTEGER DEFAULT 0"),
        ("traffic_pages_per_visit", "TEXT DEFAULT ''"),
    ]
    for col_name, col_type in traffic_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE stores ADD COLUMN {col_name} {col_type}")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_traffic ON stores(traffic_raw_value)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_traffic_status ON stores(traffic_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_traffic_source ON stores(traffic_source)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_traffic_global_rank ON stores(traffic_global_rank)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_trend_status ON stores(trend_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_trend_steady ON stores(trend_is_steady)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_is_adult ON stores(is_adult)")

    # Backfill trend_is_steady for existing records with trend data
    cursor.execute("SELECT store_id, trend_timeline_json, trend_is_steady FROM stores WHERE trend_status = 'success' AND trend_timeline_json != ''")
    rows = cursor.fetchall()
    updates = []
    for r in rows:
        try:
            tl = json.loads(r["trend_timeline_json"])
            steady_val = 1 if calculate_is_steady_trend(tl) else 0
            if r["trend_is_steady"] != steady_val:
                updates.append((steady_val, r["store_id"]))
        except Exception:
            pass
    if updates:
        cursor.executemany("UPDATE stores SET trend_is_steady = ? WHERE store_id = ?", updates)

    # Ensure stores without successful trends never have trend_is_steady flag
    cursor.execute("UPDATE stores SET trend_is_steady = 0 WHERE (trend_status != 'success' OR trend_status IS NULL) AND trend_is_steady != 0")

    conn.commit()
    conn.close()


def save_store(store: Dict[str, Any]) -> bool:
    """Save or update a single store record."""
    conn = get_db()
    cursor = conn.cursor()

    store_id = str(store.get("store_id") or store.get("name") or "").strip().lower()
    if not store_id:
        conn.close()
        return False

    name = str(store.get("name") or "Unknown Store").strip()
    website_url = str(store.get("website_url") or "").strip()
    portal_url = str(store.get("portal_url") or "").strip()
    logo_url = str(store.get("logo_url") or "").strip()
    commission_rate = str(store.get("commission_rate") or "").strip()
    currency = str(store.get("currency") or "USD").strip().upper()
    commission_val = float(store.get("commission_value") or parse_commission_numeric(commission_rate))
    cookie_days = int(store.get("cookie_days") or 30)
    category = str(store.get("category") or "General").strip()
    if category == "Home & Kitchen":
        category = "Home, Living & Decor"
    description = str(store.get("description") or "").strip()
    instant_access = 1 if store.get("instant_access", True) else 0

    cursor.execute("""
    INSERT INTO stores (
        store_id, name, website_url, portal_url, logo_url, currency,
        commission_rate, commission_value, cookie_days, category,
        description, instant_access, updated_at
    ) VALUES (
        ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, CURRENT_TIMESTAMP
    )
    ON CONFLICT(store_id) DO UPDATE SET
        name=excluded.name,
        website_url=CASE WHEN excluded.website_url != '' THEN excluded.website_url ELSE stores.website_url END,
        portal_url=CASE WHEN excluded.portal_url != '' THEN excluded.portal_url ELSE stores.portal_url END,
        logo_url=CASE WHEN excluded.logo_url != '' THEN excluded.logo_url ELSE stores.logo_url END,
        currency=excluded.currency,
        commission_rate=CASE WHEN excluded.commission_rate != '' THEN excluded.commission_rate ELSE stores.commission_rate END,
        commission_value=CASE WHEN excluded.commission_value > 0 THEN excluded.commission_value ELSE stores.commission_value END,
        cookie_days=excluded.cookie_days,
        category=CASE WHEN excluded.category != 'General' THEN excluded.category ELSE stores.category END,
        description=CASE WHEN excluded.description != '' THEN excluded.description ELSE stores.description END,
        instant_access=excluded.instant_access,
        updated_at=CURRENT_TIMESTAMP
    """, (
        store_id, name, website_url, portal_url, logo_url, currency,
        commission_rate, commission_val, cookie_days, category,
        description, instant_access
    ))

    conn.commit()
    conn.close()
    return True


def save_stores_batch(stores_list: List[Dict[str, Any]]) -> int:
    """Batch save stores and return number of successfully saved items."""
    if not stores_list:
        return 0

    conn = get_db()
    cursor = conn.cursor()
    saved = 0

    for store in stores_list:
        store_id = str(store.get("store_id") or store.get("name") or "").strip().lower()
        if not store_id:
            continue

        name = str(store.get("name") or "Unknown Store").strip()
        website_url = str(store.get("website_url") or "").strip()
        portal_url = str(store.get("portal_url") or "").strip()
        logo_url = str(store.get("logo_url") or "").strip()
        commission_rate = str(store.get("commission_rate") or "").strip()
        currency = str(store.get("currency") or "USD").strip().upper()
        commission_val = float(store.get("commission_value") or parse_commission_numeric(commission_rate))
        cookie_days = int(store.get("cookie_days") or 30)
        category = str(store.get("category") or "General").strip()
        if category == "Home & Kitchen":
            category = "Home, Living & Decor"
        description = str(store.get("description") or "").strip()
        instant_access = 1 if store.get("instant_access", True) else 0

        cursor.execute("""
        INSERT INTO stores (
            store_id, name, website_url, portal_url, logo_url, currency,
            commission_rate, commission_value, cookie_days, category,
            description, instant_access, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, CURRENT_TIMESTAMP
        )
        ON CONFLICT(store_id) DO UPDATE SET
            name=excluded.name,
            website_url=CASE WHEN excluded.website_url != '' THEN excluded.website_url ELSE stores.website_url END,
            portal_url=CASE WHEN excluded.portal_url != '' THEN excluded.portal_url ELSE stores.portal_url END,
            logo_url=CASE WHEN excluded.logo_url != '' THEN excluded.logo_url ELSE stores.logo_url END,
            currency=excluded.currency,
            commission_rate=CASE WHEN excluded.commission_rate != '' THEN excluded.commission_rate ELSE stores.commission_rate END,
            commission_value=CASE WHEN excluded.commission_value > 0 THEN excluded.commission_value ELSE stores.commission_value END,
            cookie_days=excluded.cookie_days,
            category=CASE WHEN excluded.category != 'General' THEN excluded.category ELSE stores.category END,
            description=CASE WHEN excluded.description != '' THEN excluded.description ELSE stores.description END,
            instant_access=excluded.instant_access,
            updated_at=CURRENT_TIMESTAMP
        """, (
            store_id, name, website_url, portal_url, logo_url, currency,
            commission_rate, commission_val, cookie_days, category,
            description, instant_access
        ))
        saved += 1

    conn.commit()
    conn.close()
    return saved


def delete_store(store_id: str) -> bool:
    """Delete a single store by store_id."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stores WHERE store_id = ?", (store_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def delete_stores_by_currency(currency: str) -> int:
    """Delete all stores with given currency (e.g. INR)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stores WHERE UPPER(currency) = UPPER(?)", (currency.strip(),))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count


def delete_indian_and_subcontinent_stores() -> int:
    """Delete all stores with Indian or South Asian subcontinent currencies/domains."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM stores 
        WHERE UPPER(currency) IN ('INR', 'PKR', 'BDT', 'LKR', 'NPR')
           OR website_url LIKE '%.in' 
           OR website_url LIKE '%.in/%' 
           OR website_url LIKE '%.co.in%'
           OR website_url LIKE '%.pk'
           OR website_url LIKE '%.pk/%'
           OR website_url LIKE '%.com.pk%'
           OR website_url LIKE '%.bd'
           OR website_url LIKE '%.com.bd%'
           OR website_url LIKE '%bodygoldindia.com%'
    """)
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count



def get_stores(
    search: Optional[str] = None,
    category: Optional[str] = None,
    currency: Optional[str] = None,
    min_commission: Optional[float] = None,
    cookie_days: Optional[int] = None,
    min_traffic: Optional[int] = None,
    traffic_status: Optional[str] = None,
    trend_month: Optional[Union[int, str]] = None,
    trend_min_score: Optional[Union[int, str]] = None,
    trend_peak_only: bool = False,
    trend_growth_only: bool = False,
    trend_steady_only: bool = False,
    adult_filter: Optional[str] = "hide",
    notes_filter: Optional[str] = None,
    favorite_only: bool = False,
    sort_by: str = "commission_value",
    sort_order: str = "desc",
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """Query stores with filtering, searching, and pagination."""
    conn = get_db()
    cursor = conn.cursor()

    conditions = []
    params = []

    if isinstance(search, str) and search.strip():
        search_clean = search.strip().lower()
        term = f"%{search_clean}%"
        if "home & kitchen" in search_clean:
            conditions.append("(LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(category) LIKE ? OR LOWER(category) LIKE '%home, living & decor%' OR LOWER(website_url) LIKE ? OR LOWER(notes) LIKE ? OR LOWER(site_title) LIKE ? OR LOWER(site_description) LIKE ?)")
            params.extend([term, term, term, term, term, term, term])
        else:
            conditions.append("(LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(category) LIKE ? OR LOWER(website_url) LIKE ? OR LOWER(notes) LIKE ? OR LOWER(site_title) LIKE ? OR LOWER(site_description) LIKE ?)")
            params.extend([term, term, term, term, term, term, term])

    if isinstance(category, str) and category.strip() and category.strip() != "all":
        cat_term = category.strip()
        if cat_term in ["Home & Kitchen", "Home, Living & Decor"]:
            conditions.append("(category IN ('Home, Living & Decor', 'Home & Kitchen') OR categories_json LIKE '%Home, Living & Decor%' OR categories_json LIKE '%Home & Kitchen%')")
        else:
            conditions.append("(category = ? OR category LIKE ? OR categories_json LIKE ?)")
            params.extend([cat_term, f"%{cat_term}%", f"%\"{cat_term}\"%"])

    if adult_filter == "hide":
        conditions.append("is_adult = 0")
    elif adult_filter == "only_adult":
        conditions.append("is_adult = 1")

    if isinstance(currency, str) and currency.strip() and currency.strip() != "all":
        conditions.append("UPPER(currency) = UPPER(?)")
        params.append(currency.strip())

    if min_commission is not None and isinstance(min_commission, (int, float)) and float(min_commission) > 0:
        conditions.append("commission_value >= ?")
        params.append(float(min_commission))
    elif isinstance(min_commission, str) and min_commission.strip():
        try:
            val = float(min_commission.strip())
            if val > 0:
                conditions.append("commission_value >= ?")
                params.append(val)
        except ValueError:
            pass

    if cookie_days is not None:
        if isinstance(cookie_days, (int, float)):
            conditions.append("cookie_days = ?")
            params.append(int(cookie_days))
        elif isinstance(cookie_days, str):
            c_str = cookie_days.strip().lower()
            if c_str.isdigit():
                conditions.append("cookie_days = ?")
                params.append(int(c_str))
            elif c_str in ["lt_14", "<14", "< 14"]:
                # Dưới 14 ngày (1d, 7d, etc.)
                conditions.append("cookie_days < 14")
            elif c_str in ["14_30", "14-30", "14_to_30", "14_to_30_days"]:
                # Từ 14 đến 30 ngày (14, 15, 20, 30 ngày)
                conditions.append("(cookie_days >= 14 AND cookie_days <= 30)")
            elif c_str in ["gte_30", "30+", ">=30", ">= 30"]:
                # Từ 30 ngày trở lên (30, 45, 60, 90, 180, 365 ngày)
                conditions.append("cookie_days >= 30")
            elif c_str in ["gte_14", "14+", ">=14", ">= 14"]:
                # Từ 14 ngày trở lên (toàn bộ nhóm cookie chuẩn)
                conditions.append("cookie_days >= 14")
            elif c_str in ["eq_14", "=14"]:
                conditions.append("cookie_days = 14")
            elif c_str in ["eq_30", "=30"]:
                conditions.append("cookie_days = 30")

    if min_traffic is not None and isinstance(min_traffic, (int, float)) and int(min_traffic) > 0:
        conditions.append("traffic_raw_value >= ?")
        params.append(int(min_traffic))
    elif isinstance(min_traffic, str) and min_traffic.strip():
        try:
            val = int(min_traffic.strip())
            if val > 0:
                conditions.append("traffic_raw_value >= ?")
                params.append(val)
        except ValueError:
            pass

    if isinstance(traffic_status, str) and traffic_status.strip() and traffic_status.strip() != "all":
        ts = traffic_status.strip().lower()
        if ts == "has_data":
            conditions.append("(traffic_status = 'success' OR traffic_raw_value > 0 OR trend_status = 'success')")
        elif ts == "no_data":
            conditions.append("((traffic_status = 'no_data' OR trend_status = 'no_data') AND (traffic_status != 'success' AND trend_status != 'success' AND (traffic_raw_value IS NULL OR traffic_raw_value = 0)))")
        elif ts == "pending":
            conditions.append("(traffic_status = 'pending' OR traffic_status IS NULL OR traffic_status = '' OR trend_status = 'pending')")
        elif ts in ["success", "error"]:
            conditions.append("(traffic_status = ? OR trend_status = ?)")
            params.extend([ts, ts])

    # Trend Month & Seasonality filtering
    month_val = None
    if trend_month is not None and str(trend_month).strip() and str(trend_month).strip() != "all":
        try:
            m = int(str(trend_month).strip())
            if 1 <= m <= 12:
                month_val = m
        except ValueError:
            pass

    score_val = None
    if trend_min_score is not None and str(trend_min_score).strip() and str(trend_min_score).strip() != "all":
        try:
            s = int(str(trend_min_score).strip())
            if s > 0:
                score_val = s
        except ValueError:
            pass

    peak_only = trend_peak_only is True or (isinstance(trend_peak_only, str) and trend_peak_only.strip().lower() in ("true", "1"))
    growth_only = trend_growth_only is True or (isinstance(trend_growth_only, str) and trend_growth_only.strip().lower() in ("true", "1"))
    steady_only = trend_steady_only is True or (isinstance(trend_steady_only, str) and trend_steady_only.strip().lower() in ("true", "1"))

    if steady_only:
        conditions.append("(trend_status = 'success' AND trend_is_steady = 1)")

    if month_val is not None:
        month_suffix = f"-{month_val:02d}"
        prev_month = 12 if month_val == 1 else month_val - 1
        prev_month_suffix = f"-{prev_month:02d}"

        if peak_only:
            conditions.append("(trend_status = 'success' AND trend_peak_month LIKE ?)")
            params.append(f"%{month_suffix}%")
        elif score_val is not None:
            conditions.append("""
                (trend_status = 'success' AND EXISTS (
                    SELECT 1 FROM json_each(stores.trend_timeline_json)
                    WHERE json_extract(value, '$.month') LIKE ?
                      AND CAST(json_extract(value, '$.value') AS INTEGER) >= ?
                ))
            """)
            params.extend([f"%{month_suffix}", score_val])
        elif steady_only:
            # Steady only with specific month: ensure store has active search interest in that month (non-zero)
            conditions.append("""
                (trend_status = 'success' AND EXISTS (
                    SELECT 1 FROM json_each(stores.trend_timeline_json)
                    WHERE json_extract(value, '$.month') LIKE ?
                      AND CAST(json_extract(value, '$.value') AS INTEGER) > 0
                ))
            """)
            params.append(f"%{month_suffix}")
        else:
            # Default when month is selected: store has peak in this month OR score in this month >= 30
            conditions.append("""
                (trend_status = 'success' AND (
                    trend_peak_month LIKE ?
                    OR EXISTS (
                        SELECT 1 FROM json_each(stores.trend_timeline_json)
                        WHERE json_extract(value, '$.month') LIKE ?
                          AND CAST(json_extract(value, '$.value') AS INTEGER) >= 30
                    )
                ))
            """)
            params.extend([f"%{month_suffix}%", f"%{month_suffix}"])

        if growth_only:
            conditions.append(f"""
                (trend_status = 'success' AND (
                    COALESCE((SELECT CAST(json_extract(value, '$.value') AS INTEGER) FROM json_each(stores.trend_timeline_json) WHERE json_extract(value, '$.month') LIKE '%{month_suffix}' ORDER BY json_extract(value, '$.month') DESC LIMIT 1), 0) >
                    COALESCE((SELECT CAST(json_extract(value, '$.value') AS INTEGER) FROM json_each(stores.trend_timeline_json) WHERE json_extract(value, '$.month') LIKE '%{prev_month_suffix}' ORDER BY json_extract(value, '$.month') DESC LIMIT 1), 0)
                ))
            """)
    else:
        if peak_only:
            conditions.append("(trend_status = 'success' AND trend_peak_month != '')")
        if score_val is not None:
            conditions.append("""
                (trend_status = 'success' AND EXISTS (
                    SELECT 1 FROM json_each(stores.trend_timeline_json)
                    WHERE CAST(json_extract(value, '$.value') AS INTEGER) >= ?
                ))
            """)
            params.append(score_val)
        if growth_only:
            conditions.append("""
                (trend_status = 'success' AND (
                    COALESCE((SELECT CAST(json_extract(value, '$.value') AS INTEGER) FROM json_each(stores.trend_timeline_json) ORDER BY json_extract(value, '$.month') DESC LIMIT 1), 0) >
                    COALESCE((SELECT CAST(json_extract(value, '$.value') AS INTEGER) FROM json_each(stores.trend_timeline_json) ORDER BY json_extract(value, '$.month') DESC LIMIT 1 OFFSET 1), 0)
                ))
            """)

    if isinstance(notes_filter, str):
        if notes_filter == "has_notes":
            conditions.append("(notes IS NOT NULL AND TRIM(notes) != '')")
        elif notes_filter == "no_notes":
            conditions.append("(notes IS NULL OR TRIM(notes) = '')")

    if favorite_only is True or (isinstance(favorite_only, str) and favorite_only.strip().lower() in ("true", "1")):
        conditions.append("is_favorite = 1")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Count total matching
    count_sql = f"SELECT COUNT(*) as total FROM stores {where_clause}"
    cursor.execute(count_sql, params)
    total_count = cursor.fetchone()["total"]

    # Allowed sorting fields
    safe_sort_col = "commission_value"
    if isinstance(sort_by, str) and sort_by in ["name", "commission_value", "cookie_days", "currency", "notes", "crawled_at", "updated_at", "traffic_raw_value", "trend_is_steady", "traffic_global_rank", "traffic_source"]:
        safe_sort_col = sort_by

    safe_order = "DESC"
    if isinstance(sort_order, str) and sort_order.lower() == "asc":
        safe_order = "ASC"

    safe_limit = limit if isinstance(limit, int) else 100
    safe_offset = offset if isinstance(offset, int) else 0

    query_sql = f"""
    SELECT * FROM stores
    {where_clause}
    ORDER BY {safe_sort_col} {safe_order}, name ASC
    LIMIT ? OFFSET ?
    """
    cursor.execute(query_sql, params + [safe_limit, safe_offset])
    stores = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "stores": stores
    }


def get_categories() -> List[str]:
    """Return all unique store categories."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM stores WHERE category != '' ORDER BY category ASC")
    cats = [r["category"] for r in cursor.fetchall()]
    conn.close()
    return cats


def get_traffic_stats() -> Dict[str, Any]:
    """Summary statistics for store traffic and Google Trends enrichment."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 14")
    total_cookie_14 = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 14 AND traffic_status IN ('success', 'no_data', 'error')")
    checked_cookie_14 = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 14 AND trend_status IN ('success', 'no_data')")
    trend_checked_cookie_14 = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_raw_value >= 10000 AND trend_status IN ('success', 'no_data')")
    trend_10k_done = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores")
    total_stores = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_status IN ('success', 'no_data', 'error')")
    total_traffic_checked = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_status = 'success' OR trend_status = 'success'")
    with_data = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_status = 'no_data' AND (trend_status = 'no_data' OR trend_status IS NULL OR trend_status = '' OR trend_status = 'pending')")
    no_data = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_status = 'error' OR trend_status = 'error'")
    errors = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_raw_value >= 10000")
    above_10k = cursor.fetchone()["cnt"] or 0

    conn.close()
    return {
        "total_cookie_14_plus": total_cookie_14,
        "checked_cookie_14_plus": checked_cookie_14,
        "remaining_cookie_14_plus": max(0, total_cookie_14 - checked_cookie_14),
        "trend_checked_cookie_14": trend_checked_cookie_14,
        "trend_10k_done": trend_10k_done,
        "total_stores": total_stores,
        "total_traffic_checked": total_traffic_checked,
        "with_data": with_data,
        "no_data": no_data,
        "errors": errors,
        "above_10k": above_10k
    }


def update_store_categorization(
    store_id: str,
    primary_category: str,
    categories_json: str,
    site_title: str,
    site_description: str,
    is_adult: int
) -> bool:
    """Update store category and scraped website metadata."""
    conn = get_db()
    cursor = conn.cursor()
    cat_to_save = str(primary_category or "General").strip()
    if cat_to_save == "Home & Kitchen":
        cat_to_save = "Home, Living & Decor"
    cursor.execute("""
    UPDATE stores SET
        category = ?,
        categories_json = ?,
        site_title = ?,
        site_description = ?,
        is_adult = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE store_id = ?
    """, (
        cat_to_save,
        str(categories_json or "[]"),
        str(site_title or ""),
        str(site_description or ""),
        int(is_adult or 0),
        store_id
    ))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def update_store_traffic_and_trends(store_id: str, data: Dict[str, Any]) -> bool:
    """Update store traffic, Similarweb metrics, and Google Trends data."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE stores SET
        traffic_visits = CASE WHEN ? != '' THEN ? ELSE traffic_visits END,
        traffic_raw_value = CASE WHEN ? > 0 THEN ? ELSE traffic_raw_value END,
        traffic_status = CASE WHEN ? NOT IN ('pending', '') THEN ? ELSE traffic_status END,
        traffic_top_country = COALESCE(NULLIF(?, ''), traffic_top_country),
        trend_timeline_json = ?,
        trend_peak_month = ?,
        trend_status = ?,
        trend_is_steady = ?,
        traffic_source = COALESCE(NULLIF(?, ''), traffic_source),
        traffic_bounce_rate = COALESCE(NULLIF(?, ''), traffic_bounce_rate),
        traffic_avg_duration = COALESCE(NULLIF(?, ''), traffic_avg_duration),
        traffic_global_rank = CASE WHEN ? > 0 THEN ? ELSE traffic_global_rank END,
        traffic_country_rank = CASE WHEN ? > 0 THEN ? ELSE traffic_country_rank END,
        traffic_pages_per_visit = COALESCE(NULLIF(?, ''), traffic_pages_per_visit),
        traffic_updated_at = CURRENT_TIMESTAMP
    WHERE store_id = ?
    """, (
        str(data.get("traffic_visits", "")),
        int(data.get("traffic_raw_value", 0)),
        str(data.get("traffic_status", "pending")),
        str(data.get("traffic_top_country", "")),
        str(data.get("trend_timeline_json", "")),
        str(data.get("trend_peak_month", "")),
        str(data.get("trend_status", "pending")),
        int(data.get("trend_is_steady", 0)),
        str(data.get("traffic_source", "")),
        str(data.get("traffic_bounce_rate", "")),
        str(data.get("traffic_avg_duration", "")),
        int(data.get("traffic_global_rank", 0)),
        int(data.get("traffic_global_rank", 0)),
        int(data.get("traffic_country_rank", 0)),
        int(data.get("traffic_country_rank", 0)),
        str(data.get("traffic_pages_per_visit", "")),
        store_id
    ))
    conn.commit()
    conn.close()
    return True


def get_stores_for_traffic_enrichment(limit: int = 50, cookie_min_days: int = 14) -> List[Dict[str, Any]]:
    """Get stores with cookie_days >= cookie_min_days that haven't been checked for traffic yet."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT store_id, name, website_url, cookie_days, commission_value, category, currency, status, 
           traffic_status, trend_status, trend_timeline_json, trend_peak_month, trend_is_steady, site_description
    FROM stores
    WHERE cookie_days >= ? AND (traffic_status IS NULL OR traffic_status = 'pending' OR traffic_status = '')
    ORDER BY cookie_days DESC, commission_value DESC
    LIMIT ?
    """, (cookie_min_days, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_stores_for_trend_enrichment(
    limit: int = 50,
    cookie_min_days: int = 14,
    min_traffic: int = 0
) -> List[Dict[str, Any]]:
    """Get stores with cookie_days >= cookie_min_days that have traffic checked but Google Trends is still pending."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT store_id, name, website_url, cookie_days, commission_value, category, currency, status, 
           traffic_visits, traffic_raw_value, traffic_status, trend_status, trend_timeline_json, trend_peak_month, trend_is_steady, site_description
    FROM stores
    WHERE cookie_days >= ? 
      AND (trend_status IS NULL OR trend_status IN ('pending', '', 'error'))
      AND COALESCE(traffic_raw_value, 0) >= ?
    ORDER BY COALESCE(traffic_raw_value, 0) DESC, cookie_days DESC, commission_value DESC
    LIMIT ?
    """, (cookie_min_days, min_traffic, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_traffic_cv_stats() -> Dict[str, Any]:
    """Summary statistics for Traffic.cv Similarweb enrichment."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 14")
    total_cookie_14 = cursor.fetchone()["cnt"] or 0

    # Total processed stores in cookie >= 14 (either Traffic.cv or Tranco fallback)
    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 14 AND traffic_source != '' AND traffic_source IS NOT NULL")
    enriched_cookie_14 = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 14 AND traffic_source = 'traffic_cv'")
    similarweb_cookie_14 = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 14 AND traffic_source = 'tranco'")
    tranco_cookie_14 = cursor.fetchone()["cnt"] or 0

    # Cookie >= 7 days stats
    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 7")
    total_cookie_7 = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 7 AND traffic_source != '' AND traffic_source IS NOT NULL")
    enriched_cookie_7 = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores")
    total_stores = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_source != '' AND traffic_source IS NOT NULL")
    total_processed = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_source = 'traffic_cv'")
    total_enriched = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_source = 'tranco'")
    total_tranco = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_source = 'traffic_cv' AND traffic_raw_value > 0")
    with_data = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_source = 'traffic_cv' AND traffic_status = 'no_data'")
    no_data = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_source IN ('traffic_cv', 'traffic_cv_error') AND traffic_status = 'error'")
    errors = cursor.fetchone()["cnt"] or 0

    conn.close()
    return {
        "total_cookie_14": total_cookie_14,
        "enriched_cookie_14": enriched_cookie_14,
        "similarweb_cookie_14": similarweb_cookie_14,
        "tranco_cookie_14": tranco_cookie_14,
        "remaining_cookie_14": max(0, total_cookie_14 - enriched_cookie_14),
        "percent_cookie_14": round((enriched_cookie_14 / total_cookie_14 * 100), 1) if total_cookie_14 > 0 else 0.0,
        "cookie_7_stats": {
            "total": total_cookie_7,
            "enriched": enriched_cookie_7,
            "remaining": max(0, total_cookie_7 - enriched_cookie_7),
            "percent": round((enriched_cookie_7 / total_cookie_7 * 100), 1) if total_cookie_7 > 0 else 0.0,
        },
        "total_stores": total_stores,
        "total_processed": total_processed,
        "total_enriched": total_enriched,
        "total_tranco": total_tranco,
        "with_data": with_data,
        "no_data": no_data,
        "errors": errors,
    }


def get_stores_for_traffic_cv_enrichment(
    limit: int = 50,
    cookie_min_days: int = 14,
    exclude_store_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Fetch stores that have not yet been enriched by Traffic.cv or fallback (traffic_source IS NULL OR traffic_source = '').
    Prioritizes stores with cookie_days >= cookie_min_days (descending cookie_days, commission_value).
    If all stores with cookie_days >= cookie_min_days are enriched, falls back to remaining stores.
    Supports exclude_store_ids to prevent re-querying in-flight records.
    """
    conn = get_db()
    cursor = conn.cursor()

    exclude_clause = ""
    params: List[Any] = [cookie_min_days]
    if exclude_store_ids:
        placeholders = ",".join(["?"] * len(exclude_store_ids))
        exclude_clause = f"AND store_id NOT IN ({placeholders})"
        params.extend(exclude_store_ids)

    query_priority = f"""
    SELECT store_id, name, website_url, portal_url, cookie_days, commission_value, category, currency, status, 
           traffic_visits, traffic_raw_value, traffic_status, traffic_source, traffic_global_rank
    FROM stores
    WHERE cookie_days >= ? AND (traffic_source IS NULL OR traffic_source = '')
    {exclude_clause}
    ORDER BY cookie_days DESC, commission_value DESC
    LIMIT ?
    """
    cursor.execute(query_priority, params + [limit])
    rows = [dict(r) for r in cursor.fetchall()]

    if not rows and cookie_min_days > 0:
        params_all: List[Any] = []
        if exclude_store_ids:
            placeholders = ",".join(["?"] * len(exclude_store_ids))
            exclude_clause_all = f"AND store_id NOT IN ({placeholders})"
            params_all.extend(exclude_store_ids)
        else:
            exclude_clause_all = ""

        query_all = f"""
        SELECT store_id, name, website_url, portal_url, cookie_days, commission_value, category, currency, status, 
               traffic_visits, traffic_raw_value, traffic_status, traffic_source, traffic_global_rank
        FROM stores
        WHERE (traffic_source IS NULL OR traffic_source = '')
        {exclude_clause_all}
        ORDER BY cookie_days DESC, commission_value DESC
        LIMIT ?
        """
        cursor.execute(query_all, params_all + [limit])
        rows = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return rows


def update_store_traffic_cv(store_id: str, data: Dict[str, Any]) -> bool:
    """Update store with Similarweb data extracted from Traffic.cv or fallback."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE stores SET
        traffic_visits = ?,
        traffic_raw_value = ?,
        traffic_status = ?,
        traffic_source = ?,
        traffic_bounce_rate = ?,
        traffic_avg_duration = ?,
        traffic_global_rank = ?,
        traffic_country_rank = ?,
        traffic_pages_per_visit = ?,
        traffic_updated_at = CURRENT_TIMESTAMP
    WHERE store_id = ?
    """, (
        str(data.get("traffic_visits", "")),
        int(data.get("traffic_raw_value", 0)),
        str(data.get("traffic_status", "pending")),
        str(data.get("traffic_source", "traffic_cv")),
        str(data.get("traffic_bounce_rate", "")),
        str(data.get("traffic_avg_duration", "")),
        int(data.get("traffic_global_rank", 0)),
        int(data.get("traffic_country_rank", 0)),
        str(data.get("traffic_pages_per_visit", "")),
        store_id
    ))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def get_stats() -> Dict[str, Any]:
    """Compute dashboard statistics."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total, AVG(commission_value) as avg_comm, MAX(commission_value) as max_comm FROM stores")
    row = cursor.fetchone()
    total_stores = row["total"] or 0
    avg_comm = round(row["avg_comm"] or 0.0, 1)
    max_comm = round(row["max_comm"] or 0.0, 1)

    cursor.execute("SELECT COUNT(*) as total_fav FROM stores WHERE is_favorite = 1")
    total_fav = cursor.fetchone()["total_fav"] or 0

    cursor.execute("SELECT category, COUNT(*) as cnt FROM stores WHERE category != '' GROUP BY category ORDER BY cnt DESC")
    all_categories = [{"category": r["category"], "count": r["cnt"]} for r in cursor.fetchall()]
    top_categories = all_categories[:5]

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE is_adult = 1")
    adult_count = cursor.fetchone()["cnt"] or 0

    # Currencies with store counts
    cursor.execute("SELECT currency, COUNT(*) as cnt FROM stores WHERE currency != '' GROUP BY currency ORDER BY cnt DESC")
    currencies = [{"currency": r["currency"], "count": r["cnt"]} for r in cursor.fetchall()]

    # Cookie days with store counts
    cursor.execute("SELECT cookie_days, COUNT(*) as cnt FROM stores WHERE cookie_days IS NOT NULL GROUP BY cookie_days ORDER BY cookie_days ASC")
    cookie_durations = [{"days": r["cookie_days"], "count": r["cnt"]} for r in cursor.fetchall()]

    # Concise Cookie groups
    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days < 14")
    c_lt_14 = cursor.fetchone()["cnt"] or 0
    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 14 AND cookie_days <= 30")
    c_14_30 = cursor.fetchone()["cnt"] or 0
    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 30")
    c_gte_30 = cursor.fetchone()["cnt"] or 0
    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE cookie_days >= 14")
    c_gte_14 = cursor.fetchone()["cnt"] or 0

    conn.close()

    traffic_stats = get_traffic_stats()
    traffic_cv_stats = get_traffic_cv_stats()

    return {
        "total_stores": total_stores,
        "avg_commission": avg_comm,
        "max_commission": max_comm,
        "total_favorites": total_fav,
        "top_categories": top_categories,
        "categories": all_categories,
        "adult_count": adult_count,
        "currencies": currencies,
        "cookie_durations": cookie_durations,
        "cookie_groups": {
            "lt_14": c_lt_14,
            "14_30": c_14_30,
            "gte_30": c_gte_30,
            "gte_14": c_gte_14
        },
        "traffic": traffic_stats,
        "traffic_cv": traffic_cv_stats
    }


def toggle_favorite(store_id: str) -> bool:
    """Toggle star/favorite status."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE stores SET is_favorite = 1 - is_favorite, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?", (store_id,))
    cursor.execute("SELECT is_favorite FROM stores WHERE store_id = ?", (store_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    return bool(row["is_favorite"]) if row else False


def update_store_note(store_id: str, note: str, status: Optional[str] = None) -> bool:
    """Update user note and status on store."""
    conn = get_db()
    cursor = conn.cursor()
    if status:
        cursor.execute("UPDATE stores SET notes = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?", (note, status, store_id))
    else:
        cursor.execute("UPDATE stores SET notes = ?, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?", (note, store_id))
    conn.commit()
    conn.close()
    return True


def update_crawl_job(job_id: str, **kwargs):
    """Update or insert crawl job progress."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT job_id FROM crawl_jobs WHERE job_id = ?", (job_id,))
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO crawl_jobs (job_id, status, current_page, total_pages, total_stores, new_stores, message)
        VALUES (?, 'running', 0, 0, 0, 0, 'Starting crawl...')
        """, (job_id,))

    updates = []
    values = []
    for k, v in kwargs.items():
        if k in ["status", "current_page", "total_pages", "total_stores", "new_stores", "message"]:
            updates.append(f"{k} = ?")
            values.append(v)

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        sql = f"UPDATE crawl_jobs SET {', '.join(updates)} WHERE job_id = ?"
        values.append(job_id)
        cursor.execute(sql, values)

    conn.commit()
    conn.close()


def get_crawl_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve crawl job info."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM crawl_jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def reclassify_all_stores() -> Dict[str, Any]:
    """
    Re-classify all stores in the database using the latest categorizer rules
    without network calls. Blazing fast in-memory NLP and batched SQLite transaction.
    """
    from .categorizer import classify_store

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT store_id, name, site_title, site_description, website_url, category, categories_json, is_adult FROM stores"
    )
    rows = cursor.fetchall()

    updates = []
    category_counts: Dict[str, int] = {}
    decor_matched_count = 0

    for r in rows:
        sid = r["store_id"]
        name = r["name"] or ""
        title = r["site_title"] or ""
        desc = r["site_description"] or ""
        url = r["website_url"] or ""
        old_cat = r["category"] or ""
        old_cats_json = r["categories_json"] or "[]"
        old_adult = int(r["is_adult"] or 0)

        res = classify_store(title=title, description=desc, keywords="", name=name, url=url)
        new_cat = res["primary_category"]
        new_cats_json = json.dumps(res["categories"])
        new_adult = int(res["is_adult"])

        category_counts[new_cat] = category_counts.get(new_cat, 0) + 1
        if new_cat == "Home, Living & Decor":
            decor_matched_count += 1

        if new_cat != old_cat or new_cats_json != old_cats_json or new_adult != old_adult:
            updates.append((new_cat, new_cats_json, new_adult, sid))

    if updates:
        cursor.executemany(
            "UPDATE stores SET category = ?, categories_json = ?, is_adult = ?, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?",
            updates
        )
        conn.commit()

    conn.close()

    return {
        "status": "success",
        "total_stores": len(rows),
        "updated_stores": len(updates),
        "decor_stores_total": decor_matched_count,
        "category_counts": category_counts,
    }

