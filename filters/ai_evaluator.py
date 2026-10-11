"""
AI Job Relevance and Fit Evaluator.
Leverages Google Gemini API to analyze job descriptions against candidate qualifications,
compute match scores, detect skill gaps, and generate succinct notification summaries.
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger
from pydantic import BaseModel, Field
from extractors.base import JobItem
from config import settings

BASE_DIR = Path(__file__).resolve().parent.parent


class EvaluationResult(BaseModel):
    match_score: int = Field(ge=0, le=100, description="Match score from 0 to 100")
    match_verdict: str = Field(description="STRONG_MATCH, MODERATE_MATCH, or LOW_MATCH")
    experience_fit: str = Field(description="Assessment of whether candidate's experience level matches requirements")
    matching_skills: List[str] = Field(description="Skills required by the job that candidate possesses")
    missing_skills: List[str] = Field(description="Skills required by the job that candidate lacks")
    pros: List[str] = Field(description="Key positives or selling points for the candidate")
    concerns: List[str] = Field(description="Potential friction points or deal-breakers")
    summary: str = Field(description="Two-sentence compelling summary for WhatsApp notification")


class AIEvaluator:
    """Evaluates candidate-job alignment using Google Gemini."""

    def __init__(self, profile_path: Path = None):
        path = profile_path or (BASE_DIR / "candidate_profile.json")
        self.profile: Dict[str, Any] = {}
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self.profile = json.load(f)

        self.api_key = settings.gemini_api_key
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Google GenAI client: {e}")

    def evaluate_job(self, job: JobItem) -> Dict[str, Any]:
        """
        Runs comprehensive evaluation. Falls back to heuristic matching if
        Gemini API key is not configured.
        """
        if not self.client:
            logger.info(f"Gemini API key not configured. Using heuristic matcher for '{job.title}'.")
            return self._heuristic_fallback_evaluation(job)

        return self._gemini_evaluation(job)

    def _gemini_evaluation(self, job: JobItem) -> Dict[str, Any]:
        """Prompts Google Gemini for structured evaluation."""
        from google.genai import types

        prompt = f"""
You are an expert technical recruiter and career coach evaluating a job posting for an early-career software engineer.

### CANDIDATE PROFILE:
- Target Roles: {', '.join(self.profile.get('target_roles', []))}
- Experience Level: {self.profile.get('experience_level', 'Entry / Associate (0-2 years)')} ({self.profile.get('experience_years', 1)} years)
- Primary Skills: {', '.join(self.profile.get('primary_skills', []))}
- Secondary Skills: {', '.join(self.profile.get('secondary_skills', []))}
- Education: {self.profile.get('education', '')}
- Summary: {self.profile.get('summary', '')}
- Deal Breakers: {', '.join(self.profile.get('deal_breakers', []))}

### JOB POSTING:
- Title: {job.title}
- Company: {job.company}
- Location: {job.location} ({job.workplace_type})
- Description:
{job.description if job.description else "(No full description provided, evaluate based on title and metadata)"}

### EVALUATION CRITERIA:
1. Match Score (0-100):
   - 80-100: Ideal fit for associate / junior engineer, high skill overlap, 0-2 yrs requirement.
   - 65-79: Moderate fit, reasonable overlap, slight stretch.
   - <65: Mismatch (requires senior experience, unrelated tech stack, or violates deal breakers).
2. Identify explicitly matching skills vs missing requirements.
3. Keep summary punchy, factual, and ready for a WhatsApp message alert.
"""

        try:
            response = self.client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=EvaluationResult,
                    temperature=0.2
                )
            )

            result = json.loads(response.text)
            return result

        except Exception as e:
            logger.error(f"Error during Gemini evaluation: {e}")
            return self._heuristic_fallback_evaluation(job)

    def _heuristic_fallback_evaluation(self, job: JobItem) -> Dict[str, Any]:
        """Basic keyword overlap scoring used when offline or before API key setup."""
        primary_skills = [s.lower() for s in self.profile.get("primary_skills", [])]
        text_corpus = f"{job.title} {job.description}".lower()

        matched = [skill for skill in primary_skills if skill in text_corpus]
        missing = [skill for skill in primary_skills if skill not in text_corpus][:3]

        score = 75  # Baseline score for passing heuristic filter
        if len(matched) >= 3:
            score = 85
        elif len(matched) >= 5:
            score = 92

        # Check for associate / junior tags in title
        title_lower = job.title.lower()
        if any(term in title_lower for term in ["associate", "junior", "entry", "graduate"]):
            score = min(100, score + 10)

        verdict = "STRONG_MATCH" if score >= 80 else ("MODERATE_MATCH" if score >= 65 else "LOW_MATCH")

        return {
            "match_score": score,
            "match_verdict": verdict,
            "experience_fit": "Suitable for entry to associate software engineers.",
            "matching_skills": [s.title() for s in matched] if matched else ["Software Engineering", "Problem Solving"],
            "missing_skills": [s.title() for s in missing],
            "pros": [f"Target role match: {job.title}", f"Company: {job.company}"],
            "concerns": [],
            "summary": f"Opportunities at {job.company} for {job.title}. Relevant for candidates with Python/Full Stack background."
        }
