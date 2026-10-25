# Contributing

## Branching (trunk-based)
- `main` is always deployable and protected. Changes arrive only by pull request with passing CI, using squash merge. Never push directly to `main`.
- Work on short-lived branches (under 3 days) created from `main`.
- Branch name: `<type>/<task-id>-<story-ids>-<slug>`, for example `feat/2.1-CIT-01-form-shell`.
- Types: `feat`, `fix`, `chore`, `docs`, `test`, `hotfix`.
- IDs come from docs/implementation_plan.md.

## Commits
`<type>(<scope>): <summary> [<story or task id>]`
Example: `feat(portal): add complaint form shell [CIT-01]`

## Environments and releases
- `dev`: every merge to `main`
- `staging`: tag `vX.Y.Z-rc.N`
- `production`: tag `vX.Y.Z`, approved by the required reviewer
Release: `git tag v0.1.0-rc.1 && git push origin v0.1.0-rc.1`, test on staging, then tag `v0.1.0` from the same commit.

## Pull requests
Fill in the template, keep PRs small, CI (`backend`, `frontend`) must pass. Follow the Definition of Done in the implementation plan.

## Secrets (the repo is public)
- Never commit `.env` files, passwords, keys or connection strings. Real values live only in your git-ignored `backend/.env` and in GitHub environment secrets.
- Never paste passwords or keys into issues, pull requests, chats or screenshots. If one leaks, reset it immediately.

## Database (Supabase)
The database is a hosted Supabase project, not a local install.
1. Ask the team lead for an invitation to the Supabase organization and for the database password (shared privately, never in the repo).
2. In the Supabase dashboard open your project, click **Connect**, choose the **Direct** tab, then **Session pooler**, and copy the connection string.
3. In `backend/.env` set `DATABASE_URL` using the format in `backend/.env.example` (keep the `postgresql+psycopg://` prefix).
4. Test it: `psql "$(grep '^DATABASE_URL=' backend/.env | cut -d= -f2- | sed 's/+psycopg//')" -c "select 1;"`
5. Do not create or change tables in the dashboard. Schema changes are SQL migrations in `backend/migrations/`, merged through pull requests.
6. A free Supabase project pauses after 7 days without activity. If it is paused, restore it from the dashboard.
