from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_session
from app.models import User
from app.schemas import ProfileResponse, ProfileUpdate
from app.services.wallet_service import get_or_create_wallet

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(current_user: Annotated[User, Depends(get_current_user)]) -> ProfileResponse:
    return ProfileResponse.model_validate(current_user)


@router.patch("", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> ProfileResponse:
    if payload.display_name is not None:
        current_user.display_name = payload.display_name
    if payload.photo_url is not None:
        current_user.photo_url = payload.photo_url
    if payload.default_currency is not None:
        current_user.default_currency = payload.default_currency
        get_or_create_wallet(session, current_user.id, payload.default_currency)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return ProfileResponse.model_validate(current_user)
