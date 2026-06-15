from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_current_user, get_session, get_settings_from_app
from app.models import User
from app.schemas import LoginRequest, ProfileResponse, TokenResponse, UserCreate
from app.security import create_access_token, hash_password, verify_password
from app.services.wallet_service import get_or_create_wallet

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: UserCreate,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_from_app)],
) -> TokenResponse:
    user = User(
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        photo_url=payload.photo_url,
        default_currency=payload.default_currency,
    )
    session.add(user)
    try:
        session.flush()
        get_or_create_wallet(session, user.id, user.default_currency)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc
    return TokenResponse(access_token=create_access_token(user.id, settings))


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_from_app)],
) -> TokenResponse:
    user = session.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id, settings))


@router.get("/me", response_model=ProfileResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> ProfileResponse:
    return ProfileResponse.model_validate(current_user)
