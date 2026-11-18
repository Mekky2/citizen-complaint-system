# Test report — Arabic complaint agent and RAG agent

**Date:** 2026-11-18
**Branch:** `feature/arabic-complaint-and-rag-agents` (based on `origin/main` = `9e57a67`)
**Scope:** backend only — complaint conversation agent, RAG agent, knowledge base, API layer,
ticket store, tests, migrations, knowledge documents.
**Frontend:** not part of this branch or PR. See section 9.
**Every result below comes from an actual command run on this branch.**

---

## 1. Summary

| Item | Result |
|---|---|
| Backend test suite | **233 passed, 4 skipped, 0 failed** |
| Repeat run (flakiness check) | **identical result** |
| `ruff check .` | **All checks passed** |
| RAG golden metrics | `hit@1 88.9%`, `hit@3 100%`, `recall@5 100%`, `MRR 0.944` |
| Live API checks on port 8010 | all PASS (table in section 4) |
| Edge cases (4xx) | clean 422/404/409, **zero 500s**, zero tracebacks |
| PII in logs | only `[PHONE]` / `[ID]` in replies; nothing in the server log |
| Secrets | no real secret; one pre-existing placeholder flagged (section 6) |

---

## 2. Environment

| Component | Version |
|---|---|
| Python | 3.14.10 |
| pytest | 9.2.0 |
| ruff | 0.17.5 |
| FastAPI | 0.165.0 |
| httpx | 0.28.1 |
| Node.js (for reference only) | v26.11.1 |

Commands:

```bash
cd backend
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

Third-party note: 17 `DeprecationWarning`s come from `langsmith` (`asyncio.iscoroutinefunction`),
not from this code.

---

## 3. Test runs

```text
=== RUN 1 ===
233 passed, 4 skipped, 17 warnings in 24.11s

=== RUN 2 ===
233 passed, 4 skipped, 17 warnings in 11.98s
```

Per suite:

```text
tests/unit/complaint_agent   174 passed, 1 skipped
tests/unit/rag_agent          10 passed
tests/integration             15 passed, 3 skipped
tests/unit                   218 passed, 1 skipped
```

Skipped tests:

| Test | Reason |
|---|---|
| `tests/integration/test_nim_live.py` (3 cases) | `LLM_API_KEY` is not configured; these call the real NVIDIA NIM API |
| `tests/unit/agent_eval/test_complaint_golden.py` (1 case) | Franco-Arabic needs the LLM extractor; covered by a fake-LLM test |

`ruff check .`:

```text
All checks passed!
```

New in this branch: `tests/unit/complaint_agent/test_ticket_store.py` — 8 tests covering
duplicate detection (exact, filler prefix, other category, closed ticket, single shared word,
configurable threshold, scoring helper, documented default).

---

## 4. Live API checks (uvicorn on 127.0.0.1:8010 + curl)

Start:

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```

| # | Test | Expected | Actual | Result |
|---|---|---|---|---|
| a | `GET /health` | `ok` | `{"status":"ok","env":"dev"}` | PASS |
| b | `GET /api/v1/knowledge/status` | 15 documents | `documents=15, chunks=136, provider=hashing` | PASS |
| c | Arabic RAG question «كيف أقدم شكوى؟» | Arabic answer with cited source | `type=rag, found_in_kb=true, sources=['كيفية تقديم شكوى']`, reply cites «المصدر» | PASS |
| d | Out-of-scope «كم رسوم استخراج رخصة القيادة؟» | not in KB, Arabic refusal | `found_in_kb=false`, `NO_LEXICAL_SUPPORT`, «المعلومات غير متوفرة…» | PASS |
| e | Vague complaint «في مشكلة» | follow-up, no ticket | `stage=collecting`, missing `category, location`, `ticket=null` | PASS |
| f | Details message | summary, no ticket yet | `stage=awaiting_confirmation`, `requires_confirmation=true`, `ticket=null` | PASS |
| g | `GET /api/v1/tickets` before confirmation | empty list | `[]` | PASS |
| h | Confirmation «نعم أكد الإرسال» | ticket created as `Pending` | `TKT-2026-0001`, `status=Pending`, `category=Water`, `authority=مديرية المياه` | PASS |
| i | `GET /api/v1/tickets/{id}` | ticket, no internal notes | 200, `review_notes` absent | PASS |
| j | Lifecycle `Pending→Approved→In Progress→Verifying→Done` | four 200s | four 200s, correct status each time | PASS |
| k | Transition from terminal `Done→In Progress` | 409 Arabic | `409 {"detail":"انتقال حالة غير مسموح به: cannot move ticket from 'Done' to 'In Progress'"}` | PASS |
| l | Unknown ticket ID | 404 | `{"detail":"Ticket not found"}` | PASS |
| m | Review on unknown ticket | 404 | 404 | PASS |
| n | Unknown status value | 422 | `literal_error` listing the seven statuses | PASS |
| o | Greeting «السلام عليكم» | Arabic reply, no ticket | `stage=handoff`, `handoff_to=complaint`, ticket count unchanged | PASS |
| p | Abuse «أنت غبي» | polite Arabic refusal, no ticket | `ABUSIVE_LANGUAGE`, no ticket | PASS |
| q | Prompt injection | instruction ignored | `PROMPT_INJECTION_IGNORED`, no ticket | PASS |
| r | Emergency «سلك كهرباء مكشوف» | official numbers only | `EMERGENCY_DETECTED`, all 7 numbers from `data/emergency_numbers.json`, 0 unofficial | PASS |
| s | Duplicate complaint (open ticket) | Arabic link offer | «توجد شكوى مشابهة مفتوحة برقم TKT-2026-0001 (نسبة التشابه 100%)» | PASS |
| t | Same complaint after the ticket reached `Done` | no link offer | no warning (terminal tickets excluded) | PASS |
| u | CORS preflight `http://127.0.0.1:5173` | allowed | `200`, `access-control-allow-origin: http://127.0.0.1:5173` | PASS |
| v | CORS preflight `http://localhost:5173` | allowed | `200`, matching header | PASS |
| w | CORS preflight `http://evil.example` | rejected | `400` | PASS |

---

## 5. Edge cases (real API)

| Input | HTTP | Body | Result |
|---|---|---|---|
| empty message | 422 | `string_too_short` | PASS |
| 5,000 characters | 422 | `string_too_long`, **text not echoed back** | PASS |
| invalid JSON | 422 | `json_invalid` | PASS |
| missing `message` | 422 | `missing` | PASS |
| English only | 200 | Arabic «المعلومات غير متوفرة…» | PASS (no KB answer) |
| Franco-Arabic `el share3 fih 7ofar` | 200 | Arabic follow-up question | PASS (no crash) |
| Arabic-Indic digits `١٢٣` | 200 | correct Arabic summary | PASS |
| Mixed `عندي water leak في street النيل` | 200 | `Water` + street `النيل` + confirmation | PASS |

Server log after all of the above: **0 occurrences of `" 500 ` and 0 `Traceback`.**

PII check — message contains `01123456789` and `29912345678901`:

```text
phone plaintext in reply? False
id plaintext in reply? False
masked phone present? True   ([PHONE])
masked id present? True      ([ID])
grep for both numbers in uvicorn log -> no match
```

---

## 6. Duplicate detection

`InMemoryTicketStore.find_similar` compares **normalized Arabic tokens**
(`tokenize_for_search` + filler removal: `مشكله, شكوى, شكوه, بلاغ, ابلاغ, مشاكل, موضوع, بخصوص`)
and scores with the **better of Jaccard and the overlap (containment) coefficient**.
A match also requires at least 2 shared problem tokens, the same category, an open status
(`Pending`, `Approved`, `In Progress`, `Verifying`) and a nearby location.
Threshold: `DUPLICATE_SIMILARITY_THRESHOLD` (default `0.45`).

Live proof: an identical complaint scored `0.8333` (Jaccard) and was still offered for
linking because the overlap coefficient reached `1.0`; the same complaint was **not** offered
once the ticket became `Done`.

Note on an earlier false alarm: duplicate detection had not failed before. In the earlier
manual run the ticket had already been moved to `Done`, and terminal tickets are deliberately
excluded from duplicate candidates.

---

## 7. RAG metrics

15 Arabic documents, 136 chunks, 36 golden questions, deterministic `hashing` embedder:

```text
hit@1=32/36 (88.9%)  hit@3=36/36 (100.0%)  recall@5=100.0%  MRR=0.944
```

This is an offline baseline, not the quality of a semantic model. Re-measure after switching
to `openai_compatible` embeddings.

---

## 8. How this coexists with the rest of `main`

| Area | Finding |
|---|---|
| `app/api/routes.py` | Did not exist on `main`; this branch adds it. No duplicate routes. |
| `complaint_agent` | `main` exports `run_complaint_agent(state, llm, rag)` (PR #8). This branch adds `handle_message` / `new_session` in `conversation.py`. No name collisions. |
| `orchestrator` | `send_to_complaint_agent` is still a placeholder: it does not call any agent and returns a hardcoded `severity="Critical"` and `recommendations=["Immediate repair required within 24h"]`. Must be wired or stripped — it conflicts with the "never invent durations" rule. |
| Ticket persistence | `main` has no `TicketService` and no DB layer. `ticket_store.py` (in-memory) is the only source of ticket state. |
| `core/config.py` | Added `embedding_*`, `rag_*`, `complaint_*`, `cors_*`, `duplicate_*`. No duplicated keys (checked). |
| Knowledge base | `main` has an empty `knowledge_base/ingestion/__init__.py`; the working pipeline is `knowledge_base/ingest.py`. Naming overlap only. |
| Teammate tests | `test_agent.py`, `test_orchestrator.py`, `test_grounding.py`, `test_rules.py`, `test_severity_and_review.py`, `test_nim_client.py` all pass unchanged. |

---

## 9. Frontend status (not part of this PR)

The real frontend is **not on `main`**. It lives on `origin/mustafa-integration`
(commit `c7a9240`, 2026-11-09), which also rewrites the backend (auth, SQLAlchemy models,
Alembic, routers) and deletes complaint-agent files that `main` added later.
That branch's frontend calls `http://127.0.0.1:8000/api/v1` with `VITE_API_URL`, sends
`Authorization: Bearer <token>` with refresh handling, and expects a much larger API surface
(auth, users, admin, maintenance, notifications, storage).
Frontend/backend integration is therefore **the team leader's decision** and is excluded from
this branch.

---

## 10. Security notes

- Secret scan over all changed/new files (`sk-`, `nvapi-`, `github_pat_`, `ghp_`,
  `API_KEY=<value>`, `password=`, `Bearer <token>`): **no real secret**.
  The only hit is the pre-existing placeholder value for `LLM_API_KEY` in `.env.example`
  (inherited from `main`).
- The local git remote URL embeds a personal access token. It is not tracked and is not part of
  this branch, but it should be revoked and replaced with a credential helper.
- `.env`, `.venv`, `node_modules`, `frontend/`, `zz*.txt` are not in the diff.

---

## 11. Known limitations

1. `hashing` embeddings are an offline baseline; semantic quality needs a real provider.
2. Live NVIDIA NIM tests are skipped without `LLM_API_KEY`.
3. Franco-Arabic and full English extraction need the LLM; the rule-based extractor asks a
   follow-up question or answers "not in the knowledge base".
4. Tickets live in memory: they disappear when the server restarts.
5. The PostgreSQL/pgvector path was not executed here (no `psycopg` installed); the migration
   was reviewed and the store is unit-tested in memory.
6. No structured complaint form endpoint and no standalone tracking endpoint yet.
7. Emergency numbers and the response durations in the Arabic knowledge documents still need
   official government confirmation.

---

## 12. Re-run commands

```bash
cd backend

.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q                      # flakiness check
.venv/bin/python -m pytest tests/unit/test_retrieval_golden.py -q -s
.venv/bin/ruff check .

.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
curl -sS http://127.0.0.1:8010/api/v1/knowledge/status
curl -sS -X POST http://127.0.0.1:8010/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"حفرة في شارع النيل","session_id":"rerun-1"}'
curl -i -X OPTIONS http://127.0.0.1:8010/api/v1/chat \
  -H "Origin: http://127.0.0.1:5173" \
  -H "Access-Control-Request-Method: POST"
```
