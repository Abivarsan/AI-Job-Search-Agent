"""
Telegram Bot Notification Dispatcher.
Offers instant, 100% free alerting with rich markdown and one-click apply links.
"""

import html
import time
from typing import Dict, Any, Tuple
import httpx
from loguru import logger
from extractors.base import JobItem
from notifiers.base import BaseNotifier
from config import settings


class TelegramNotifier(BaseNotifier):
    """Delivers job notifications via Telegram Bot API with robust HTML formatting."""

    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage" if self.bot_token else ""

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def format_html_message(self, job: JobItem, evaluation: Dict[str, Any]) -> str:
        score = evaluation.get("match_score", 0)
        verdict = html.escape(str(evaluation.get("match_verdict", "MATCH")))
        summary = html.escape(str(evaluation.get("summary", "")))
        matched_skills = evaluation.get("matching_skills", [])
        skills_str = html.escape(", ".join(matched_skills[:5]) if matched_skills else "General SWE")

        source_names = {
            "linkedin_guest": "LinkedIn",
            "topjobs_lk": "TopJobs.lk",
            "itpro_lk": "ITPro.lk",
            "rooster_jobs": "Rooster.jobs",
            "xpress_jobs": "Xpress.jobs"
        }
        source_display = source_names.get(job.source, job.source.replace("_", " ").title())
        source_esc = html.escape(source_display)
        title_esc = html.escape(str(job.title))
        company_esc = html.escape(str(job.company))
        location_esc = html.escape(str(job.location))
        workplace_esc = html.escape(str(job.workplace_type))
        apply_url = job.apply_url.strip()

        msg = (
            f"🎯 <b>NEW JOB MATCH: {title_esc}</b>\n"
            f"🏢 <b>Company:</b> {company_esc}\n"
            f"📍 <b>Location:</b> {location_esc} ({workplace_esc})\n"
            f"🌐 <b>Source:</b> {source_esc}\n"
            f"⭐ <b>AI Match Score:</b> {score}% ({verdict})\n\n"
            f"💡 <b>Summary:</b> {summary}\n"
            f"✅ <b>Skills:</b> {skills_str}\n\n"
            f'🔗 <a href="{apply_url}">View & Apply on {source_esc}</a>'
        )
        return msg

    def format_plain_message(self, job: JobItem, evaluation: Dict[str, Any]) -> str:
        score = evaluation.get("match_score", 0)
        verdict = evaluation.get("match_verdict", "MATCH")
        summary = evaluation.get("summary", "")
        matched_skills = evaluation.get("matching_skills", [])
        skills_str = ", ".join(matched_skills[:5]) if matched_skills else "General SWE"
        source_names = {
            "linkedin_guest": "LinkedIn",
            "topjobs_lk": "TopJobs.lk",
            "itpro_lk": "ITPro.lk",
            "rooster_jobs": "Rooster.jobs",
            "xpress_jobs": "Xpress.jobs"
        }
        source_display = source_names.get(job.source, job.source.replace("_", " ").title())

        msg = (
            f"🎯 NEW JOB MATCH: {job.title}\n"
            f"🏢 Company: {job.company}\n"
            f"📍 Location: {job.location} ({job.workplace_type})\n"
            f"🌐 Source: {source_display}\n"
            f"⭐ AI Match Score: {score}% ({verdict})\n\n"
            f"💡 Summary: {summary}\n"
            f"✅ Skills: {skills_str}\n\n"
            f"🔗 Apply URL: {job.apply_url}"
        )
        return msg

    def send_job_alert(self, job: JobItem, evaluation: Dict[str, Any]) -> Tuple[bool, str]:
        if not self.is_configured():
            return False, "Telegram bot token or chat ID not set in .env"

        # Rate-limiting safety: Telegram allows max 1 msg/second to an individual chat
        time.sleep(1.2)

        # 1. Attempt sending formatted HTML
        html_text = self.format_html_message(job, evaluation)
        payload = {
            "chat_id": self.chat_id,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(self.base_url, json=payload)
                if res.status_code == 200:
                    return True, "Telegram message sent (HTML)"
                
                logger.warning(f"Telegram HTML send returned HTTP {res.status_code}: {res.text}. Retrying plain text...")
                
                # 2. Fallback to plain text if HTML parsing ever fails
                time.sleep(1.0)
                plain_text = self.format_plain_message(job, evaluation)
                fallback_payload = {
                    "chat_id": self.chat_id,
                    "text": plain_text,
                    "disable_web_page_preview": False
                }
                res_plain = client.post(self.base_url, json=fallback_payload)
                if res_plain.status_code == 200:
                    return True, "Telegram message sent (Plain text fallback)"
                return False, f"Telegram API error HTTP {res_plain.status_code}: {res_plain.text}"

        except Exception as e:
            return False, f"Failed to dispatch Telegram message: {e}"

    def send_test_message(self) -> Tuple[bool, str]:
        """Sends a verification ping to confirm Telegram bot connectivity."""
        if not self.is_configured():
            return False, "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set."

        text = (
            "🤖 <b>AI Job Search Agent Connected!</b>\n\n"
            "Your Telegram notifications are successfully configured.\n"
            "You will receive alerts here whenever matching Software Engineer positions are found."
        )
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(self.base_url, json=payload)
                if res.status_code == 200:
                    return True, "Telegram test message delivered!"
                return False, f"Telegram API error HTTP {res.status_code}: {res.text}"
        except Exception as e:
            return False, f"Failed to send test message: {e}"

