from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Preference(Base):
    """Per-visitor display preferences. One row per anonymous client."""

    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    temperature_unit: Mapped[str] = mapped_column(String(10), default="celsius")
    unit_system: Mapped[str] = mapped_column(String(10), default="metric")
    theme: Mapped[str] = mapped_column(String(10), default="system")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
