-- =============================================================================
-- EG Civic Operations — Core Tables
-- =============================================================================
-- Convention: every table has id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
-- created_at TIMESTAMPTZ NOT NULL DEFAULT now(). Tables that can be edited after
-- creation also have updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), kept current
-- by the triggers in 05_triggers.sql. Append-only/log tables (ticket_media,
-- ticket_status_history, ai_tool_calls, ai_evidence, supervisor_decisions,
-- task_evidence, verifications, notifications, audit_logs) have no updated_at:
-- they are written once and never changed in place.
--
-- Foreign key policy: ON DELETE RESTRICT by default (nothing referenced by a
-- ticket, a decision or an audit record should be able to vanish silently).
-- CASCADE is used only where the child row has no meaning without its parent
-- (e.g. ticket_media without its ticket). SET NULL is used where losing the
-- reference is a legitimate, harmless outcome (e.g. a category's default
-- department, or the actor on an audit log if that user is later removed).
-- Tables are created in dependency order, so no forward references are needed.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Identity & RBAC
-- -----------------------------------------------------------------------------

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    national_id     TEXT,
    password_hash   TEXT NOT NULL,
    deactivated_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT users_email_unique UNIQUE (email),
    CONSTRAINT users_phone_unique UNIQUE (phone),
    CONSTRAINT users_national_id_unique UNIQUE (national_id),
    -- Egyptian National ID: exactly 14 digits. Full semantic validation (century
    -- digit, valid birth date, governorate code, age >= 18) is application-layer
    -- logic (already built in the citizen-portal frontend); this is the
    -- database-level backstop against obviously malformed values.
    CONSTRAINT users_national_id_format_check
        CHECK (national_id IS NULL OR national_id ~ '^[0-9]{14}$'),
    -- Egyptian mobile number: 01 + one of 0/1/2/5 + 8 digits.
    CONSTRAINT users_phone_format_check
        CHECK (phone IS NULL OR phone ~ '^01[0125][0-9]{8}$')
);

COMMENT ON TABLE users IS 'All principals: citizens, supervisors, technicians, admins. No hard delete — deactivated_at marks an account inactive without breaking FK history (tickets, decisions, audit logs).';
COMMENT ON COLUMN users.national_id IS 'Egyptian National ID, citizens only in practice. Sensitive PII — see design notes for encryption-at-rest and logging guidance.';

CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT roles_name_unique UNIQUE (name)
);

COMMENT ON TABLE roles IS 'citizen, supervisor, technician, admin. Seed data (06_seed.sql), not meant to be admin-editable at runtime.';

CREATE TABLE user_roles (
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id     UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

COMMENT ON TABLE user_roles IS 'Many-to-many so a second role never needs a schema change, though in practice one user has one role.';


-- -----------------------------------------------------------------------------
-- 2. Organization
-- -----------------------------------------------------------------------------

CREATE TABLE departments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT NOT NULL,
    description  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT departments_name_unique UNIQUE (name)
);

CREATE TABLE maintenance_teams (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id  UUID NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    name           TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT maintenance_teams_dept_name_unique UNIQUE (department_id, name)
);

CREATE TABLE maintenance_team_members (
    team_id     UUID NOT NULL REFERENCES maintenance_teams(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (team_id, user_id)
);

COMMENT ON TABLE maintenance_team_members IS 'A technician''s department membership is derived from their team, not a direct users.department_id column — a technician moving teams is one row change, not a user update, and a technician on two teams needs no schema change.';


-- -----------------------------------------------------------------------------
-- 3. Tickets
-- -----------------------------------------------------------------------------

CREATE TABLE categories (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL,
    default_department_id   UUID REFERENCES departments(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT categories_name_unique UNIQUE (name)
);

COMMENT ON COLUMN categories.default_department_id IS 'Routing hint, not a hard rule — AI/supervisor can still route a ticket to a different department. Nullable: some categories need judgment, not a fixed default.';

CREATE TABLE tickets (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    citizen_id     UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    category_id    UUID REFERENCES categories(id) ON DELETE RESTRICT,
    department_id  UUID REFERENCES departments(id) ON DELETE RESTRICT,
    severity       severity_enum,
    status         ticket_status_enum NOT NULL DEFAULT 'submitted',
    title          TEXT,
    description    TEXT NOT NULL,
    lat            DOUBLE PRECISION NOT NULL,
    lng            DOUBLE PRECISION NOT NULL,
    address        TEXT,
    governorate    TEXT,
    city           TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT tickets_lat_check CHECK (lat BETWEEN -90 AND 90),
    CONSTRAINT tickets_lng_check CHECK (lng BETWEEN -180 AND 180)
);

COMMENT ON TABLE tickets IS 'Never hard-deleted — a citizen cancellation is status=cancelled, not a DELETE, so history and audit stay intact.';
COMMENT ON COLUMN tickets.category_id IS 'Nullable: unset at submission until AI classifies it or a supervisor sets it.';
COMMENT ON COLUMN tickets.department_id IS 'Nullable: unset until AI/supervisor routes it. Plain lat/lng is sufficient at this scale — see design notes on PostGIS.';

CREATE TABLE ticket_media (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id   UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    type        media_type_enum NOT NULL,
    url         TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE ticket_media IS 'Citizen-submitted evidence at report time. URL points at object storage (Supabase Storage or equivalent) — binary content is never stored in Postgres.';

CREATE TABLE ticket_status_history (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id    UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    from_status  ticket_status_enum,
    to_status    ticket_status_enum NOT NULL,
    changed_by   UUID REFERENCES users(id) ON DELETE SET NULL,
    reason       TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN ticket_status_history.from_status IS 'NULL for the first row (ticket creation itself).';
COMMENT ON COLUMN ticket_status_history.changed_by IS 'NULL for a system-driven transition (e.g. the AI run completing moves submitted -> under_ai_review automatically).';


-- -----------------------------------------------------------------------------
-- 4. RAG — Legal knowledge base (laws, regulations, SOPs)
-- -----------------------------------------------------------------------------
-- See the "Embedding dimension strategy" note at the top of 04_indexes.sql and
-- in the design notes: embedding is left UNCONSTRAINED (no fixed dimension) on
-- purpose, because the AI team's embedding model is not yet finalized.

CREATE TABLE legal_knowledge_documents (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title              TEXT NOT NULL,
    source_type        legal_source_type_enum NOT NULL,
    reference_number   TEXT,
    department_id      UUID REFERENCES departments(id) ON DELETE SET NULL,
    content            TEXT NOT NULL,
    published_date     DATE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE legal_knowledge_documents IS 'LEGAL RAG corpus: laws, regulations, government decisions, department SOPs. This is the only source an AI recommendation may cite as LEGAL_EVIDENCE (see ai_evidence). Never holds citizen tickets.';

CREATE TABLE legal_knowledge_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES legal_knowledge_documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    token_count     INTEGER,
    embedding       vector,
    embedding_model TEXT,
    embedding_dim   INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT legal_knowledge_chunks_doc_chunk_unique UNIQUE (document_id, chunk_index),
    CONSTRAINT legal_knowledge_chunks_dim_check
        CHECK (embedding IS NULL OR embedding_dim IS NULL OR vector_dims(embedding) = embedding_dim)
);

COMMENT ON COLUMN legal_knowledge_chunks.embedding IS 'Unconstrained vector type (no fixed dimension) until the AI team confirms their embedding model. embedding_model/embedding_dim record what produced each vector. See design notes for the migration path once the model is final.';


-- -----------------------------------------------------------------------------
-- 5. RAG — Similar-case support (resolved ticket embeddings)
-- -----------------------------------------------------------------------------
-- A SEPARATE table from legal_knowledge_*, on purpose: similar-case retrieval
-- embeds ticket content, which is operationally and legally a different kind of
-- object from an official document. Keeping it a distinct table (rather than an
-- embedding column on `tickets` itself) means the embedding lifecycle — model
-- changes, re-embedding, backfills — never touches the tickets table at all.

CREATE TABLE ticket_embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       UUID NOT NULL UNIQUE REFERENCES tickets(id) ON DELETE CASCADE,
    content_hash    TEXT NOT NULL,
    embedding       vector,
    embedding_model TEXT,
    embedding_dim   INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ticket_embeddings_dim_check
        CHECK (embedding IS NULL OR embedding_dim IS NULL OR vector_dims(embedding) = embedding_dim)
);

COMMENT ON TABLE ticket_embeddings IS 'SIMILAR_CASE retrieval source: one embedding per resolved (or any) ticket, used by the AI team''s similarity search. content_hash lets the AI team detect a ticket whose description changed and the embedding is stale. Evidence shown to a supervisor cites the ticket itself (ai_evidence.cited_ticket_id -> tickets), never this table directly — this table only backs the search.';


-- -----------------------------------------------------------------------------
-- 6. AI
-- -----------------------------------------------------------------------------

CREATE TABLE ai_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    status          ai_run_status_enum NOT NULL DEFAULT 'pending',
    model_provider  TEXT,
    model_name      TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE ai_runs IS 'One row per orchestrator invocation for a ticket. Without this, a retried or re-run AI call has nowhere to record that it ran, only its final recommendation (if any).';

CREATE TABLE ai_tool_calls (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ai_run_id    UUID NOT NULL REFERENCES ai_runs(id) ON DELETE CASCADE,
    tool_name    TEXT NOT NULL,
    input        JSONB NOT NULL,
    output       JSONB,
    status       TEXT,
    duration_ms  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE ai_tool_calls IS 'Structured tool I/O only (tool name + JSON input/output) — this is what makes "genuinely agentic, multiple tool calls reasoned over" demonstrable with data. NEVER a raw model reasoning trace / chain-of-thought.';

CREATE TABLE ai_recommendations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ai_run_id       UUID NOT NULL REFERENCES ai_runs(id) ON DELETE CASCADE,
    ticket_id       UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    category_id     UUID REFERENCES categories(id) ON DELETE RESTRICT,
    severity        severity_enum,
    department_id   UUID REFERENCES departments(id) ON DELETE RESTRICT,
    confidence      NUMERIC(4,3),
    explanation     TEXT,
    factors         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ai_recommendations_confidence_check
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

COMMENT ON TABLE ai_recommendations IS 'The AI''s original structured output. Never overwritten by a supervisor''s edit (supervisor_decisions is a separate table) — that separation is what makes AI-acceptance rate measurable later.';
COMMENT ON COLUMN ai_recommendations.explanation IS 'Safe, backend-validated structured explanation text — never a raw chain-of-thought dump. Length-capped at the application layer.';
COMMENT ON COLUMN ai_recommendations.factors IS 'Short structured list of factors (e.g. ["obstructs a traffic lane", "primary road"]), not free-form reasoning.';

CREATE TABLE ai_evidence (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id   UUID NOT NULL REFERENCES ai_recommendations(id) ON DELETE CASCADE,
    evidence_type       ai_evidence_type_enum NOT NULL,
    knowledge_chunk_id  UUID REFERENCES legal_knowledge_chunks(id) ON DELETE RESTRICT,
    cited_ticket_id     UUID REFERENCES tickets(id) ON DELETE RESTRICT,
    snippet             TEXT,
    similarity_score    NUMERIC(5,4),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- THE FINAL RAG DECISION, ENFORCED AT THE DATABASE LEVEL:
    -- LEGAL_EVIDENCE must point at a legal_knowledge_chunks row and nothing else;
    -- SIMILAR_CASE must point at a ticket and nothing else. A previous ticket can
    -- never be stored as, or mistaken for, a legal source, and the two can never
    -- be left ambiguous (both set, or neither set).
    CONSTRAINT ai_evidence_type_source_check CHECK (
        (evidence_type = 'LEGAL_EVIDENCE' AND knowledge_chunk_id IS NOT NULL AND cited_ticket_id IS NULL)
        OR
        (evidence_type = 'SIMILAR_CASE' AND cited_ticket_id IS NOT NULL AND knowledge_chunk_id IS NULL)
    ),
    CONSTRAINT ai_evidence_similarity_check
        CHECK (similarity_score IS NULL OR (similarity_score >= 0 AND similarity_score <= 1))
);

COMMENT ON TABLE ai_evidence IS 'Every piece of evidence behind a recommendation, typed LEGAL_EVIDENCE or SIMILAR_CASE. The CHECK constraint is the actual enforcement of "a previous ticket must never be presented as a legal source" — it is impossible to insert a row that violates it, regardless of what the AI service sends.';

CREATE TABLE supervisor_decisions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id          UUID NOT NULL REFERENCES tickets(id) ON DELETE RESTRICT,
    recommendation_id  UUID REFERENCES ai_recommendations(id) ON DELETE RESTRICT,
    supervisor_id      UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    action             decision_action_enum NOT NULL,
    changed_fields     JSONB,
    reason             TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN supervisor_decisions.recommendation_id IS 'Nullable: a supervisor can still act (e.g. manually triage) even if the AI run failed or timed out.';
COMMENT ON COLUMN supervisor_decisions.changed_fields IS 'What the supervisor changed from the AI''s recommendation, e.g. {"severity": {"from": "medium", "to": "high"}} — the comparison dataset for evaluating the AI.';


-- -----------------------------------------------------------------------------
-- 7. Maintenance & verification
-- -----------------------------------------------------------------------------

CREATE TABLE maintenance_tasks (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id      UUID NOT NULL REFERENCES tickets(id) ON DELETE RESTRICT,
    team_id        UUID NOT NULL REFERENCES maintenance_teams(id) ON DELETE RESTRICT,
    assigned_by    UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    attempt_number INTEGER NOT NULL DEFAULT 1,
    status         task_status_enum NOT NULL DEFAULT 'assigned',
    notes          TEXT,
    assigned_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at     TIMESTAMPTZ,
    completed_at   TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT maintenance_tasks_ticket_attempt_unique UNIQUE (ticket_id, attempt_number),
    CONSTRAINT maintenance_tasks_attempt_positive_check CHECK (attempt_number >= 1)
);

COMMENT ON TABLE maintenance_tasks IS 'One row per work attempt (not one row reused/reset on rework): a failed verification creates a NEW row with attempt_number + 1, same ticket. This gives assignment history and a rework count for free, with no derived/computed state.';

CREATE TABLE task_evidence (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     UUID NOT NULL REFERENCES maintenance_tasks(id) ON DELETE CASCADE,
    type        media_type_enum NOT NULL,
    stage       TEXT NOT NULL DEFAULT 'after',
    url         TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT task_evidence_stage_check CHECK (stage IN ('progress', 'after'))
);

COMMENT ON TABLE task_evidence IS 'Technician-submitted evidence. stage distinguishes in-progress photos from the final after-repair evidence used in the before/after comparison (before = ticket_media on the originating ticket).';

CREATE TABLE verifications (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id      UUID NOT NULL REFERENCES maintenance_tasks(id) ON DELETE RESTRICT,
    verifier_id  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    result       verification_result_enum NOT NULL,
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE verifications IS 'A deliberately separate step from supervisor approval, even when the same person performs both roles early on — a distinct status is what lets the system show a true before/after comparison and measure rework rate.';


-- -----------------------------------------------------------------------------
-- 8. Notifications & audit
-- -----------------------------------------------------------------------------

CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticket_id   UUID REFERENCES tickets(id) ON DELETE CASCADE,
    channel     notification_channel_enum NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT,
    read_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_logs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    action       TEXT NOT NULL,
    entity_type  TEXT NOT NULL,
    entity_id    UUID NOT NULL,
    before       JSONB,
    after        JSONB,
    ip_address   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE audit_logs IS 'Write-only from the service layer; never UPDATEd or DELETEd by application code. actor_id is SET NULL (not RESTRICT) so a log entry survives even if the acting user is later removed.';
