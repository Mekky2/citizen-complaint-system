"""Deterministic, offline "LLM" used only for demos/tests when no API key is configured.

It does not know anything about laws or fees: it simply returns the retrieved context it was
given, so the RAG agent still answers strictly from the knowledge base. Production must use a
real model (set ``LLM_API_KEY`` and ``EMBEDDING_PROVIDER``).
"""

from __future__ import annotations

import json
import re

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
