"""The LLM-backed tools: categorize, classify severity, draft + verify recommendations.

Each function is ONE LLM call. They raise ToolError (with a FailureReason) instead of
returning bad data, and the agent turns that into a structured Failed output.
"""

import json
import re

from pydantic import BaseModel, ValidationError

from app.agents.complaint_agent.interfaces import LLMClient
from app.agents.complaint_agent.prompts import (
    CATEGORY_SYSTEM,
    RECOMMENDATION_SYSTEM,
    SEVERITY_SYSTEM,
    VERIFY_SYSTEM,
)
from app.agents.complaint_agent.schemas import (
    CATEGORIES,
    CategoryAnswer,
    FailureReason,
    RagChunk,
    RecommendationAnswer,
    RecommendationDraft,
    SeverityAnswer,
    VerificationAnswer,
)

UNCLEAR = "Unclear"
MAX_DESCRIPTION_CHARS = 2000  # cost and prompt-injection surface; far above real complaints


class ToolError(Exception):
    def __init__(self, reason: FailureReason):
        super().__init__(reason.value)
        self.reason = reason


def _ask_json[T: BaseModel](llm: LLMClient, system: str, user: str, model: type[T]) -> T:
    """Call the LLM, extract the JSON object from its text, validate it with Pydantic."""
    try:
        raw = llm.complete(system, user)
    except Exception as exc:  # provider failure: any exception type
        raise ToolError(FailureReason.LLM_PROVIDER_ERROR) from exc

    if not isinstance(raw, str):
        raise ToolError(FailureReason.MALFORMED_LLM_RESPONSE)
    start, end = raw.find("{"), raw.rfind("}")  # tolerates ```json fences and chatter
    if start == -1 or end <= start:
        raise ToolError(FailureReason.MALFORMED_LLM_RESPONSE)
    try:
        return model.model_validate(json.loads(raw[start : end + 1]))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ToolError(FailureReason.MALFORMED_LLM_RESPONSE) from exc


def _complaint_block(description: str) -> str:
    """Wrap the complaint as quoted data. The closing tag is neutralised so the text cannot
    break out of the block."""
    text = description.strip()[:MAX_DESCRIPTION_CHARS].replace("</complaint>", "")
    return f"<complaint>\n{text}\n</complaint>"


def categorize(llm: LLMClient, description: str, authority: str) -> tuple[str, bool]:
    """Return (category, was_unclear).

    A taxonomy category is returned as-is, even when it differs from the authority (the
    Orchestrator decides about declines; the reviewer can override). "Unclear" falls back
    to the citizen's authority and was_unclear=True. Anything else is rejected.
    """
    user = f"Selected authority: {authority}\n{_complaint_block(description)}"
    answer = _ask_json(llm, CATEGORY_SYSTEM, user, CategoryAnswer)
    if answer.category in CATEGORIES:
        return answer.category, False
    if answer.category == UNCLEAR:
        return authority, True
    raise ToolError(FailureReason.MALFORMED_LLM_RESPONSE)  # invented category: reject


def classify_severity(llm: LLMClient, description: str, category: str) -> SeverityAnswer:
    user = f"Category: {category}\n{_complaint_block(description)}"
    return _ask_json(llm, SEVERITY_SYSTEM, user, SeverityAnswer)


# --- Recommendations -----------------------------------------------------------------
# Grounding has three layers, from cheap to semantic:
#   1. structure: the model must cite sources that were actually retrieved;
#   2. string check: any law/number it writes must literally appear in the cited text
#      (catches invented citations only, says nothing about meaning);
#   3. verify_support(): a second LLM call judges whether the cited text really supports
#      the recommendation. This is an LLM judging an LLM: it lowers the risk, it does not
#      guarantee semantic grounding. Humans still review every ticket.
_KEYWORD_REF = re.compile(
    r"(?:regulation|law|article|art\.|decree|clause|section|code|مادة|قانون|لائحة)\s*(?:no\.?\s*)?"
    r"([A-Za-z]{0,4}-?\d+(?:[-/.]\d+)*)",
    re.IGNORECASE,
)
_CODE_REF = re.compile(r"\b([A-Z]{1,4}-\d+(?:[-/.]\d+)*)\b")


def _unsupported_reference(text: str, cited: list[RagChunk]) -> bool:
    evidence = " ".join(f"{c.source} {c.excerpt}" for c in cited).lower()
    refs = _KEYWORD_REF.findall(text) + _CODE_REF.findall(text)
    return any(ref.lower() not in evidence for ref in refs)


def _numbered_sources(chunks: list[RagChunk]) -> str:
    return "\n".join(f"[{i}] {c.source}: {c.excerpt}" for i, c in enumerate(chunks, 1))


def generate_recommendations(
    llm: LLMClient,
    description: str,
    category: str,
    severity: str,
    chunks: list[RagChunk],
) -> tuple[list[RecommendationDraft], int]:
    """Return (drafts that passed layers 1-2, number dropped). Needs at least one chunk."""
    user = (
        f"Category: {category}\nSeverity: {severity}\n{_complaint_block(description)}\n\n"
        f"SOURCES:\n{_numbered_sources(chunks)}"
    )
    answer = _ask_json(llm, RECOMMENDATION_SYSTEM, user, RecommendationAnswer)

    kept: list[RecommendationDraft] = []
    for draft in answer.recommendations:
        if not all(1 <= i <= len(chunks) for i in draft.source_ids):
            continue  # cites a source that was never retrieved
        cited = [chunks[i - 1] for i in dict.fromkeys(draft.source_ids)]
        if _unsupported_reference(draft.text, cited):
            continue  # mentions a law/number the cited sources do not contain
        kept.append(draft)
    return kept, len(answer.recommendations) - len(kept)


def verify_support(
    llm: LLMClient,
    description: str,
    drafts: list[RecommendationDraft],
    chunks: list[RagChunk],
) -> list[RecommendationDraft]:
    """Layer 3: keep only drafts the verifier marks supported. Fails closed: a draft with
    no verdict (or an out-of-range / duplicate index) is dropped."""
    lines = [
        f"R{n}: {d.text}  (cites source(s): {', '.join(map(str, dict.fromkeys(d.source_ids)))})"
        for n, d in enumerate(drafts, 1)
    ]
    user = (
        f"{_complaint_block(description)}\n\nSOURCES:\n{_numbered_sources(chunks)}\n\n"
        "RECOMMENDATIONS:\n" + "\n".join(lines)
    )
    answer = _ask_json(llm, VERIFY_SYSTEM, user, VerificationAnswer)
    supported = {v.index for v in answer.verdicts if v.supported}
    return [d for n, d in enumerate(drafts, 1) if n in supported]


def render_recommendation(draft: RecommendationDraft, chunks: list[RagChunk]) -> str:
    """Keep the documented list[str] contract and carry attribution: "... [Source: X]"."""
    names = "; ".join(dict.fromkeys(chunks[i - 1].source for i in draft.source_ids))
    return f"{draft.text.strip()} [Source: {names}]"
