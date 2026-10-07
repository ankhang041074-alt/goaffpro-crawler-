import io
import uuid
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse, StreamingResponse
from pydantic import BaseModel
import pandas as pd

from . import db
from . import crawler
from . import traffic_worker

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="GoAffPro Store Hunter & CRM API",
    description="Backend API for crawling and managing GoAffPro affiliate stores",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    db.init_db()
    print("[GoAffPro API] Database initialized.")


class OpenBrowserRequest(BaseModel):
    url: Optional[str] = "https://goaffpro.com/login"


class StartCrawlRequest(BaseModel):
    max_pages: Optional[int] = 50
    start_url: Optional[str] = "https://goaffpro.com/login"


class UpdateNoteRequest(BaseModel):
    note: str
    status: Optional[str] = None


@app.get("/api/status")
def get_system_status():
    """Return health check and local profile state."""
    profile_dir = crawler.get_profile_dir()
    stats = db.get_stats()
    return {
        "status": "online",
        "has_profile": profile_dir.exists(),
        "profile_dir": str(profile_dir),
        "stats": stats
    }


@app.post("/api/browser/open")
def open_browser(req: OpenBrowserRequest):
    """Launch persistent browser context for user login."""
    target_url = (req.url or "https://goaffpro.com/login").strip()
    if "goaffpro.com/stores" in target_url.lower() and "affiliate" not in target_url.lower():
        target_url = "https://goaffpro.com/login"
    res = crawler.open_login_window(url=target_url)
    return res


@app.post("/api/crawl/start")
def start_crawl(req: StartCrawlRequest):
    """Start background crawl task."""
    job_id = str(uuid.uuid4())[:8]
    start_url = req.start_url or "https://goaffpro.com/login"
    if "goaffpro.com/stores" in start_url.lower() and "affiliate" not in start_url.lower():
        start_url = "https://goaffpro.com/login"
    crawler.start_background_crawl(
        job_id=job_id,
        max_pages=req.max_pages or 50,
        start_url=start_url
    )
    return {
        "job_id": job_id,
        "status": "started",
        "max_pages": req.max_pages,
        "message": "Tiến trình cào GoAffPro đã được khởi chạy trong nền!"
    }


@app.get("/api/crawl/job/{job_id}")
def get_crawl_progress(job_id: str):
    """Poll progress of a specific crawl job."""
    job = db.get_crawl_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return job


@app.get("/api/stores")
def get_stores_endpoint(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    min_commission: Optional[float] = Query(None),
    cookie_days: Optional[str] = Query(None),
    min_traffic: Optional[str] = Query(None),
    traffic_status: Optional[str] = Query(None),
    trend_month: Optional[str] = Query(None),
    trend_min_score: Optional[str] = Query(None),
    trend_peak_only: bool = Query(False),
    trend_growth_only: bool = Query(False),
    adult_filter: Optional[str] = Query("hide"),
    notes_filter: Optional[str] = Query(None),
    favorite_only: bool = Query(False),
    sort_by: str = Query("commission_value"),
    sort_order: str = Query("desc"),
    limit: int = Query(100),
    offset: int = Query(0)
):
    """Query stores with filtering, searching, and pagination."""
    # Convert cookie_days to int if it's not empty
    cookie_days_val = None
    if isinstance(cookie_days, int):
        cookie_days_val = cookie_days
    elif isinstance(cookie_days, str) and cookie_days.strip() and cookie_days.strip() != "all":
        try:
            cookie_days_val = int(cookie_days.strip())
        except ValueError:
            pass

    # Convert min_traffic to int if it's not empty
    min_traffic_val = None
    if isinstance(min_traffic, int):
        min_traffic_val = min_traffic
    elif isinstance(min_traffic, str) and min_traffic.strip() and min_traffic.strip() != "all":
        try:
            min_traffic_val = int(min_traffic.strip())
        except ValueError:
            pass

    # Convert trend_min_score to int if present
    trend_min_score_val = None
    if isinstance(trend_min_score, int):
        trend_min_score_val = trend_min_score
    elif isinstance(trend_min_score, str) and trend_min_score.strip() and trend_min_score.strip() != "all":
        try:
            trend_min_score_val = int(trend_min_score.strip())
        except ValueError:
            pass

    return db.get_stores(
        search=search,
        category=category,
        currency=currency,
        min_commission=min_commission,
        cookie_days=cookie_days_val,
        min_traffic=min_traffic_val,
        traffic_status=traffic_status,
        trend_month=trend_month,
        trend_min_score=trend_min_score_val,
        trend_peak_only=trend_peak_only,
        trend_growth_only=trend_growth_only,
        adult_filter=adult_filter,
        notes_filter=notes_filter,
        favorite_only=favorite_only,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset
    )


@app.get("/api/categories")
def get_categories_endpoint():
    """Retrieve distinct category list."""
    return {"categories": db.get_categories()}


@app.get("/api/stats")
def get_stats_endpoint():
    """Retrieve aggregate summary stats."""
    return db.get_stats()


@app.post("/api/stores/{store_id}/favorite")
def toggle_favorite_endpoint(store_id: str):
    """Toggle star/favorite on a store."""
    fav = db.toggle_favorite(store_id)
    return {"store_id": store_id, "is_favorite": fav}


@app.post("/api/stores/{store_id}/note")
def update_store_note_endpoint(store_id: str, req: UpdateNoteRequest):
    """Update notes and status for a store."""
    db.update_store_note(store_id, note=req.note, status=req.status)
    return {"store_id": store_id, "notes": req.note, "status": req.status}


@app.delete("/api/stores/{store_id}")
def delete_store_endpoint(store_id: str):
    """Delete a single store."""
    deleted = db.delete_store(store_id)
    return {"store_id": store_id, "deleted": deleted}


@app.delete("/api/stores/currency/{currency}")
def delete_stores_by_currency_endpoint(currency: str):
    """Delete all stores with given currency (e.g. INR)."""
    count = db.delete_stores_by_currency(currency)
    return {"currency": currency, "deleted_count": count}


@app.delete("/api/stores/purge-indian")
def purge_indian_stores_endpoint():
    """Purge all stores with Indian/subcontinent currencies or .in domains."""
    count = db.delete_indian_and_subcontinent_stores()
    return {"status": "success", "deleted_count": count}



@app.get("/api/export/csv")
def export_csv_endpoint(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    min_commission: Optional[float] = Query(None),
    cookie_days: Optional[str] = Query(None),
    min_traffic: Optional[str] = Query(None),
    traffic_status: Optional[str] = Query(None),
    trend_month: Optional[str] = Query(None),
    trend_min_score: Optional[str] = Query(None),
    trend_peak_only: bool = Query(False),
    trend_growth_only: bool = Query(False),
    adult_filter: Optional[str] = Query("hide"),
    notes_filter: Optional[str] = Query(None),
    favorite_only: bool = Query(False)
):
    """Export filtered stores to CSV."""
    cookie_days_val = None
    if isinstance(cookie_days, int):
        cookie_days_val = cookie_days
    elif isinstance(cookie_days, str) and cookie_days.strip() and cookie_days.strip() != "all":
        try:
            cookie_days_val = int(cookie_days.strip())
        except ValueError:
            pass

    min_traffic_val = None
    if isinstance(min_traffic, int):
        min_traffic_val = min_traffic
    elif isinstance(min_traffic, str) and min_traffic.strip() and min_traffic.strip() != "all":
        try:
            min_traffic_val = int(min_traffic.strip())
        except ValueError:
            pass

    trend_min_score_val = None
    if isinstance(trend_min_score, int):
        trend_min_score_val = trend_min_score
    elif isinstance(trend_min_score, str) and trend_min_score.strip() and trend_min_score.strip() != "all":
        try:
            trend_min_score_val = int(trend_min_score.strip())
        except ValueError:
            pass

    data = db.get_stores(
        search=search,
        category=category,
        currency=currency,
        min_commission=min_commission,
        cookie_days=cookie_days_val,
        min_traffic=min_traffic_val,
        traffic_status=traffic_status,
        trend_month=trend_month,
        trend_min_score=trend_min_score_val,
        trend_peak_only=trend_peak_only,
        trend_growth_only=trend_growth_only,
        adult_filter=adult_filter,
        notes_filter=notes_filter,
        favorite_only=favorite_only,
        limit=100000,
        offset=0
    )
    df = pd.DataFrame(data["stores"])
    if df.empty:
        df = pd.DataFrame(columns=["name", "website_url", "currency", "commission_rate", "cookie_days", "category", "site_title", "site_description", "traffic_visits", "trend_peak_month"])

    # Select and order user-friendly columns
    export_cols = [c for c in [
        "name", "website_url", "portal_url", "currency", "commission_rate",
        "commission_value", "cookie_days", "category", "site_title", "site_description",
        "traffic_visits", "traffic_status", "trend_peak_month", "instant_access", "notes", "crawled_at"
    ] if c in df.columns]
    df = df[export_cols]

    csv_data = df.to_csv(index=False)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=goaffpro_stores.csv"}
    )


@app.get("/api/export/excel")
def export_excel_endpoint(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    min_commission: Optional[float] = Query(None),
    cookie_days: Optional[str] = Query(None),
    min_traffic: Optional[str] = Query(None),
    traffic_status: Optional[str] = Query(None),
    trend_month: Optional[str] = Query(None),
    trend_min_score: Optional[str] = Query(None),
    trend_peak_only: bool = Query(False),
    trend_growth_only: bool = Query(False),
    adult_filter: Optional[str] = Query("hide"),
    notes_filter: Optional[str] = Query(None),
    favorite_only: bool = Query(False)
):
    """Export filtered stores to Excel .xlsx format."""
    cookie_days_val = None
    if isinstance(cookie_days, int):
        cookie_days_val = cookie_days
    elif isinstance(cookie_days, str) and cookie_days.strip() and cookie_days.strip() != "all":
        try:
            cookie_days_val = int(cookie_days.strip())
        except ValueError:
            pass

    min_traffic_val = None
    if isinstance(min_traffic, int):
        min_traffic_val = min_traffic
    elif isinstance(min_traffic, str) and min_traffic.strip() and min_traffic.strip() != "all":
        try:
            min_traffic_val = int(min_traffic.strip())
        except ValueError:
            pass

    trend_min_score_val = None
    if isinstance(trend_min_score, int):
        trend_min_score_val = trend_min_score
    elif isinstance(trend_min_score, str) and trend_min_score.strip() and trend_min_score.strip() != "all":
        try:
            trend_min_score_val = int(trend_min_score.strip())
        except ValueError:
            pass

    data = db.get_stores(
        search=search,
        category=category,
        currency=currency,
        min_commission=min_commission,
        cookie_days=cookie_days_val,
        min_traffic=min_traffic_val,
        traffic_status=traffic_status,
        trend_month=trend_month,
        trend_min_score=trend_min_score_val,
        trend_peak_only=trend_peak_only,
        trend_growth_only=trend_growth_only,
        adult_filter=adult_filter,
        notes_filter=notes_filter,
        favorite_only=favorite_only,
        limit=100000,
        offset=0
    )
    df = pd.DataFrame(data["stores"])
    if df.empty:
        df = pd.DataFrame(columns=["name", "website_url", "currency", "commission_rate", "cookie_days", "category", "site_title", "site_description", "traffic_visits", "trend_peak_month"])

    export_cols = [c for c in [
        "name", "website_url", "portal_url", "currency", "commission_rate",
        "commission_value", "cookie_days", "category", "site_title", "site_description",
        "traffic_visits", "traffic_status", "trend_peak_month", "instant_access", "notes", "crawled_at"
    ] if c in df.columns]
    df = df[export_cols]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="GoAffPro Stores")
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=goaffpro_stores.xlsx"}
    )


@app.post("/api/traffic/start")
def start_traffic_worker_endpoint():
    """Start or resume background traffic & Google Trends enrichment."""
    return traffic_worker.worker.start()


@app.post("/api/traffic/pause")
def pause_traffic_worker_endpoint():
    """Pause background traffic enrichment."""
    return traffic_worker.worker.pause()


@app.post("/api/traffic/resume")
def resume_traffic_worker_endpoint():
    """Resume background traffic enrichment."""
    return traffic_worker.worker.resume()


@app.post("/api/traffic/stop")
def stop_traffic_worker_endpoint():
    """Stop background traffic enrichment."""
    return traffic_worker.worker.stop()


@app.get("/api/traffic/status")
def get_traffic_status_endpoint():
    """Get current status and progress of the traffic worker."""
    return traffic_worker.worker.get_status()


@app.post("/api/stores/{store_id}/refresh-traffic")
def refresh_store_traffic_endpoint(store_id: str):
    """Enrich or refresh traffic and Google Trends for a specific store."""
    res = traffic_worker.worker.refresh_single_store(store_id)
    if not res:
        raise HTTPException(status_code=404, detail="Store not found")
    return res
