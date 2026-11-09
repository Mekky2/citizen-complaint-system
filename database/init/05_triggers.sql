-- =============================================================================
-- EG Civic Operations — Triggers
-- =============================================================================
-- One generic function, reused by every table that has an updated_at column.
-- Append-only/log tables (user_roles, maintenance_team_members, ticket_media,
-- ticket_status_history, ai_tool_calls, ai_evidence, supervisor_decisions,
-- task_evidence, verifications, notifications, audit_logs) have no updated_at
-- and so get no trigger — they are written once and never changed in place.
-- =============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION set_updated_at() IS 'Stamps updated_at = now() on every UPDATE. Attached via BEFORE UPDATE triggers below.';

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_roles_updated_at
    BEFORE UPDATE ON roles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_departments_updated_at
    BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_maintenance_teams_updated_at
    BEFORE UPDATE ON maintenance_teams
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_categories_updated_at
    BEFORE UPDATE ON categories
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_legal_knowledge_documents_updated_at
    BEFORE UPDATE ON legal_knowledge_documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_legal_knowledge_chunks_updated_at
    BEFORE UPDATE ON legal_knowledge_chunks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_ticket_embeddings_updated_at
    BEFORE UPDATE ON ticket_embeddings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_ai_runs_updated_at
    BEFORE UPDATE ON ai_runs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_ai_recommendations_updated_at
    BEFORE UPDATE ON ai_recommendations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_maintenance_tasks_updated_at
    BEFORE UPDATE ON maintenance_tasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
