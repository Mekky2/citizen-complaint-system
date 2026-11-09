"""Schemas for /api/v1/users and /api/v1/admin user management."""
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.auth import PHONE_RE
from app.schemas.common import ORMBase


class UserOut(ORMBase):
    id: UUID
    name: str
    email: str | None
    phone: str | None
    role: str  # resolved from user_roles/roles, not a raw DB column on users


class StaffCreateIn(BaseModel):
    """Admin-only: create a supervisor/technician/admin account. Citizens self-register
    (see schemas.auth.CitizenRegisterIn) — this endpoint never creates a citizen."""

    name: str = Field(min_length=3)
    email: EmailStr
    phone: str | None = None
    password: str = Field(min_length=8)
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in {"supervisor", "technician", "admin"}:
            raise ValueError("role must be one of: supervisor, technician, admin")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is not None and not PHONE_RE.match(v):
            raise ValueError("phone must be a valid Egyptian mobile number")
        return v


class UserUpdateIn(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    deactivated: bool | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is not None and not PHONE_RE.match(v):
            raise ValueError("phone must be a valid Egyptian mobile number")
        return v
