"""
End-to-end Job Search Pipeline Controller.
Orchestrates multi-portal ingestion (LinkedIn, TopJobs, ITPro, Rooster, XpressJobs),
deduplication, heuristic filtering, AI evaluation, and notification delivery.
"""

from typing import Dict, Any, List
from loguru import logger
from config import settings
from database import JobRepository, init_db
from extractors.linkedin_guest import LinkedInGuestExtractor
from extractors.rapidapi_jsearch import JSearchExtractor
from extractors.topjobs_lk import TopJobsExtractor
from extractors.itpro_lk import ITProExtractor
from extractors.rooster_jobs import RoosterExtractor
from extractors.xpress_jobs import XpressJobsExtractor
from extractors.base import JobItem
from filters.heuristic_filter import HeuristicFilter
from filters.ai_evaluator import AIEvaluator
from notifiers.whatsapp_twilio import WhatsAppTwilioNotifier
from notifiers.telegram_notifier import TelegramNotifier


class JobSearchPipeline:
    """Coordinates multi-source ingestion and intelligent matching."""

    def __init__(self):
        init_db()
        self.linkedin_extractor = LinkedInGuestExtractor()
        self.jsearch_extractor = JSearchExtractor()
        self.topjobs_extractor = TopJobsExtractor()
        self.itpro_extractor = ITProExtractor()
        self.rooster_extractor = RoosterExtractor()
        self.xpress_extractor = XpressJobsExtractor()
        self.heuristic_filter = HeuristicFilter()
        self.ai_evaluator = AIEvaluator()
        self.whatsapp_notifier = WhatsAppTwilioNotifier()
        self.telegram_notifier = TelegramNotifier()

    def run_cycle(self) -> Dict[str, Any]:
        """
        Executes a complete multi-portal search, evaluation, and alert cycle across:
        1. LinkedIn (Guest Public Search)
        2. TopJobs.lk (IT / Software QA)
        3. ITPro.lk (Software Engineering)
        4. Rooster.jobs (Tech REST API)
        5. Xpress.jobs (Sitemap Feed)
        """
        logger.info("==================================================")
        logger.info("Starting Multi-Portal AI Job Search pipeline cycle...")
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

        # ----------------------------------------------------------------------
        # 1. LinkedIn Ingestion
        # ----------------------------------------------------------------------
        for kw in keywords_list:
            for loc in locations_list:
                logger.info(f"[LinkedIn] Scanning for '{kw}' in '{loc}'...")
                jobs = self.linkedin_extractor.search_jobs(keywords=kw, location=loc, limit=12)
                
                # Fallback to JSearch API if guest search is throttled
                if not jobs and settings.rapidapi_key:
                    logger.info("[LinkedIn Fallback] Querying JSearch API...")
                    jobs = self.jsearch_extractor.search_jobs(keywords=kw, location=loc, limit=12)

                all_candidate_jobs.extend(jobs)

        # ----------------------------------------------------------------------
        # 2. Sri Lankan Job Portals Ingestion
        # ----------------------------------------------------------------------
        # A. TopJobs.lk
        try:
            topjobs = self.topjobs_extractor.search_jobs(limit=35)
            all_candidate_jobs.extend(topjobs)
        except Exception as e:
            logger.error(f"Error scraping TopJobs: {e}")

        # B. ITPro.lk
        try:
            itpro_jobs = self.itpro_extractor.search_jobs(limit=35)
            all_candidate_jobs.extend(itpro_jobs)
        except Exception as e:
            logger.error(f"Error scraping ITPro.lk: {e}")

        # C. Rooster.jobs
        try:
            rooster_jobs = self.rooster_extractor.search_jobs(keywords="software", limit=25)
            all_candidate_jobs.extend(rooster_jobs)
        except Exception as e:
            logger.error(f"Error querying Rooster: {e}")

        # D. Xpress.jobs
        try:
            xpress_jobs = self.xpress_extractor.search_jobs(limit=30)
            all_candidate_jobs.extend(xpress_jobs)
        except Exception as e:
            logger.error(f"Error scraping Xpress.jobs: {e}")

        stats["total_extracted"] = len(all_candidate_jobs)
        logger.info(f"Total multi-portal candidates discovered: {len(all_candidate_jobs)} jobs.")

        # ----------------------------------------------------------------------
        # 3. Deduplication, Filtering, AI Scoring & Alerting
        # ----------------------------------------------------------------------
        for job in all_candidate_jobs:
            evaluation = None
            score = 0
            verdict = "UNKNOWN"

            # Check if already processed
            if JobRepository.is_duplicate(job.id):
                # If already notified on Telegram, skip completely
                if JobRepository.is_already_notified(job.id, "TELEGRAM"):
                    stats["duplicates_skipped"] += 1
                    logger.debug(f"Skipping already notified job: [{job.source}] {job.title} at {job.company}")
                    continue

                # If previously evaluated with high match but alert was not delivered (e.g. earlier error)
                saved_eval = JobRepository.get_saved_evaluation(job.id)
                if saved_eval and saved_eval.get("match_score", 0) >= settings.min_match_score:
                    logger.info(f"Retrying unnotified high match from database: [{job.source}] '{job.title}' ({saved_eval.get('match_score')}%)...")
                    evaluation = saved_eval
                    score = saved_eval.get("match_score", 0)
                    verdict = saved_eval.get("match_verdict", "UNKNOWN")
                else:
                    stats["duplicates_skipped"] += 1
                    continue
            else:
                # Deterministic Heuristic Filter (Seniority & Location rules)
                passes_heuristic, reason = self.heuristic_filter.evaluate(job)
                if not passes_heuristic:
                    stats["heuristically_rejected"] += 1
                    logger.debug(f"Heuristically rejected: [{job.source}] {job.title} - {reason}")
                    continue

                # Save initial job record
                JobRepository.save_job(job.model_dump())

                # Fetch full LinkedIn description if applicable and missing
                if not job.description and job.source == "linkedin_guest":
                    desc = self.linkedin_extractor.fetch_job_description(job.id)
                    if desc:
                        job.description = desc

                # Google Gemini AI Semantic Evaluation
                logger.info(f"Running AI fit evaluation on: [{job.source}] '{job.title}' at '{job.company}'...")
                evaluation = self.ai_evaluator.evaluate_job(job)
                stats["evaluated_by_ai"] += 1

                # Persist AI evaluation
                JobRepository.save_evaluation(job.id, evaluation)

                score = evaluation.get("match_score", 0)
                verdict = evaluation.get("match_verdict", "UNKNOWN")
                logger.info(f"-> Result: Score {score}% ({verdict}) for {job.title} at {job.company}")

            # Threshold Gate (min_match_score)
            if score >= settings.min_match_score and evaluation:
                stats["matches_found"] += 1
                logger.info(f"🎯 High match ({score}% >= {settings.min_match_score}%)! Dispatching alerts...")

                # Telegram notification
                if self.telegram_notifier.is_configured():
                    logger.info(f"Dispatching Telegram alert for: {job.title} ({job.source})...")
                    tg_success, tg_res = self.telegram_notifier.send_job_alert(job, evaluation)
                    tg_status = "SENT" if tg_success else "FAILED"
                    if tg_success:
                        logger.info(f"✅ Telegram alert delivered: {job.title} at {job.company}")
                        stats["alerts_sent"] += 1
                    else:
                        logger.error(f"❌ Telegram alert FAILED for {job.title}: {tg_res}")
                    JobRepository.mark_notified(job.id, "TELEGRAM", settings.telegram_chat_id or "", tg_status, tg_res)
                else:
                    logger.warning("Telegram notifier is NOT configured (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing).")

                # WhatsApp notification (if configured)
                if self.whatsapp_notifier.is_configured():
                    success, res = self.whatsapp_notifier.send_job_alert(job, evaluation)
                    status_str = "SENT" if success else "FAILED"
                    JobRepository.mark_notified(job.id, "WHATSAPP", settings.whatsapp_to or "", status_str, res)

        logger.info(f"Multi-Portal Pipeline cycle finished. Metrics: {stats}")
        return stats
