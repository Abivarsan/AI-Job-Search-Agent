"""
Base interface for notification dispatchers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
from extractors.base import JobItem


class BaseNotifier(ABC):
    """Abstract base class for delivering job notifications."""

    @abstractmethod
    def send_job_alert(self, job: JobItem, evaluation: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Sends an alert for a matched job.
        
        Args:
            job: The normalized JobItem
            evaluation: AI evaluation dictionary
            
        Returns:
            Tuple of (success: bool, response_or_error_msg: str)
        """
        pass
