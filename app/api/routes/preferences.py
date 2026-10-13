from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_client_id
from app.database.session import get_db
from app.repositories.favorites import PreferencesRepository
from app.schemas.favorite import PreferencesIn, PreferencesOut

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesOut, summary="Get my display preferences")
def get_preferences(client_id: Annotated[str, Depends(get_client_id)], db: Annotated[Session, Depends(get_db)]):
    return PreferencesRepository(db).get(client_id)


@router.put("", response_model=PreferencesOut, summary="Save my display preferences")
def save_preferences(
    body: PreferencesIn, client_id: Annotated[str, Depends(get_client_id)], db: Annotated[Session, Depends(get_db)]
):
    return PreferencesRepository(db).save(client_id, body)
