"""
Database models and storage repository for the AI Job Search Agent.
Uses SQLite and SQLAlchemy for persistence, duplicate detection, and audit trails.
"""

from datetime import datetime
import json
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config import settings

Base = declarative_base()


class JobRecord(Base):
    """Stores raw and normalized job listings."""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)  # LinkedIn job ID or content hash
    external_id = Column(String, index=True)
    source = Column(String, default="linkedin_guest")  # linkedin_guest, rapidapi, etc.
    title = Column(String, nullable=False, index=True)
    company = Column(String, nullable=False, index=True)
    location = Column(String)
    workplace_type = Column(String, default="Unknown")  # Remote, Hybrid, On-site
    apply_url = Column(Text, nullable=False)
    description = Column(Text)
    experience_level = Column(String)
    posted_date = Column(String)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="PENDING")  # PENDING, EVALUATED, NOTIFIED, SKIPPED

    # Relationships
    evaluation = relationship("JobEvaluationRecord", back_populates="job", uselist=False)
    notifications = relationship("NotificationRecord", back_populates="job")

    __table_args__ = (
        Index("idx_company_title", "company", "title"),
    )


class JobEvaluationRecord(Base):
    """Stores LLM relevance evaluation and skill gap analysis."""
    __tablename__ = "job_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False, unique=True)
    match_score = Column(Integer, nullable=False)  # 0 to 100
    match_verdict = Column(String, nullable=False)  # STRONG_MATCH, MODERATE_MATCH, LOW_MATCH
    experience_fit = Column(Text)
    matching_skills = Column(Text)  # JSON-encoded array
    missing_skills = Column(Text)   # JSON-encoded array
    pros = Column(Text)             # JSON-encoded array
    concerns = Column(Text)         # JSON-encoded array
    summary = Column(Text)
    evaluated_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    job = relationship("JobRecord", back_populates="evaluation")


class NotificationRecord(Base):
    """Audit log of delivered notifications."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    channel = Column(String, nullable=False)  # WHATSAPP, TELEGRAM, DISCORD
    recipient = Column(String)
    status = Column(String, nullable=False)   # SENT, FAILED
    response_payload = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    job = relationship("JobRecord", back_populates="notifications")


# Database engine & session maker
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initializes tables in the SQLite database."""
    Base.metadata.create_all(bind=engine)


class JobRepository:
    """Encapsulates all database operations for clean separation of concerns."""

    @staticmethod
    def is_duplicate(job_id: str) -> bool:
        """Checks if a job has already been scraped and recorded."""
        with SessionLocal() as session:
            return session.query(JobRecord).filter(JobRecord.id == job_id).first() is not None

    @staticmethod
    def save_job(job_data: Dict[str, Any]) -> JobRecord:
        """Saves a new job listing to the database."""
        with SessionLocal() as session:
            record = JobRecord(
                id=job_data["id"],
                external_id=job_data.get("external_id", job_data["id"]),
                source=job_data.get("source", "linkedin_guest"),
                title=job_data["title"],
                company=job_data["company"],
                location=job_data.get("location", ""),
                workplace_type=job_data.get("workplace_type", "Unknown"),
                apply_url=job_data["apply_url"],
                description=job_data.get("description", ""),
                experience_level=job_data.get("experience_level", ""),
                posted_date=job_data.get("posted_date", ""),
                discovered_at=datetime.utcnow(),
                status="PENDING"
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    @staticmethod
    def save_evaluation(job_id: str, eval_data: Dict[str, Any]):
        """Persists AI evaluation results for a job."""
        with SessionLocal() as session:
            eval_record = JobEvaluationRecord(
                job_id=job_id,
                match_score=eval_data.get("match_score", 0),
                match_verdict=eval_data.get("match_verdict", "UNKNOWN"),
                experience_fit=eval_data.get("experience_fit", ""),
                matching_skills=json.dumps(eval_data.get("matching_skills", [])),
                missing_skills=json.dumps(eval_data.get("missing_skills", [])),
                pros=json.dumps(eval_data.get("pros", [])),
                concerns=json.dumps(eval_data.get("concerns", [])),
                summary=eval_data.get("summary", ""),
                evaluated_at=datetime.utcnow()
            )
            session.add(eval_record)
            # Update job status
            job = session.query(JobRecord).filter(JobRecord.id == job_id).first()
            if job:
                job.status = "EVALUATED"
            session.commit()

    @staticmethod
    def mark_notified(job_id: str, channel: str, recipient: str, status: str, payload: str = ""):
        """Logs a notification dispatch and updates job status."""
        with SessionLocal() as session:
            notif = NotificationRecord(
                job_id=job_id,
                channel=channel,
                recipient=recipient,
                status=status,
                response_payload=payload,
                sent_at=datetime.utcnow()
            )
            session.add(notif)
            if status == "SENT":
                job = session.query(JobRecord).filter(JobRecord.id == job_id).first()
                if job:
                    job.status = "NOTIFIED"
            session.commit()
