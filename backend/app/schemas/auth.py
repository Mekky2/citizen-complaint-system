"""Schemas for /api/v1/auth."""

import re
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

NATIONAL_ID_RE = re.compile(r"^[0-9]{14}$")
PHONE_RE = re.compile(r"^01[0125][0-9]{8}$")


class CitizenRegisterIn(BaseModel):
    """Self-registration — always creates a 'citizen' role user. Staff accounts
    (supervisor/technician/admin) are created by an admin via /api/v1/admin,
    never through self-registration."""

    name: str = Field(min_length=3)
    phone: str
    national_id: str | None = None
    email: str | None = None
    password: str = Field(min_length=8)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not PHONE_RE.match(v):
            raise ValueError("phone must be a valid Egyptian mobile number, e.g. 01012345678")
        return v

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, v: str | None) -> str | None:
        if v is not None and not NATIONAL_ID_RE.match(v):
            raise ValueError("national_id must be exactly 14 digits")
        return v


class LoginIn(BaseModel):
    """Login by phone OR email — whichever the account was created with."""

    identifier: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class MeOut(BaseModel):
    id: UUID
    name: str
    role: str
