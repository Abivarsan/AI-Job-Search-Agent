"""
Fast heuristic filter to eliminate out-of-scope jobs before LLM evaluation.
Prevents wasted API costs and latency on irrelevant roles (e.g., Senior, Lead, Director).
"""

import re
import json
from pathlib import Path
from typing import Tuple, Dict, Any
from loguru import logger
from extractors.base import JobItem

BASE_DIR = Path(__file__).resolve().parent.parent


class HeuristicFilter:
    """Evaluates titles and locations against candidate criteria."""

    def __init__(self, profile_path: Path = None):
        path = profile_path or (BASE_DIR / "candidate_profile.json")
        self.profile: Dict[str, Any] = {}
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self.profile = json.load(f)

        self.negative_keywords = self.profile.get("negative_keywords_in_title", [
            "Senior", "Lead", "Principal", "Staff", "Architect", "Director", "Manager", "VP", "Head of"
        ])
        self.target_roles = self.profile.get("target_roles", [
            "Software Engineer", "Associate Software Engineer", "Junior Software Engineer", "Full Stack", "Backend"
        ])

    def evaluate(self, job: JobItem) -> Tuple[bool, str]:
        """
        Determines whether the job should proceed to full AI evaluation.
        Enforces identical rules across dedicated job portals and LinkedIn Posts.
        
        Returns:
            Tuple of (passes_filter: bool, reason: str)
        """
        title = job.title.strip()
        title_lower = title.lower()

        # 1. Negative title checks
        for neg in self.negative_keywords:
            # Use word boundary to avoid matching substring inside other words
            pattern = rf"\b{re.escape(neg.lower())}\b"
            if re.search(pattern, title_lower):
                return False, f"Title contains excluded keyword: '{neg}'"

        # 2. Experience level gate (reject roles demanding 4+ years tenure)
        exp_lower = (job.experience_level or "").lower()
        if re.search(r"\b([4-9]|1\d)\+\s*years\b", exp_lower):
            return False, f"Role requires senior tenure ({job.experience_level})"

        # 3. Positive title checks (must match at least one relevant role pattern)
        is_relevant_role = False
        for target in self.target_roles:
            target_words = [w.lower() for w in target.split() if len(w) > 2]
            if any(w in title_lower for w in [
                "software", "engineer", "developer", "programmer", "associate",
                "full stack", "fullstack", "backend", "frontend", ".net", "java"
            ]):
                is_relevant_role = True
                break

        if not is_relevant_role:
            return False, f"Title '{title}' does not match target software engineering titles"

        # 4. Location & Workplace Type Validation:
        # Rule: Within Sri Lanka -> On-site, Hybrid, and Remote are all allowed.
        # Rule: Outside Sri Lanka (Foreign) -> ONLY 100% Remote is allowed.
        sri_lanka_terms = [
            "sri lanka", "colombo", "moratuwa", "jaffna", "kandy", "galle",
            "dehiwala", "rajagiriya", "nugegoda", "battaramulla", "malabe",
            "mount lavinia", "gampaha", "kurunegala", "negombo", "ratnapura",
            "matara", "kalutara", "katunayake", "panadura", "wattala", "kelaniya"
        ]

        # Sri Lankan native portals are always domestic Sri Lanka
        is_domestic_portal = job.source in ["topjobs_lk", "itpro_lk", "rooster_jobs", "xpress_jobs"]
        loc_str = f"{job.location} {job.title}".lower()
        is_sri_lanka = is_domestic_portal or any(term in loc_str for term in sri_lanka_terms)

        if not is_sri_lanka:
            # Foreign job: MUST be strictly 100% Remote. Absolutely NO On-site or Hybrid.
            wp_lower = (job.workplace_type or "").lower()
            title_lower = job.title.lower()
            loc_lower = (job.location or "").lower()

            if wp_lower in ["on-site", "onsite", "hybrid"]:
                return False, f"Foreign role is '{job.workplace_type}' in '{job.location}'. Only 100% Remote allowed outside Sri Lanka."

            if "onsite" in title_lower or "on-site" in title_lower or "hybrid" in title_lower or "hybrid" in loc_lower:
                return False, f"Foreign role indicates on-site/hybrid in '{job.location}'. Only 100% Remote allowed outside Sri Lanka."

            # Positive proof required: foreign jobs must explicitly designate Remote in title or location
            is_verified_remote = (
                "remote" in loc_lower or
                "remote" in title_lower or
                (wp_lower == "remote" and ("remote" in loc_lower or "remote" in title_lower))
            )
            if not is_verified_remote:
                return False, f"Foreign role in '{job.location}' lacks verified 100% Remote status. Only 100% Remote allowed outside Sri Lanka."

        return True, "Passed heuristic filter"
