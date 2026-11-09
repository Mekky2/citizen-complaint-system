"""
FastAPI application entrypoint.

GET /health does a real database round trip (app.db.check_database_connection),
not just process liveness — the point is to catch "the app is up but can't
reach Postgres" before a load balancer or the frontend does.

No router here (or anywhere in app/) ever calls Base.metadata.create_all():
the schema is owned entirely by database/init/*.sql, and this file only
mounts routes on top of it.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import check_database_connection
from app.routers import (
    admin,
    ai,
    auth,
    maintenance,
    notifications,
    supervisor,
    tickets,
    users,
    verification,
)

settings = get_settings()

app = FastAPI(
    title="EG Civic Operations API",
    description="Backend for the EG Civic Operations graduation project — citizen "
    "ticketing, AI-assisted triage with human approval, maintenance workflow, and admin.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tickets.router)
app.include_router(supervisor.router)
app.include_router(maintenance.router)
app.include_router(verification.router)
app.include_router(notifications.router)
app.include_router(ai.router)
app.include_router(admin.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    db_ok = check_database_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
    }
