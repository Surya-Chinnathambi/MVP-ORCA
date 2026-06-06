"""Audit-log retention — delete AuditTrailEvents older than the policy window.

Can be run as an RQ job (scheduled nightly) or called directly.
Never deletes pending ApprovalRequests regardless of age.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def apply_retention_policy(db_url: str, retention_days: int = 365) -> int:
    """Delete AuditTrailEvents older than *retention_days*.

    Returns the count of rows deleted.
    Creates its own DB session so the function can run as an RQ job.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models.workflow import AuditTrailEvent

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    with Session(engine) as db:
        count = (
            db.query(AuditTrailEvent)
            .filter(AuditTrailEvent.created_at < cutoff)
            .count()
        )
        if count:
            db.query(AuditTrailEvent).filter(
                AuditTrailEvent.created_at < cutoff
            ).delete(synchronize_session=False)
            db.commit()

    engine.dispose()
    return count


def run_retention_job(db_url: str, retention_days: int = 365) -> int:
    """RQ job entry point — same as apply_retention_policy."""
    return apply_retention_policy(db_url, retention_days)
