import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.clients import Client, Project


class RoleName(str, enum.Enum):
    # 10 canonical roles per RBAC.md §1 (ordered highest → lowest privilege)
    platform_admin = "platform_admin"
    partner = "partner"
    pm = "pm"
    lead_consultant = "lead_consultant"
    analyst = "analyst"
    senior_reviewer = "senior_reviewer"
    qa = "qa"
    client_approver = "client_approver"
    client_contributor = "client_contributor"
    readonly = "readonly"


class ScopeLevel(str, enum.Enum):
    # Original MVP levels (kept)
    client = "client"
    project = "project"
    # Phase 2 extended levels (Stage 20)
    organization = "organization"
    evidence_item = "evidence_item"
    deliverable = "deliverable"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Stage 19 — context-restore fields (per db.md)
    last_client_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("clients.id"), nullable=True
    )
    last_project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True
    )
    last_work_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Stage 21 — MFA fields
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recovery_codes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # T&C acceptance
    terms_accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    permissions: Mapped[list["Permission"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        Enum(RoleName, name="role_name_enum"), unique=True, nullable=False
    )

    permissions: Mapped[list["Permission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    scope_level: Mapped[str] = mapped_column(
        Enum(ScopeLevel, name="scope_level_enum"), nullable=False
    )
    scope_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roles.id"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="permissions")
    role: Mapped["Role"] = relationship(back_populates="permissions")
