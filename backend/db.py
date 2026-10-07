import sqlite3
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
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
        ("traffic_updated_at", "DATETIME DEFAULT NULL"),
    ]
    for col_name, col_type in traffic_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE stores ADD COLUMN {col_name} {col_type}")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_traffic ON stores(traffic_raw_value)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_traffic_status ON stores(traffic_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_trend_status ON stores(trend_status)")

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
    currency = str(store.get("currency") or "USD").strip()
    commission_val = float(store.get("commission_value") or parse_commission_numeric(commission_rate))
    cookie_days = int(store.get("cookie_days") or 30)
    category = str(store.get("category") or "General").strip()
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
        currency = str(store.get("currency") or "USD").strip()
        commission_val = float(store.get("commission_value") or parse_commission_numeric(commission_rate))
        cookie_days = int(store.get("cookie_days") or 30)
        category = str(store.get("category") or "General").strip()
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


def get_stores(
    search: Optional[str] = None,
    category: Optional[str] = None,
    currency: Optional[str] = None,
    min_commission: Optional[float] = None,
    cookie_days: Optional[int] = None,
    min_traffic: Optional[int] = None,
    traffic_status: Optional[str] = None,
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
        term = f"%{search.strip().lower()}%"
        conditions.append("(LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(category) LIKE ? OR LOWER(website_url) LIKE ? OR LOWER(notes) LIKE ?)")
        params.extend([term, term, term, term, term])

    if isinstance(category, str) and category.strip() and category.strip() != "all":
        conditions.append("category = ?")
        params.append(category.strip())

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

    if cookie_days is not None and isinstance(cookie_days, (int, float)):
        conditions.append("cookie_days = ?")
        params.append(int(cookie_days))
    elif isinstance(cookie_days, str) and cookie_days.strip() and cookie_days.strip() != "all":
        try:
            conditions.append("cookie_days = ?")
            params.append(int(cookie_days.strip()))
        except ValueError:
            pass

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
    if isinstance(sort_by, str) and sort_by in ["name", "commission_value", "cookie_days", "currency", "notes", "crawled_at", "updated_at", "traffic_raw_value"]:
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

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_status = 'success' OR trend_status = 'success'")
    with_data = cursor.fetchone()["cnt"] or 0

    cursor.execute("SELECT COUNT(*) as cnt FROM stores WHERE traffic_status = 'no_data' AND (trend_status = 'no_data' OR trend_status IS NULL OR trend_status = '')")
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
        "with_data": with_data,
        "no_data": no_data,
        "errors": errors,
        "above_10k": above_10k
    }


def update_store_traffic_and_trends(store_id: str, data: Dict[str, Any]) -> bool:
    """Update store traffic and Google Trends data."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE stores SET
        traffic_visits = ?,
        traffic_raw_value = ?,
        traffic_status = ?,
        traffic_top_country = ?,
        trend_timeline_json = ?,
        trend_peak_month = ?,
        trend_status = ?,
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
    SELECT store_id, name, website_url, cookie_days, commission_value, category, currency, status
    FROM stores
    WHERE cookie_days >= ? AND (traffic_status IS NULL OR traffic_status = 'pending' OR traffic_status = '')
    ORDER BY cookie_days DESC, commission_value DESC
    LIMIT ?
    """, (cookie_min_days, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


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

    cursor.execute("SELECT category, COUNT(*) as cnt FROM stores GROUP BY category ORDER BY cnt DESC LIMIT 5")
    top_categories = [{"category": r["category"], "count": r["cnt"]} for r in cursor.fetchall()]

    # Currencies with store counts
    cursor.execute("SELECT currency, COUNT(*) as cnt FROM stores WHERE currency != '' GROUP BY currency ORDER BY cnt DESC")
    currencies = [{"currency": r["currency"], "count": r["cnt"]} for r in cursor.fetchall()]

    # Cookie days with store counts
    cursor.execute("SELECT cookie_days, COUNT(*) as cnt FROM stores WHERE cookie_days IS NOT NULL GROUP BY cookie_days ORDER BY cookie_days ASC")
    cookie_durations = [{"days": r["cookie_days"], "count": r["cnt"]} for r in cursor.fetchall()]

    conn.close()

    traffic_stats = get_traffic_stats()

    return {
        "total_stores": total_stores,
        "avg_commission": avg_comm,
        "max_commission": max_comm,
        "total_favorites": total_fav,
        "top_categories": top_categories,
        "currencies": currencies,
        "cookie_durations": cookie_durations,
        "traffic": traffic_stats
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
