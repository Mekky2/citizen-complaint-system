# Handoff — merged Arabic agents on the teammate's backend

Branch: `feature/enhanced-agents`, based on `origin/main` (`9e57a67`, PR #8 "complaint agent").
Scope: **backend only**. Nothing was pushed and no PR was opened.

This branch keeps the teammate's structured complaint agent, rules, schemas and orchestrator
graph, and adds the citizen-facing conversation agent, the RAG agent, the knowledge base,
resilience (one LLM gateway) and concurrency-safe API wiring on top of them.

---

## 1. Architecture (one system)

```text
Citizen (Arabic)
      |
      |  POST /api/v1/chat  {message, session_id, user_id?}
      v
+----------------------------- app/api/routes.py -----------------------------+
| 1. per-client sliding window  -> 429 + Retry-After (Arabic)                 |
| 2. bounded in-flight gate     -> 503 + Retry-After (Arabic)                 |
| 3. asyncio.to_thread(runtime.chat)          (no blocking of the event loop) |
+------------------------------------+----------------------------------------+
                                     |
                          runtime.chat (one lock per session)
                                     |
          +--------------------------+---------------------------+
          |                                                      |
  complaint intent / active session                    question / greeting / emergency
          |                                                      |
          v                                                      v
  ComplaintSession (conversation.py)                       RAGAgent
  - rules first, LLM when available                        - normalize query
  - asks short Arabic questions                            - hybrid BM25 + vector search
  - summary -> explicit confirmation                       - grounded Arabic answer + source
  - ticket only after confirmation                         - "not in KB" when unsupported
          |                                                      |
          +--------------------------+---------------------------+
                                     |
                              LLMGateway (the only LLM entry point)
                              - provider chain (primary -> secondary -> offline)
                              - multi-key rotation + circuit breaker + Retry-After
                              - retries with backoff, budgets, concurrency limit
                              - offline Arabic fallback, never raises
                                     |
          +--------------------------+---------------------------+
          |                                                      |
  InMemoryKnowledgeBase (15 docs / 136 chunks)           InMemoryTicketStore
  - one Arabic normalizer                                - 7 statuses + transition map
  - cache invalidated on re-ingest                       - duplicate detection
                                                         - idempotent create
```

Structured analysis of a submitted ticket (called by the orchestrator graph, not by `/chat`):

```text
orchestrator.send_to_complaint_agent
   -> strips national_id
   -> run_complaint_agent(state, LLMGateway, KnowledgeBaseRetriever)
        categorize -> severity -> retrieve (hybrid) -> recommendations -> verify
   -> {severity, category, recommendations with [Source: ...], status="ComplaintAnalyzed"}
```

---

## 2. What changed relative to the teammate's `main`

| File | Change | Why |
|---|---|---|
| `app/agents/orchestrator/orchestrator.py` | body of `send_to_complaint_agent` replaced; optional keyword-only `llm`/`rag` added | remove the hardcoded `Critical` / `"Immediate repair required within 24h"`; call the real agent |
| `app/agents/orchestrator/middleware.py` | `validate_ticket` requires only description + authority; identity fields optional; never mutates | the citizen agent does not collect a national ID; the old assertion `result == state` still passes |
| `app/agents/orchestrator/rag_adapter.py` | **new** `KnowledgeBaseRetriever` | implements the teammate's `RagRetriever` contract over the hybrid KB |
| `app/agents/complaint_agent/nim_client.py` | `LLMProviderError.retry_after_seconds` (optional); `_retry_after` parses the header; `_wrap` passes it | let the gateway honour `Retry-After`; backwards compatible |
| `app/agents/complaint_agent/conversation.py` | `_submit` passes `idempotency_key=session_id:draft-fingerprint`; `hashlib` import | a retry or double confirmation cannot create a second ticket |
| `app/services/ticket_store.py` | `TicketRepository` protocol, idempotency map, locked reads, `clear()` resets the map | storage seam + idempotency without changing statuses/transitions |
| `app/knowledge_base/store.py` | `version` counter bumped on document change | answer-cache invalidation after re-ingestion |
| `app/knowledge_base/ingestion/__init__.py` | was empty; now a delegating shim to `app/knowledge_base/ingest.py` | one ingestion entry point |
| `app/services/llm_gateway.py` | **new** | provider chain, rotation, retries, circuits, budgets, offline fallback |
| `app/services/offline_llm.py` | `OfflineToolLLM` added (`GroundedTemplateLLM` kept) | answer the teammate's JSON tool prompts offline |
| `app/services/session_store.py`, `answer_cache.py`, `rate_limit.py`, `observability.py` | **new** | TTL sessions, cache, admission control, metadata-only traces |
| `app/services/runtime.py`, `app/api/routes.py`, `app/main.py` | rewritten | wire the above; async endpoints; `/ready`, `/api/v1/admin/status`, Arabic 503 handler |
| `app/core/config.py`, `.env.example` | new setting **names** only | gateway/session/cache/limit knobs |

### Deliberately unchanged

`agent.py`, `tools.py`, `rules.py`, `schemas.py`, `prompts.py`, `interfaces.py`, `graph.py`,
`route_department`, the seven ticket statuses and the transition map, the knowledge documents,
the golden files, and every existing test. The public names and signatures the teammate exposed
are still there.

---

## 3. How to run

### bash

```bash
cd backend
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
cp .env.example .env          # then fill values locally; never commit .env
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```

### fish

```fish
cd backend
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
cp .env.example .env
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```

One worker only for now (see section 10). Without keys the service runs in offline mode and
still answers in Arabic; every such answer has `"degraded": true`.

---

## 4. API contract

Base URL: `http://127.0.0.1:8010`. JSON only. No auth yet.

### `POST /api/v1/chat`

```json
{ "message": "ماسورة مياه مكسورة في شارع النيل", "session_id": "citizen-1", "user_id": null }
```

`message` 1–4000 chars, `session_id` 1–100 (default `demo-session`), `user_id` optional
(opaque; used for per-user budgets and rate limiting).

Complaint response:

```json
{
  "type": "complaint",
  "session_id": "citizen-1",
  "reply_ar": "ملخص الشكوى: ... هل تأكد إرسال الشكوى؟",
  "stage": "awaiting_confirmation",
  "ticket": null,
  "missing_fields": [],
  "requires_confirmation": true,
  "handoff_to": null,
  "sources": [],
  "confidence": null,
  "found_in_kb": null,
  "review_notes": [],
  "degraded": false,
  "request_id": "9f2c…"
}
```

RAG response:

```json
{
  "type": "rag",
  "reply_ar": "... المصدر: كيفية تقديم شكوى",
  "sources": [{ "title": "كيفية تقديم شكوى", "excerpt": "...", "page": null }],
  "found_in_kb": true,
  "degraded": true,
  "request_id": "9f2c…"
}
```

`degraded` means *this answer used the offline fallback*, not "the service is down". A
confirmation turn that only writes a ticket has no model call and is reported `degraded:false`
even while the provider is down.

Errors: `429` (per-client limit, `Retry-After`) and `503` (overloaded, `Retry-After`) both
return `{"detail": "<Arabic message>"}`. Unhandled errors become the same Arabic `503`; the
API never returns a `500` or a stack trace.

### Ticket endpoints

`GET /api/v1/tickets`, `GET /api/v1/tickets/{id}`, `POST /api/v1/tickets/{id}/review`

```json
{ "status": "Approved", "reviewer_note": "تم التحقق من الموقع" }
```

`404` unknown ticket, `409` invalid transition (Arabic message), `422` unknown status value.
Internal `review_notes` are never returned.

### System endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness; does not touch providers (`{"status":"ok","env":"dev"}`) |
| `GET /ready` | knowledge loaded + offline fallback wired; `503` only if the KB is empty. Reports `paid_provider_available`; a missing provider is **not** fatal |
| `GET /api/v1/knowledge/status` | documents, chunks, embedding provider, KB version, ingest counters |
| `GET /api/v1/admin/status` | provider/key counters, budget usage, sessions, cache, limiter, gate, ticket count. **No keys, prompts or complaint text** |

---

## 5. Tickets: statuses, repository, idempotency

Statuses (exact, case-sensitive): `Pending`, `Approved`, `In Progress`, `Verifying`, `Done`,
`Declined`, `Dismissed`.

```text
Pending      -> Approved | Dismissed | Declined
Approved     -> In Progress | Dismissed | Declined
In Progress  -> Verifying | Dismissed | Declined
Verifying    -> Done | In Progress | Dismissed | Declined
Done / Declined / Dismissed -> terminal
```

`TicketRepository` is the seam for a database implementation: `create`, `get`, `list`,
`update_status`, `find_similar`. `InMemoryTicketStore` implements it. `create(...)` accepts
`idempotency_key`; the conversation layer passes `"<session_id>:<draft fingerprint>"`, so:

* a client retry of the confirmation returns the existing ticket;
* the same draft confirmed twice in parallel returns one ticket (tested with two threads).

A Postgres/Supabase repository must enforce the same key with a **unique index**, because the
in-memory map is per process.

---

## 6. LLM gateway

`LLMGateway.complete(system, user, *, user_id=None) -> str` is the only LLM entry point. It
never raises; a failure degrades to the offline answer.

| Behaviour | Default |
|---|---|
| Provider chain | primary (Mistral on NVIDIA NIM) → optional secondary OpenAI-compatible → offline |
| Keys | `LLM_API_KEY` + `LLM_API_KEYS` (comma-separated), round-robin |
| Retries | `LLM_MAX_ATTEMPTS=3`, exponential backoff `0.25 s` → `3 s` with jitter, honours `Retry-After` |
| Circuit breaker | per key, opens after `3` failures for `30 s`, then one half-open probe |
| Auth failure (401/403) | key cooled down for `300 s` instead of retrying |
| 429 without `Retry-After` | cooled down for `LLM_RETRY_AFTER_DEFAULT_SECONDS=5` |
| Budgets | global `2,000,000` tokens / `20,000` requests per UTC day; per user `50,000` / `500` |
| Concurrency | `8` simultaneous provider calls; `5 s` wait, then offline |
| Prompt size | `LLM_MAX_INPUT_TOKENS=6000` (estimated), trims the middle of long prompts |
| Offline | `LLM_OFFLINE_FALLBACK=true`; deterministic Arabic rules/templates |

### Add a key or a provider

1. Put additional keys for the same provider in `LLM_API_KEYS` (comma-separated). No restart
   logic is needed beyond a restart of the process; rotation happens on the next call.
2. For a second provider set `LLM_SECONDARY_MODEL`, `LLM_SECONDARY_BASE_URL`,
   `LLM_SECONDARY_API_KEYS` (and optionally `LLM_SECONDARY_NAME`,
   `LLM_SECONDARY_TIMEOUT_SECONDS`). Any OpenAI-compatible `/chat/completions` endpoint works.
3. Never put a value in `.env.example`, a commit, a log or a chat. `.env` is git-ignored.

### Degradation

`complete` returns the offline answer and the request trace is marked with a stable reason
(`no_provider_configured`, `all_keys_cooling`, `provider_error`, `budget_exceeded`,
`concurrency_limit`, `offline_fallback`). The API exposes the flag as `degraded`.
`/ready` exposes `paid_provider_available`; `/api/v1/admin/status` exposes per-key
`keys_total/available/open/half_open`.

---

## 7. Orchestrator wiring

`send_to_complaint_agent(state, *, llm=None, rag=None)`:

* strips `national_id` from `payload.citizen` before anything else;
* uses the injected `llm`/`rag` when given (tests), otherwise the runtime gateway/retriever;
* returns `status="ComplaintAnalyzed"` with `severity`, `category`, `recommendations`,
  `rag_context`, `review_notes`, or `status="ComplaintFailed"` with an error code — it does not
  raise, so the graph can continue;
* adds `category`, `rag_context` and `review_notes` keys; callers that only read `severity`
  and `recommendations` are unaffected.

`validate_ticket` checks description and authority; identity data is optional and validated
only when present. It never mutates or copies the state.

No duration, fee, law or phone number is generated by any agent. Recommendations quote the
retrieved document and include `[Source: <title>]`; numbers come only from
`data/emergency_numbers.json` (still pending official verification).

---

## 8. Knowledge ingestion — one entry point

```bash
cd backend

# sanity check (load + chunk, no embeddings)
.venv/bin/python -m app.knowledge_base.ingest --path data/knowledge --dry-run --json

# in-memory index (offline hashing embeddings)
.venv/bin/python -m app.knowledge_base.ingest --path data/knowledge --backend memory

# pgvector after the migration
.venv/bin/python -m app.knowledge_base.ingest --path data/knowledge --backend pgvector
```

`app/knowledge_base/ingestion/` now forwards to the same functions, so both module paths work.
Re-ingestion bumps `InMemoryKnowledgeBase.version`, which invalidates the answer cache.

---

## 9. Environment variable names (names only — never commit values)

Existing: `APP_ENV`, `DATABASE_URL`, `STORAGE_BACKEND`, `STORAGE_LOCAL_PATH`, `LLM_API_KEY`,
`LLM_TIMEOUT_SECONDS`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `EMBEDDING_PROVIDER`,
`EMBEDDING_MODEL`, `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_DIMENSION`,
`EMBEDDING_TIMEOUT_SECONDS`, `RAG_TOP_K`, `RAG_SIMILARITY_THRESHOLD`, `COMPLAINT_MAX_TURNS`,
`COMPLAINT_MIN_CONFIDENCE`, `KNOWLEDGE_DIR`, `CORS_ORIGINS`,
`DUPLICATE_SIMILARITY_THRESHOLD`.

Added by this branch:

```text
LLM_API_KEYS
LLM_SECONDARY_NAME
LLM_SECONDARY_MODEL
LLM_SECONDARY_BASE_URL
LLM_SECONDARY_API_KEYS
LLM_SECONDARY_TIMEOUT_SECONDS
LLM_MAX_TOKENS
LLM_MAX_INPUT_TOKENS
LLM_MAX_CALL_SECONDS
LLM_MAX_ATTEMPTS
LLM_BACKOFF_BASE_SECONDS
LLM_BACKOFF_MAX_SECONDS
LLM_RETRY_AFTER_DEFAULT_SECONDS
LLM_CIRCUIT_FAILURE_THRESHOLD
LLM_CIRCUIT_OPEN_SECONDS
LLM_AUTH_COOLDOWN_SECONDS
LLM_OFFLINE_FALLBACK
LLM_GLOBAL_DAILY_TOKEN_BUDGET
LLM_USER_DAILY_TOKEN_BUDGET
LLM_GLOBAL_DAILY_REQUEST_BUDGET
LLM_USER_DAILY_REQUEST_BUDGET
LLM_MAX_CONCURRENT_CALLS
LLM_QUEUE_TIMEOUT_SECONDS
RAG_CACHE_TTL_SECONDS
RAG_CACHE_MAX_ENTRIES
SESSION_TTL_SECONDS
SESSION_MAX_ENTRIES
SESSION_MAX_HISTORY_MESSAGES
API_MAX_CONCURRENT_REQUESTS
API_QUEUE_TIMEOUT_SECONDS
RATE_LIMIT_PER_MINUTE
RATE_LIMIT_BURST
```

---

## 10. Scaling: before you add workers

Today these are in-process and **not shared**:

| Component | Single-process behaviour | Needed for `--workers N` |
|---|---|---|
| `InMemorySessionStore` | one lock per session, TTL 30 min, 5000 entries | Redis (hash + TTL) or DB row with a row lock |
| `AnswerCache` | 300 s TTL, 500 entries, invalidated by KB version | Redis with a namespace per KB version |
| `SlidingWindowLimiter` / `ConcurrencyGate` | per process | Redis counters / gateway-level limits |
| `InMemoryTicketStore` | per process, idempotency map | `TicketRepository` over Postgres with a unique idempotency index |

With N workers today, limits multiply by N and sessions/tickets are not visible across workers.
Keep one worker, or move the four components before scaling out. The repository protocols and
the `SessionStore` protocol are already the seams; the agents and routes do not need changes.

Also note: budgets are per process and reset at UTC midnight; token counts are estimates
(`characters/3`, closer for Arabic) because no provider tokenizer is used.

---

## 11. Production checklist (owner: team leader)

- [ ] Verify every number in `data/emergency_numbers.json` officially before citizens see it.
- [ ] Verify the response durations and any procedural claims in `data/knowledge/*.md`.
- [ ] Apply `migrations/001_knowledge_base.sql` to Supabase; keep `EMBEDDING_DIMENSION` in sync.
- [ ] Configure a real LLM (`LLM_API_KEY`/`LLM_API_KEYS`, provider, model, base URL) and a real
      embedding provider; re-measure the RAG goldens afterwards.
- [ ] Set `CORS_ORIGINS` to the real frontend origin(s).
- [ ] Add authentication/authorisation before exposing the API publicly.
- [ ] Add alerting on `/ready` (`paid_provider_available=false`), on `degraded` rate and on
      `admin/status` key counters.
- [ ] Move sessions/cache/limits/tickets to shared storage before running multiple workers.
- [ ] Revoke the personal access token embedded in the local git remote URL and use a
      credential helper.

---

## 12. Known limitations

1. The paid provider was not available in this environment; live tests that call NVIDIA NIM
   remain skipped. Normal-mode metrics use a deterministic provider stand-in.
2. Offline `hashing` embeddings are a baseline; semantic quality needs a real model.
3. The answer cache only stores non-degraded answers (by design), so it stays empty while the
   provider is down.
4. Abuse detection is phrase-based; an unlisted insult wording gets the normal follow-up
   question instead of the polite refusal (still no ticket, no crash).
5. Tickets are in memory and disappear on restart.
6. The pgvector path was reviewed but not executed here (no `psycopg`).
7. No structured complaint-form endpoint, no standalone ticket-tracking endpoint, no auth yet.

---

## 13. ملخص عربي

- الفرع `feature/enhanced-agents` يدمج وكيل المحادثة العربية ووكيل RAG داخل backend الفريق
  (المصنّف، قواعد الشدة، المخطط، والـ orchestrator كما هي) في نظام واحد.
- كل نداءات النماذج تمر عبر بوابة واحدة: سلسلة مزوّدين، مفاتيح متعددة بالتناوب، إعادة محاولة
  مع احترام `Retry-After`، قاطع دائرة لكل مفتاح، ميزانيات يومية، وحد تزامن، وبديل عربي يعمل
  بدون إنترنت. البوابة لا ترفع استثناءً أبدًا، والرد يُعلَّم بـ `degraded: true` عند استخدام
  البديل.
- `send_to_complaint_agent` لم يعد يعيد قيمًا ثابتة: يستدعي الوكيل الحقيقي، ويحذف رقم الهوية
  قبل التحليل، والتوصيات مقتبسة من المستند مع `[Source: …]` دون اختراع مبالغ أو مدد أو قوانين.
- الجلسات معزولة بقفل لكل جلسة، وتأكيد الشكوى مرتين لا ينشئ إلا تذكرة واحدة (مفتاح تكرار)،
  والحدود تعيد `429/503` برسالة عربية و`Retry-After` بدل الانهيار. `/ready` و
  `/api/v1/admin/status` يعرضان الحالة دون أي مفاتيح أو نصوص شكاوى.
- التشغيل: `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010`، والاختبارات
  `.venv/bin/python -m pytest -q` → **277 passed / 4 skipped**، و`ruff` نظيف.
- **قبل الدمج:** التحقق الرسمي من أرقام الطوارئ والمدد، ضبط مزوّد LLM/embeddings حقيقي،
  تطبيق ترحيل pgvector، ضبط `CORS_ORIGINS`، إضافة المصادقة، ونقل الجلسات/الكاش/الحدود/التذاكر
  إلى تخزين مشترك قبل تشغيل أكثر من عامل. الواجهة الأمامية غير مشمولة.
