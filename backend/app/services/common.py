"""
Shared helpers used by several services: resolving a user's CURRENT role
(the same Role/UserRole join used by app/dependencies/auth.py, so there is
exactly one place that query is written), and writing audit log rows.

Nothing here commits — every service function that calls write_audit_log is
expected to db.commit() itself once it has made every change for that
request, so the audit row is part of the same transaction as the business
change it describes, never a separate one that could survive a rollback of
the thing it is auditing.
"""
import uuid

from sqlalchemy.orm import Session

from app.models.identity import Role, User, UserRole
from app.models.system import AuditLog


def get_user_role(db: Session, user_id: uuid.UUID) -> str | None:
    """A user's current role, re-read from the database. Returns None if the
    user has no role row (should not happen for a real account, but callers
    must not assume it can't)."""
    row = (
        db.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id)
        .first()
    )
    return row[0] if row else None


def get_active_user(db: Session, user_id: uuid.UUID) -> User | None:
    user = db.get(User, user_id)
    if user is None or user.deactivated_at is not None:
        return None
    return user


def write_audit_log(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    before: dict | None = None,
    after: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
    )
    db.add(log)
    return log
