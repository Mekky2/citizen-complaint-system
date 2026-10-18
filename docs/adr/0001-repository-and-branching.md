# ADR-0001: Monorepo, trunk-based branching, three environments

- **Status:** Proposed
- **Plan reference:** Phase 0, task 0.1

## Decision
1. Monorepo with `backend/`, `frontend/`, `infra/`, `docs/`.
2. Trunk-based development: protected `main`, short-lived branches, squash merge, no long-lived `develop`.
3. Three environments by Git event: `dev` (merge to `main`), `staging` (tag `vX.Y.Z-rc.N`), `production` (tag `vX.Y.Z`, manual approval).
4. Branch names and commits carry plan task IDs and story IDs.

## Stack (assumed, not yet confirmed)
Python 3.12 + FastAPI, React + TypeScript + Vite, PostgreSQL (pgvector added in Phase 4), local file storage in development and S3-compatible storage when deployed, GitHub Actions.
