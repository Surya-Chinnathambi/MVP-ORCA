import enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.clients import Project


class RoleName(str, enum.Enum):
    # Original MVP roles (kept — do not remove)
    admin = "admin"
    partner = "partner"
    pm = "pm"
    analyst = "analyst"
    reviewer = "reviewer"
    qa = "qa"
    client = "client"
    readonly = "readonly"
    # Phase 2 extended roles (Stage 20)
    platform_admin = "platform_admin"
    lead_consultant = "lead_consultant"
    senior_reviewer = "senior_reviewer"
    client_approver = "client_approver"
    client_contributor = "client_contributor"


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
