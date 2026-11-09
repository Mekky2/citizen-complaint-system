"""Business logic for /api/v1/users (self) and the admin-only staff management
endpoints exposed under /api/v1/admin."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.identity import Role, User, UserRole
from app.schemas.user import StaffCreateIn, UserUpdateIn
from app.security.hashing import hash_password
from app.services.common import get_user_role, write_audit_log


def get_user_with_role(db: Session, user_id: uuid.UUID) -> tuple[User, str] | None:
    user = db.get(User, user_id)
    if user is None:
        return None
    role = get_user_role(db, user_id)
    return user, (role or "")


def list_users(
    db: Session, *, role_filter: str | None, limit: int, offset: int
) -> tuple[list[tuple[User, str]], int]:
    query = (
        db.query(User, Role.name)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
    )
    if role_filter:
        query = query.filter(Role.name == role_filter)
    total = query.count()
    rows = query.order_by(User.created_at.desc()).limit(limit).offset(offset).all()
    return [(user, role_name) for user, role_name in rows], total


def create_staff_user(
    db: Session, payload: StaffCreateIn, *, created_by: uuid.UUID
) -> tuple[User, str]:
    """Admin-only: create a supervisor/technician/admin account. Citizens always
    self-register via app/services/auth.py:register_citizen — this path never
    creates a citizen, and StaffCreateIn's own validator already rejects role='citizen'."""
    conditions = [User.email == payload.email]
    if payload.phone:
        conditions.append(User.phone == payload.phone)
    if db.query(User).filter(or_(*conditions)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email or phone already exists",
        )

    role = db.query(Role).filter(Role.name == payload.role).first()
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Role '{payload.role}' is not seeded in the database",
        )

    user = User(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()

    db.add(UserRole(user_id=user.id, role_id=role.id))
    write_audit_log(
        db,
        actor_id=created_by,
        action="create_staff_user",
        entity_type="user",
        entity_id=user.id,
        after={"role": payload.role},
    )

    db.commit()
    db.refresh(user)
    return user, payload.role


def update_user(
    db: Session, user_id: uuid.UUID, payload: UserUpdateIn, *, actor_id: uuid.UUID
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    before = {
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "deactivated": user.deactivated_at is not None,
    }

    if payload.name is not None:
        user.name = payload.name
    if payload.email is not None:
        user.email = payload.email
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.deactivated is True and user.deactivated_at is None:
        user.deactivated_at = datetime.now(timezone.utc)
    elif payload.deactivated is False:
        user.deactivated_at = None

    after = {
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "deactivated": user.deactivated_at is not None,
    }
    write_audit_log(
        db,
        actor_id=actor_id,
        action="update_user",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=after,
    )

    db.commit()
    db.refresh(user)
    return user
