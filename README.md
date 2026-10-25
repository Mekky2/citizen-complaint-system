# Citizen Complaint Management System

AI-driven, human-in-the-loop platform for municipal complaint management.

## Documentation
- [Overview](docs/project_overview.md)
- [Architecture](docs/system_architecture.md)
- [Implementation plan](docs/implementation_plan.md)
- User stories: [citizen](docs/citizen_user_stories.md), [admin/reviewer](docs/administrator_reviewer_user_stories.md), [maintenance](docs/maintenance_team_user_stories.md)
- [Contributing guide](CONTRIBUTING.md)

## Layout
- `backend/` FastAPI API, agents (orchestrator, complaint agent, tools, middleware), knowledge base
- `frontend/` React app: `src/portal` (citizens), `src/dashboard` (staff), `src/shared`
- `infra/` environment notes and deployment files
- `docs/` all documentation

## Run locally
Backend:
```
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows Git Bash: source .venv/Scripts/activate
pip install -e ".[dev]"
cp .env.example .env             # then set DATABASE_URL (see CONTRIBUTING.md, "Database")
uvicorn app.main:app --reload
```
Frontend:
```
cd frontend
npm install
npm run dev
```
Database: hosted on Supabase (PostgreSQL + pgvector + Storage). See "Database (Supabase)" in CONTRIBUTING.md.
