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
    Index,
    text,
    or_
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config import settings

Base = declarative_base()


class JobRecord(Base):
    """Stores raw and normalized job listings."""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)  # LinkedIn job ID or content hash
    external_id = Column(String, index=True)
    source = Column(String, default="linkedin_guest")  # linkedin_guest, topjobs_lk, itpro_lk, etc.
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
    user_status = Column(String, default="NEW")  # NEW, BOOKMARKED, APPLIED, INTERVIEWING, REJECTED, OFFER
    user_notes = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    """Initializes tables in the SQLite database and performs schema migrations."""
    Base.metadata.create_all(bind=engine)
    # Lightweight column migration for existing databases
    with engine.connect() as conn:
        for col_name, col_type in [
            ("user_status", "VARCHAR DEFAULT 'NEW'"),
            ("user_notes", "TEXT DEFAULT ''"),
            ("updated_at", "DATETIME")
        ]:
            try:
                conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}"))
                conn.commit()
            except Exception:
                pass

    # Automatically purge historical foreign non-remote records
    try:
        JobRepository.purge_non_compliant_jobs()
    except Exception:
        pass


class JobRepository:
    """Encapsulates all database operations for clean separation of concerns."""

    @staticmethod
    def is_duplicate(job_id: str) -> bool:
        """Checks if a job has already been scraped and recorded."""
        with SessionLocal() as session:
            return session.query(JobRecord).filter(JobRecord.id == job_id).first() is not None

    @staticmethod
    def is_already_notified(job_id: str, channel: str = "TELEGRAM") -> bool:
        """Checks if a notification was already successfully delivered for this job."""
        with SessionLocal() as session:
            notif = (
                session.query(NotificationRecord)
                .filter(
                    NotificationRecord.job_id == job_id,
                    NotificationRecord.channel == channel,
                    NotificationRecord.status == "SENT"
                )
                .first()
            )
            return notif is not None

    @staticmethod
    def get_saved_evaluation(job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves an existing AI evaluation record if already computed."""
        with SessionLocal() as session:
            rec = session.query(JobEvaluationRecord).filter(JobEvaluationRecord.job_id == job_id).first()
            if not rec:
                return None
            return {
                "match_score": rec.match_score,
                "match_verdict": rec.match_verdict,
                "experience_fit": rec.experience_fit or "",
                "matching_skills": json.loads(rec.matching_skills) if rec.matching_skills else [],
                "missing_skills": json.loads(rec.missing_skills) if rec.missing_skills else [],
                "pros": json.loads(rec.pros) if rec.pros else [],
                "concerns": json.loads(rec.concerns) if rec.concerns else [],
                "summary": rec.summary or ""
            }

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

    @staticmethod
    def update_user_tracking(job_id: str, status: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Updates personal tracking status (APPLIED, BOOKMARKED, etc.) and notes for a job."""
        with SessionLocal() as session:
            job = session.query(JobRecord).filter(JobRecord.id == job_id).first()
            if not job:
                return False
            if status is not None:
                job.user_status = status.upper()
            if notes is not None:
                job.user_notes = notes
            job.updated_at = datetime.utcnow()
            session.commit()
            return True

    @staticmethod
    def get_all_jobs_with_evaluations(
        search: str = "",
        source: str = "",
        location: str = "",
        min_score: int = 0,
        user_status: str = "",
        limit: int = 500,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieves jobs joined with AI evaluation details, ordered by match score."""
        with SessionLocal() as session:
            query = session.query(JobRecord, JobEvaluationRecord).outerjoin(
                JobEvaluationRecord, JobRecord.id == JobEvaluationRecord.job_id
            )

            if source and source.lower() != "all":
                query = query.filter(JobRecord.source == source)

            if location and location.lower() != "all":
                loc_key = location.lower()
                if loc_key == "colombo":
                    colombo_terms = [
                        'colombo', 'nugegoda', 'battaramulla', 'malabe', 'kaduwela',
                        'kollupitiya', 'kottawa', 'piliyandala', 'dehiwala', 'rajagiriya',
                        'mount lavinia', 'moratuwa', 'western province'
                    ]
                    query = query.filter(or_(*[JobRecord.location.ilike(f"%{t}%") for t in colombo_terms]))
                elif loc_key == "jaffna":
                    query = query.filter(
                        (JobRecord.location.ilike("%jaffna%")) |
                        (JobRecord.location.ilike("%northern province%"))
                    )
                elif loc_key == "kandy":
                    query = query.filter(
                        (JobRecord.location.ilike("%kandy%")) |
                        (JobRecord.location.ilike("%central province%"))
                    )
                elif loc_key == "galle":
                    query = query.filter(
                        (JobRecord.location.ilike("%galle%")) |
                        (JobRecord.location.ilike("%southern province%")) |
                        (JobRecord.location.ilike("%matara%"))
                    )
                elif loc_key == "kurunegala":
                    query = query.filter(
                        (JobRecord.location.ilike("%kurunegala%")) |
                        (JobRecord.location.ilike("%north western province%"))
                    )
                elif loc_key == "gampaha":
                    gampaha_terms = ['gampaha', 'negombo', 'ja-ela', 'kandana', 'katunayake', 'wattala', 'kelaniya', 'kochchikade', 'badalgama']
                    query = query.filter(or_(*[JobRecord.location.ilike(f"%{t}%") for t in gampaha_terms]))
                elif loc_key == "remote":
                    query = query.filter(
                        (JobRecord.workplace_type.ilike("remote")) |
                        (JobRecord.location.ilike("%remote%"))
                    )
                elif loc_key == "other_sl":
                    query = query.filter(JobRecord.location.ilike("%sri lanka%"))
                else:
                    loc_pattern = f"%{loc_key}%"
                    query = query.filter(JobRecord.location.ilike(loc_pattern))

            if user_status and user_status.lower() != "all":
                query = query.filter(JobRecord.user_status == user_status.upper())

            if min_score > 0:
                query = query.filter(JobEvaluationRecord.match_score >= min_score)

            if search:
                term = f"%{search.lower()}%"
                query = query.filter(
                    (JobRecord.title.ilike(term)) |
                    (JobRecord.company.ilike(term)) |
                    (JobRecord.location.ilike(term)) |
                    (JobEvaluationRecord.matching_skills.ilike(term))
                )

            results = (
                query.order_by(
                    JobEvaluationRecord.match_score.desc().nullslast(),
                    JobRecord.discovered_at.desc()
                )
                .offset(offset)
                .limit(limit)
                .all()
            )

            jobs_list = []
            for job, eval_rec in results:
                eval_data = {}
                if eval_rec:
                    eval_data = {
                        "match_score": eval_rec.match_score,
                        "match_verdict": eval_rec.match_verdict,
                        "experience_fit": eval_rec.experience_fit or "",
                        "matching_skills": json.loads(eval_rec.matching_skills) if eval_rec.matching_skills else [],
                        "missing_skills": json.loads(eval_rec.missing_skills) if eval_rec.missing_skills else [],
                        "pros": json.loads(eval_rec.pros) if eval_rec.pros else [],
                        "concerns": json.loads(eval_rec.concerns) if eval_rec.concerns else [],
                        "summary": eval_rec.summary or ""
                    }
                else:
                    eval_data = {
                        "match_score": 0,
                        "match_verdict": "PENDING",
                        "matching_skills": [],
                        "missing_skills": [],
                        "pros": [],
                        "concerns": [],
                        "summary": "Pending AI evaluation."
                    }

                jobs_list.append({
                    "id": job.id,
                    "external_id": job.external_id,
                    "source": job.source,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location or "Sri Lanka",
                    "workplace_type": job.workplace_type or "On-site",
                    "apply_url": job.apply_url,
                    "description": job.description or "",
                    "experience_level": job.experience_level or "Associate",
                    "posted_date": job.posted_date or "Recent",
                    "discovered_at": job.discovered_at.isoformat() if job.discovered_at else "",
                    "status": job.status,
                    "user_status": job.user_status or "NEW",
                    "user_notes": job.user_notes or "",
                    "evaluation": eval_data
                })

            return jobs_list

    @staticmethod
    def get_stats_summary() -> Dict[str, Any]:
        """Calculates high-level metrics and portal breakdown."""
        with SessionLocal() as session:
            total_jobs = session.query(JobRecord).count()
            evaluated_jobs = session.query(JobEvaluationRecord).count()
            high_matches = (
                session.query(JobEvaluationRecord)
                .filter(JobEvaluationRecord.match_score >= settings.min_match_score)
                .count()
            )
            bookmarked = session.query(JobRecord).filter(JobRecord.user_status == "BOOKMARKED").count()
            applied = session.query(JobRecord).filter(JobRecord.user_status == "APPLIED").count()
            omitted = session.query(JobRecord).filter(JobRecord.user_status == "OMITTED").count()
            interviewing = session.query(JobRecord).filter(JobRecord.user_status == "INTERVIEWING").count()

            # Group by sources
            from sqlalchemy import func
            sources = (
                session.query(JobRecord.source, func.count(JobRecord.id))
                .group_by(JobRecord.source)
                .all()
            )
            source_breakdown = {s: count for s, count in sources}

            return {
                "total_jobs": total_jobs,
                "evaluated_jobs": evaluated_jobs,
                "high_matches": high_matches,
                "bookmarked_count": bookmarked,
                "applied_count": applied,
                "omitted_count": omitted,
                "interviewing_count": interviewing,
                "source_breakdown": source_breakdown,
                "min_match_score_threshold": settings.min_match_score
            }

    @staticmethod
    def export_dashboard_payload() -> Dict[str, Any]:
        """Builds a complete, standalone payload for offline / static web viewing."""
        stats = JobRepository.get_stats_summary()
        all_jobs = JobRepository.get_all_jobs_with_evaluations(limit=1000)
        return {
            "meta": {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "app_name": "AI Job Search Agent",
                "candidate_name": "Abivarsan Ketheeswaran",
                "total_count": len(all_jobs)
            },
            "stats": stats,
            "jobs": all_jobs
        }

    @staticmethod
    def purge_non_compliant_jobs() -> int:
        """
        Removes any historical jobs that violate location preferences:
        Outside Sri Lanka, ONLY 100% Remote roles are allowed.
        Any foreign on-site or hybrid roles are permanently purged from database.
        """
        sri_lanka_terms = [
            "sri lanka", "colombo", "moratuwa", "jaffna", "kandy", "galle",
            "dehiwala", "rajagiriya", "nugegoda", "battaramulla", "malabe",
            "mount lavinia", "gampaha", "kurunegala", "negombo", "ratnapura",
            "matara", "kalutara", "katunayake", "panadura", "wattala", "kelaniya"
        ]
        domestic_portals = {"topjobs_lk", "itpro_lk", "rooster_jobs", "xpress_jobs"}

        with SessionLocal() as session:
            all_jobs = session.query(JobRecord).all()
            to_delete_ids = []

            for job in all_jobs:
                # Purge legacy TopJobs records lacking required '&ec=' servlet parameter (Error 601)
                if job.source == "topjobs_lk" and "&ec=" not in (job.apply_url or ""):
                    to_delete_ids.append(job.id)
                    continue

                is_domestic = job.source in domestic_portals
                loc_lower = f"{job.location or ''} {job.title or ''}".lower()
                is_sri_lanka = is_domestic or any(t in loc_lower for t in sri_lanka_terms)

                if not is_sri_lanka:
                    wp_lower = (job.workplace_type or "").lower()
                    title_lower = (job.title or "").lower()
                    loc_only_lower = (job.location or "").lower()

                    is_on_site_or_hybrid = (
                        wp_lower in ["on-site", "onsite", "hybrid"] or
                        "onsite" in title_lower or "on-site" in title_lower or "hybrid" in title_lower or "hybrid" in loc_only_lower
                    )
                    # Foreign roles MUST have positive proof of remote status (in location or title)
                    is_verified_remote = (
                        "remote" in loc_only_lower or
                        "remote" in title_lower or
                        (wp_lower == "remote" and ("remote" in loc_only_lower or "remote" in title_lower))
                    )

                    if is_on_site_or_hybrid or not is_verified_remote:
                        to_delete_ids.append(job.id)

            if to_delete_ids:
                session.query(JobEvaluationRecord).filter(JobEvaluationRecord.job_id.in_(to_delete_ids)).delete(synchronize_session=False)
                session.query(NotificationRecord).filter(NotificationRecord.job_id.in_(to_delete_ids)).delete(synchronize_session=False)
                session.query(JobRecord).filter(JobRecord.id.in_(to_delete_ids)).delete(synchronize_session=False)
                session.commit()

            return len(to_delete_ids)
