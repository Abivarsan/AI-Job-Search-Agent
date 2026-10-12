"""
Rooster.jobs Extractor (Sri Lanka).
Queries Rooster's public REST API (api.rooster.jobs/jobSearch/jobs/search)
to retrieve live tech vacancies across Sri Lanka.
"""

from typing import List, Optional
import httpx
from loguru import logger
from extractors.base import BaseJobExtractor, JobItem


class RoosterExtractor(BaseJobExtractor):
    """Fetches job vacancies from Rooster.jobs REST API."""

    SEARCH_API = "https://api.rooster.jobs/jobSearch/jobs/search"
    BASE_URL = "https://rooster.jobs/jobs/{job_id}"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*"
        }

    def search_jobs(self, keywords: str = "software", location: str = "Sri Lanka", limit: int = 30) -> List[JobItem]:
        """Queries Rooster API for software developer and engineer positions."""
        jobs: List[JobItem] = []
        logger.info(f"Scanning Rooster.jobs for '{keywords}'...")

        query_terms = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else ["software"]

        payload = {
            "query": query_terms,
            "limit": limit,
            "page": 1,
            "filters": {
                "salary": None
            }
        }

        try:
            with httpx.Client(headers=self.headers, timeout=12.0) as client:
                resp = client.post(self.SEARCH_API, json=payload)
                if resp.status_code not in [200, 201]:
                    logger.warning(f"Rooster API returned HTTP {resp.status_code}")
                    return []

                data = resp.json()
                items = data.get("body", {}).get("data", [])
                logger.info(f"Rooster.jobs: retrieved {len(items)} raw listings.")

                for item in items:
                    job_obj = self._parse_rooster_item(item)
                    if job_obj:
                        jobs.append(job_obj)

        except Exception as e:
            logger.error(f"Error querying Rooster API: {e}")

        logger.info(f"Rooster.jobs: successfully normalized {len(jobs)} vacancies.")
        return jobs

    def _parse_rooster_item(self, item: dict) -> Optional[JobItem]:
        try:
            job_id = item.get("_id", "") or item.get("id", "")
            if not job_id:
                return None

            title = item.get("title", "")
            if not title:
                return None

            company = item.get("companyName", "") or "Sri Lankan Company"
            workplace_raw = item.get("workplaceType", "On-site")
            workplace = "Remote" if "remote" in str(workplace_raw).lower() else ("Hybrid" if "hybrid" in str(workplace_raw).lower() else "On-site")
            
            loc_str = "Sri Lanka"
            city = item.get("location", {}).get("location", "") if isinstance(item.get("location"), dict) else ""
            if city:
                loc_str = f"{city}, Sri Lanka"

            slug = item.get("slug", "")
            apply_url = f"https://rooster.jobs/jobs/{job_id}/{slug}" if slug else f"https://rooster.jobs/jobs/{job_id}"

            desc = item.get("description", "") or f"Tech vacancy on Rooster.jobs: {title} at {company}."

            return JobItem(
                id=f"rooster_{job_id}",
                external_id=str(job_id),
                source="rooster_jobs",
                title=title.strip(),
                company=company.strip(),
                location=loc_str,
                workplace_type=workplace,
                apply_url=apply_url,
                description=desc,
                experience_level="Entry / Associate",
                posted_date="Recent"
            )
        except Exception as e:
            logger.debug(f"Rooster item parse error: {e}")
            return None
