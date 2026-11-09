"""
Business logic for /api/v1/auth: citizen self-registration, login, token refresh.

Staff accounts (supervisor/technician/admin) are never created here — only
app/services/users.py (an admin-only path) creates those. This module only
ever assigns the 'citizen' role.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.identity import Role, User, UserRole
from app.schemas.auth import CitizenRegisterIn, LoginIn
from app.security.hashing import hash_password, verify_password
from app.security.jwt import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.services.common import get_user_role, write_audit_log

CITIZEN_ROLE_NAME = "citizen"


def _get_role_or_500(db: Session, name: str) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if role is None:
        # database/init/06_seed.sql seeds all four roles; a missing one means
        # the deployment itself is incomplete, not that the request is bad.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Role '{name}' is not seeded in the database",
        )
    return role


def register_citizen(db: Session, payload: CitizenRegisterIn) -> User:
    conditions = [User.phone == payload.phone]
    if payload.email:
        conditions.append(User.email == payload.email)
    if payload.national_id:
        conditions.append(User.national_id == payload.national_id)

    if db.query(User).filter(or_(*conditions)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this phone, email, or national ID already exists",
        )

    citizen_role = _get_role_or_500(db, CITIZEN_ROLE_NAME)

    user = User(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        national_id=payload.national_id,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()  # assigns user.id without committing yet

    db.add(UserRole(user_id=user.id, role_id=citizen_role.id))
    write_audit_log(db, actor_id=user.id, action="register", entity_type="user", entity_id=user.id)

    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, identifier: str, password: str) -> tuple[User, str]:
    """identifier is the phone OR email the account was created with."""
    user = db.query(User).filter(or_(User.phone == identifier, User.email == identifier)).first()

    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user is None or not verify_password(password, user.password_hash):
        raise invalid
    if user.deactivated_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    role = get_user_role(db, user.id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User has no assigned role"
        )
    return user, role


def login(db: Session, payload: LoginIn) -> dict:
    user, role = authenticate_user(db, payload.identifier, payload.password)
    return {
        "access_token": create_access_token(str(user.id), role),
        "refresh_token": create_refresh_token(str(user.id), role),
        "token_type": "bearer",
    }


def refresh_access_token(db: Session, refresh_token: str) -> dict:
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except InvalidTokenError:
        raise invalid from None

    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError:
        raise invalid from None

    user = db.get(User, user_id)
    if user is None or user.deactivated_at is not None:
        raise invalid

    role = get_user_role(db, user.id)
    if role is None:
        raise invalid

    return {
        "access_token": create_access_token(str(user.id), role),
        "refresh_token": create_refresh_token(str(user.id), role),
        "token_type": "bearer",
    }
