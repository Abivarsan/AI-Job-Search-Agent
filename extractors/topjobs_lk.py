"""
TopJobs.lk Extractor (Sri Lanka).
Scrapes vacancies from the Software Development & QA functional area (FA=SDQ)
on TopJobs / careers.lk without requiring authentication.
"""

import re
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from extractors.base import BaseJobExtractor, JobItem


class TopJobsExtractor(BaseJobExtractor):
    """Fetches Software Engineering vacancies from TopJobs.lk."""

    BASE_URL = "https://www.topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA=SDQ&jst=OPEN"
    DETAIL_URL = (
        "https://www.topjobs.lk/employer/JobAdvertismentServlet"
        "?rid={rid}&ac={ac}&jc={jc}&ec={ec}&pg=applicant/vacancybyfunctionalarea.jsp"
    )

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.topjobs.lk/"
        }

    def search_jobs(self, keywords: str = "", location: str = "Sri Lanka", limit: int = 40) -> List[JobItem]:
        """Scrapes open software engineering vacancies from TopJobs."""
        jobs: List[JobItem] = []
        logger.info("Scanning TopJobs.lk for IT / Software vacancies...")

        try:
            with httpx.Client(headers=self.headers, timeout=15.0, follow_redirects=True) as client:
                resp = client.get(self.BASE_URL)
                if resp.status_code != 200:
                    logger.warning(f"TopJobs returned HTTP status {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                rows = soup.find_all("tr", id=re.compile(r"^tr\d+"))
                logger.info(f"TopJobs: found {len(rows)} raw vacancy rows.")

                for row in rows:
                    if len(jobs) >= limit:
                        break

                    item = self._parse_row(row)
                    if item:
                        # Keyword filter if keyword specified
                        if keywords:
                            kw_lower = keywords.lower()
                            if kw_lower not in item.title.lower() and kw_lower not in item.description.lower():
                                continue
                        jobs.append(item)

        except Exception as e:
            logger.error(f"Error fetching TopJobs vacancies: {e}")

        logger.info(f"TopJobs: successfully parsed {len(jobs)} software vacancies.")
        return jobs

    def _parse_row(self, row_soup: BeautifulSoup) -> Optional[JobItem]:
        try:
            # 1. Extract Row ID (rid), Agent Code (ac), Job Code (jc), and Employer Code (ec)
            row_id_attr = row_soup.get("id", "")
            rid_match = re.search(r"\d+", row_id_attr)
            rid = rid_match.group(0) if rid_match else "0"

            onclick_attr = row_soup.get("onclick", "")
            alert_match = re.search(
                r"createAlert\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'",
                onclick_attr
            )

            jc_span = row_soup.find("span", id=re.compile(r"^hdnJC"))
            ec_span = row_soup.find("span", id=re.compile(r"^hdnEC"))
            ac_span = row_soup.find("span", id=re.compile(r"^hdnAC"))

            if alert_match:
                rid = alert_match.group(1).strip() or rid
                ac = alert_match.group(2).strip()
                jc = alert_match.group(3).strip()
                ec = alert_match.group(4).strip()
            else:
                jc = jc_span.get_text(strip=True) if jc_span else ""
                ac = ac_span.get_text(strip=True) if ac_span else "0000000000"
                ec = ec_span.get_text(strip=True) if ec_span else ""

            if not jc:
                # Fallback to td text
                tds = row_soup.find_all("td")
                if len(tds) > 1:
                    jc = tds[1].get_text(strip=True)

            if not jc or not ec:
                return None

            # 2. Title & Company
            h2 = row_soup.find("h2")
            h1 = row_soup.find("h1")

            title = h2.get_text(strip=True) if h2 else ""
            company = h1.get_text(strip=True) if h1 else "Unknown Company"

            if not title:
                return None

            # 3. Location and Dates
            tds = row_soup.find_all("td")
            loc_text = "Sri Lanka"
            posted_date = "Recent"

            if len(tds) >= 7:
                # Column 4: Opening date, Column 5: Closing date, Column 6: City
                date_td = tds[4].get_text(strip=True)
                if date_td:
                    posted_date = date_td
                city_td = tds[6].get_text(strip=True)
                if city_td and len(city_td) > 2:
                    loc_text = f"{city_td}, Sri Lanka"

            # Check workplace type
            title_lower = title.lower()
            workplace = "On-site"
            if "remote" in title_lower or "remote" in loc_text.lower():
                workplace = "Remote"
            elif "hybrid" in title_lower or "hybrid" in loc_text.lower():
                workplace = "Hybrid"

            apply_url = self.DETAIL_URL.format(rid=rid, ac=ac, jc=jc, ec=ec)

            return JobItem(
                id=f"topjobs_{jc}",
                external_id=jc,
                source="topjobs_lk",
                title=title,
                company=company,
                location=loc_text,
                workplace_type=workplace,
                apply_url=apply_url,
                description=f"Software opening on TopJobs.lk. Company: {company}. Location: {loc_text}. Closing: {tds[5].get_text(strip=True) if len(tds) >= 6 else 'N/A'}",
                experience_level="Entry / Associate",
                posted_date=posted_date
            )
        except Exception as e:
            logger.debug(f"TopJobs row parse error: {e}")
            return None
