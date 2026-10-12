"""
Static Web Data Exporter for AI Job Search Agent Dashboard.
Exports SQLite database records into a lightweight JSON bundle (web/data/jobs.json)
for static hosting on Vercel, GitHub Pages, or offline browser viewing.
"""

import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from loguru import logger
from database import JobRepository, init_db

WEB_DATA_DIR = BASE_DIR / "web" / "data"


def export_to_json(output_file: Path = None) -> Path:
    """Exports all indexed jobs and AI evaluations into a standalone JSON file."""
    init_db()
    target_path = output_file or (WEB_DATA_DIR / "jobs.json")
    target_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Exporting SQLite database records to static dashboard payload...")
    payload = JobRepository.export_dashboard_payload()

    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    total_jobs = payload["meta"]["total_count"]
    logger.info(f"Successfully exported {total_jobs} jobs to {target_path}")
    return target_path


if __name__ == "__main__":
    export_to_json()
