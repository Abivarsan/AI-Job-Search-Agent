"""
Xpress.jobs Extractor (Sri Lanka).
Extracts active IT and Software Engineering vacancies from Xpress.jobs via
its dynamic sitemap feed (xpress.jobs/sitemap.xml) and structured job slugs.
"""

import re
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from extractors.base import BaseJobExtractor, JobItem


TARGET_SLUG_KEYWORDS = [
    "software", "developer", "full-stack", "backend", "frontend", 
    ".net", "java", "python", "react", "programmer", "web-developer"
]


class XpressJobsExtractor(BaseJobExtractor):
    """Fetches vacancies from Xpress.jobs."""

    SITEMAP_URL = "https://xpress.jobs/sitemap.xml"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/xml, text/xml, */*"
        }

    def search_jobs(self, keywords: str = "", location: str = "Sri Lanka", limit: int = 35) -> List[JobItem]:
        """Parses software and IT listings from Xpress.jobs sitemap."""
        jobs: List[JobItem] = []
        logger.info("Scanning Xpress.jobs sitemap for software engineering positions...")

        try:
            with httpx.Client(headers=self.headers, timeout=20.0, follow_redirects=True) as client:
                resp = client.get(self.SITEMAP_URL)
                if resp.status_code != 200:
                    logger.warning(f"Xpress.jobs sitemap returned HTTP {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.text, "xml")
                loc_tags = soup.find_all("loc")
                logger.info(f"Xpress.jobs: total sitemap entries: {len(loc_tags)}")

                # Filter URLs that are job postings matching tech keywords
                for loc in loc_tags:
                    if len(jobs) >= limit:
                        break

                    url = loc.get_text(strip=True)
                    if "/jobs/view/" not in url:
                        continue

                    # Check if URL slug contains any target keywords
                    slug = url.split("/jobs/view/")[-1].lower()
                    if not any(k in slug for k in TARGET_SLUG_KEYWORDS):
                        continue

                    job_obj = self._parse_url(url)
                    if job_obj:
                        jobs.append(job_obj)

        except Exception as e:
            logger.error(f"Error fetching Xpress.jobs: {e}")

        logger.info(f"Xpress.jobs: successfully matched {len(jobs)} tech vacancies.")
        return jobs

    def _parse_url(self, url: str) -> Optional[JobItem]:
        try:
            # Format: https://xpress.jobs/jobs/view/338034/associate-software-engineer-company-pvt-ltd
            match = re.search(r"/jobs/view/(\d+)/(.+)", url)
            if not match:
                return None

            job_id = match.group(1)
            raw_slug = match.group(2)

            # Clean and split slug into title and company
            # Slug format is typically: title-words-company-name
            words = raw_slug.replace("-", " ").strip().title()

            # Workplace type inference
            workplace = "On-site"
            slug_lower = raw_slug.lower()
            if "remote" in slug_lower:
                workplace = "Remote"
            elif "hybrid" in slug_lower:
                workplace = "Hybrid"

            return JobItem(
                id=f"xpress_{job_id}",
                external_id=job_id,
                source="xpress_jobs",
                title=words[:70],
                company="Sri Lankan Employer (via XpressJobs)",
                location="Sri Lanka",
                workplace_type=workplace,
                apply_url=url,
                description=f"Vacancy on Xpress.jobs: {words}. Apply directly at {url}.",
                experience_level="Entry / Associate",
                posted_date="Recent"
            )
        except Exception as e:
            logger.debug(f"Xpress parse error: {e}")
            return None
