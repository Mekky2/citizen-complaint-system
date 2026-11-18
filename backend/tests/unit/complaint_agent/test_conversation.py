"""Conversation tests for the Arabic Complaint Agent (offline, no keys)."""

import json
from pathlib import Path

import pytest

from app.agents.complaint_agent.conversation import (
    ComplaintDraft,
    handle_message,
    new_session,
    summary_ar,
)
from app.services.emergency_numbers import emergency_numbers_singleton
from app.services.ticket_store import STATUS_PENDING, InMemoryTicketStore

GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "complaints_golden.json"


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"]


@pytest.fixture()
def store() -> InMemoryTicketStore:
    return InMemoryTicketStore()


def _is_special(case: dict) -> bool:
    return (
        case["expected_emergency"]
        or case["expected_injection"]
        or case["expected_abusive"]
        or case["expected_intent"] in {"question", "greeting", "thanks"}
    )


def test_golden_dataset_has_enough_varied_cases(cases):
    assert len(cases) >= 30
    languages = {case["language"] for case in cases}
    assert {"ar-msa", "ar-eg", "franco", "ar-typo"} <= languages
    assert any(case["expected_emergency"] for case in cases)
    assert any(case["expected_injection"] for case in cases)
    assert any(case["expected_abusive"] for case in cases)
    assert any(case["expected_category"] is None for case in cases)


@pytest.mark.parametrize("case", json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"])
def test_golden_case(case, store):
    if case["requires_llm"]:
        pytest.skip("Franco-Arabic needs the LLM extractor; covered by test_franco_with_fake_llm")

    session = new_session(f"S-{case['id']}")
    result = handle_message(session, case["text"], store=store)
    notes = set(result["review_notes"])

    assert ("EMERGENCY_DETECTED" in notes) is case["expected_emergency"]
    assert ("PROMPT_INJECTION_IGNORED" in notes) is case["expected_injection"]
    assert ("ABUSIVE_LANGUAGE" in notes) is case["expected_abusive"]

    intent = case["expected_intent"]
    if intent == "question":
        assert result["handoff_to"] == "rag"
    elif intent == "greeting":
        assert result["handoff_to"] == "complaint"
    elif intent == "thanks":
        assert result["handoff_to"] == "rag"
    elif not _is_special(case):
        assert result["handoff_to"] is None

    if case["expected_category"] and not _is_special(case):
        assert result["draft"]["category"] == case["expected_category"]
    if case["expected_urgency"] and not _is_special(case):
        assert result["draft"]["urgency"] == case["expected_urgency"]

    if not _is_special(case):
        assert bool(result["missing_fields"]) is case["expected_follow_up"]

    if case["expected_emergency"]:
        assert result["draft"]["urgency"] == "critical"
        assert store.list() == []
        assert "122" in result["reply_ar"]

    if case["expected_injection"] or case["expected_abusive"]:
        assert store.list() == []


def test_no_ticket_before_confirmation_then_pending(store):
    session = new_session("S-FLOW")
    first = handle_message(
        session,
        "ماسورة مياه مكسورة في شارع النيل بالجيزة من يومين",
        store=store,
    )

    assert first["requires_confirmation"] is True
    assert first["stage"] == "awaiting_confirmation"
    assert first["ticket"] is None
    assert store.list() == []
    assert "هل تأكد إرسال الشكوى؟" in first["reply_ar"]
    assert first["draft"]["category"] == "Water"
    assert first["draft"]["authority"] == "مديرية المياه"

    confirmed = handle_message(session, "نعم أكد الإرسال", store=store)

    assert confirmed["stage"] == "submitted"
    assert confirmed["ticket"]["status"] == STATUS_PENDING
    assert confirmed["ticket"]["ticket_id"].startswith("TKT-")
    assert len(store.list()) == 1


def test_vague_message_asks_follow_up_then_accepts_details(store):
    session = new_session("S-VAGUE")
    first = handle_message(session, "في مشكلة", store=store)

    assert first["missing_fields"] == ["category", "location"]
    assert "ما نوع المشكلة" in first["reply_ar"]
    assert store.list() == []

    second = handle_message(
        session, "المشكلة زبالة متراكمة في شارع النيل", store=store
    )
    assert second["stage"] == "awaiting_confirmation"
    assert second["draft"]["category"] == "Environment"
    assert second["missing_fields"] == []
    assert store.list() == []


def test_rejection_cancels_submission_and_keeps_draft(store):
    session = new_session("S-REJECT")
    handle_message(session, "تسريب مياه في شارع النيل", store=store)

    result = handle_message(session, "لا، عايز أعدل", store=store)

    assert result["stage"] == "collecting"
    assert "لم يتم الإرسال" in result["reply_ar"]
    assert store.list() == []
    assert session.draft.category == "Water"


def test_duplicate_ticket_is_detected_and_linked(store):
    first_session = new_session("S-DUP-1")
    handle_message(first_session, "زبالة متراكمة في شارع النيل", store=store)
    created = handle_message(first_session, "نعم", store=store)
    ticket_id = created["ticket"]["ticket_id"]

    second_session = new_session("S-DUP-2")
    summary = handle_message(second_session, "زبالة متراكمة في شارع النيل", store=store)

    assert ticket_id in summary["reply_ar"]
    assert "شكوى مشابهة" in summary["reply_ar"]
    assert len(store.list()) == 1

    linked = handle_message(second_session, "نعم اربطها", store=store)

    assert linked["stage"] == "linked"
    assert linked["ticket"]["ticket_id"] == ticket_id
    assert len(store.list()) == 1
    assert any(
        note.startswith("LINKED_DUPLICATE") for note in store.get(ticket_id).review_notes
    )


def test_emergency_uses_only_official_numbers_and_creates_no_ticket(store):
    session = new_session("S-EMERGENCY")
    result = handle_message(session, "فيه حريق في الشارع", store=store)
    official = {item["number"] for item in emergency_numbers_singleton().get_all_numbers()}
    assert "EMERGENCY_DETECTED" in result["review_notes"]
    assert "الحماية المدنية" in result["reply_ar"]
    for number in official:
        assert number in result["reply_ar"]
    assert store.list() == []


def test_exposed_electrical_wire_is_treated_as_emergency(store):
    """Regression: singular wording ("سلك ... مكشوف") must trigger the emergency path."""
    session = new_session("S-EMERGENCY-WIRE")
    result = handle_message(session, "سلك كهرباء مكشوف في الشارع", store=store)

    assert "EMERGENCY_DETECTED" in result["review_notes"]
    assert result["draft"]["urgency"] == "critical"
    assert "121" in result["reply_ar"]
    assert store.list() == []


def test_pii_is_masked_and_never_stored_in_plaintext(store):
    session = new_session("S-PII")
    result = handle_message(
        session,
        "تسريب مياه في شارع النيل، رقمي 01012345678 وهوية 29812345678901",
        store=store,
    )

    assert "01012345678" not in result["draft"]["description"]
    assert "29812345678901" not in result["draft"]["description"]
    assert "[PHONE]" in result["draft"]["description"]
    assert "[ID]" in result["draft"]["description"]

    confirmed = handle_message(session, "نعم", store=store)
    stored = store.get(confirmed["ticket"]["ticket_id"])
    assert "01012345678" not in stored.description
    assert "29812345678901" not in stored.description


class _FrancoLLM:
    """Scripted extractor: proves the LLM path and merge without a network call."""

    def complete(self, system: str, user: str) -> str:
        return json.dumps(
            {
                "title": "تسريب مياه في شارع النيل",
                "description": "تسريب مياه في شارع النيل",
                "category": "Water",
                "location": {"governorate": "", "city": "", "street": "شارع النيل", "landmark": ""},
                "incident_date": None,
                "urgency": "high",
                "urgency_reason": "تسريب مياه مستمر",
                "attachments_mentioned": [],
                "contact_preference": None,
                "confidence": 0.9,
                "missing_fields": [],
            },
            ensure_ascii=False,
        )


def test_franco_with_fake_llm_extracts_water_without_creating_ticket(store):
    session = new_session("S-FRANCO")
    result = handle_message(
        session,
        "fi tasreeb maya fi share3 el nil",
        store=store,
        llm=_FrancoLLM(),
    )

    assert result["draft"]["category"] == "Water"
    assert result["requires_confirmation"] is True
    assert result["ticket"] is None
    assert store.list() == []


def test_summary_is_arabic_and_contains_authority_and_location():
    draft = ComplaintDraft(
        title="تسريب مياه",
        description="تسريب مياه في شارع النيل",
        category="Water",
        authority="مديرية المياه",
    )
    text = summary_ar(draft)
    assert "ملخص الشكوى" in text
    assert "مديرية المياه" in text
    assert "المياه والصرف" in text


def test_arabic_markers_match_whole_words_not_substrings(store):
    """Regression: "خرا" inside "استخراج" must not be read as abusive language."""
    session = new_session("S-SUBSTRING")
    result = handle_message(session, "كم رسوم استخراج رخصة القيادة؟", store=store)

    assert "ABUSIVE_LANGUAGE" not in result["review_notes"]
    assert result["handoff_to"] == "rag"


def test_mixed_arabic_english_extracts_category_and_street(store):
    session = new_session("S-MIXED")
    result = handle_message(session, "عندي water leak في street النيل", store=store)

    assert result["draft"]["category"] == "Water"
    assert result["draft"]["location"]["street"] == "النيل"
    assert result["stage"] == "awaiting_confirmation"
