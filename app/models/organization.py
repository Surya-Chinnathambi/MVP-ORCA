from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.clients import Client


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    settings: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    clients: Mapped[list["Client"]] = relationship(back_populates="organization")
