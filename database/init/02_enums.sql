-- =============================================================================
-- EG Civic Operations — Enum Types
-- =============================================================================
-- Roles are a TABLE (roles / user_roles), not an enum: four roles today, but a
-- lookup table lets a role be added without a migration, and user_roles is what
-- the RBAC dependency joins against at request time.
--
-- Everything below IS a fixed, small set of values that the application logic
-- branches on directly, so an enum is the right tool: cheaper than a lookup
-- table, and Postgres enforces the valid set for free.
-- =============================================================================

-- Ticket lifecycle (see Section "Ticket Lifecycle" in the design doc):
-- submitted -> under_ai_review -> awaiting_approval -> (assigned | rejected)
-- assigned -> in_progress -> pending_verification -> (completed | assigned [rework])
-- submitted/under_ai_review -> cancelled (citizen-initiated, only before awaiting_approval)
CREATE TYPE ticket_status_enum AS ENUM (
    'submitted',
    'under_ai_review',
    'awaiting_approval',
    'assigned',
    'in_progress',
    'pending_verification',
    'completed',
    'rejected',
    'cancelled'
);

CREATE TYPE severity_enum AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

-- Used by both ticket_media (citizen-submitted) and task_evidence (technician-submitted)
CREATE TYPE media_type_enum AS ENUM (
    'image',
    'video',
    'audio'
);

CREATE TYPE ai_run_status_enum AS ENUM (
    'pending',
    'succeeded',
    'failed'
);

CREATE TYPE decision_action_enum AS ENUM (
    'approve',
    'edit',
    'reject'
);

CREATE TYPE task_status_enum AS ENUM (
    'assigned',
    'in_progress',
    'pending_verification',
    'completed'
);

CREATE TYPE verification_result_enum AS ENUM (
    'pass',
    'fail'
);

CREATE TYPE notification_channel_enum AS ENUM (
    'email',
    'sms',
    'push',
    'in_app'
);

-- The final RAG decision: an AI recommendation's evidence is EITHER an official
-- legal/regulatory source OR a similar past ticket — never ambiguous, never both,
-- and a past ticket can never be mislabeled as legal evidence. Enforced again at
-- the table level in 03_tables.sql via a CHECK constraint on ai_evidence.
CREATE TYPE ai_evidence_type_enum AS ENUM (
    'LEGAL_EVIDENCE',
    'SIMILAR_CASE'
);

-- What kind of official document a legal_knowledge_documents row is.
CREATE TYPE legal_source_type_enum AS ENUM (
    'law',
    'regulation',
    'government_decision',
    'sop',
    'other'
);
