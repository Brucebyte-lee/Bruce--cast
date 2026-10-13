from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_id
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.repositories.favorites import FavoritesRepository
from app.schemas.favorite import FavoriteCreate, FavoriteOrder, FavoriteOut

router = APIRouter(prefix="/favorites", tags=["favorites"])

ClientId = Annotated[str, Depends(get_client_id)]


def get_repo(db: Annotated[Session, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)]):
    return FavoritesRepository(db, settings.max_favorites_per_client)


Repo = Annotated[FavoritesRepository, Depends(get_repo)]


@router.get("", response_model=list[FavoriteOut], summary="List my favorites")
def list_favorites(client_id: ClientId, repo: Repo):
    return repo.list_all(client_id)


@router.post("", response_model=FavoriteOut, status_code=status.HTTP_201_CREATED, summary="Add a favorite")
def add_favorite(body: FavoriteCreate, client_id: ClientId, repo: Repo):
    return repo.add(client_id, body)


@router.put("/order", response_model=list[FavoriteOut], summary="Reorder favorites")
def reorder_favorites(body: FavoriteOrder, client_id: ClientId, repo: Repo):
    return repo.reorder(client_id, body.ids)


@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a favorite")
def delete_favorite(favorite_id: int, client_id: ClientId, repo: Repo) -> Response:
    repo.delete(client_id, favorite_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
