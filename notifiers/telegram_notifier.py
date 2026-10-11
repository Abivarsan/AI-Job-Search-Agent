"""
Telegram Bot Notification Dispatcher.
Offers instant, 100% free alerting with rich markdown and one-click apply links.
"""

from typing import Dict, Any, Tuple
import httpx
from loguru import logger
from extractors.base import JobItem
from notifiers.base import BaseNotifier
from config import settings


class TelegramNotifier(BaseNotifier):
    """Delivers job notifications via Telegram Bot API."""

    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage" if self.bot_token else ""

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def format_message(self, job: JobItem, evaluation: Dict[str, Any]) -> str:
        score = evaluation.get("match_score", 0)
        verdict = evaluation.get("match_verdict", "MATCH")
        summary = evaluation.get("summary", "")
        matched_skills = evaluation.get("matching_skills", [])
        skills_str = ", ".join(matched_skills[:5]) if matched_skills else "General SWE"

        msg = (
            f"🎯 *NEW JOB MATCH: {job.title}*\n"
            f"🏢 *Company:* {job.company}\n"
            f"📍 *Location:* {job.location} ({job.workplace_type})\n"
            f"⭐ *AI Match Score:* {score}% ({verdict})\n\n"
            f"💡 *Summary:* {summary}\n"
            f"✅ *Skills:* {skills_str}\n\n"
            f"🔗 [Apply on LinkedIn]({job.apply_url})"
        )
        return msg

    def send_job_alert(self, job: JobItem, evaluation: Dict[str, Any]) -> Tuple[bool, str]:
        if not self.is_configured():
            return False, "Telegram bot token or chat ID not set in .env"

        text = self.format_message(job, evaluation)
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(self.base_url, json=payload)
                if res.status_code == 200:
                    return True, "Telegram message sent"
                return False, f"Telegram API error HTTP {res.status_code}: {res.text}"
        except Exception as e:
            return False, f"Failed to dispatch Telegram message: {e}"
