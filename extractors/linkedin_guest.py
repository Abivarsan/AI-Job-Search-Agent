"""
LinkedIn Public Guest API Job Extractor.
Extracts public job listings from LinkedIn without requiring authentication,
completely eliminating the risk of personal LinkedIn account bans.
"""

import time
import random
import re
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from extractors.base import BaseJobExtractor, JobItem


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
]


class LinkedInGuestExtractor(BaseJobExtractor):
    """Fetches job listings from LinkedIn unauthenticated public endpoints."""

    BASE_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    BASE_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

    def __init__(self, request_delay: float = 2.5):
        self.request_delay = request_delay

    def _get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.linkedin.com/",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1"
        }

    def search_jobs(self, keywords: str, location: str, limit: int = 25) -> List[JobItem]:
        """Queries LinkedIn public guest search for jobs posted recently."""
        jobs: List[JobItem] = []
        logger.info(f"Querying LinkedIn Guest API for '{keywords}' in '{location}'...")

        params = {
            "keywords": keywords,
            "location": location,
            "start": 0,
            "f_TPR": "r86400",  # Past 24 hours
            "f_E": "1,2,3"      # Internship (1), Entry level (2), Associate (3)
        }

        # If searching for Remote, apply LinkedIn's dedicated remote workplace filter (f_WT=2)
        if "remote" in location.lower():
            params["f_WT"] = "2"

        try:
            with httpx.Client(headers=self._get_headers(), timeout=15.0, follow_redirects=True) as client:
                response = client.get(self.BASE_SEARCH_URL, params=params)

                if response.status_code == 429:
                    logger.warning("LinkedIn rate limited guest search (HTTP 429). Will need backoff or fallback.")
                    return []

                if response.status_code != 200:
                    logger.warning(f"LinkedIn search returned HTTP status {response.status_code}")
                    return []

                soup = BeautifulSoup(response.text, "html.parser")
                job_cards = soup.find_all("li")
                logger.info(f"Retrieved {len(job_cards)} raw job cards from LinkedIn guest endpoint.")

                for card in job_cards[:limit]:
                    job_item = self._parse_card(card, query_location=location)
                    if job_item:
                        jobs.append(job_item)

        except Exception as e:
            logger.error(f"Error querying LinkedIn Guest API: {e}")
            return []

        return jobs

    def _parse_card(self, card_soup: BeautifulSoup, query_location: str = "") -> Optional[JobItem]:
        """Extracts metadata from an individual LinkedIn job search card."""
        try:
            # 1. Title & Link
            title_tag = card_soup.find("h3", class_=re.compile("base-search-card__title"))
            if not title_tag:
                title_tag = card_soup.find("h3")
            if not title_tag:
                return None
            title = title_tag.get_text(strip=True)

            link_tag = card_soup.find("a", class_=re.compile("base-card__full-link|job-search-card"))
            if not link_tag or not link_tag.get("href"):
                link_tag = card_soup.find("a")
            if not link_tag or not link_tag.get("href"):
                return None

            raw_url = link_tag.get("href").split("?")[0]  # Clean tracking params

            # 2. Extract job ID
            job_id_match = re.search(r"view/(\d+)", raw_url) or re.search(r"-(\d+)$", raw_url)
            job_id = job_id_match.group(1) if job_id_match else None

            # Fallback to urn in card
            if not job_id:
                div_card = card_soup.find("div", {"data-entity-urn": True})
                if div_card:
                    urn = div_card.get("data-entity-urn", "")
                    urn_match = re.search(r"jobPosting:(\d+)", urn)
                    if urn_match:
                        job_id = urn_match.group(1)

            if not job_id:
                # Fallback to hash of title and URL
                job_id = str(abs(hash(f"{title}_{raw_url}")))

            # 3. Company
            company_tag = card_soup.find("h4", class_=re.compile("base-search-card__subtitle"))
            company = company_tag.get_text(strip=True) if company_tag else "Unknown Company"

            # 4. Location
            loc_tag = card_soup.find("span", class_=re.compile("job-search-card__location"))
            location = loc_tag.get_text(strip=True) if loc_tag else "Unknown"

            # Workplace type inference
            loc_lower = location.lower()
            title_lower = title.lower()
            if "on-site" in title_lower or "onsite" in title_lower:
                workplace_type = "On-site"
            elif "hybrid" in loc_lower or "hybrid" in title_lower:
                workplace_type = "Hybrid"
            elif "remote" in loc_lower or "remote" in title_lower or "remote" in query_location.lower():
                workplace_type = "Remote"
            else:
                workplace_type = "On-site"

            # 5. Posted Date
            time_tag = card_soup.find("time")
            posted_date = time_tag.get_text(strip=True) if time_tag else "Recent"

            return JobItem(
                id=f"li_{job_id}",
                external_id=job_id,
                source="linkedin_guest",
                title=title,
                company=company,
                location=location,
                workplace_type=workplace_type,
                apply_url=raw_url,
                description="",  # Full description can be fetched on demand
                experience_level="Associate / Entry Level",
                posted_date=posted_date
            )

        except Exception as e:
            logger.debug(f"Failed to parse job card: {e}")
            return None

    def fetch_job_description(self, job_id: str) -> str:
        """
        Fetches the full job description HTML/text for a given job ID.
        Uses LinkedIn's public job detail endpoint without login.
        """
        clean_id = job_id.replace("li_", "")
        url = self.BASE_DETAIL_URL.format(job_id=clean_id)

        try:
            # Jitter delay
            time.sleep(self.request_delay + random.uniform(0.5, 1.5))
            with httpx.Client(headers=self._get_headers(), timeout=12.0, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    desc_div = soup.find("div", class_=re.compile("show-more-less-html__markup"))
                    if desc_div:
                        return desc_div.get_text(separator="\n", strip=True)
                    # Fallback to body text
                    return soup.get_text(separator="\n", strip=True)[:4000]
                else:
                    logger.debug(f"Job detail endpoint returned status {resp.status_code} for job {job_id}")
        except Exception as e:
            logger.debug(f"Could not fetch full description for job {job_id}: {e}")

        return ""
