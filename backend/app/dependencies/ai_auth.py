"""
Service-to-service authentication for the AI integration boundary.

Deliberately NOT a user JWT: the AI service is not a user, has no role, and
should never be able to mint or be mistaken for a citizen/staff session. It
authenticates with a shared secret sent as a custom header, checked here
before the request body is even parsed into the AI response schema.
"""

from fastapi import Header, HTTPException, status

from app.config import get_settings

settings = get_settings()


def verify_ai_service_secret(x_ai_service_secret: str = Header(default="")) -> None:
    if not x_ai_service_secret or x_ai_service_secret != settings.ai_service_shared_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing AI service credentials",
        )
