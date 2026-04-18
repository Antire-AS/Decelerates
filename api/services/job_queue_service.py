"""PostgreSQL-backed job queue — durable alternative to FastAPI BackgroundTasks.

Usage:
    # Enqueue
    JobQueueService(db).enqueue("pdf_extract", {"orgnr": "123456789"})

    # Worker loop (run from main.py on startup)
    JobQueueService.process_pending(db_factory=SessionLocal)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db import JobQueue, SessionLocal

logger = logging.getLogger(__name__)

# Registry: job_type → handler function (db, payload) -> None
_HANDLERS: dict[str, Callable] = {}


def register_handler(job_type: str, fn: Callable) -> None:
    """Register a function to handle jobs of the given type."""
    _HANDLERS[job_type] = fn


class JobQueueService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def enqueue(self, job_type: str, payload: dict[str, Any] | None = None) -> JobQueue:
        """Add a job to the queue. Returns the created row."""
        now = datetime.now(timezone.utc)
        job = JobQueue(
            job_type=job_type,
            payload=payload,
            status="pending",
            attempts=0,
            created_at=now,
            scheduled_at=now,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    @staticmethod
    def process_pending(db_factory=None) -> int:
        """Claim and execute one pending job. Returns 1 if a job was processed, 0 otherwise."""
        factory = db_factory or SessionLocal
        db: Session = factory()
        try:
            job = _claim_next(db)
            if not job:
                return 0
            _execute_job(db, job)
            return 1
        except Exception as exc:
            logger.error("Job queue worker error: %s", exc)
            return 0
        finally:
            db.close()


def _claim_next(db: Session) -> JobQueue | None:
    """Atomically claim the next pending job using SELECT FOR UPDATE SKIP LOCKED."""
    result = db.execute(
        text("""
            UPDATE job_queue SET status = 'running', attempts = attempts + 1,
                started_at = NOW()
            WHERE id = (
                SELECT id FROM job_queue
                WHERE status = 'pending' AND attempts < max_attempts
                    AND scheduled_at <= NOW()
                ORDER BY scheduled_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id
        """)
    ).fetchone()
    db.commit()
    if not result:
        return None
    return db.query(JobQueue).filter(JobQueue.id == result[0]).first()


def _execute_job(db: Session, job: JobQueue) -> None:
    handler = _HANDLERS.get(job.job_type)
    if not handler:
        _fail_job(db, job, f"No handler registered for job_type={job.job_type!r}")
        return
    try:
        handler(db, job.payload or {})
        job.status = "done"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "Job %d (%s) completed in attempt %d", job.id, job.job_type, job.attempts
        )
    except Exception as exc:
        _fail_job(db, job, str(exc))


def _fail_job(db: Session, job: JobQueue, error: str) -> None:
    job.error = error[:500]
    job.status = "failed" if job.attempts >= job.max_attempts else "pending"
    job.finished_at = datetime.now(timezone.utc) if job.status == "failed" else None
    db.commit()
    logger.warning(
        "Job %d (%s) failed (attempt %d): %s", job.id, job.job_type, job.attempts, error
    )
