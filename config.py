"""
Configuration manager for the AI Job Search Agent.
Loads settings from environment variables and local .env file.
"""

import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load .env file explicitly
load_dotenv(BASE_DIR / ".env")

class Settings:
    def __init__(self):
        # AI Engine (Google Gemini)
        self.gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.min_match_score: int = int(os.getenv("MIN_MATCH_SCORE", "75"))

        # Notification: Twilio WhatsApp
        self.twilio_account_sid: Optional[str] = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token: Optional[str] = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_whatsapp_from: str = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        self.whatsapp_to: Optional[str] = os.getenv("WHATSAPP_TO")

        # Notification: Telegram (Alternative)
        self.telegram_bot_token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")

        # Third-Party Job API Fallback (RapidAPI JSearch)
        self.rapidapi_key: Optional[str] = os.getenv("RAPIDAPI_KEY")

        # Search Preferences
        self.search_keywords_raw: str = os.getenv(
            "SEARCH_KEYWORDS",
            "Software Engineer, Associate Software Engineer, Junior Software Engineer"
        )
        self.search_locations_raw: str = os.getenv(
            "SEARCH_LOCATIONS",
            "Remote, United States"
        )
        self.poll_interval_minutes: int = int(os.getenv("POLL_INTERVAL_MINUTES", "180"))
        self.database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'jobs.db'}")

    @property
    def search_keywords(self) -> List[str]:
        return [k.strip() for k in self.search_keywords_raw.split(",") if k.strip()]

    @property
    def search_locations(self) -> List[str]:
        return [loc.strip() for loc in self.search_locations_raw.split(",") if loc.strip()]


# Global settings instance
settings = Settings()
