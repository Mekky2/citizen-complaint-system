# Complaint Agent

Entry point: `run_complaint_agent(state: dict, llm: LLMClient, rag: RagRetriever) -> dict` (never raises).

```
state ─► categorize ─► classify_severity ─► rag.retrieve ─► generate_recommendations ─► verify_support
 (LLM)       (LLM)        (teammate)               (LLM)                 (LLM)
   └───────────── any ToolError ──────────► Failed payload (partial category/severity kept)
```
Happy path = **5 tool calls** (docs say 4; the 5th is the grounding verification). If RAG returns nothing,
steps 4-5 are skipped (3 calls). All calls are counted into `tool_calls`; limits/retries/timeouts stay with the Orchestrator.

| File | Role |
|---|---|
| `schemas.py` | Taxonomy, input/success/failure Pydantic models |
| `interfaces.py` | `LLMClient` and `RagRetriever` protocols (the two seams) |
| `nim_client.py` | **The only provider-specific file**: NVIDIA NIM via the OpenAI SDK + `build_llm_client()` |
| `tools.py` | The LLM tools, JSON validation, 3-layer recommendation grounding |
| `prompts.py` | Prompt texts (severity rubric is an ASSUMED team baseline, not official policy) |
| `agent.py` | Pipeline, counter, success/failure assembly, review notes |
| `rules.py` | Keyword baseline for the eval + emergency-wording flag (never overrides the model) |

## Configuration (backend/.env, never committed)
| Variable | Default / example |
|---|---|
| `LLM_PROVIDER` | `nvidia_nim` (only value supported) |
| `LLM_MODEL` | `mistralai/mistral-large-4-1t-a52b` |
| `LLM_BASE_URL` | `https://integrate.api.nvidia.com/v1` |
| `LLM_API_KEY` | your key (placeholder `changeme` in `.env.example`; treated as missing) |
| `LLM_TIMEOUT_SECONDS` | `120` — SDK HTTP timeout for each LLM call (reasoning models may take 5-40 s) |

Get a key: sign in at https://build.nvidia.com, open the model's page, choose **Get API Key**, and paste it
into `backend/.env` only. The SDK timeout is `LLM_TIMEOUT_SECONDS` (default 120 s); SDK retries are off
(the Orchestrator retries). Provider errors raise `LLMProviderError(transient=...)` so the caller can tell retryable
failures (timeout, 429, 5xx) from non-retryable ones (bad key, bad request).

Use it:
```python
from app.agents.complaint_agent import run_complaint_agent
from app.agents.complaint_agent.nim_client import build_llm_client

result = run_complaint_agent(state, build_llm_client(), rag)  # rag = teammate's RagRetriever
```
To change the model/provider later: write another class with `complete(system, user) -> str` and
switch `build_llm_client`. Nothing else changes.

## Install and test
```bash
cd backend
pip install -e ".[dev]"
pytest tests/unit tests/integration -q          # no API key needed, all external calls mocked
pytest -m live -v                               # OPT-IN live smoke test; skipped unless LLM_API_KEY is real
python -m tests.agent_eval.run_eval             # keyword baseline (no key)
python -m tests.agent_eval.run_eval --llm nim   # evaluate the real model (needs key; 2 calls per row)
```

## Output contract
Documented fields are unchanged. **Proposed extension (needs team approval):** success output also has
`review_notes: list[str]` of `"CODE: explanation"` strings, e.g. `NO_RETRIEVED_EVIDENCE`,
`NO_SUPPORTED_RECOMMENDATIONS`, `RECOMMENDATIONS_REMOVED`, `SEVERITY_LOW_CONFIDENCE`,
`POSSIBLE_UNDERESTIMATED_SEVERITY`, `AMBIGUOUS_DESCRIPTION`, `CATEGORY_DIFFERS_FROM_AUTHORITY`.
Failure reasons beyond the documented `TOOL_CALL_LIMIT_EXCEEDED`: `INVALID_INPUT`, `LLM_PROVIDER_ERROR`,
`MALFORMED_LLM_RESPONSE`, `RAG_UNAVAILABLE`, `INTERNAL_ERROR`.

## Severity rules (assumed baseline, not official policy)
Critical = danger to life/public safety exists now or a major service failure; Medium = real disruption, not
immediately dangerous; Weak = minor/cosmetic. The prompt tells the model to judge the *current* situation,
that negated hazards ("no danger", "مفيش خطر") do not raise severity, that resolved past incidents are not
Critical by themselves, that calm wording does not lower severity, and to answer Medium + low confidence
when vague. Needs a human: low confidence, emergency wording on a non-Critical rating (could be negation
or a past event), ambiguous text, no/insufficient evidence. Every ticket is human-reviewed anyway.

## Recommendation grounding (what is and is not guaranteed)
1. Cited source numbers must exist in what RAG returned. 2. Any law/article/code the model writes must appear
verbatim in the cited text (catches invented citations only; says nothing about meaning). 3. A verifier LLM call
judges whether each cited source supports the recommendation; missing/failed verification drops the draft
or fails the ticket (fail closed). Layer 3 is an LLM judging an LLM: it **reduces** unsupported claims, it does
**not** guarantee semantic grounding.

## Integration requirements for the RAG teammate
`retrieve(query: str, category: str, top_k: int = 5) -> list[RagChunk]`, `RagChunk = {source, excerpt}` both
non-empty and copied from the stored document; return `[]` for no result, raise only on real failure; `source`
must be a citable label (it is appended to every recommendation). The query contains no citizen PII.

## Handoffs outside this component (not changed by us)
- Orchestrator: `send_to_complaint_agent` is still a placeholder; call `run_complaint_agent(state, llm, rag)`.
  Its state lacks `tool_call_limit`, `location`, `attachments`; the agent defaults the limit to 8. Accept the new
  failure reasons and `review_notes`, and update "happy path uses 4 tool calls" to 5.
- Taxonomy: docs say Garbage, code says Environment; we follow the code (`CATEGORIES` in `schemas.py`).

## Known limitations and evaluation status
- **Live evaluation (Mistral Large 4 via NVIDIA NIM, 69 rows, single run, author-written labels not reviewed by municipal staff):**
  Severity 88.4% (keyword baseline 62.3%); Critical recall 23/26 = 88.5% (baseline 38.5%);
  negation 7/7, calm_emergency 3/3, past_incident 4/5.
- 5 of 69 rows returned no valid answer (4 logged as API timeouts, 1 unexplained). On the 64
  answered rows: category 64/64, severity 61/64.
- Real severity misses: E57 (past accident, hazard still present, rated Medium not Critical);
  E39 and E10 (labels debatable).
- Category score is not informative: `category = authority` alone scores 97.1%.
- **Caveats:** small sample, single run; prompt few-shot examples share patterns with the
  negation/past_incident tags, so those scores may be optimistic.
- **Latency:** 5-40 s per call for the same prompt. Orchestrator limits (15 s per tool, 60 s
  per ticket) with 5 calls per ticket may be too tight; team decision needed (raise limits or
  try a faster model such as GLM-5.3 Flash via `--llm-factory`).
- Keyword-baseline results (69 rows; 48 original + 21 harder cases): severity 62.3%, Critical recall 38.5%
  (16 Critical complaints rated lower), negation 1/7, calm emergencies 0/3, category 100% (but
  `category = authority` alone gets 97.1%, so the category number is not informative).
- Dataset labels are by the author, unreviewed by municipal staff, and some are debatable.
- NIM JSON mode was not relied on (unconfirmed for this model); the parser tolerates fences and extra text.
- Emergency-wording flags are keyword-based: they over-flag negated text on purpose and miss unlisted words.
- Images/attachments are ignored (metadata only).
