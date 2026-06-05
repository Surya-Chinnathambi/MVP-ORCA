import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, _utcnow

if TYPE_CHECKING:
    from app.models.clients import Project
    from app.models.organization import Organization
    from app.models.users import User


class PackLifecycle(str, enum.Enum):
    draft = "draft"
    internal_review = "internal_review"
    approved = "approved"
    active = "active"
    deprecated = "deprecated"
    archived = "archived"


class MethodologyPack(TimestampMixin, Base):
    __tablename__ = "methodology_packs"

    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    lifecycle: Mapped[str] = mapped_column(
        Enum(PackLifecycle, name="pack_lifecycle_enum"),
        default=PackLifecycle.draft,
        nullable=False,
    )
    source_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization", foreign_keys=[organization_id]
    )
    projects: Mapped[list["Project"]] = relationship(back_populates="methodology_pack")
    approver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[approved_by]
    )
