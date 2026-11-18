"""Deterministic, offline "LLM" used only for demos/tests when no API key is configured.

It does not know anything about laws or fees: it simply returns the retrieved context it was
given, so the RAG agent still answers strictly from the knowledge base. Production must use a
real model (set ``LLM_API_KEY`` and ``EMBEDDING_PROVIDER``).
"""

from __future__ import annotations

import json
import re

from app.agents.complaint_agent.authorities import CATEGORY_KEYWORDS
from app.agents.complaint_agent.schemas import CATEGORIES
from app.utils.arabic_normalizer import normalize_arabic

_CONTEXT = re.compile(r"<retrieved_context>(.*?)</retrieved_context>", re.DOTALL)
_ITEM = re.compile(r"^\[(\d+)\]\s*(.+?)\n(.+)$", re.MULTILINE | re.DOTALL)
_QUERY = re.compile(r"الاستفسار:\s*(.+?)(?:\n|$)", re.DOTALL)


def _tokens(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"\w+", normalize_arabic(text, fold_taa_marbuta=True))
        if len(word) > 1
    }


class GroundedTemplateLLM:
    """Returns an Arabic answer assembled from the best-matching retrieved passage.

    This is not a language model. It selects the passage with the largest word overlap with
    the question, so the API and tests stay grounded in the knowledge base without pretending
    to reason. Production must configure ``LLM_API_KEY``.
    """

    def complete(self, system: str, user: str) -> str:
        match = _CONTEXT.search(user)
        if not match:
            return json.dumps(
                {"answer": "المعلومات غير متوفرة في قاعدة المعرفة.", "sources_used": []},
                ensure_ascii=False,
            )

        blocks = _ITEM.findall(match.group(1))
        if not blocks:
            return json.dumps(
                {"answer": "المعلومات غير متوفرة في قاعدة المعرفة.", "sources_used": []},
                ensure_ascii=False,
            )

        query = _QUERY.search(user)
        query_tokens = _tokens(query.group(1)) if query else set()

        def overlap(block: tuple[str, str, str]) -> tuple[int, int]:
            _, title, body = block
            return len(query_tokens & _tokens(f"{title} {body}")), -len(body)

        index, title, body = max(blocks, key=overlap)
        excerpt = re.sub(r"\s+", " ", body).strip()
        if len(excerpt) > 450:
            excerpt = excerpt[:447].rstrip() + "..."
        answer = f"بحسب المعلومات المتاحة في قاعدة المعرفة عن «{title.strip()}»: {excerpt}"
        return json.dumps(
            {"answer": answer, "sources_used": [int(index)], "confidence": "medium"},
            ensure_ascii=False,
        )


# --- Offline structured tools ------------------------------------------------------
# The teammate's structured agent asks the model for four JSON shapes (category, severity,
# recommendations, verdicts). When every paid provider is down we still answer with valid
# JSON from rules so the ticket keeps its structured analysis. Text is only ever quoted from
# the retrieved sources, so nothing is invented.

_CRITICAL_SIGNALS = (
    "مكشوف",
    "مكهرب",
    "صعقه",
    "صعقة",
    "شرر",
    "شرارة",
    "حريق",
    "نار",
    "دخان",
    "غاز",
    "تسريب غاز",
    "انفجار",
    "عميق",
    "غرق",
    "طفح",
    "سقوط",
    "خطر",
    "اصابه",
    "إصابة",
    "مصاب",
    "electrocution",
    "exposed",
    "fire",
    "gas leak",
    "collapse",
    "danger",
)
_WEAK_SIGNALS = (
    "بسيط",
    "بسيطه",
    "خفيف",
    "دهان",
    "لون",
    "تجميل",
    "شكل",
    "cosmetic",
    "minor",
    "faded",
)
_SOURCE_LINE = re.compile(r"^\[(\d+)\]\s*([^:]+):\s*(.+)$", re.MULTILINE)
_VERDICT_LINE = re.compile(r"^R(\d+):", re.MULTILINE)


def _block(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1) if match else text


def _category_from_text(text: str) -> str:
    normalized = normalize_arabic(text, fold_taa_marbuta=True)
    best, best_score = "Unclear", 0
    for category in CATEGORIES:
        score = sum(
            1
            for keyword in CATEGORY_KEYWORDS.get(category, ())
            if normalize_arabic(keyword, fold_taa_marbuta=True) in normalized
        )
        if score > best_score:
            best, best_score = category, score
    return best


def _severity_from_text(text: str) -> dict[str, str]:
    normalized = normalize_arabic(text, fold_taa_marbuta=True)
    if any(signal in normalized for signal in _CRITICAL_SIGNALS):
        return {"severity": "Critical", "confidence": "high"}
    if any(signal in normalized for signal in _WEAK_SIGNALS):
        return {"severity": "Weak", "confidence": "low"}
    return {"severity": "Medium", "confidence": "low"}


def _first_sentence(text: str, limit: int = 240) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    match = re.search(r"(.+?[.!؟?])(\s|$)", cleaned)
    sentence = match.group(1) if match else cleaned
    if len(sentence) > limit:
        sentence = sentence[: limit - 3].rstrip() + "..."
    return sentence


class OfflineToolLLM:
    """Rule-based stand-in for the complaint agent's JSON tools.

    It recognises the teammate's four system prompts and answers with the same JSON shape.
    Anything else (notably the RAG answer prompt) is delegated to
    :class:`GroundedTemplateLLM`, so knowledge answers stay grounded in retrieved text.
    """

    def __init__(self, rag_llm: GroundedTemplateLLM | None = None):
        self._rag = rag_llm or GroundedTemplateLLM()

    def complete(self, system: str, user: str) -> str:
        if "You assign a severity" in system:
            return json.dumps(_severity_from_text(_block(user, "complaint")), ensure_ascii=False)

        if "one verdict for every recommendation" in system:
            verdicts = [{"index": int(n), "supported": True} for n in _VERDICT_LINE.findall(user)]
            return json.dumps({"verdicts": verdicts}, ensure_ascii=False)

        if "source_ids" in system and '"recommendations"' in system:
            sources = _SOURCE_LINE.findall(user)
            if not sources:
                return json.dumps({"recommendations": []}, ensure_ascii=False)
            index, _title, excerpt = sources[0]
            text = _first_sentence(excerpt)
            if not text:
                return json.dumps({"recommendations": []}, ensure_ascii=False)
            return json.dumps(
                {"recommendations": [{"text": text, "source_ids": [int(index)]}]},
                ensure_ascii=False,
            )

        if "Pick exactly one category" in system or "one of the categories or Unclear" in system:
            return json.dumps(
                {"category": _category_from_text(_block(user, "complaint"))}, ensure_ascii=False
            )

        if "urgency_reason" in system and '"title"' in system:
            return self._draft_json(_block(user, "complaint"))

        # RAG answers: the grounded template already handles them without a model.
        return self._rag.complete(system, user)

    @staticmethod
    def _draft_json(message: str) -> str:
        """Answer the conversation extractor with the rule-based draft, in its JSON shape.

        Returning a JSON object without the expected keys (e.g. the RAG answer shape) would
        validate as an empty draft and silently downgrade urgency, so this branch must exist.
        """
        from app.agents.complaint_agent.conversation import (
            extract_with_rules,
            missing_fields,
        )

        draft = extract_with_rules(message)
        payload = draft.model_dump()
        payload["missing_fields"] = missing_fields(draft)
        return json.dumps(payload, ensure_ascii=False)
