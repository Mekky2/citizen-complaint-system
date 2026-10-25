# ADR-0001: Monorepo, trunk-based branching, three environments, Supabase

- **Status:** Accepted
- **Plan reference:** Phase 0, tasks 0.1 to 0.3

## Decision
1. Monorepo with `backend/`, `frontend/`, `infra/`, `docs/`.
2. Trunk-based development: protected `main`, short-lived branches, squash merge, no long-lived `develop`.
3. Three environments by Git event: `dev` (merge to `main`), `staging` (tag `vX.Y.Z-rc.N`), `production` (tag `vX.Y.Z`, required reviewer).
4. Branch names and commits carry plan task IDs and story IDs.
5. **Supabase** replaces a self-managed PostgreSQL: hosted Postgres, pgvector for RAG, and Storage for files. All access goes through the FastAPI backend, and the Supabase Data API is disabled.

## Stack
Python 3.12 + FastAPI, React + TypeScript + Vite, Supabase (PostgreSQL, pgvector, Storage), GitHub Actions. Undecided: Supabase Auth, Supabase Realtime, ORM and migration tool, LLM provider, hosting for the backend and frontend.

## Consequences
- Local development needs internet access and a Supabase connection string (session pooler).
- The free plan allows 2 active projects and pauses idle projects after 7 days, so only a `dev` project exists for now.
- The repo is public, so no credentials are ever committed.
