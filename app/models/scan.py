"""ScanJob model — tracks PT-Orc scan jobs triggered from the UI."""
import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models.base import TimestampMixin


class ScanJobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class ScanJob(TimestampMixin, Base):
    __tablename__ = "scan_jobs"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    host: Mapped[str] = mapped_column(nullable=False)
    phases: Mapped[list] = mapped_column(JSON, default=list)
    tier: Mapped[str] = mapped_column(default="standard")
    api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum(ScanJobStatus, name="scan_job_status_enum"),
        default=ScanJobStatus.queued.value,
        index=True,
    )
    run_dir: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    log_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    import_result: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
