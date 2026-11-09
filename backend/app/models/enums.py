"""
Python mirrors of the 10 Postgres enum types created by database/init/02_enums.sql.

Every value here must match the database exactly — these are NOT redefinitions,
they are SQLAlchemy's view of enum types that already exist in Postgres
(create_type=False on every mapped column means SQLAlchemy never tries to
CREATE TYPE; it only ever reads/writes values against the existing type).
"""
import enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[enum.Enum], pg_type_name: str) -> SAEnum:
    """
    Build a SQLAlchemy Enum column type bound to an EXISTING Postgres enum type.

    create_type=False / checkfirst=False: SQLAlchemy must never try to CREATE
    TYPE or DROP TYPE for these — the types were created by
    database/init/02_enums.sql and are owned by that file, not by the ORM.

    values_callable uses each member's .value (not .name) as the wire/DB value,
    which matters for VerificationResult.pass_ ("pass" is a Python keyword, so
    the member name can't be "pass" even though the DB value must be).
    """
    return SAEnum(
        enum_cls,
        name=pg_type_name,
        create_type=False,
        checkfirst=False,
        values_callable=lambda obj: [member.value for member in obj],
    )


class TicketStatus(str, enum.Enum):
    submitted = "submitted"
    under_ai_review = "under_ai_review"
    awaiting_approval = "awaiting_approval"
    assigned = "assigned"
    in_progress = "in_progress"
    pending_verification = "pending_verification"
    completed = "completed"
    rejected = "rejected"
    cancelled = "cancelled"


class Severity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class MediaType(str, enum.Enum):
    image = "image"
    video = "video"
    audio = "audio"


class AiRunStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"


class DecisionAction(str, enum.Enum):
    approve = "approve"
    edit = "edit"
    reject = "reject"


class TaskStatus(str, enum.Enum):
    assigned = "assigned"
    in_progress = "in_progress"
    pending_verification = "pending_verification"
    completed = "completed"


class VerificationResult(str, enum.Enum):
    pass_ = "pass"
    fail = "fail"


class NotificationChannel(str, enum.Enum):
    email = "email"
    sms = "sms"
    push = "push"
    in_app = "in_app"


class AiEvidenceType(str, enum.Enum):
    LEGAL_EVIDENCE = "LEGAL_EVIDENCE"
    SIMILAR_CASE = "SIMILAR_CASE"


class LegalSourceType(str, enum.Enum):
    law = "law"
    regulation = "regulation"
    government_decision = "government_decision"
    sop = "sop"
    other = "other"
