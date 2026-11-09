"""/api/v1/admin/* — staff user management, departments, categories, audit log reads.
Every route here is admin-only."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import CurrentUser, require_role
from app.schemas.admin import AuditLogOut, CategoryCreateIn, CategoryOut, DepartmentCreateIn, DepartmentOut
from app.schemas.user import StaffCreateIn, UserOut
from app.services import admin as admin_service
from app.services import users as users_service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/staff", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_staff_user(
    payload: StaffCreateIn,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> UserOut:
    user, role = users_service.create_staff_user(db, payload, created_by=current_user.id)
    return UserOut(id=user.id, name=user.name, email=user.email, phone=user.phone, role=role)


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreateIn,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> DepartmentOut:
    return admin_service.create_department(db, payload, actor_id=current_user.id)


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    current_user: CurrentUser = Depends(require_role("admin", "supervisor")), db: Session = Depends(get_db)
) -> list[DepartmentOut]:
    return admin_service.list_departments(db)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreateIn,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> CategoryOut:
    return admin_service.create_category(db, payload, actor_id=current_user.id)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    current_user: CurrentUser = Depends(require_role("admin", "supervisor")), db: Session = Depends(get_db)
) -> list[CategoryOut]:
    return admin_service.list_categories(db)


@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    rows, _total = admin_service.list_audit_logs(db, entity_type=entity_type, limit=limit, offset=offset)
    return rows
