"""
LinkedIn Public Feed Posts Job Extractor.
Discovers and extracts job opportunities shared by recruiters, HR managers, and
engineering leads in public LinkedIn posts (linkedin.com/posts/...), normalizing
unstructured post text into structured JobItem records for unified filtering.
"""

import re
import json
import time
import random
import unicodedata
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Set
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from extractors.base import BaseJobExtractor, JobItem
from database import JobRepository


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

SRI_LANKA_CITIES = [
    "colombo", "moratuwa", "jaffna", "kandy", "galle", "dehiwala",
    "rajagiriya", "nugegoda", "battaramulla", "malabe", "mount lavinia",
    "gampaha", "kurunegala", "negombo", "ratnapura", "matara",
    "kalutara", "katunayake", "panadura", "wattala", "kelaniya"
]

SRI_LANKA_HASHTAGS_AND_TERMS = [
    "sri lanka", "srilanka", "#srilanka", "#srilankajobs", "#colombojobs",
    "#lkjobs", "#itjobssrilanka", "#techjobssrilanka", "#nextjobsl", "🇱🇰"
]

CANDIDATE_SEEKING_PHRASES = [
    "#opentowork", "open to work", "looking for a job", "looking for an internship",
    "seeking an internship", "seeking a job", "seeking an opportunity",
    "looking for my next opportunity", "am looking for a software",
    "happy to share that i", "excited to announce that i", "thrilled to share that i",
    "pleased to announce that i", "i have joined", "i've joined",
    "completed my internship", "successfully completed my", "technology stack of 55"
]

POSITIVE_HIRING_SIGNALS = [
    "we're hiring", "we are hiring", "is hiring", "are hiring", "hiring!",
    "hiring:", "hiring -", "hiring a ", "hiring an ", "hiring for",
    "vacancy", "vacancies", "open role", "open position", "job opportunity",
    "looking for a ", "looking for an ", "join our team", "join the team",
    "send your cv", "share your cv", "forward your cv", "drop your cv",
    "send us your cv", "email your cv", "send your resume", "apply now",
    "apply here", "how to apply", "#hiring", "#wearehiring", "#werehiring"
]

TARGET_ROLE_PATTERNS = [
    r"(?:Associate|Junior|Intern|Trainee|Graduate)\s+(?:Full[- ]?Stack\s+)?(?:Software|Backend|Frontend|Web|\.NET|Java|Python|AI)\s+(?:Engineer|Developer)",
    r"(?:Software|Full[- ]?Stack|Backend|Frontend|\.NET|Java)\s+(?:Engineering|Developer|Development)\s+(?:Intern|Internship|Trainee|Associate)",
    r"(?:Associate|Junior)\s+(?:Software|Systems|Application|Web|Cloud|DevOps|QA)\s+(?:Engineer|Developer)",
    r"(?:Full[- ]?Stack|Software|Backend|\.NET|Java|React|Node\.?js|Python|C#)\s+(?:Software\s+)?(?:Engineer|Developer)",
    r"(?:Software|Web|Application|Mobile)\s+(?:Engineer|Developer)"
]

GENERIC_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "live.com"
}


class LinkedInPostsExtractor(BaseJobExtractor):
    """Discovers and extracts job openings shared via public LinkedIn feed posts."""

    def __init__(self, max_age_days: int = 45, request_delay: float = 1.2):
        self.max_age_days = max_age_days
        self.request_delay = request_delay
        self._seen_post_ids: Set[str] = set()

    def _get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        }

    @staticmethod
    def decode_snowflake_timestamp(url_or_id: str) -> Optional[Tuple[str, datetime]]:
        """
        Extracts the 19-digit LinkedIn Snowflake activity/share ID and decodes its
        exact UTC creation timestamp (top 41 bits = Unix epoch milliseconds).
        """
        match = re.search(r"(?:activity|share|ugcPost)-(\d{19})", url_or_id)
        if not match:
            match = re.search(r"\b(\d{19})\b", url_or_id)
        if not match:
            return None

        post_id = match.group(1)
        try:
            ts_ms = int(post_id) >> 22
            dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
            if 2015 <= dt.year <= datetime.now(timezone.utc).year + 1:
                return post_id, dt
        except Exception:
            pass
        return None

    def search_jobs(self, keywords: str = "Software Engineer", location: str = "Sri Lanka", limit: int = 20) -> List[JobItem]:
        """
        Discovers public LinkedIn hiring posts matching keywords and location,
        hydrates fresh posts, and returns normalized JobItem instances.
        """
        logger.info(f"[LinkedIn Posts] Discovering public hiring posts for '{keywords}' in '{location}'...")
        discovered_candidates = self._discover_post_urls(keywords=keywords, location=location, max_results=limit * 2)

        jobs: List[JobItem] = []
        now_utc = datetime.now(timezone.utc)

        for url, snippet_title, snippet_body in discovered_candidates:
            if len(jobs) >= limit:
                break

            snowflake = self.decode_snowflake_timestamp(url)
            if not snowflake:
                continue

            post_id, post_dt = snowflake
            if post_id in self._seen_post_ids:
                continue
            self._seen_post_ids.add(post_id)

            # 1. Pre-fetch Snowflake Age Filter
            age_days = (now_utc - post_dt).days
            if age_days > self.max_age_days:
                logger.debug(f"[LinkedIn Posts] Skipping stale post {post_id} ({post_dt.strftime('%Y-%m-%d')}, {age_days}d old)")
                continue

            job_uid = f"lipost_{post_id}"

            # 2. Skip network hydration if already stored and evaluated in DB
            if JobRepository.is_duplicate(job_uid) and JobRepository.get_saved_evaluation(job_uid):
                logger.debug(f"[LinkedIn Posts] Post {job_uid} already indexed in database.")
                continue

            # 3. Hydrate and parse the public LinkedIn post
            job_item = self._fetch_and_parse_post(
                url=url,
                post_id=post_id,
                post_dt=post_dt,
                snippet_title=snippet_title,
                snippet_body=snippet_body,
                query_location=location
            )
            if job_item:
                jobs.append(job_item)

        logger.info(f"[LinkedIn Posts] Extracted {len(jobs)} valid job opportunities from LinkedIn posts for '{keywords}' ({location}).")
        return jobs

    def _discover_post_urls(self, keywords: str, location: str, max_results: int = 25) -> List[Tuple[str, str, str]]:
        """
        Uses multi-backend search queries (Yahoo, Bing, DuckDuckGo) to discover
        public linkedin.com/posts URLs without requiring LinkedIn login.
        Returns list of (url, snippet_title, snippet_body).
        """
        results: List[Tuple[str, str, str]] = []
        seen_urls: Set[str] = set()

        loc_clean = location.strip()
        dorks = [f"site:linkedin.com/posts hiring {keywords} {loc_clean}"]

        try:
            from ddgs import DDGS
            ddgs_client = DDGS()
            for q in dorks:
                for backend in ["yahoo", "bing"]:
                    try:
                        hits = ddgs_client.text(q, backend=backend, max_results=15)
                        for h in hits or []:
                            href = (h.get("href") or "").split("?")[0]
                            if "/posts/" in href or "/feed/update/" in href:
                                if href not in seen_urls:
                                    seen_urls.add(href)
                                    results.append((
                                        href,
                                        h.get("title") or "",
                                        h.get("body") or ""
                                    ))
                    except Exception as e:
                        logger.debug(f"[LinkedIn Posts] Search backend '{backend}' returned no hits for '{q}': {e}")
                    time.sleep(0.35)
                if len(results) >= max_results:
                    break
        except ImportError:
            logger.warning("[LinkedIn Posts] 'ddgs' library not installed; skipping search discovery.")
        except Exception as e:
            logger.error(f"[LinkedIn Posts] Unexpected error during post discovery: {e}")

        return results

    def _fetch_and_parse_post(
        self,
        url: str,
        post_id: str,
        post_dt: datetime,
        snippet_title: str = "",
        snippet_body: str = "",
        query_location: str = ""
    ) -> Optional[JobItem]:
        """Fetches a public LinkedIn post URL and extracts structured job details."""
        post_text = ""
        headline = ""
        author_name = ""
        author_type = "Person"
        author_url = ""
        published_str = post_dt.strftime("%Y-%m-%d")

        try:
            time.sleep(self.request_delay + random.uniform(0.2, 0.5))
            with httpx.Client(headers=self._get_headers(), timeout=12.0, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")

                    # 1. Try Schema.org SocialMediaPosting JSON-LD
                    ld_tag = soup.find("script", type="application/ld+json")
                    if ld_tag and ld_tag.string:
                        try:
                            ld_data = json.loads(ld_tag.string)
                            if isinstance(ld_data, dict):
                                post_text = ld_data.get("articleBody") or ""
                                headline = ld_data.get("headline") or ""
                                date_pub = ld_data.get("datePublished") or ""
                                if date_pub:
                                    published_str = date_pub[:10]
                                author_obj = ld_data.get("author") or {}
                                if isinstance(author_obj, dict):
                                    author_name = author_obj.get("name") or ""
                                    author_type = author_obj.get("@type") or "Person"
                                    author_url = author_obj.get("url") or ""
                        except Exception:
                            pass

                    # 2. Fallback / Supplement with OpenGraph Meta Tags
                    if not post_text:
                        og_desc = soup.find("meta", property="og:description")
                        if og_desc and og_desc.get("content"):
                            post_text = og_desc["content"].strip()

                    if not headline:
                        og_title = soup.find("meta", property="og:title")
                        if og_title and og_title.get("content"):
                            headline = og_title["content"].strip()
                            if "|" in headline and not author_name:
                                parts = headline.rsplit("|", 1)
                                author_name = parts[-1].replace("posted on the topic", "").replace("- LinkedIn", "").strip()
                else:
                    logger.debug(f"[LinkedIn Posts] HTTP {resp.status_code} for {url}, falling back to search snippet.")
        except Exception as e:
            logger.debug(f"[LinkedIn Posts] Failed to fetch post {url}: {e}")

        # Fallback to search engine snippet if post page blocked or unavailable
        if not post_text and snippet_body:
            post_text = f"{snippet_title}\n{snippet_body}"

        if not post_text or len(post_text.strip()) < 30:
            return None

        return self.parse_post_content(
            url=url,
            post_id=post_id,
            post_text=post_text,
            headline=headline or snippet_title,
            author_name=author_name,
            author_type=author_type,
            author_url=author_url,
            published_date=published_str
        )

    def parse_post_content(
        self,
        url: str,
        post_id: str,
        post_text: str,
        headline: str = "",
        author_name: str = "",
        author_type: str = "Person",
        author_url: str = "",
        published_date: str = "Recent"
    ) -> Optional[JobItem]:
        """
        Determines whether a LinkedIn post is an authentic job opening and parses
        structured JobItem fields (title, company, location, workplace_type, experience).
        """
        normalized_text = unicodedata.normalize("NFKC", post_text)
        normalized_headline = unicodedata.normalize("NFKC", headline)
        combined = f"{normalized_headline}\n{normalized_text}"
        combined_lower = combined.lower()

        # 1. Verify Hiring Intent (Reject candidate #OpenToWork or general articles)
        if any(phrase in combined_lower for phrase in CANDIDATE_SEEKING_PHRASES):
            logger.debug(f"[LinkedIn Posts] Rejected candidate/non-hiring post {post_id}")
            return None

        if not any(sig in combined_lower for sig in POSITIVE_HIRING_SIGNALS):
            logger.debug(f"[LinkedIn Posts] Rejected post {post_id}: no positive hiring signal")
            return None

        # 2. Extract Role Title
        title = self._extract_role_title(normalized_text, normalized_headline)
        if not title:
            logger.debug(f"[LinkedIn Posts] Rejected post {post_id}: could not identify target engineering title")
            return None

        # 3. Extract Experience Requirement & Filter Senior-Only Posts
        experience_level, is_senior_only = self._extract_experience_level(normalized_text, title)
        if is_senior_only and not any(k in title.lower() for k in ["senior", "lead"]):
            title = f"{title} (Senior {experience_level})"

        # 4. Extract Company Name
        company = self._extract_company(normalized_text, author_name, author_type, url)

        # 5. Extract Location & Strict Workplace Type (Never assume Remote from search query!)
        location, workplace_type = self._extract_location_and_workplace(
            normalized_text, url, author_url
        )

        # 6. Extract Application Emails / Links to enrich description
        emails = list(dict.fromkeys(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", normalized_text)))
        links = list(dict.fromkeys(re.findall(r"https?://[^\s\)\]>\"']+", normalized_text)))

        contact_header_lines = []
        if emails:
            contact_header_lines.append(f"📩 Apply / Contact Email: {', '.join(emails[:3])}")
        if links:
            contact_header_lines.append(f"🔗 Direct Link in Post: {', '.join(links[:2])}")
        if author_name:
            contact_header_lines.append(f"👤 Posted by: {author_name}")

        enriched_description = normalized_text.strip()
        if contact_header_lines:
            enriched_description = "\n".join(contact_header_lines) + "\n\n---\n" + enriched_description

        return JobItem(
            id=f"lipost_{post_id}",
            external_id=post_id,
            source="linkedin_posts",
            title=title,
            company=company,
            location=location,
            workplace_type=workplace_type,
            apply_url=url,
            description=enriched_description[:4000],
            experience_level=experience_level,
            posted_date=published_date
        )

    def _extract_role_title(self, text: str, headline: str) -> Optional[str]:
        """Extracts a clean software engineering role title from unstructured post text."""
        corpus = f"{headline}\n{text}"

        # Pass 1: Look for explicit labeled position lines (e.g. "Position: Associate Software Engineer")
        labeled_patterns = [
            r"(?:Position|Role|Job Title|Vacancy|Opening)\s*[:\-–]\s*([^\n•|🎯🚀📍💼]{4,65})",
            r"(?:We['’]?re\s+Hiring|We\s+are\s+Hiring|Hiring\s+Now|Hiring)\s*[!:\-–|]+\s*([^\n•|🎯🚀📍💼]{4,65})"
        ]
        for pat in labeled_patterns:
            for match in re.finditer(pat, corpus, flags=re.IGNORECASE):
                candidate = self._clean_title_candidate(match.group(1))
                if self._is_software_role(candidate):
                    return candidate

        # Pass 2: Search for target software engineering role phrases in the body
        for pattern in TARGET_ROLE_PATTERNS:
            match = re.search(pattern, corpus, flags=re.IGNORECASE)
            if match:
                candidate = self._clean_title_candidate(match.group(0))
                if candidate:
                    return candidate

        return None

    @staticmethod
    def _clean_title_candidate(raw: str) -> str:
        """Removes hashtags, emojis, locations, and trailing noise from a candidate title."""
        cleaned = re.sub(r"#\S+", "", raw)
        cleaned = re.split(
            r"\s+[\|•📍💼]\s+|\s+-\s+(?:Colombo|Sri Lanka|Remote|On-?site|Hybrid|\d+\s*[-–]\s*\d+\s*years)",
            cleaned,
            flags=re.IGNORECASE
        )[0]
        cleaned = re.sub(r"[^\w\s\.\-\(\)/#\+&]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–:.,|/")
        # Balance parentheses if needed
        if cleaned.count("(") > cleaned.count(")"):
            cleaned = cleaned.rstrip("(").strip()
            if "(" in cleaned and not cleaned.endswith(")"):
                cleaned += ")"
        elif cleaned.count(")") > cleaned.count("("):
            cleaned = cleaned.rstrip(")").strip()

        if cleaned.islower() or cleaned.isupper():
            cleaned = cleaned.title()
        return cleaned[:75].strip()

    @staticmethod
    def _is_software_role(title: str) -> bool:
        t_low = title.lower()
        if len(t_low) < 4:
            return False
        keywords = [
            "software", "engineer", "developer", "full stack", "fullstack",
            "backend", "frontend", ".net", "java", "react", "node", "python", "associate"
        ]
        return any(k in t_low for k in keywords)

    def _extract_company(self, text: str, author_name: str, author_type: str, url: str) -> str:
        """Identifies the hiring company from organization author, text patterns, or email domain."""
        if author_type == "Organization" and author_name:
            return author_name.strip()

        company_patterns = [
            r"(?:join\s+the\s+team\s+at|join\s+us\s+at|hiring\s+at|opportunity\s+at|working\s+at)\s+([A-Z][A-Za-z0-9\s&\.\(\)-]{2,40}?)(?:!|\.|,|\n|\s+is\s+|\s+in\s+|\s+to\s+)",
            r"([A-Z][A-Za-z0-9\s&\.]{2,35}?(?:\(Pvt\)\s*Ltd|Pvt\s*Ltd|Labs|Technologies|Solutions|Systems|Digital|Software))\s+is\s+(?:seeking|hiring|looking\s+for)"
        ]
        for pat in company_patterns:
            m = re.search(pat, text)
            if m:
                comp = m.group(1).strip(" .,!-:")
                if 2 < len(comp) <= 45 and "linkedin" not in comp.lower():
                    return comp

        emails = re.findall(r"[a-zA-Z0-9_.+-]+@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", text)
        for domain in emails:
            domain_low = domain.lower().strip(".")
            if domain_low not in GENERIC_EMAIL_DOMAINS:
                company_part = domain_low.split(".")[0]
                if len(company_part) >= 3 and company_part not in {"careers", "jobs", "info", "mail", "apply"}:
                    return company_part.upper() if len(company_part) <= 4 else company_part.capitalize()

        if author_name:
            clean_author = re.sub(r"\s*[-|]\s*LinkedIn.*", "", author_name, flags=re.IGNORECASE).strip()
            if clean_author:
                return f"{clean_author} (LinkedIn Post)"

        slug_match = re.search(r"linkedin\.com/posts/([a-zA-Z0-9-]+?)_", url)
        if slug_match:
            slug = slug_match.group(1)
            slug = re.sub(r"-[0-9a-f]{6,}$", "", slug)
            return slug.replace("-", " ").title()

        return "LinkedIn Hiring Post"

    def _extract_location_and_workplace(self, text: str, url: str, author_url: str) -> Tuple[str, str]:
        """
        Deterministically extracts location and workplace type from post text.
        Strictly requires explicit remote indicators in the post text to classify as Remote.
        """
        text_lower = text.lower()
        url_lower = f"{url} {author_url}".lower()

        detected_sl_city = None
        for city in SRI_LANKA_CITIES:
            if re.search(rf"\b{re.escape(city)}\b", text_lower):
                detected_sl_city = city.title()
                break

        is_sri_lanka = (
            detected_sl_city is not None
            or any(term in text_lower for term in SRI_LANKA_HASHTAGS_AND_TERMS)
            or "lk.linkedin.com" in url_lower
        )

        has_remote = bool(
            re.search(r"\b(?:100%\s*remote|fully\s*remote|remote\s*work|work\s*from\s*home|wfh|remote)\b", text_lower)
            or "#remotejobs" in text_lower
            or "#remotework" in text_lower
            or "#remoteinternship" in text_lower
        ) and not bool(re.search(r"\b(?:no\s+remote|not\s+remote|strictly\s+on-?site)\b", text_lower))

        has_hybrid = bool(re.search(r"\bhybrid\b", text_lower) or "#hybrid" in text_lower)
        has_onsite = bool(re.search(r"\b(?:on-?site|office[- ]based|in[- ]office)\b", text_lower))

        if has_remote and not has_hybrid:
            workplace_type = "Remote"
        elif has_hybrid:
            workplace_type = "Hybrid"
        elif has_onsite:
            workplace_type = "On-site"
        else:
            workplace_type = "On-site"

        if is_sri_lanka:
            if detected_sl_city and detected_sl_city.lower() != "sri lanka":
                location = f"{detected_sl_city}, Sri Lanka"
            else:
                location = "Sri Lanka"
        else:
            loc_match = re.search(r"(?:Location|Based in|📍)\s*[:\-–]?\s*([A-Za-z\s,]{3,35})", text)
            if loc_match:
                extracted_loc = loc_match.group(1).strip(" .,|-•\n\r")
                location = extracted_loc if extracted_loc else ("Remote" if workplace_type == "Remote" else "Foreign / International")
            elif workplace_type == "Remote":
                location = "Remote"
            else:
                location = "Foreign / International"

        return location, workplace_type

    @staticmethod
    def _extract_experience_level(text: str, title: str) -> Tuple[str, bool]:
        """
        Extracts experience level requirement and flags if the post exclusively demands
        senior tenure (4+ years) with no entry/associate/junior track.
        """
        combined_lower = f"{title} {text}".lower()

        has_entry_or_associate = bool(
            re.search(r"\b(?:intern|internship|trainee|fresh\s*graduate|entry[- ]level|associate|junior|0\s*[-–to]+\s*[123]\s*years?|[12]\+?\s*years?)\b", combined_lower)
        )

        senior_years_match = re.search(r"\b([4-9]|1\d)\s*\+?\s*(?:to\s*\d+\s*)?years?(?:\s+of)?\s+experience\b", combined_lower)

        if senior_years_match and not has_entry_or_associate:
            yrs = senior_years_match.group(1)
            return f"{yrs}+ Years", True

        if "intern" in combined_lower or "trainee" in combined_lower:
            return "Internship / Trainee", False
        if "associate" in combined_lower or "0-" in combined_lower or "fresh" in combined_lower:
            return "Associate / Entry Level", False
        if "junior" in combined_lower or "1+" in combined_lower or "1-2" in combined_lower:
            return "Junior (1-2 Years)", False

        return "Associate / Entry Level", False
