"""
FastAPI Local Application Server for AI Job Search Agent Dashboard.
Provides interactive REST API for real-time querying, application status tracking,
manual sweep triggering, and serves the mobile-responsive web dashboard.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from database import JobRepository, init_db
from dashboard.exporter import export_to_json

WEB_DIR = BASE_DIR / "web"

app = FastAPI(
    title="AI Job Search Agent Dashboard",
    description="Interactive local dashboard and application tracker for software engineering positions.",
    version="1.0.0"
)

# Enable CORS for local testing and PWA
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StatusUpdateRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


@app.on_event("startup")
def on_startup():
    init_db()


# API Endpoints
@app.get("/api/stats")
def get_stats() -> Dict[str, Any]:
    """Returns database KPIs and portal summary."""
    return JobRepository.get_stats_summary()


@app.get("/api/jobs")
def get_jobs(
    search: str = Query("", description="Keywords to match across titles, companies, skills"),
    source: str = Query("all", description="Job source portal"),
    location: str = Query("all", description="Location / city filter"),
    min_score: int = Query(0, description="Minimum AI match score threshold"),
    user_status: str = Query("all", description="Tracking status (NEW, BOOKMARKED, APPLIED, etc.)"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0)
) -> Dict[str, Any]:
    """Returns paginated and filtered jobs with AI evaluation breakdown."""
    jobs = JobRepository.get_all_jobs_with_evaluations(
        search=search,
        source=source,
        location=location,
        min_score=min_score,
        user_status=user_status,
        limit=limit,
        offset=offset
    )
    return {
        "count": len(jobs),
        "jobs": jobs
    }


@app.post("/api/jobs/{job_id}/status")
def update_job_status(job_id: str, req: StatusUpdateRequest) -> Dict[str, Any]:
    """Updates application tracking status and personal notes for a job."""
    success = JobRepository.update_user_tracking(job_id, status=req.status, notes=req.notes)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {"success": True, "job_id": job_id, "status": req.status, "notes": req.notes}


def _run_sweep_task():
    try:
        from pipeline import JobSearchPipeline
        pipeline = JobSearchPipeline()
        pipeline.run_cycle()
        export_to_json()
    except Exception as e:
        logger.error(f"Error during on-demand sweep: {e}")


@app.post("/api/trigger-sweep")
def trigger_sweep(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Triggers an on-demand job scraping & evaluation sweep in the background."""
    background_tasks.add_task(_run_sweep_task)
    return {"message": "Job search sweep triggered in the background."}


@app.post("/api/export")
def trigger_export() -> Dict[str, Any]:
    """Exports current SQLite database into web/data/jobs.json."""
    path = export_to_json()
    return {"message": "Export completed.", "path": str(path)}


# Serve Static Assets & Main Dashboard App
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/app.js")
    def serve_app_js():
        return FileResponse(WEB_DIR / "app.js", media_type="application/javascript")

    @app.get("/manifest.json")
    def serve_manifest():
        return FileResponse(WEB_DIR / "manifest.json", media_type="application/manifest+json")

    @app.get("/sw.js")
    def serve_sw():
        return FileResponse(WEB_DIR / "sw.js", media_type="application/javascript")

    @app.get("/data/jobs.json")
    def serve_data_json():
        data_file = WEB_DIR / "data" / "jobs.json"
        if not data_file.exists():
            export_to_json()
        return FileResponse(data_file, media_type="application/json")
