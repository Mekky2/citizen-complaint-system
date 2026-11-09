"""
Business logic for the parts of /api/v1/admin not covered elsewhere:
departments, categories, and read-only audit log access. Staff user
management lives in app/services/users.py (it needs the same User/Role
machinery as citizen auth); this module is organization-structure CRUD.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.org import Category, Department
from app.models.system import AuditLog
from app.schemas.admin import CategoryCreateIn, DepartmentCreateIn
from app.services.common import write_audit_log


def create_department(db: Session, payload: DepartmentCreateIn, *, actor_id: uuid.UUID) -> Department:
    if db.query(Department).filter(Department.name == payload.name).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department already exists")

    department = Department(name=payload.name, description=payload.description)
    db.add(department)
    db.flush()
    write_audit_log(db, actor_id=actor_id, action="create_department", entity_type="department",
                     entity_id=department.id)
    db.commit()
    db.refresh(department)
    return department


def list_departments(db: Session) -> list[Department]:
    return db.query(Department).order_by(Department.name).all()


def create_category(db: Session, payload: CategoryCreateIn, *, actor_id: uuid.UUID) -> Category:
    if db.query(Category).filter(Category.name == payload.name).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category already exists")

    if payload.default_department_id is not None:
        if db.get(Department, payload.default_department_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="default_department_id not found")

    category = Category(name=payload.name, default_department_id=payload.default_department_id)
    db.add(category)
    db.flush()
    write_audit_log(db, actor_id=actor_id, action="create_category", entity_type="category", entity_id=category.id)
    db.commit()
    db.refresh(category)
    return category


def list_categories(db: Session) -> list[Category]:
    return db.query(Category).order_by(Category.name).all()


def list_audit_logs(
    db: Session, *, entity_type: str | None, limit: int, offset: int
) -> tuple[list[AuditLog], int]:
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset).all()
    return rows, total
