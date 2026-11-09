-- =============================================================================
-- EG Civic Operations — Indexes
-- =============================================================================
-- Every UNIQUE constraint declared in 03_tables.sql already created its own
-- index automatically; this file adds the indexes those constraints don't give
-- us for free — foreign-key lookups actually used by the API, and the two
-- composite indexes the map/queue views need.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- RBAC / organization
-- -----------------------------------------------------------------------------

-- user_roles' PK (user_id, role_id) already indexes user_id-first lookups;
-- this covers the reverse direction ("everyone with role X").
CREATE INDEX idx_user_roles_role_id ON user_roles (role_id);

CREATE INDEX idx_maintenance_teams_department_id ON maintenance_teams (department_id);

-- maintenance_team_members' PK (team_id, user_id) covers "members of team X";
-- this covers "which team(s) is user X on".
CREATE INDEX idx_maintenance_team_members_user_id ON maintenance_team_members (user_id);

CREATE INDEX idx_categories_default_department_id ON categories (default_department_id);


-- -----------------------------------------------------------------------------
-- Tickets
-- -----------------------------------------------------------------------------

CREATE INDEX idx_tickets_citizen_id ON tickets (citizen_id);
CREATE INDEX idx_tickets_category_id ON tickets (category_id);
CREATE INDEX idx_tickets_status ON tickets (status);
-- Operations Room's primary filtered view: "open tickets for department X".
CREATE INDEX idx_tickets_department_status ON tickets (department_id, status);
-- Map view bounding-box queries (lat BETWEEN ... AND lng BETWEEN ...).
CREATE INDEX idx_tickets_lat_lng ON tickets (lat, lng);

CREATE INDEX idx_ticket_media_ticket_id ON ticket_media (ticket_id);
CREATE INDEX idx_ticket_status_history_ticket_id ON ticket_status_history (ticket_id);


-- -----------------------------------------------------------------------------
-- AI
-- -----------------------------------------------------------------------------

CREATE INDEX idx_ai_runs_ticket_id ON ai_runs (ticket_id);
CREATE INDEX idx_ai_runs_status ON ai_runs (status);

CREATE INDEX idx_ai_tool_calls_ai_run_id ON ai_tool_calls (ai_run_id);

CREATE INDEX idx_ai_recommendations_ticket_id ON ai_recommendations (ticket_id);

CREATE INDEX idx_ai_evidence_recommendation_id ON ai_evidence (recommendation_id);
CREATE INDEX idx_ai_evidence_knowledge_chunk_id ON ai_evidence (knowledge_chunk_id);
CREATE INDEX idx_ai_evidence_cited_ticket_id ON ai_evidence (cited_ticket_id);

CREATE INDEX idx_supervisor_decisions_ticket_id ON supervisor_decisions (ticket_id);


-- -----------------------------------------------------------------------------
-- Maintenance & verification
-- -----------------------------------------------------------------------------

CREATE INDEX idx_maintenance_tasks_team_id ON maintenance_tasks (team_id);
CREATE INDEX idx_maintenance_tasks_status ON maintenance_tasks (status);

CREATE INDEX idx_task_evidence_task_id ON task_evidence (task_id);
CREATE INDEX idx_verifications_task_id ON verifications (task_id);


-- -----------------------------------------------------------------------------
-- Notifications & audit
-- -----------------------------------------------------------------------------

-- "My unread notifications" is the only query this screen ever runs.
CREATE INDEX idx_notifications_user_read ON notifications (user_id, read_at);
CREATE INDEX idx_notifications_ticket_id ON notifications (ticket_id);

CREATE INDEX idx_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX idx_audit_logs_actor_id ON audit_logs (actor_id);


-- -----------------------------------------------------------------------------
-- Legal knowledge base
-- -----------------------------------------------------------------------------

CREATE INDEX idx_legal_knowledge_documents_department_id ON legal_knowledge_documents (department_id);
CREATE INDEX idx_legal_knowledge_documents_source_type ON legal_knowledge_documents (source_type);
-- legal_knowledge_chunks_doc_chunk_unique already indexes document_id as its
-- leading column, so a plain lookup by document_id alone is already fast.


-- =============================================================================
-- Vector (ANN) indexes — DEFERRED ON PURPOSE
-- =============================================================================
-- legal_knowledge_chunks.embedding and ticket_embeddings.embedding are declared
-- as an UNCONSTRAINED `vector` type (no fixed dimension) in 03_tables.sql,
-- because the AI team's embedding model/dimension is not finalized yet. An
-- ivfflat/hnsw ANN index needs every indexed vector to share one fixed
-- dimension, so we cannot build one yet without risking locking in the wrong
-- number.
--
-- This is not a blocker for the MVP: at graduation-project data volumes
-- (hundreds to low thousands of chunks/tickets), an exact sequential-scan
-- cosine search (`ORDER BY embedding <=> query_embedding LIMIT k`) is fast
-- enough with no index at all, as long as all stored vectors in a given column
-- already share one dimension (which embedding_dim + the CHECK constraint
-- verifies at write time).
--
-- ONCE the AI team confirms their embedding model and its output dimension N:
--
--   1. Fix the column's dimension (safe only if every existing row already has
--      dimension N — the CHECK constraint guarantees no row disagrees):
--         ALTER TABLE legal_knowledge_chunks
--             ALTER COLUMN embedding TYPE vector(N);
--         ALTER TABLE ticket_embeddings
--             ALTER COLUMN embedding TYPE vector(N);
--
--   2. Then build the ANN index (ivfflat shown; swap to hnsw if the pgvector
--      version installed supports it and the team prefers its recall/build
--      trade-off — both are created the same way):
--         CREATE INDEX idx_legal_knowledge_chunks_embedding
--             ON legal_knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
--             WITH (lists = 100);
--         CREATE INDEX idx_ticket_embeddings_embedding
--             ON ticket_embeddings USING ivfflat (embedding vector_cosine_ops)
--             WITH (lists = 100);
--
--      `lists` is a tuning parameter (rows / 1000 is the common starting point
--      — 100 is fine until the corpus is well past 100k rows, which this
--      project will not reach).
--
-- See "Design Notes" in the chat response for the full reasoning.
-- =============================================================================
