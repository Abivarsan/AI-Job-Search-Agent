"""
End-to-end Job Search Pipeline Controller.
Orchestrates ingestion, deduplication, heuristic filtering, AI evaluation, and notification delivery.
"""

from typing import Dict, Any, List
from loguru import logger
from config import settings
from database import JobRepository, init_db
from extractors.linkedin_guest import LinkedInGuestExtractor
from extractors.rapidapi_jsearch import JSearchExtractor
from extractors.base import JobItem
from filters.heuristic_filter import HeuristicFilter
from filters.ai_evaluator import AIEvaluator
from notifiers.whatsapp_twilio import WhatsAppTwilioNotifier
from notifiers.telegram_notifier import TelegramNotifier


class JobSearchPipeline:
    """Coordinates all sub-systems of the AI Job Search Agent."""

    def __init__(self):
        init_db()
        self.linkedin_extractor = LinkedInGuestExtractor()
        self.jsearch_extractor = JSearchExtractor()
        self.heuristic_filter = HeuristicFilter()
        self.ai_evaluator = AIEvaluator()
        self.whatsapp_notifier = WhatsAppTwilioNotifier()
        self.telegram_notifier = TelegramNotifier()

    def run_cycle(self) -> Dict[str, Any]:
        """
        Executes a complete search, evaluation, and alert cycle across
        all configured keywords and target locations.
        """
        logger.info("==================================================")
        logger.info("Starting AI Job Search Agent pipeline cycle...")
        logger.info("==================================================")

        stats = {
            "total_extracted": 0,
            "duplicates_skipped": 0,
            "heuristically_rejected": 0,
            "evaluated_by_ai": 0,
            "matches_found": 0,
            "alerts_sent": 0
        }

        keywords_list = settings.search_keywords
        locations_list = settings.search_locations

        all_candidate_jobs: List[JobItem] = []

        for kw in keywords_list:
            for loc in locations_list:
                logger.info(f"Scanning for '{kw}' in '{loc}'...")
                
                # 1. Primary: LinkedIn Public Guest Endpoint
                jobs = self.linkedin_extractor.search_jobs(keywords=kw, location=loc, limit=15)
                
                # 2. Fallback: RapidAPI JSearch if guest search yielded zero or was throttled
                if not jobs and settings.rapidapi_key:
                    logger.info("Falling back to JSearch API...")
                    jobs = self.jsearch_extractor.search_jobs(keywords=kw, location=loc, limit=15)

                all_candidate_jobs.extend(jobs)

        stats["total_extracted"] = len(all_candidate_jobs)
        logger.info(f"Extraction complete: {len(all_candidate_jobs)} raw candidate jobs discovered.")

        # Process each job
        for job in all_candidate_jobs:
            # 3. Deduplication Check
            if JobRepository.is_duplicate(job.id):
                stats["duplicates_skipped"] += 1
                logger.debug(f"Skipping duplicate job: [{job.id}] {job.title} at {job.company}")
                continue

            # 4. Fast Heuristic Pre-Filter
            passes_heuristic, reason = self.heuristic_filter.evaluate(job)
            if not passes_heuristic:
                stats["heuristically_rejected"] += 1
                logger.debug(f"Heuristically rejected: {job.title} - {reason}")
                continue

            # Save initial job record
            job_record = JobRepository.save_job(job.model_dump())

            # 5. Fetch full description if missing and supported
            if not job.description and job.source == "linkedin_guest":
                logger.info(f"Fetching full description for: {job.title} at {job.company}...")
                desc = self.linkedin_extractor.fetch_job_description(job.id)
                if desc:
                    job.description = desc

            # 6. AI Semantic Evaluation (Google Gemini)
            logger.info(f"Running AI fit evaluation on: '{job.title}' at '{job.company}'...")
            evaluation = self.ai_evaluator.evaluate_job(job)
            stats["evaluated_by_ai"] += 1

            # Persist AI evaluation
            JobRepository.save_evaluation(job.id, evaluation)

            score = evaluation.get("match_score", 0)
            verdict = evaluation.get("match_verdict", "UNKNOWN")
            logger.info(f"-> AI Evaluation Result: Score {score}% ({verdict}) for {job.title} at {job.company}")

            # 7. Alert Triggering (Threshold check)
            if score >= settings.min_match_score:
                stats["matches_found"] += 1
                logger.info(f"🎯 High match ({score}% >= {settings.min_match_score}%)! Dispatching alerts...")

                # WhatsApp notification
                if self.whatsapp_notifier.is_configured():
                    success, res = self.whatsapp_notifier.send_job_alert(job, evaluation)
                    status_str = "SENT" if success else "FAILED"
                    JobRepository.mark_notified(job.id, "WHATSAPP", settings.whatsapp_to or "", status_str, res)
                    if success:
                        stats["alerts_sent"] += 1
                else:
                    logger.info("ℹ️ WhatsApp credentials not yet set in .env. Logging match without sending WhatsApp.")

                # Telegram notification (if enabled)
                if self.telegram_notifier.is_configured():
                    tg_success, tg_res = self.telegram_notifier.send_job_alert(job, evaluation)
                    tg_status = "SENT" if tg_success else "FAILED"
                    JobRepository.mark_notified(job.id, "TELEGRAM", settings.telegram_chat_id or "", tg_status, tg_res)

        logger.info(f"Pipeline cycle finished. Metrics: {stats}")
        return stats
