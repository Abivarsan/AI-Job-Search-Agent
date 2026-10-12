"""
ITPro.lk Extractor (Sri Lanka).
Scrapes vacancies from Sri Lanka's dedicated IT job portal (itpro.lk/jobs/software-engineering/).
"""

import re
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from extractors.base import BaseJobExtractor, JobItem


class ITProExtractor(BaseJobExtractor):
    """Fetches Software Engineering vacancies from ITPro.lk."""

    BASE_URL = "https://itpro.lk/jobs/software-engineering/"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

    def search_jobs(self, keywords: str = "", location: str = "Sri Lanka", limit: int = 40) -> List[JobItem]:
        """Fetches listings from ITPro.lk software engineering category."""
        jobs: List[JobItem] = []
        logger.info("Scanning ITPro.lk for Software Engineering positions...")

        try:
            with httpx.Client(headers=self.headers, timeout=15.0, follow_redirects=True) as client:
                resp = client.get(self.BASE_URL)
                if resp.status_code != 200:
                    logger.warning(f"ITPro.lk returned HTTP status {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                # Find all job links pointing to /job/\d+/
                job_links = soup.find_all("a", href=re.compile(r"/job/\d+/"))
                seen_urls = set()

                for link in job_links:
                    if len(jobs) >= limit:
                        break

                    href = link.get("href", "")
                    if not href or href in seen_urls:
                        continue
                    seen_urls.add(href)

                    item = self._parse_job_card(link, href)
                    if item:
                        if keywords:
                            kw_lower = keywords.lower()
                            if kw_lower not in item.title.lower():
                                continue
                        jobs.append(item)

        except Exception as e:
            logger.error(f"Error fetching ITPro.lk vacancies: {e}")

        logger.info(f"ITPro.lk: successfully extracted {len(jobs)} software vacancies.")
        return jobs

    def _parse_job_card(self, link_tag, href: str) -> Optional[JobItem]:
        try:
            # 1. Job ID from URL: /job/15419/slug
            id_match = re.search(r"/job/(\d+)/", href)
            job_id = id_match.group(1) if id_match else str(abs(hash(href)))

            # 2. Extract title & metadata
            # Often link contains the full card text: e.g. "Associate Full Stack DeveloperImperial Edutech - iMETColombo09 Oct"
            # Or parent contains h2/h3
            parent = link_tag.find_parent(["article", "div", "li"])
            
            title = ""
            company = "Sri Lankan Tech Company"
            loc_text = "Colombo, Sri Lanka"
            posted_date = "Recent"

            h2 = parent.find(["h2", "h3"]) if parent else None
            if h2:
                title = h2.get_text(strip=True)
            else:
                raw_text = link_tag.get_text(strip=True)
                # Split title from company if joined
                title = raw_text[:60].strip()

            if not title:
                # Infer title from URL slug: e.g. /job/15419/associate-full-stack-developer-at-company
                slug = href.split("/")[-2] if href.endswith("/") else href.split("/")[-1]
                slug_parts = slug.split("-at-")
                title = slug_parts[0].replace("-", " ").title()
                if len(slug_parts) > 1:
                    company = slug_parts[1].replace("-", " ").title()

            # Find company & location from parent text if possible
            if parent:
                parent_text = parent.get_text(" ", strip=True)
                for city in ["Colombo", "Kandy", "Jaffna", "Moratuwa", "Galle", "Kurunegala", "Remote"]:
                    if city in parent_text:
                        loc_text = f"{city}, Sri Lanka" if city != "Remote" else "Remote"
                        break

            # Workplace type
            workplace = "On-site"
            title_lower = f"{title} {loc_text}".lower()
            if "remote" in title_lower:
                workplace = "Remote"
            elif "hybrid" in title_lower:
                workplace = "Hybrid"

            return JobItem(
                id=f"itpro_{job_id}",
                external_id=job_id,
                source="itpro_lk",
                title=title,
                company=company,
                location=loc_text,
                workplace_type=workplace,
                apply_url=href,
                description=f"Software engineering opening on ITPro.lk: {title} at {company} ({loc_text}).",
                experience_level="Entry / Associate",
                posted_date=posted_date
            )
        except Exception as e:
            logger.debug(f"ITPro parse error: {e}")
            return None
