"""
Import every model module here so that Base.metadata knows about all mapped
classes (needed for relationship resolution and for Alembic's --autogenerate
diffing, even though we never run create_all() against this metadata — see
README "Database baseline").
"""
from app.models.ai import (  # noqa: F401
    AiEvidence,
    AiRecommendation,
    AiRun,
    AiToolCall,
    SupervisorDecision,
)
from app.models.identity import Role, User, UserRole  # noqa: F401
from app.models.maintenance import MaintenanceTask, TaskEvidence, Verification  # noqa: F401
from app.models.org import Category, Department, MaintenanceTeam, MaintenanceTeamMember  # noqa: F401
from app.models.rag import LegalKnowledgeChunk, LegalKnowledgeDocument, TicketEmbedding  # noqa: F401
from app.models.system import AuditLog, Notification  # noqa: F401
from app.models.ticket import Ticket, TicketMedia, TicketStatusHistory  # noqa: F401

__all__ = [
    "AiEvidence",
    "AiRecommendation",
    "AiRun",
    "AiToolCall",
    "AuditLog",
    "Category",
    "Department",
    "LegalKnowledgeChunk",
    "LegalKnowledgeDocument",
    "MaintenanceTask",
    "MaintenanceTeam",
    "MaintenanceTeamMember",
    "Notification",
    "Role",
    "SupervisorDecision",
    "TaskEvidence",
    "Ticket",
    "TicketEmbedding",
    "TicketMedia",
    "TicketStatusHistory",
    "User",
    "UserRole",
    "Verification",
]
