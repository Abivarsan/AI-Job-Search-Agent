"""
Scheduler Daemon for the AI Job Search Agent.
Runs recurring pipeline sweeps in the background at configured intervals.
"""

import sys
import time
from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger
from config import settings
from pipeline import JobSearchPipeline


def start_scheduler():
    """Initializes and runs the recurring background scheduler."""
    pipeline = JobSearchPipeline()
    scheduler = BlockingScheduler()

    interval_min = settings.poll_interval_minutes
    logger.info(f"Scheduling AI Job Search Agent to run every {interval_min} minutes.")

    # Run one immediate pass upon startup
    try:
        logger.info("Executing initial startup sweep...")
        pipeline.run_cycle()
    except Exception as e:
        logger.error(f"Error during initial sweep: {e}")

    # Add recurring interval job
    scheduler.add_job(
        pipeline.run_cycle,
        "interval",
        minutes=interval_min,
        id="job_search_sweep",
        replace_existing=True
    )

    try:
        logger.info(f"Scheduler active. Next sweep in {interval_min} minutes. Press Ctrl+C to stop.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user.")
        scheduler.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    start_scheduler()
