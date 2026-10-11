"""
Base interface and data models for job extraction.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field


class JobItem(BaseModel):
    """Normalized job posting data model."""
    id: str = Field(description="Unique identifier (e.g. LinkedIn ID or content hash)")
    external_id: Optional[str] = Field(default=None, description="Platform native ID")
    source: str = Field(default="linkedin_guest", description="Origin platform / API")
    title: str = Field(description="Job title")
    company: str = Field(description="Hiring company name")
    location: str = Field(default="Unknown", description="Job location")
    workplace_type: str = Field(default="Unknown", description="Remote, Hybrid, or On-site")
    apply_url: str = Field(description="Direct URL to view or apply for the job")
    description: str = Field(default="", description="Full or extracted job description text")
    experience_level: str = Field(default="Entry / Associate", description="Experience level requirement")
    posted_date: str = Field(default="Recent", description="When the position was published")


class BaseJobExtractor(ABC):
    """Abstract interface for all job extractors."""

    @abstractmethod
    def search_jobs(self, keywords: str, location: str, limit: int = 25) -> List[JobItem]:
        """
        Executes a job search query and returns normalized job items.
        
        Args:
            keywords: Search terms (e.g., 'Software Engineer')
            location: Geographic location or 'Remote'
            limit: Maximum number of jobs to fetch
            
        Returns:
            List of normalized JobItem objects
        """
        pass
