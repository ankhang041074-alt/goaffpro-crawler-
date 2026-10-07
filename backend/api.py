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
    start_url: Optional[str] = "https://goaffpro.com/stores"


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
    res = crawler.open_login_window(url=req.url or "https://goaffpro.com/login")
    return res


@app.post("/api/crawl/start")
def start_crawl(req: StartCrawlRequest):
    """Start background crawl task."""
    job_id = str(uuid.uuid4())[:8]
    crawler.start_background_crawl(
        job_id=job_id,
        max_pages=req.max_pages or 50,
        start_url=req.start_url or "https://goaffpro.com/stores"
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
    min_commission: Optional[float] = Query(None),
    favorite_only: bool = Query(False),
    sort_by: str = Query("commission_value"),
    sort_order: str = Query("desc"),
    limit: int = Query(100),
    offset: int = Query(0)
):
    """Query stores with filtering, searching, and pagination."""
    return db.get_stores(
        search=search,
        category=category,
        min_commission=min_commission,
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


@app.get("/api/export/csv")
def export_csv_endpoint(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_commission: Optional[float] = Query(None),
    favorite_only: bool = Query(False)
):
    """Export filtered stores to CSV."""
    data = db.get_stores(
        search=search,
        category=category,
        min_commission=min_commission,
        favorite_only=favorite_only,
        limit=10000,
        offset=0
    )
    df = pd.DataFrame(data["stores"])
    if df.empty:
        df = pd.DataFrame(columns=["name", "website_url", "commission_rate", "cookie_days", "category", "description"])
    
    # Select and order user-friendly columns
    export_cols = [c for c in ["name", "website_url", "portal_url", "commission_rate", "commission_value", "cookie_days", "category", "instant_access", "notes", "crawled_at"] if c in df.columns]
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
    min_commission: Optional[float] = Query(None),
    favorite_only: bool = Query(False)
):
    """Export filtered stores to Excel .xlsx format."""
    data = db.get_stores(
        search=search,
        category=category,
        min_commission=min_commission,
        favorite_only=favorite_only,
        limit=10000,
        offset=0
    )
    df = pd.DataFrame(data["stores"])
    if df.empty:
        df = pd.DataFrame(columns=["name", "website_url", "commission_rate", "cookie_days", "category", "description"])

    export_cols = [c for c in ["name", "website_url", "portal_url", "commission_rate", "commission_value", "cookie_days", "category", "instant_access", "notes", "crawled_at"] if c in df.columns]
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
