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

        # 2. Positive title checks (must match at least one relevant role pattern)
        is_relevant_role = False
        for target in self.target_roles:
            target_words = [w.lower() for w in target.split() if len(w) > 2]
            # Match if key terms appear
            if any(w in title_lower for w in ["software", "engineer", "developer", "programmer", "associate"]):
                is_relevant_role = True
                break

        if not is_relevant_role:
            return False, f"Title '{title}' does not match target software engineering titles"

        # 3. Location & Workplace Type Validation:
        # Rule: Within Sri Lanka -> On-site, Hybrid, and Remote are all allowed.
        # Rule: Outside Sri Lanka -> ONLY 100% Remote is allowed.
        loc_str = f"{job.location} {job.title}".lower()
        is_sri_lanka = any(term in loc_str for term in ["sri lanka", "colombo", "moratuwa", "jaffna", "kandy", "galle"])
        is_remote = (
            job.workplace_type.lower() == "remote" 
            or "remote" in job.title.lower() 
            or "remote" in job.location.lower()
        )

        if not is_sri_lanka and not is_remote:
            return False, f"International role is '{job.workplace_type}' in '{job.location}'. Only 100% Remote allowed outside Sri Lanka."

        return True, "Passed heuristic filter"

