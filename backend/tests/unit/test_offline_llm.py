"""The offline stand-in must answer every prompt shape the agents use (no network)."""

from __future__ import annotations

import json

from app.agents.complaint_agent.conversation import system_prompt
from app.services.offline_llm import GroundedTemplateLLM, OfflineToolLLM


def _llm() -> OfflineToolLLM:
    return OfflineToolLLM(GroundedTemplateLLM())


def test_conversation_extraction_keeps_rule_based_urgency():
    text = "تسريب مياه في ماسورة رئيسية أمام مسجد الرحمة بشارع النيل في الجيزة"
    raw = _llm().complete(system_prompt(), f"<complaint>\n{text}\n</complaint>")
    payload = json.loads(raw)

    assert payload["description"] == text
    assert payload["category"] == "Water"
    assert payload["urgency"] == "high"  # not the "medium" model default
    assert payload["location"]["governorate"] == "الجيزة"
    assert payload["missing_fields"] == []


def test_category_and_severity_tools_answer_their_own_json_shape():
    llm = _llm()
    category = json.loads(
        llm.complete("Pick exactly one category.", '<complaint>حفرة كبيرة في الطريق</complaint>')
    )
    assert category == {"category": "Roads"}

    severity = json.loads(
        llm.complete(
            "You assign a severity.",
            "<complaint>عمود كهرباء مكشوف وخطير</complaint>",
        )
    )
    assert severity["severity"] == "Critical"


def test_recommendations_quote_the_retrieved_source_verbatim():
    system = 'Return JSON with "recommendations" and "source_ids".'
    user = "[1] المياه: إصلاح التسريب من أسفل الأرض أولًا.\n\n[2] أخرى: نص ثانٍ."
    payload = json.loads(_llm().complete(system, user))

    assert payload["recommendations"][0]["source_ids"] == [1]
    assert "إصلاح التسريب من أسفل الأرض" in payload["recommendations"][0]["text"]


def test_verdicts_cover_each_recommendation():
    user = "R1: إصلاح التسريب.\nR2: إبلاغ الشركة."
    payload = json.loads(_llm().complete("one verdict for every recommendation", user))

    assert [item["index"] for item in payload["verdicts"]] == [1, 2]


def test_rag_prompt_without_context_is_grounded_and_says_so():
    payload = json.loads(_llm().complete("answer the question", "الاستفسار: ما هي رسوم الشكوى؟"))

    assert payload["answer"] == "المعلومات غير متوفرة في قاعدة المعرفة."
    assert payload["sources_used"] == []
