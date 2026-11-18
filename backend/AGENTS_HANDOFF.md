# Handoff — Arabic complaint agent and RAG agent

Branch: `feature/arabic-complaint-and-rag-agents` (based on `origin/main` = `9e57a67`).
Scope: **backend only**. The frontend is not part of this branch or pull request.

---

## 1. What was added

| Area | Files | What it does |
|---|---|---|
| Complaint agent | `app/agents/complaint_agent/conversation.py`, `authorities.py`, `prompts_arabic.py`, `prompt_files/` | Multi-turn Arabic complaint intake: category, location, urgency, confirmation, duplicate linking, PII masking, abuse/injection/emergency handling. Never creates a ticket before confirmation. |
| RAG agent | `app/agents/rag_agent/` | Answers Arabic questions strictly from the knowledge base, cites sources, refuses when the answer is not in the KB. |
| Knowledge base | `app/knowledge_base/{loaders,chunking,embeddings,keywords,store,ingest}.py` | Arabic-aware loading, chunking, offline hashing or OpenAI-compatible embeddings, hybrid (vector + BM25) retrieval, ingestion CLI. |
| Ticket store | `app/services/ticket_store.py` | In-memory tickets, the seven documented statuses, a strict transition map, duplicate detection. |
| Other services | `app/services/{emergency_numbers,offline_llm,runtime}.py` | Official emergency numbers only, deterministic offline LLM fallback, runtime wiring. |
| API | `app/api/routes.py`, `app/main.py`, `app/core/config.py` | `POST /api/v1/chat`, `GET /api/v1/tickets`, `GET /api/v1/tickets/{id}`, `POST /api/v1/tickets/{id}/review`, `GET /api/v1/knowledge/status`, `GET /health`. CORS, sanitized 422 responses. |
| Data | `data/knowledge/*.md` (15 Arabic documents), `data/emergency_numbers.json` | Knowledge base content and official emergency numbers. |
| DB | `migrations/001_knowledge_base.sql` | pgvector schema for the knowledge base. |
| Normalizer | `app/utils/arabic_normalizer.py` | One shared Arabic normalization utility for both agents. |
| Tests | `tests/unit/complaint_agent/`, `tests/unit/rag_agent/`, `tests/unit/test_*.py`, `tests/integration/test_api_e2e.py`, `tests/golden/` | 233 passing tests, 38 complaint goldens, 36 RAG goldens. |

---

## 2. How to run

### fish

```fish
cd backend
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/unit/test_retrieval_golden.py -q -s
.venv/bin/ruff check .
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```

### bash

```bash
cd backend
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/unit/test_retrieval_golden.py -q -s
.venv/bin/ruff check .
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Port 8010 avoids the port 8000 process that another user already runs in this environment.
Copy `backend/.env.example` to `backend/.env` first (`.env` is git-ignored).

---

## 3. API contract

Base URL (local): `http://127.0.0.1:8010`. All requests `Content-Type: application/json`.
No auth yet. Every citizen-facing string is Arabic.

### `POST /api/v1/chat`

```json
{ "message": "ماسورة مياه مكسورة في شارع النيل", "session_id": "citizen-1", "user_id": null }
```

`message` 1–4000 characters, `session_id` 1–100 (default `demo-session`), `user_id` optional.

Complaint response:

```json
{
  "type": "complaint",
  "reply_ar": "ملخص الشكوى: ... هل تأكد إرسال الشكوى؟",
  "stage": "awaiting_confirmation",
  "ticket": null,
  "missing_fields": [],
  "requires_confirmation": true,
  "handoff_to": null,
  "sources": [],
  "found_in_kb": null,
  "review_notes": []
}
```

Stages: `collecting` → `awaiting_confirmation` → `submitted` (or `linked`), plus `handoff`
when a question is redirected to the RAG agent.

Confirmation: `{"message": "نعم أكد الإرسال", "session_id": "citizen-1"}` → ticket `Pending`.

RAG response:

```json
{
  "type": "rag",
  "reply_ar": "... المصدر: كيفية تقديم شكوى",
  "sources": [{ "title": "كيفية تقديم شكوى", "excerpt": "...", "page": null }],
  "found_in_kb": true
}
```

Out-of-scope question: `found_in_kb=false` and «المعلومات غير متوفرة في قاعدة المعرفة…».

### `GET /api/v1/tickets`

Returns an array of tickets. A ticket:

```json
{
  "ticket_id": "TKT-2026-0001",
  "title": "ماسورة مياه مكسورة",
  "description": "...",
  "category": "Water",
  "authority": "مديرية المياه",
  "location": { "governorate": "الجيزة", "city": "", "street": "النيل", "landmark": "" },
  "urgency": "high",
  "urgency_reason": "...",
  "incident_date": null,
  "attachments_mentioned": [],
  "contact_preference": null,
  "status": "Pending",
  "created_at": "2026-11-18T21:00:00+00:00",
  "updated_at": "2026-11-18T21:00:00+00:00",
  "linked_to": null
}
```

Internal `review_notes` are never returned to clients.

### `GET /api/v1/tickets/{ticket_id}`

200 with the ticket, or `404 {"detail": "Ticket not found"}`.

### `POST /api/v1/tickets/{ticket_id}/review`

```json
{ "status": "Approved", "reviewer_note": "تم التحقق من الموقع" }
```

`reviewer_note` optional, ≤ 500 characters.
200 returns the updated ticket. `404` unknown ticket.
`409` invalid transition: `{"detail": "انتقال حالة غير مسموح به: ..."}`.
`422` unknown status value.

### `GET /api/v1/knowledge/status`

```json
{ "documents": 15, "chunks": 136, "embedding_provider": "hashing", "embedding_dimension": 1024 }
```

### `GET /health`

```json
{ "status": "ok", "env": "dev" }
```

---

## 4. Ticket statuses and transitions

Statuses (exact, case-sensitive): `Pending`, `Approved`, `In Progress`, `Verifying`, `Done`,
`Declined`, `Dismissed`.

```text
Pending      -> Approved | Dismissed | Declined
Approved     -> In Progress | Dismissed | Declined
In Progress  -> Verifying | Dismissed | Declined
Verifying    -> Done | In Progress | Dismissed | Declined
Done         -> (terminal)
Declined     -> (terminal)
Dismissed    -> (terminal)
```

Duplicate candidates are only open tickets (`Pending`, `Approved`, `In Progress`, `Verifying`).
`Verifying -> In Progress` exists so rejected proof can return to the maintenance team
(ADM-13, MNT-05).

---

## 5. Environment variable names (names only — never commit values)

```text
APP_ENV
DATABASE_URL
STORAGE_BACKEND
STORAGE_LOCAL_PATH
LLM_API_KEY
LLM_TIMEOUT_SECONDS
LLM_PROVIDER
LLM_MODEL
LLM_BASE_URL
EMBEDDING_PROVIDER
EMBEDDING_MODEL
EMBEDDING_BASE_URL
EMBEDDING_API_KEY
EMBEDDING_DIMENSION
EMBEDDING_TIMEOUT_SECONDS
RAG_TOP_K
RAG_SIMILARITY_THRESHOLD
COMPLAINT_MAX_TURNS
COMPLAINT_MIN_CONFIDENCE
KNOWLEDGE_DIR
CORS_ORIGINS
DUPLICATE_SIMILARITY_THRESHOLD
```

---

## 6. Ingest / refresh the knowledge base

```bash
cd backend

# load + chunk only, no embeddings (fast sanity check)
.venv/bin/python -m app.knowledge_base.ingest --path data/knowledge --dry-run --json

# build the in-memory index (default, offline hashing embeddings)
.venv/bin/python -m app.knowledge_base.ingest --path data/knowledge --backend memory

# target pgvector after the migration is applied and DATABASE_URL is set
.venv/bin/python -m app.knowledge_base.ingest --path data/knowledge --backend pgvector
```

`GET /api/v1/knowledge/status` shows `documents` and `chunks` after ingestion.

---

## 7. Wiring checklist before production (owner: team leader)

- [ ] Replace the in-memory `InMemoryTicketStore` with the real `TicketService`/database
      repository. Keep `TICKET_STATUSES`, `OPEN_STATUSES` and `ALLOWED_TRANSITIONS` as the single
      source of truth so the API, agents and DB agree.
- [ ] Apply `backend/migrations/001_knowledge_base.sql` to Supabase (enables pgvector; the
      `EMBEDDING_DIMENSION` must match the column).
- [ ] Configure a real LLM (`LLM_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`) and a real
      embedding provider (`EMBEDDING_PROVIDER=openai_compatible`, `EMBEDDING_MODEL`,
      `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_DIMENSION`).
      Re-measure the RAG goldens after switching: the reported metrics are for the offline
      hashing baseline.
- [ ] Set `CORS_ORIGINS` to the real frontend origin(s), not just the Vite defaults.
- [ ] Verify every number in `backend/data/emergency_numbers.json` against official Egyptian
      government sources before showing it to citizens.
- [ ] Wire the orchestrator: `app/agents/orchestrator/orchestrator.py::send_to_complaint_agent`
      is still a placeholder that returns a hardcoded `severity="Critical"` and
      `recommendations=["Immediate repair required within 24h"]`. It must call the real agent or
      drop the invented values.
- [ ] Decide the single ingestion entry point: `app/knowledge_base/ingest.py` (working) versus the
      empty `app/knowledge_base/ingestion/` package on `main`.
- [ ] Add authentication before exposing the API publicly (today every endpoint is anonymous).

---

## 8. Known limitations

1. Default embeddings are the offline `hashing` baseline, not a semantic model.
2. Live NVIDIA NIM tests are skipped without `LLM_API_KEY`.
3. Franco-Arabic and English-only text needs the LLM extractor; the rule-based path asks a
   follow-up question.
4. Tickets are in memory and disappear on restart.
5. The pgvector path was not executed here (no `psycopg`); it is reviewed and unit-tested in memory.
6. No structured complaint form endpoint and no standalone ticket-tracking endpoint yet.

---

## 9. Frontend note (not part of this PR)

The real frontend is not on `main`. It lives on `origin/mustafa-integration` (`c7a9240`), which
also rewrites the backend (auth, SQLAlchemy models, Alembic, routers) and deletes complaint-agent
files that `main` added later. That frontend calls `http://127.0.0.1:8000/api/v1` through
`VITE_API_URL`, sends `Authorization: Bearer <token>` with refresh handling, and expects auth,
users, admin, maintenance, notifications and storage endpoints.

Integrating that frontend with this API is the team leader's decision and is deliberately
excluded from this branch and pull request.

---

## 10. ملخص عربي قصير

- الفرع `feature/arabic-complaint-and-rag-agents` يحتوي **الـ backend فقط**: وكيل محادثة الشكاوى،
  وكيل RAG، قاعدة المعرفة العربية، مخزن التذاكر بالحالات السبع، وواجهة API.
- التشغيل: `cd backend` ثم `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010`.
- الاختبارات: `.venv/bin/python -m pytest -q` → **233 passed / 4 skipped**، و`ruff` نظيف.
- لا تُنشأ تذكرة قبل تأكيد المواطن، والردود عربية، والأرقام الطارئة من الملف الرسمي فقط،
  والبيانات الشخصية تُقنَّع (`[PHONE]`, `[ID]`).
- **قبل الدمج:** استبدال المخزن المؤقت بقاعدة بيانات حقيقية، تطبيق ترحيل pgvector على Supabase،
  ضبط مزوّد LLM/embeddings حقيقي، ضبط `CORS_ORIGINS`، والتحقق الرسمي من أرقام الطوارئ.
- **الواجهة الأمامية غير مشمولة في هذا الفرع**؛ مصدرها `origin/mustafa-integration` وقرار
  الربط للقائد.
