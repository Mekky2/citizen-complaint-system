# Contributing

## Branching (trunk-based)
- `main` is always deployable and protected. Changes arrive only by pull request with passing CI and approval, using squash merge.
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
- `production`: tag `vX.Y.Z`, manual approval
Release: `git tag v0.1.0-rc.1 && git push origin v0.1.0-rc.1`, test on staging, then tag `v0.1.0` from the same commit.

## Pull requests
Fill in the template, keep PRs small, CI (`backend`, `frontend`) must pass. Follow the Definition of Done in the implementation plan.

## Local database
```
psql postgres        # Ubuntu: sudo -u postgres psql   Windows: psql -U postgres
CREATE USER complaints WITH PASSWORD 'complaints';
CREATE DATABASE complaints OWNER complaints;
```
