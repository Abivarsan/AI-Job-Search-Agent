"""
RapidAPI JSearch Fallback Extractor.
Aggregates job postings from LinkedIn, Indeed, and Google Jobs via a managed API.
Serves as an automatic failover when direct scraping is rate limited.
"""

from typing import List
import httpx
from loguru import logger
from extractors.base import BaseJobExtractor, JobItem
from config import settings


class JSearchExtractor(BaseJobExtractor):
    """Fetches jobs via RapidAPI JSearch service."""

    SEARCH_URL = "https://jsearch.p.rapidapi.com/search"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.rapidapi_key

    def search_jobs(self, keywords: str, location: str, limit: int = 20) -> List[JobItem]:
        if not self.api_key:
            logger.debug("RapidAPI key not set, skipping JSearch extractor.")
            return []

        logger.info(f"Querying JSearch API for '{keywords}' in '{location}'...")
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "jsearch.p.rapidapi.com"
        }
        params = {
            "query": f"{keywords} in {location}",
            "page": "1",
            "num_pages": "1",
            "date_posted": "today"
        }

        jobs: List[JobItem] = []
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.get(self.SEARCH_URL, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    raw_jobs = data.get("data", [])
                    for item in raw_jobs[:limit]:
                        job_id = item.get("job_id", "")
                        title = item.get("job_title", "Unknown")
                        company = item.get("employer_name", "Unknown")
                        apply_url = item.get("job_apply_link", "") or item.get("job_google_link", "")
                        desc = item.get("job_description", "")
                        city = item.get("job_city", "")
                        country = item.get("job_country", "")
                        is_remote = item.get("job_is_remote", False)

                        loc_str = "Remote" if is_remote else f"{city}, {country}".strip(", ")
                        workplace = "Remote" if is_remote else "On-site"

                        jobs.append(JobItem(
                            id=f"js_{job_id}",
                            external_id=job_id,
                            source="jsearch_api",
                            title=title,
                            company=company,
                            location=loc_str,
                            workplace_type=workplace,
                            apply_url=apply_url,
                            description=desc,
                            experience_level="Entry / Associate",
                            posted_date="Today"
                        ))
                else:
                    logger.warning(f"JSearch API responded with status {response.status_code}")
        except Exception as e:
            logger.error(f"Error querying JSearch API: {e}")

        return jobs
