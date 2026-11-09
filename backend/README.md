# EG Civic Operations — Backend

FastAPI modular-monolith backend for the EG Civic Operations graduation
project. Maps onto an **already-existing, already-deployed** PostgreSQL 17 +
pgvector database (23 tables, 10 enums, 62 indexes, 36 FKs) that this backend
never creates, alters, or recreates.

## Fix pass (2026-11-01) — see "Changes in this review pass" below

A round of review feedback (technician task-authorization, task evidence API,
Legal RAG boundary, Similar Cases privacy, plus async/validation/JWT/refresh
improvements) was implemented, automated-tested against the live database
(30/30 passing), and two real bugs were found and fixed along the way. Jump
to [Changes in this review pass](#changes-in-this-review-pass) for the full
account, or run `pytest tests/ -v` yourself (see "Automated tests" below).

## Database baseline — read this first

The database is the source of truth. It was built entirely by
`database/init/01_extensions.sql` through `06_seed.sql` (a separate
deliverable), and nothing in this backend ever runs DDL against it:

- `app/db.py` never calls `Base.metadata.create_all()`.
- Every SQLAlchemy `Enum(...)` column uses `create_type=False,
  checkfirst=False` (`app/models/enums.py:pg_enum`) — SQLAlchemy only ever
  reads/writes existing Postgres enum values, never creates or alters a type.
- Alembic is configured to treat the existing database as its **baseline**
  (see "Alembic" below), not as something to build from scratch.

**No schema compatibility issue was found.** The SQLAlchemy models in
`app/models/` were verified against a live instance of the database via
`sqlalchemy.inspect()` — every table, column, type, FK, and constraint
matched exactly. Per the brief's instruction, if such an issue *had* been
found, this README would say so here instead of a silent workaround. It
wasn't, so none follows.

### A deployment gotcha worth knowing

If your `egcivic` database's tables were created while connected as a
different Postgres role than the one `DATABASE_URL` uses (e.g. tables owned
by `postgres`, app connects as `egcivic_user`), you will get
`permission denied for table X` on first request. Fix once, as a superuser:

```sql
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO egcivic_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO egcivic_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO egcivic_user;
```

If your `egcivic-postgres` container's tables were created directly as
`egcivic_user` (the normal case for the Docker setup described in the task
brief), you will likely never hit this.

## Setup

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install --break-system-packages -r requirements.txt   # or omit the flag outside a managed env

cp .env.example .env
# edit .env: DATABASE_URL (point at your running egcivic-postgres),
# JWT_SECRET_KEY (generate: python -c "import secrets; print(secrets.token_urlsafe(64))"),
# AI_SERVICE_URL / AI_SERVICE_SHARED_SECRET once the AI team's service exists.
```

## Running

```bash
uvicorn app.main:app --reload --port 8000
```

- `GET /health` — does a real `SELECT 1` against Postgres, not just
  process liveness.
- `GET /docs` — interactive OpenAPI docs (Swagger UI).

### First admin account

Self-registration (`POST /api/v1/auth/register`) only ever creates a
**citizen**. There is no seeded admin, deliberately — a real deployment
creates its first admin out-of-band. For local development, insert one
directly:

```sql
-- Generate a hash first:
--   python -c "from app.security.hashing import hash_password; print(hash_password('YourPassword123'))"
INSERT INTO users (name, email, phone, password_hash)
VALUES ('Admin', 'admin@example.com', '01000000000', '<paste the hash>')
RETURNING id;

INSERT INTO user_roles (user_id, role_id)
SELECT '<the id above>', id FROM roles WHERE name = 'admin';
```

From there, `POST /api/v1/admin/staff` creates every other supervisor /
technician / admin account through the normal authenticated API.

### Known harmless warning

`passlib[bcrypt]==1.7.4` logs `(trapped) error reading bcrypt version` on
first use against `bcrypt==4.2.1` (passlib 1.7.4 predates bcrypt 4.x's
`__about__` removal). It is cosmetic — password hashing and verification
both work correctly, verified live in this project's test pass. If it
bothers you, pin `bcrypt==4.0.1` instead; not done here since it changes
nothing functionally and a newer bcrypt is otherwise preferable.

## Alembic

The database already exists, fully built by `database/init/*.sql` — Alembic
is configured as a baseline on top of it, not as the tool that built it.

- `alembic/env.py` points `target_metadata` at the same `Base`/models the
  app uses, and reads `DATABASE_URL` from `app.config.get_settings()` — one
  source of truth, not two connection strings that can drift apart.
- `alembic/versions/f479cacdd53c_baseline.py` is a **hand-written, empty**
  migration — `upgrade()`/`downgrade()` both do nothing. The database has
  already been stamped at this revision (`alembic stamp head`), so Alembic
  considers it fully up to date without ever running DDL against it.

**Why the migration is empty rather than autogenerated:** running
`alembic revision --autogenerate` against the live database does NOT come
back empty. It proposes dropping every hand-written index from
`03_tables.sql` (`idx_tickets_status`, `idx_ai_evidence_*`, …) and every
`COMMENT ON COLUMN` from the init scripts, because those aren't declared as
SQLAlchemy `Index(...)` objects or `.comment=` on the ORM models — the ORM
doesn't need them mapped to use the schema correctly. That diff was
reviewed, confirmed to be autogenerate noise and not a real mismatch (see
"Database baseline" above), and discarded rather than applied, since
applying it would drop real, useful indexes for no reason.

For a genuinely new schema change in the future (the AI team asks for a new
column, say): change the database via a new, hand-reviewed migration (or a
new `database/init/`-style script, by prior convention), update the
matching SQLAlchemy model, and only then run
`alembic revision --autogenerate` — review its diff carefully against the
"indexes/comments aren't mapped" noise described above before trusting it.

## API surface

| Prefix | Who | What |
|---|---|---|
| `/api/v1/auth` | public | citizen register, login, refresh, `/me` |
| `/api/v1/users` | self / admin | own profile; admin lists/updates any user |
| `/api/v1/tickets` | citizen / staff | create (citizen-only), list, detail, media |
| `/api/v1/supervisor` | supervisor, admin | the human-approval gate (approve/edit/reject an AI recommendation) |
| `/api/v1/maintenance` | admin, supervisor, technician (team-scoped — see FIX 1) | teams, team membership, task assignment/rework, task status, task evidence (FIX 2), `/tasks/mine` |
| `/api/v1/verification` | supervisor, admin | pass/fail a completed maintenance task |
| `/api/v1/notifications` | self | list / mark-read own notifications |
| `/api/v1/ai` | staff (trigger) / AI service (callback, similar-cases, legal-search — all shared secret) | the AI integration boundary, incl. Legal RAG (FIX 3) |
| `/api/v1/admin` | admin | staff accounts, departments, categories, audit log |
| `/health` | public | DB connectivity check |

## AI integration contract

- **Backend → AI**: `app/ai/client.py:send_run_trigger()` POSTs to
  `{AI_SERVICE_URL}/v1/runs` with `app/schemas/ai.py:AiRunTriggerOut`
  (ticket description, media, location) plus the `run_id`.
- **AI → Backend**: the AI service POSTs to `POST /api/v1/ai/recommendations`
  (`app/schemas/ai.py:AiRecommendationCallbackIn`), authenticated by a shared
  secret header (`X-AI-Service-Secret`, checked by
  `app/dependencies/ai_auth.py`) — **never** a user JWT, so a leaked
  AI-service credential can't mint a citizen/staff session and vice versa.
- `run_id` (`ai_runs.id`) is the **idempotency key** —
  `app/services/ai.py:process_ai_recommendation_callback()` returns early,
  without reprocessing, for a run already in a terminal state
  (`succeeded`/`failed`). Verified live: resending an identical callback
  does not duplicate evidence rows or change the stored recommendation.
- The AI service **never connects to Postgres directly** — it gets
  historical-ticket data through `GET /api/v1/ai/similar-cases` (shared
  secret), which only ever returns `completed` tickets.
- **Human-in-the-loop**: a successful callback advances a ticket to
  `awaiting_approval` and stops. Only `POST
  /api/v1/supervisor/tickets/{id}/decisions` can move it further — the AI
  can never assign, approve, or otherwise act on its own recommendation.
- **No chain-of-thought storage**: `AiRecommendationPayload.explanation` is
  capped at 1000 chars, each `factor` at 200 chars (max 10 factors) — a
  structured summary fits; a reasoning trace doesn't, and the schema has no
  field that could hold one even if the AI service sent it (Pydantic drops
  unknown fields by default).

## Business rules enforced in code (not the schema)

1. **Technician-only maintenance team membership** —
   `app/services/maintenance.py:add_team_member()` checks the target user's
   *current* role (re-read from the DB, not a client-supplied claim) and
   403s if it isn't `technician`. Verified live: adding a technician
   succeeds (201), adding a citizen is rejected (403).
2. **Similar-case evidence must cite a completed ticket** —
   `app/services/ai.py:_validate_similar_case_is_historical()` 400s a
   `SIMILAR_CASE` evidence item whose `cited_ticket_id` points at anything
   but a `completed` ticket (never `cancelled` or still-active). The
   read-side counterpart, `list_similar_case_candidates()` (behind
   `GET /api/v1/ai/similar-cases`), only ever offers `completed` tickets as
   candidates in the first place.

## Automated tests

```bash
pip install --break-system-packages -r requirements-dev.txt   # adds pytest on top of requirements.txt
pytest tests/ -v
```

`tests/` is an **integration** suite: it runs FastAPI's `TestClient` against
`app.main.app` wired to the **real** `DATABASE_URL` from `.env` — the same
live PostgreSQL 17 + pgvector database, not sqlite or a mocked session. It
needs Postgres running and reachable exactly as the app itself does (see
"A deployment gotcha worth knowing" above). Each test uses randomly-suffixed
emails/phones/names so repeat runs don't collide; there is no
teardown/rollback, so test data (tickets, users, teams…) accumulates in the
database across runs — acceptable for a dev/integration database, noted here
so it isn't a surprise (see "Remaining limitations" below).

Current result: **30 passed, 0 failed** (`pytest tests/ -v`, ~11s). Coverage:
auth (register/login/invalid-credentials/JWT/role-authorization), tickets
(create/IDOR/supervisor-access/status-transition), maintenance (team
membership enforcement — FIX 1 — task evidence — FIX 2 — rework attempts,
`/tasks/mine`), and AI (run creation, callback validation + idempotency,
unknown-category rejection, evidence type/completeness rules, Legal RAG via
real pgvector cosine search — FIX 3, Similar Cases privacy — FIX 4).

For a quick manual spot-check instead:

```bash
curl -X POST localhost:8000/api/v1/auth/register -H 'Content-Type: application/json' \
  -d '{"name":"Ahmed","phone":"01012345678","password":"password123"}'
```

## Changes in this review pass

Implements the four requested fixes plus the four additional improvements,
against the existing architecture — no schema changes, no new tables, no
rebuild. Full detail in each file's own docstring; summary here.

**FIX 1 — Technician task authorization is now team-scoped.**
`app/services/maintenance.py:_assert_can_access_task()` is the single
enforcement point every technician-sensitive task endpoint (status update,
evidence add/list) calls: a technician may act on a task only if they have a
`maintenance_team_members` row for *that task's* `team_id`, re-checked
against the database every call. The actual bug being fixed: the old code
only checked *role* (technician/supervisor/admin), never *which team* —
any technician who knew a task_id could update it regardless of team.
Supervisor/admin stay unscoped (operational oversight). Tested: a technician
on a different team gets 403 on the same task a correctly-assigned
technician gets 200 on (`tests/test_maintenance.py::test_technician_team_membership_enforcement`).

**FIX 2 — Task Evidence API added.**
`POST` / `GET /api/v1/maintenance/tasks/{task_id}/evidence`, using the
existing `task_evidence` table and the existing `TaskEvidenceCreateIn`/
`TaskEvidenceOut` schemas (no new table, no new schema). Authorization goes
through the same `_assert_can_access_task()` as FIX 1. Tested: valid
creation, an outsider technician rejected (403), a nonexistent task (404),
and retrieval by the authorized technician and by a supervisor
(`tests/test_maintenance.py::test_task_evidence_api`).

**FIX 3 — Legal RAG backend boundary added.**
`POST /api/v1/ai/legal-search` (shared-secret only, like the other AI-facing
routes) calls `app/services/legal_rag.py:search_legal_knowledge()`, a pgvector
cosine-similarity search over `legal_knowledge_chunks`/`legal_knowledge_documents`
only — it has no import of, and never queries, `Ticket`, so it cannot return
a historical ticket as legal evidence even by accident. No fixed embedding
dimension: the query matches only chunks whose own `embedding_dim` equals
`len(query_embedding)`, respecting the column's deliberately unconstrained
`vector` type. Tested against real pgvector cosine distance (not mocked) with
an inserted chunk and a near-identical query vector
(`tests/test_ai.py::test_legal_search_finds_matching_chunk_via_pgvector`).

**FIX 4 — Similar Cases response is now privacy-minimized.**
`GET /api/v1/ai/similar-cases` returns a new `SimilarCaseOut` schema
(`ticket_id`, `category_id`, `description`, `severity`, `status`,
`governorate`, `created_at`, `completed_at`) instead of `TicketOut` —
`citizen_id`, exact `address`, `city`, phone/email never leave the backend
toward the AI service. Built field-by-field in
`app/services/ai.py:list_similar_case_candidates()` rather than trusting a
`response_model` to strip fields later. Still filtered to `status=completed`
only (the pre-existing rule). Tested: response never contains the forbidden
fields, and every item's `status` is `completed`
(`tests/test_ai.py::test_similar_cases_endpoint_privacy_and_completed_only`).

**Improvement 1 — Async HTTP for the one real outbound call.**
`app/ai/client.py:send_run_trigger()` is now `async def` using
`httpx.AsyncClient`, and its caller (`trigger_ai_run` in
`app/services/ai.py`, and `POST /api/v1/ai/tickets/{id}/trigger` in
`app/routers/ai.py`) is `async def` all the way up, so the `await` is real
rather than a sync call blocking the event loop. Every other route stays a
plain sync `def` — FastAPI already runs blocking DB-only handlers in a
worker thread pool, so there was nothing to convert there.

**Improvement 2 — AI validation no longer silently nulls bad data.**
An AI recommendation naming an unrecognized `category` or `department` is
now rejected with 400 (`app/services/ai.py:_resolve_category_id`/
`_resolve_department_id`) instead of being stored as `category_id=NULL` —
which used to be indistinguishable from "the AI genuinely didn't classify
this," a real and legitimate state `category=None` already represents.
`run.status` is left `pending` (not flipped to `succeeded`) on this
rejection. Tested in `test_ai_callback_rejects_unknown_category_instead_of_nulling_it`.

**Improvement 3 — JWT/Swagger security scheme fixed, login endpoint untouched.**
`app/dependencies/auth.py` switched from `OAuth2PasswordBearer` to
`HTTPBearer`: the OAuth2 scheme told Swagger's "Authorize" dialog to POST
form-encoded `username`/`password` to `/api/v1/auth/login`, but that endpoint
has always taken JSON `{identifier, password}` (`LoginIn`) — so clicking
"Authorize" in `/docs` 422'd against the real endpoint. `HTTPBearer` just
asks for a bearer token to paste (call login via "Try it out" first, paste
`access_token`); on the wire both schemes read the same `Authorization:
Bearer <token>` header, so `decode_token()` and every existing client are
unchanged. **Bug caught by the fix's own test:** `HTTPBearer(auto_error=True)`
(the default) raises 403, not 401, for a missing Authorization header —
breaking `test_no_token_rejected`. Fixed with `auto_error=False` plus an
explicit `if credentials is None: raise credentials_exception` in
`get_current_user`, so missing and malformed tokens both consistently 401.

**Improvement 4 — Refresh tokens reviewed, limitation documented, no new table.**
See the full writeup in `app/security/jwt.py`'s module docstring. Summary:
refresh tokens are stateless JWTs with no server-side revocation record, so
(a) there is no real "logout" before natural expiry, and (b) refreshing
doesn't invalidate the token that was just used (no rotation-with-reuse-
detection). Real revocation needs a persisted denylist/used-token table or a
per-user token-version column — none of which exist in the current schema,
and the task brief is explicit that a schema gap gets documented, not
silently worked around. Mitigation available today with no schema change:
keep `ACCESS_TOKEN_EXPIRE_MINUTES` short and treat
`REFRESH_TOKEN_EXPIRE_MINUTES` as the real exposure window for a stolen
refresh token.

### Bugs found and fixed during this pass

1. **403 vs 401 on missing token** (Improvement 3's own regression) — fixed
   as described above; `test_no_token_rejected` now passes.
2. **Test-fixture phone numbers were invalid** — `tests/conftest.py`'s
   `unique()` returns a hex string (can contain `a`-`f`), and several tests
   prepended prefixes (`020`, `021`) that don't match the Egyptian format
   `01[0125][0-9]{8}` at all. Both the Pydantic validator (`app/schemas/auth.py`)
   and the database's own `users_phone_format_check` CHECK constraint
   correctly rejected these — this was a test-code bug, not an application
   bug, but it cascaded into ~20 failing/erroring tests whose real assertions
   never got to run. Fixed by adding `unique_digits(n)` (digits only, derived
   from `uuid4().int`) and using it everywhere a test builds a phone number.
3. **`test_register_duplicate_phone_conflicts` used a 1-character name**
   (`"A"`/`"B"`) against `CitizenRegisterIn.name`'s `min_length=3` — fixed to
   use real names; unrelated to any of the four fixes above, caught while
   fixing bug 2.

### Remaining limitations

- Refresh-token revocation/rotation — see Improvement 4 above; documented,
  not fixed, by design (would require a schema change).
- The test suite leaves its data in the database (no rollback) — fine for a
  dev database, not meant to run against a production one.
- `_resolve_category_id`/`_resolve_department_id` match AI-supplied
  category/department **names** against the `categories`/`departments`
  tables; if the AI team's naming ever drifts from this backend's (e.g.
  casing), every recommendation using that name 400s until they're
  reconciled — intentional per Improvement 2, but worth knowing operationally.

## Project layout

```
backend/
  app/
    main.py            FastAPI app, CORS, router mounting, /health
    config.py           Settings (pydantic-settings, reads .env)
    db.py                Engine/session/Base — never creates schema
    models/              SQLAlchemy models, 1:1 with the existing DB
    schemas/              Pydantic request/response models
    security/             JWT + password hashing
    dependencies/          get_current_user / require_role, AI shared-secret check
    services/              Business logic — one module per domain area
    ai/                    AI integration HTTP client (app/schemas/ai.py has the shapes)
    routers/                One module per API prefix, wired in main.py
  alembic/                Baseline-only migration config (see "Alembic" above)
  requirements.txt
  .env.example
```
