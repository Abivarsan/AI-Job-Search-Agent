"""
WhatsApp Notification Dispatcher using Twilio API.
Formats and delivers instant alerts to candidate's WhatsApp.
"""

from typing import Dict, Any, Tuple
from loguru import logger
from extractors.base import JobItem
from notifiers.base import BaseNotifier
from config import settings


class WhatsAppTwilioNotifier(BaseNotifier):
    """Delivers job notifications via Twilio WhatsApp."""

    def __init__(self):
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.from_number = settings.twilio_whatsapp_from
        self.to_number = settings.whatsapp_to
        self.client = None

        if self.account_sid and self.auth_token:
            try:
                from twilio.rest import Client
                self.client = Client(self.account_sid, self.auth_token)
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")

    def is_configured(self) -> bool:
        """Checks if Twilio credentials and recipient number are set."""
        return bool(self.client and self.to_number and self.from_number)

    def format_message(self, job: JobItem, evaluation: Dict[str, Any]) -> str:
        """Formats an attractive, informative WhatsApp message."""
        score = evaluation.get("match_score", 0)
        verdict = evaluation.get("match_verdict", "MATCH")
        summary = evaluation.get("summary", "")
        matched_skills = evaluation.get("matching_skills", [])
        missing_skills = evaluation.get("missing_skills", [])

        skills_str = ", ".join(matched_skills[:5]) if matched_skills else "General SWE"
        missing_str = ", ".join(missing_skills[:3]) if missing_skills else "None noted"

        msg = (
            f"🎯 *NEW JOB MATCH: {job.title}*\n"
            f"🏢 *Company:* {job.company}\n"
            f"📍 *Location:* {job.location} ({job.workplace_type})\n"
            f"⭐ *AI Match Score:* {score}% ({verdict})\n\n"
            f"💡 *Summary:* {summary}\n\n"
            f"✅ *Matched Skills:* {skills_str}\n"
            f"⚠️ *Skill Gaps:* {missing_str}\n\n"
            f"🔗 *Apply Here:* {job.apply_url}"
        )
        return msg

    def send_job_alert(self, job: JobItem, evaluation: Dict[str, Any]) -> Tuple[bool, str]:
        """Dispatches the WhatsApp message via Twilio."""
        if not self.is_configured():
            err = "Twilio WhatsApp is not configured in .env (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, WHATSAPP_TO)"
            logger.warning(err)
            return False, err

        body = self.format_message(job, evaluation)

        try:
            message = self.client.messages.create(
                body=body,
                from_=self.from_number,
                to=self.to_number
            )
            logger.info(f"WhatsApp alert sent successfully! SID: {message.sid}")
            return True, message.sid
        except Exception as e:
            err = f"Failed to send WhatsApp message via Twilio: {e}"
            logger.error(err)
            return False, err

    def send_test_message(self) -> Tuple[bool, str]:
        """Sends a verification test message to ensure credentials and sandbox work."""
        if not self.is_configured():
            return False, "Twilio WhatsApp credentials missing in .env"

        try:
            msg = (
                "🤖 *AI Job Search Agent Connected!*\n\n"
                "Your WhatsApp notifications are successfully configured. "
                "You will receive alerts here whenever matching Software Engineer positions are found."
            )
            message = self.client.messages.create(
                body=msg,
                from_=self.from_number,
                to=self.to_number
            )
            return True, message.sid
        except Exception as e:
            return False, str(e)
