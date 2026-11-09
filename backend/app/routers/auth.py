"""POST/GET /api/v1/auth/* — citizen self-registration, login, refresh, me."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.auth import CitizenRegisterIn, LoginIn, MeOut, RefreshIn, TokenOut
from app.services import auth as auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: CitizenRegisterIn, db: Session = Depends(get_db)) -> TokenOut:
    """Citizen self-registration. Always creates a 'citizen' role account and
    logs the new user in immediately (returns tokens), so the Citizen Portal
    doesn't need a separate register-then-login round trip."""
    user = auth_service.register_citizen(db, payload)
    tokens = auth_service.login(db, LoginIn(identifier=user.phone, password=payload.password))
    return TokenOut(**tokens)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    return TokenOut(**auth_service.login(db, payload))


@router.post("/refresh", response_model=TokenOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)) -> TokenOut:
    return TokenOut(**auth_service.refresh_access_token(db, payload.refresh_token))


@router.get("/me", response_model=MeOut)
def me(current_user: CurrentUser = Depends(get_current_user)) -> MeOut:
    return MeOut(id=current_user.id, name=current_user.name, role=current_user.role)
