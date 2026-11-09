"""GET/PATCH /api/v1/users/* — self profile, and admin listing/updating of any user."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import CurrentUser, get_current_user, require_role
from app.schemas.user import UserOut, UserUpdateIn
from app.services import users as users_service

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def get_my_profile(
    current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserOut:
    result = users_service.get_user_with_role(db, current_user.id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user, role = result
    return UserOut(id=user.id, name=user.name, email=user.email, phone=user.phone, role=role)


@router.get("", response_model=list[UserOut])
def list_users(
    role: str | None = Query(default=None, description="Filter by role name"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    rows, _total = users_service.list_users(db, role_filter=role, limit=limit, offset=offset)
    return [UserOut(id=u.id, name=u.name, email=u.email, phone=u.phone, role=r) for u, r in rows]


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateIn,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> UserOut:
    user = users_service.update_user(db, user_id, payload, actor_id=current_user.id)
    role = users_service.get_user_with_role(db, user.id)
    role_name = role[1] if role else ""
    return UserOut(id=user.id, name=user.name, email=user.email, phone=user.phone, role=role_name)
