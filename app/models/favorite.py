from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Favorite(Base):
    """A saved location. `client_id` is a random anonymous id stored in an httpOnly cookie.

    Coordinates are rounded to 4 decimals (~11 m) before saving, which makes the
    (client_id, latitude, longitude) unique constraint reliable for duplicate prevention.
    """

    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("client_id", "latitude", "longitude", name="uq_favorite_client_coords"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
