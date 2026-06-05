"""Background job enqueue helper.

Usage:
    from app.services.jobs import enqueue_evidence_extraction
    job = enqueue_evidence_extraction(evidence_item_id)

All functions return an rq.job.Job (or None if Redis is unavailable and
JOBS_SYNC_FALLBACK=True). Callers can poll job.get_status() for progress.

Queue names:
  evidence     — text/OCR extraction
  import       — PT-Orc run-dir import
  deliverables — gap matrix / roadmap / report generation
"""
from __future__ import annotations

import logging
from typing import Optional

import redis
from rq import Queue
from rq.job import Job

from app.config import settings

logger = logging.getLogger(__name__)

_redis_conn: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = redis.from_url(settings.redis_url)
    return _redis_conn


def _queue(name: str) -> Queue:
    return Queue(name, connection=_get_redis())


def _override_redis(conn) -> None:
    """Allow tests to inject a fakeredis connection."""
    global _redis_conn
    _redis_conn = conn


# ── Evidence extraction ───────────────────────────────────────────────────────

def enqueue_evidence_extraction(evidence_item_id: str) -> Job:
    """Enqueue text/OCR extraction for an already-ingested EvidenceItem."""
    return _queue("evidence").enqueue(
        "app.services.jobs_impl.run_evidence_extraction",
        evidence_item_id,
        job_timeout=300,
    )


# ── PT-Orc import ─────────────────────────────────────────────────────────────

def enqueue_ptorc_import(project_id: str, run_dir: str) -> Job:
    """Enqueue import of a PT-Orc run directory into the project."""
    return _queue("import").enqueue(
        "app.services.jobs_impl.run_ptorc_import",
        project_id,
        run_dir,
        job_timeout=600,
    )


# ── Deliverable generation ────────────────────────────────────────────────────

def enqueue_gap_matrix(project_id: str, output_dir: str) -> Job:
    return _queue("deliverables").enqueue(
        "app.services.jobs_impl.run_gap_matrix",
        project_id,
        output_dir,
        job_timeout=300,
    )


def enqueue_roadmap(project_id: str, output_dir: str) -> Job:
    return _queue("deliverables").enqueue(
        "app.services.jobs_impl.run_roadmap",
        project_id,
        output_dir,
        job_timeout=300,
    )


def enqueue_report(project_id: str, output_dir: str) -> Job:
    return _queue("deliverables").enqueue(
        "app.services.jobs_impl.run_report",
        project_id,
        output_dir,
        job_timeout=300,
    )
