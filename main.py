"""
Command-Line Interface for the AI Job Search Agent.
Provides interactive controls to run sweeps, view matched jobs, test notifications, and run daemon mode.
"""

import argparse
import sys
import os

# Ensure UTF-8 stdout encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from loguru import logger

console = Console(highlight=False)
from database import SessionLocal, JobRecord, JobEvaluationRecord, NotificationRecord, init_db
from pipeline import JobSearchPipeline
from scheduler import start_scheduler
from config import settings

console = Console()

# Optional top-level ASGI app export for Vercel / serverless runners
try:
    from dashboard.app import app
except Exception:
    app = None


def display_stats():
    """Prints a summary table of database records and past matches."""
    init_db()
    with SessionLocal() as session:
        total_jobs = session.query(JobRecord).count()
        total_evals = session.query(JobEvaluationRecord).count()
        total_notified = session.query(NotificationRecord).filter(NotificationRecord.status == "SENT").count()
        high_matches = session.query(JobEvaluationRecord).filter(JobEvaluationRecord.match_score >= settings.min_match_score).count()

        console.print(Panel(
            f"[bold green]AI Job Search Agent Database Statistics[/bold green]\n\n"
            f"• Total Jobs Indexed: [cyan]{total_jobs}[/cyan]\n"
            f"• Jobs Evaluated by AI: [cyan]{total_evals}[/cyan]\n"
            f"• High-Fit Matches (Score >= {settings.min_match_score}%): [bold yellow]{high_matches}[/bold yellow]\n"
            f"• Notifications Delivered: [bold green]{total_notified}[/bold green]",
            title="Database Overview",
            expand=False
        ))


def display_matched_jobs():
    """Displays high-scoring jobs in a structured table."""
    init_db()
    with SessionLocal() as session:
        records = (
            session.query(JobRecord, JobEvaluationRecord)
            .join(JobEvaluationRecord, JobRecord.id == JobEvaluationRecord.job_id)
            .filter(JobEvaluationRecord.match_score >= settings.min_match_score)
            .order_by(JobEvaluationRecord.match_score.desc())
            .limit(20)
            .all()
        )

        if not records:
            console.print("[yellow]No high-matching jobs found yet in the database. Run --run-once to search.[/yellow]")
            return

        table = Table(title=f"Top Matched Software Engineering Positions (Score >= {settings.min_match_score}%)")
        table.add_column("Score", style="bold green", justify="center")
        table.add_column("Title", style="bold white")
        table.add_column("Company", style="cyan")
        table.add_column("Location", style="dim")
        table.add_column("Status", style="magenta")
        table.add_column("Apply Link", style="blue")

        for job, evaluation in records:
            table.add_row(
                f"{evaluation.match_score}%",
                job.title,
                job.company,
                f"{job.location} ({job.workplace_type})",
                job.status,
                job.apply_url
            )

        console.print(table)


def start_dashboard(host: str = "127.0.0.1", port: int = 8000):
    """Launches the local FastAPI dashboard and opens it in the default web browser."""
    import webbrowser
    import threading
    import uvicorn
    from dashboard.exporter import export_to_json

    # Pre-export latest data bundle
    export_to_json()

    url = f"http://{host}:{port}"
    console.print(Panel(
        f"[bold green]Starting Local AI Job Search Dashboard[/bold green]\n\n"
        f"• Local URL: [bold cyan]{url}[/bold cyan]\n"
        f"• Mode: [bold yellow]Full Read & Write (Local SQLite)[/bold yellow]\n"
        f"• PWA Offline Ready: [bold green]Enabled[/bold green]\n\n"
        f"Press [red]Ctrl+C[/red] to terminate the server.",
        title="Dashboard Online",
        expand=False
    ))

    # Auto-open browser after 1 second
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run("dashboard.app:app", host=host, port=port, log_level="info")


def main():
    parser = argparse.ArgumentParser(description="AI Job Search & Notification Agent")
    parser.add_argument("--run-once", action="store_true", help="Execute a single search and alert cycle right now")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in the background on configured schedule")
    parser.add_argument("--dashboard", action="store_true", help="Launch interactive local web dashboard at http://localhost:8000")
    parser.add_argument("--export-web", action="store_true", help="Export SQLite jobs to web/data/jobs.json for Vercel / PWA")
    parser.add_argument("--stats", action="store_true", help="Show statistics of indexed and alerted jobs")
    parser.add_argument("--list-matches", action="store_true", help="Show all high-matching jobs in the database")

    args = parser.parse_args()

    if args.run_once:
        pipeline = JobSearchPipeline()
        stats = pipeline.run_cycle()
        display_matched_jobs()
    elif args.dashboard:
        start_dashboard()
    elif args.export_web:
        from dashboard.exporter import export_to_json
        path = export_to_json()
        console.print(f"[bold green]Web export completed![/bold green] File generated at [cyan]{path}[/cyan]")
    elif args.daemon:
        start_scheduler()
    elif args.stats:
        display_stats()
    elif args.list_matches:
        display_matched_jobs()
    else:
        # Default help and status view
        console.print(Panel(
            "[bold cyan]AI Job Search Agent[/bold cyan]\n\n"
            "Automated job searching, Gemini AI matching, and Dashboard updates for Software Engineers.\n\n"
            "[bold white]Available Commands:[/bold white]\n"
            "  [green]python main.py --dashboard[/green]       Launch interactive local web dashboard\n"
            "  [green]python main.py --run-once[/green]       Run a search cycle immediately\n"
            "  [green]python main.py --export-web[/green]      Export listings to web/data/jobs.json\n"
            "  [green]python main.py --daemon[/green]         Run background scheduler continuously\n"
            "  [green]python main.py --list-matches[/green]   View all matched jobs in database\n"
            "  [green]python main.py --stats[/green]          View pipeline statistics\n"
            "To configure your credentials, copy [yellow].env.example[/yellow] to [yellow].env[/yellow].",
            title="Welcome",
            expand=False
        ))


if __name__ == "__main__":
    main()
