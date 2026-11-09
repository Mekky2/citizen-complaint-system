"""
Authentication + RBAC dependencies.

get_current_user is the one place a request's JWT is turned into a real,
still-active database user: it re-reads the user's CURRENT role from the
database on every request (one JOIN query), rather than trusting the role
claim embedded in the token. That means a role change or account
deactivation takes effect immediately, even against a token issued minutes
ago — a live-but-stale token cannot act as a role the user no longer has.

require_role(...) is the RBAC enforcement point used by every protected
router. It is deliberately a thin wrapper, not a general permissions engine —
four roles with a fixed set of allowed actions per role does not need one
(see the backend design doc, Section 5).

SECURITY SCHEME (JWT/Swagger review fix): this used to be
`OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`. That tells Swagger
UI's "Authorize" dialog that /api/v1/auth/login is an OAuth2 "password
grant" token endpoint, so Swagger would try to POST
`application/x-www-form-urlencoded` with fields named `username`/`password`
to it. Our actual login endpoint (app/routers/auth.py) takes JSON
(`app.schemas.auth.LoginIn`: `identifier`/`password`) — a deliberate choice,
since login-by-phone-or-email doesn't fit OAuth2's `username` field well.
Swagger's Authorize flow was therefore sending a request shape our endpoint
has never accepted, so clicking "Authorize" in /docs would 422 against the
real login endpoint. Switching to HTTPBearer fixes that WITHOUT changing
`/api/v1/auth/login` at all: on the wire, both schemes read the exact same
`Authorization: Bearer <token>` header (decode_token() below is unchanged),
so every existing client keeps working unmodified. The only behavior change
is what Swagger's "Authorize" dialog asks for: a single token field to paste
a value into (call /api/v1/auth/login via "Try it out" first, copy
access_token, paste it there), which is what this API actually is — a plain
bearer-token API, not an OAuth2 password-grant one.
"""
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.identity import Role, User, UserRole
from app.security.jwt import InvalidTokenError, decode_token

# auto_error=False, NOT the library default: FastAPI's HTTPBearer, with
# auto_error=True, raises 403 (not 401) when the Authorization header is
# missing entirely — a real regression introduced by the OAuth2PasswordBearer
# -> HTTPBearer switch above, caught by tests/test_auth.py::test_no_token_rejected
# expecting 401. auto_error=False hands `credentials` to get_current_user as
# None instead of raising, so get_current_user can raise the same 401
# credentials_exception for "missing" as it already does for "malformed" —
# one consistent "not authenticated" status for every no-valid-token case.
bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    description="Paste the access_token returned by POST /api/v1/auth/login (no 'Bearer ' prefix needed here).",
    auto_error=False,
)


@dataclass
class CurrentUser:
    id: uuid.UUID
    name: str
    role: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        # No Authorization header at all — same 401 as a malformed/expired
        # one, not FastAPI's HTTPBearer default of 403. See bearer_scheme above.
        raise credentials_exception

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except InvalidTokenError:
        raise credentials_exception from None

    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError:
        raise credentials_exception from None

    row = (
        db.query(User.id, User.name, User.deactivated_at, Role.name.label("role_name"))
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(User.id == user_id)
        .first()
    )
    if row is None:
        raise credentials_exception
    if row.deactivated_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    return CurrentUser(id=row.id, name=row.name, role=row.role_name)


def require_role(*allowed_roles: str):
    """
    Usage: Depends(require_role("supervisor", "admin"))

    A route with no require_role(...) dependency is reachable by any
    authenticated user; one with it enforces that the user's CURRENT role
    (re-read from the database by get_current_user, not the token's claim)
    is one of allowed_roles.
    """

    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return _check
