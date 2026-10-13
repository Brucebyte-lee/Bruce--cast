"""Database access for favorites and preferences. No HTTP or weather logic lives here."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import DuplicateFavorite, FavoriteLimitReached, FavoriteNotFound, InvalidOrder
from app.models import Favorite, Preference
from app.schemas.favorite import FavoriteCreate, PreferencesIn


class FavoritesRepository:
    def __init__(self, db: Session, max_per_client: int = 50) -> None:
        self.db = db
        self.max_per_client = max_per_client

    def list_all(self, client_id: str) -> list[Favorite]:
        stmt = select(Favorite).where(Favorite.client_id == client_id).order_by(Favorite.position, Favorite.id)
        return list(self.db.scalars(stmt))

    def add(self, client_id: str, data: FavoriteCreate) -> Favorite:
        count = self.db.scalar(select(func.count()).select_from(Favorite).where(Favorite.client_id == client_id))
        if (count or 0) >= self.max_per_client:
            raise FavoriteLimitReached()
        favorite = Favorite(
            client_id=client_id, name=data.name, country=data.country, timezone=data.timezone,
            latitude=round(data.latitude, 4), longitude=round(data.longitude, 4), position=count or 0,
        )  # fmt: skip
        self.db.add(favorite)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise DuplicateFavorite() from exc
        return favorite

    def delete(self, client_id: str, favorite_id: int) -> None:
        # Filtering by client_id means one visitor can never delete another visitor's record.
        favorite = self.db.scalar(select(Favorite).where(Favorite.id == favorite_id, Favorite.client_id == client_id))
        if favorite is None:
            raise FavoriteNotFound()
        self.db.delete(favorite)
        self.db.commit()

    def reorder(self, client_id: str, ids: list[int]) -> list[Favorite]:
        favorites = {f.id: f for f in self.list_all(client_id)}
        if sorted(ids) != sorted(favorites) or len(set(ids)) != len(ids):
            raise InvalidOrder()
        for position, favorite_id in enumerate(ids):
            favorites[favorite_id].position = position
        self.db.commit()
        return self.list_all(client_id)


class PreferencesRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, client_id: str) -> Preference:
        pref = self.db.scalar(select(Preference).where(Preference.client_id == client_id))
        return pref or Preference(client_id=client_id, temperature_unit="celsius", unit_system="metric", theme="system")

    def save(self, client_id: str, data: PreferencesIn) -> Preference:
        pref = self.db.scalar(select(Preference).where(Preference.client_id == client_id))
        if pref is None:
            pref = Preference(client_id=client_id)
            self.db.add(pref)
        pref.temperature_unit, pref.unit_system, pref.theme = data.temperature_unit, data.unit_system, data.theme
        self.db.commit()
        return pref
