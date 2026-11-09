"""
JWT issuing/verification for citizen/staff user sessions.

The access token embeds the user's role directly (claim "role"), so the RBAC
dependency (app/dependencies/auth.py) can authorize a request from the token
alone, with no extra database round-trip per request — a deliberate
performance/simplicity choice. The role claim is a snapshot at login time;
app/dependencies/auth.py still re-checks deactivated_at against the DB so a
deactivated account loses access immediately even with a live token.

Service-to-service auth for the AI integration (POST /api/v1/ai/recommendations)
is intentionally NOT a user JWT — see app/dependencies/ai_auth.py — so a leaked
AI-service credential can never be used to mint a citizen/staff session, and
vice versa.

KNOWN LIMITATION — refresh token revocation (reviewed, not fixed, documented
on purpose): refresh tokens here are pure stateless JWTs, verified only by
signature + expiry (decode_token(..., expected_type="refresh")). There is no
server-side record of which refresh tokens have been issued, used, or should
be considered revoked. Concretely:

  - A refresh token cannot be invalidated before its own expiry
    (REFRESH_TOKEN_EXPIRE_MINUTES, default 7 days) — there is no "logout"
    that actually revokes it, only a client discarding it.
  - app/services/auth.py:refresh_access_token() issues a brand-new
    access+refresh pair on every refresh WITHOUT invalidating the refresh
    token that was just used — so a stolen refresh token keeps working in
    parallel with the legitimate one, silently, until it naturally expires.
    There is no rotation-with-reuse-detection.

Why this isn't fixed here: real revocation/rotation needs somewhere to
persist "this token (or its jti) is no longer valid" — a token denylist, a
used-refresh-tokens table, or a per-user token-version counter column on
`users`. The existing database schema (the source of truth for this
project) has none of those, and the task brief is explicit that an existing
database limitation gets documented, not silently worked around by adding a
table. jti (see TokenPayload below) already exists precisely so that a
future, explicitly-approved schema change (one new table, or one new column
on `users`) could add real revocation later without reshaping the token
format again.

Mitigation available today, with no schema change: keep
ACCESS_TOKEN_EXPIRE_MINUTES short (the default, 60 minutes, limits how long
a stolen ACCESS token works) and treat REFRESH_TOKEN_EXPIRE_MINUTES as the
real exposure window for a stolen refresh token — shortening it in .env
directly shrinks that window at the cost of forcing more frequent logins.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()

TokenType = Literal["access", "refresh"]


class TokenPayload(BaseModel):
    sub: str  # user id (UUID as string)
    role: str
    type: TokenType
    exp: datetime
    jti: str


class InvalidTokenError(Exception):
    pass


def _create_token(user_id: uuid.UUID, role: str, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        # A random per-token id. exp/iat are only second-precision once encoded,
        # so two tokens issued for the same user within the same second would
        # otherwise be byte-identical; jti also gives a hook for future
        # token revocation/blacklisting without changing the token shape again.
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    return _create_token(
        user_id, role, "access", timedelta(minutes=settings.access_token_expire_minutes)
    )


def create_refresh_token(user_id: uuid.UUID, role: str) -> str:
    return _create_token(
        user_id, role, "refresh", timedelta(minutes=settings.refresh_token_expire_minutes)
    )


def decode_token(token: str, expected_type: TokenType = "access") -> TokenPayload:
    try:
        raw = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    payload = TokenPayload.model_validate(raw)
    if payload.type != expected_type:
        raise InvalidTokenError(f"expected a {expected_type} token, got {payload.type}")
    return payload
