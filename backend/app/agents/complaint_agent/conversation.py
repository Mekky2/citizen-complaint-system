"""Conversational Complaint Agent (Arabic, human-in-the-loop).

This module is the citizen-facing layer. It understands MSA, Egyptian Arabic, mixed
Arabic/English and Franco-Arabic, extracts a structured draft, asks short Arabic follow-up
questions, shows a summary and only creates a ticket after explicit confirmation. The ticket
always starts as ``Pending`` (see ``docs/system_architecture.md``).

It is deliberately separate from ``agent.py`` (the orchestrator analysis node): that node
classifies an already-submitted ticket; this layer talks to the citizen.

The optional LLM extractor uses ``prompt_files/complaint_agent_ar.md``. When no LLM is
available the deterministic extractor is used, which keeps tests and demos offline.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.complaint_agent.authorities import (
    CATEGORY_LABEL_AR,
    authority_for_category,
    category_for_text,
    contact_preference,
    extract_incident_date,
    extract_location,
    mentions_attachments,
    short_title,
    urgency_for_text,
)
from app.agents.complaint_agent.schemas import CATEGORIES
from app.services.emergency_numbers import FileEmergencyNumbers, emergency_numbers_singleton
from app.services.ticket_store import STATUS_PENDING, InMemoryTicketStore, to_public_dict
from app.utils.arabic_normalizer import normalize_arabic

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).with_name("prompt_files") / "complaint_agent_ar.md"
MAX_MESSAGE_CHARS = 4000
REQUIRED_FIELDS = ("description", "category", "location")

_INJECTION_MARKERS = (
    "تجاهل التعليمات السابقة",
    "تجاهل كل التعليمات",
    "تجاهل التعليمات",
    "تجاهل ما سبق",
    "أنت الآن",
    "انت الآن",
    "اكشف التعليمات",
    "اطبع التعليمات",
    "ignore previous instructions",
    "ignore all instructions",
    "disregard the above",
    "system prompt",
    "you are now",
)
_EMERGENCY_MARKERS = (
    "حريق",
    "بيولع",
    "ولعت",
    "احتراق",
    "انفجار",
    "انفجر",
    "غاز",
    "صعق",
    "كهربا بتفرقع",
    "اسلاك مكشوفه",
    "أسلاك مكشوفة",
    "سلك مكشوف",
    "سلك كهرباء",
    "سلك كهربا",
    "كابل مكشوف",
    "كيبل مكشوف",
    "ماس كهربائي",
    "ماس كهرباء",
    "شرار",
    "انهيار",
    "سقوط",
    "غرق",
    "فيضان",
    "طوارئ",
    "خطر",
)
_ABUSE_MARKERS = (
    "غبي",
    "احمق",
    "أحمق",
    "كلب",
    "حمار",
    "خرا",
    "زفت",
    "stupid",
    "idiot",
)
_GREETING_MARKERS = (
    "السلام عليكم",
    "السلام",
    "مرحبا",
    "مرحباً",
    "اهلا",
    "أهلا",
    "صباح الخير",
    "مساء الخير",
    "hello",
    "hi",
)
_THANKS_MARKERS = (
    "شكرا",
    "شكرًا",
    "متشكر",
    "مشكور",
    "thanks",
    "thank you",
)
_QUESTION_STARTS = (
    "كيف",
    "ازاي",
    "إزاي",
    "هل",
    "ما ",
    "ماذا",
    "متى",
    "امتى",
    "لماذا",
    "ليه",
    "اين",
    "أين",
    "فين",
    "كم",
    "what",
    "how",
    "when",
    "where",
    "why",
)
_COMPLAINT_SIGNALS = (
    "شكوى",
    "شكوه",
    "بلاغ",
    "ابلاغ",
    "أبلغ",
    "مشكلة",
    "مشكله",
    "عطل",
    "عاطل",
    "مكسور",
    "مكسوره",
    "مكسورة",
    "تسريب",
    "حفره",
    "حفرة",
    "زباله",
    "زبالة",
    "قمامه",
    "قمامة",
    "انقطاع",
    "مقطوع",
    "مقطوعه",
    "مقطوعة",
    "طفح",
    "اسلاك",
    "أسلاك",
    "ضوضاء",
    "دخان",
    "رائحه",
    "رائحة",
    "مخالفه",
    "مخالفة",
    "مخالفات",
)
_PROBLEM_SIGNALS = tuple(
    signal
    for signal in _COMPLAINT_SIGNALS
    if signal not in {"شكوى", "شكوه", "بلاغ", "ابلاغ", "أبلغ"}
)
_CONFIRM_WORDS = (
    "نعم",
    "أكد",
    "اكد",
    "تأكيد",
    "تاكيد",
    "موافق",
    "موافقة",
    "تمام",
    "أرسل",
    "ارسل",
    "ابعت",
    "ابعتها",
    "ارسلها",
    "confirm",
    "yes",
    "ok",
    "send",
)
_REJECT_WORDS = (
    "لا",
    "مش",
    "الغ",
    "إلغاء",
    "الغاء",
    "انتظر",
    "تعديل",
    "اعدل",
    "أعدل",
    "غير",
    "no",
    "cancel",
    "edit",
)
_LINK_WORDS = ("اربط", "أربط", "ربط", "اربطها", "أربطها", "link")


class ComplaintLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    governorate: str = ""
    city: str = ""
    street: str = ""
    landmark: str = ""

    def is_empty(self) -> bool:
        return not any((self.governorate, self.city, self.street, self.landmark))

    def as_text(self) -> str:
        parts = [self.governorate, self.city, self.street, self.landmark]
        return "، ".join(part for part in parts if part)


class ComplaintDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    description: str = ""
    category: str | None = None
    authority: str | None = None
    location: ComplaintLocation = Field(default_factory=ComplaintLocation)
    incident_date: str | None = None
    urgency: Literal["low", "medium", "high", "critical"] = "medium"
    urgency_reason: str = ""
    attachments_mentioned: list[str] = Field(default_factory=list)
    contact_preference: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_fields: list[str] = Field(default_factory=list)


class ComplaintSession(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str
    draft: ComplaintDraft = Field(default_factory=ComplaintDraft)
    stage: Literal[
        "collecting", "awaiting_confirmation", "submitted", "linked", "handoff", "cancelled"
    ] = "collecting"
    turn_count: int = 0
    max_turns: int = 6
    pending_duplicate_id: str | None = None
    pending_duplicate_similarity: float | None = None
    ticket: dict[str, Any] | None = None
    history: list[dict[str, str]] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- helpers
@lru_cache(maxsize=1)
def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _marker_pattern(marker: str) -> re.Pattern[str]:
    """Word-start pattern allowing the Arabic proclitics و/ف/ب/ك/ل and the article ال.

    Plain substring matching is unsafe in Arabic: "خرا" appears inside "استخراج", so an
    abusive-word list would flag a perfectly normal question.
    """
    normalized = normalize_arabic(marker, fold_taa_marbuta=True).lower().strip()
    words = [word for word in normalized.split() if word]
    body = r"\s+".join(r"(?:[وفبكل])?(?:ال)?" + re.escape(word) for word in words)
    return re.compile(r"(?<!\w)" + body + r"(?!\w)")


@lru_cache(maxsize=256)
def _cached_marker_pattern(marker: str) -> re.Pattern[str]:
    return _marker_pattern(marker)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    normalized = normalize_arabic(text, fold_taa_marbuta=True).lower()
    return any(_cached_marker_pattern(marker).search(normalized) for marker in markers)


def _tokens(text: str) -> set[str]:
    return set(normalize_arabic(text, fold_taa_marbuta=True).split())


def is_confirmation(message: str) -> bool:
    words = _tokens(message)
    return any(word in words for word in _CONFIRM_WORDS) or _contains_any(
        message, ("أكد إرسال", "تأكيد الإرسال")
    )


def is_rejection(message: str) -> bool:
    words = _tokens(message)
    return any(word in words for word in _REJECT_WORDS)


def is_link_request(message: str) -> bool:
    words = _tokens(message)
    return any(word in words for word in _LINK_WORDS)


def looks_like_complaint(message: str) -> bool:
    """Cheap routing hint for the API: a non-question message that describes a problem."""
    if _is_question(message):
        return False
    return _contains_any(message, _PROBLEM_SIGNALS) or category_for_text(message) is not None


def _mask_pii(text: str) -> str:
    """Mask national IDs and phone numbers before sending text to an LLM."""
    text = re.sub(r"\b\d{14}\b", "[ID]", text)
    text = re.sub(r"\b01\d{9}\b", "[PHONE]", text)
    return text


def _strip_injection(text: str) -> str:
    """Remove obvious injected instruction phrases; keep the citizen's actual complaint."""
    cleaned = text
    for marker in _INJECTION_MARKERS:
        cleaned = re.sub(re.escape(marker), " ", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def missing_fields(draft: ComplaintDraft) -> list[str]:
    missing: list[str] = []
    if not draft.description.strip():
        missing.append("description")
    if draft.category not in CATEGORIES:
        missing.append("category")
    if draft.location.is_empty():
        missing.append("location")
    return missing


def _confidence(draft: ComplaintDraft) -> float:
    score = 0.2
    if len(draft.description.strip()) >= 15:
        score += 0.2
    if draft.category:
        score += 0.25
    if not draft.location.is_empty():
        score += 0.2
    if draft.urgency_reason:
        score += 0.1
    if draft.title:
        score += 0.05
    return round(min(score, 0.95), 2)


def _finalise(draft: ComplaintDraft) -> ComplaintDraft:
    draft.category = draft.category if draft.category in CATEGORIES else None
    draft.authority = authority_for_category(draft.category)
    if draft.description:
        draft.title = short_title(draft.description, draft.category)
    draft.missing_fields = missing_fields(draft)
    draft.confidence = _confidence(draft)
    return draft


# ------------------------------------------------------------------------- extractors
def extract_with_rules(message: str, previous: ComplaintDraft | None = None) -> ComplaintDraft:
    """Deterministic extractor used offline and as the LLM fallback."""
    previous = previous or ComplaintDraft()
    text = (message or "").strip()[:MAX_MESSAGE_CHARS]
    if not text:
        return previous.model_copy(deep=True)

    description = text
    if previous.description and text not in previous.description:
        description = f"{previous.description} {text}".strip()

    category = category_for_text(text) or previous.category
    urgency, reason = urgency_for_text(description)
    location = extract_location(text)
    merged_location = ComplaintLocation(
        governorate=location["governorate"] or previous.location.governorate,
        city=location["city"] or previous.location.city,
        street=location["street"] or previous.location.street,
        landmark=location["landmark"] or previous.location.landmark,
    )

    draft = ComplaintDraft(
        title=short_title(description, category),
        description=description,
        category=category,
        location=merged_location,
        incident_date=extract_incident_date(text) or previous.incident_date,
        urgency=urgency,
        urgency_reason=reason,
        attachments_mentioned=sorted(
            set(previous.attachments_mentioned) | set(mentions_attachments(text))
        ),
        contact_preference=contact_preference(text) or previous.contact_preference,
    )
    return _finalise(draft)


def extract_with_llm(
    llm: Any, message: str, previous: ComplaintDraft | None = None
) -> tuple[ComplaintDraft, list[str]]:
    """Ask the LLM for a structured draft; always fall back to the rule extractor."""
    notes: list[str] = []
    try:
        raw = llm.complete(
            system_prompt(),
            f"<complaint>\n{_mask_pii(message)}\n</complaint>",
        )
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in LLM answer")
        data = json.loads(raw[start : end + 1])
        if not isinstance(data, dict):
            raise ValueError("LLM answer is not an object")
        # Reuse the strict model for types, then merge with the deterministic extraction so
        # a missing LLM field never deletes information the citizen already gave.
        parsed = ComplaintDraft.model_validate(data)
        fallback = extract_with_rules(message, previous)
        draft = _merge(fallback, parsed)
        return _finalise(draft), notes
    except Exception as exc:  # provider error, bad JSON, invalid fields
        notes.append("LLM_EXTRACTION_FALLBACK")
        logger.warning("complaint extraction fell back to rules: %s", type(exc).__name__)
        return extract_with_rules(message, previous), notes


def _merge(base: ComplaintDraft, extra: ComplaintDraft) -> ComplaintDraft:
    """Merge a parsed LLM draft over the rule draft, never erasing known values."""
    return ComplaintDraft(
        title=extra.title or base.title,
        description=extra.description or base.description,
        category=extra.category or base.category,
        authority=extra.authority or base.authority,
        location=ComplaintLocation(
            governorate=extra.location.governorate or base.location.governorate,
            city=extra.location.city or base.location.city,
            street=extra.location.street or base.location.street,
            landmark=extra.location.landmark or base.location.landmark,
        ),
        incident_date=extra.incident_date or base.incident_date,
        urgency=extra.urgency or base.urgency,
        urgency_reason=extra.urgency_reason or base.urgency_reason,
        attachments_mentioned=sorted(
            set(base.attachments_mentioned) | set(extra.attachments_mentioned)
        ),
        contact_preference=extra.contact_preference or base.contact_preference,
    )


# -------------------------------------------------------------------------- replies
_QUICK_QUESTIONS = {
    "description": "من فضلك اكتب وصفًا واضحًا للمشكلة.",
    "category": "ما نوع المشكلة: مياه، كهرباء، طرق، أم نظافة/بيئة؟",
    "location": "أين حدثت المشكلة؟ اذكر المحافظة والحي أو الشارع.",
}


def follow_up_question(draft: ComplaintDraft) -> str:
    questions = [_QUICK_QUESTIONS[field] for field in draft.missing_fields[:2]]
    return " ".join(questions) if questions else ""


def summary_ar(draft: ComplaintDraft) -> str:
    lines = ["ملخص الشكوى:"]
    lines.append(f"- العنوان: {draft.title or 'غير محدد'}")
    lines.append(f"- الوصف: {draft.description or 'غير محدد'}")
    lines.append(
        f"- الفئة: {CATEGORY_LABEL_AR.get(draft.category or '', draft.category or 'غير محددة')}"
    )
    lines.append(f"- الجهة: {draft.authority or 'غير محددة'}")
    lines.append(f"- الموقع: {draft.location.as_text() or 'غير محدد'}")
    lines.append(f"- الأهمية: {draft.urgency} — {draft.urgency_reason}")
    if draft.missing_fields:
        lines.append(f"- حقول تحتاج مراجعة بشرية: {', '.join(draft.missing_fields)}")
    return "\n".join(lines)


def emergency_reply(provider: FileEmergencyNumbers) -> str:
    from app.services.emergency_numbers import arabic_description, arabic_name

    numbers = provider.get_all_numbers()
    lines = [
        "هذا يبدو كحالة طوارئ. يُرجى الاتصال مباشرة بأرقام الطوارئ الرسمية فورًا:",
    ]
    for item in numbers:
        label = arabic_name(item)
        description = arabic_description(item)
        suffix = f" — {description}" if description else ""
        lines.append(f"• {label}: {item['number']}{suffix}")
    lines.append("بعد اتخاذ الإجراء الطارئ يمكنك إكمال الشكوى هنا لمتابعة المشكلة.")
    return "\n".join(lines)


# -------------------------------------------------------------------------- session
def new_session(session_id: str, *, max_turns: int = 6) -> ComplaintSession:
    return ComplaintSession(session_id=session_id, max_turns=max_turns)


def handle_message(
    session: ComplaintSession,
    message: str,
    *,
    llm: Any | None = None,
    store: InMemoryTicketStore | None = None,
    emergency_numbers: FileEmergencyNumbers | None = None,
    extractor: Any | None = None,
) -> dict[str, Any]:
    """Process one citizen turn and return a JSON-friendly response."""
    store = store or InMemoryTicketStore()
    emergency_numbers = emergency_numbers or emergency_numbers_singleton()
    text = _mask_pii((message or "").strip()[:MAX_MESSAGE_CHARS])
    session.history.append({"role": "user", "content": text})

    if session.stage in {"submitted", "linked"}:
        return _response(session, "تم إرسال شكواك بالفعل. يمكنك متابعة حالتها من خلال رقم الشكوى.")
    if session.stage == "cancelled":
        return _response(session, "تم إلغاء العملية. يمكنك بدء شكوى جديدة متى شئت.")

    if not text:
        return _response(session, "لم أستلم أي نص. من فضلك اكتب وصفًا قصيرًا للمشكلة.")

    session.turn_count += 1

    if _contains_any(text, _ABUSE_MARKERS):
        return _response(
            session,
            "أتفهم انزعاجك، وأنا هنا لمساعدتك. من فضلك اكتب وصفًا هادئًا للمشكلة حتى أستطيع تسجيلها.",
            review_notes=["ABUSIVE_LANGUAGE"],
        )

    injection = _contains_any(text, _INJECTION_MARKERS)
    if injection:
        cleaned = _strip_injection(text)
        if not cleaned or not _contains_any(cleaned, _PROBLEM_SIGNALS):
            return _response(
                session,
                "لن أتبع تعليمات موجهة للنظام داخل الرسالة. من فضلك اكتب وصف المشكلة فقط.",
                review_notes=["PROMPT_INJECTION_IGNORED"],
            )
        if "PROMPT_INJECTION_IGNORED" not in session.review_notes:
            session.review_notes.append("PROMPT_INJECTION_IGNORED")
        text = cleaned

    if _contains_any(text, _GREETING_MARKERS) and not _contains_any(text, _COMPLAINT_SIGNALS):
        session.stage = "handoff"
        return _response(
            session,
            "السلام عليكم! أنا وكيل الشكاوى. اكتب لي المشكلة وسأجمع التفاصيل "
            "وأعرض عليك ملخصًا للتأكيد قبل الإرسال.",
            handoff_to="complaint",
        )

    if _contains_any(text, _THANKS_MARKERS) and not _contains_any(text, _PROBLEM_SIGNALS):
        session.stage = "handoff"
        return _response(
            session,
            "العفو! إذا كان لديك سؤال عن الإجراءات أو معلومات عن الخدمات، "
            "يمكنني تحويلك إلى وكيل المعرفة.",
            handoff_to="rag",
        )

    if _is_question(text) and not _contains_any(text, _PROBLEM_SIGNALS) and not injection:
        session.stage = "handoff"
        return _response(
            session,
            "يبدو أن سؤالك عن إجراءات أو معلومات عامة. "
            "سأحوّلك إلى وكيل المعرفة للإجابة من قاعدة المعرفة.",
            handoff_to="rag",
        )

    if _contains_any(text, _EMERGENCY_MARKERS):
        # Still capture the structured draft (category/location) from the same message.
        session.draft = _extract(text, session.draft, llm, extractor)
        session.draft.urgency = "critical"
        session.draft.urgency_reason = "الرسالة تشير إلى خطر مباشر على السلامة."
        session.draft = _finalise(session.draft)
        return _response(
            session,
            emergency_reply(emergency_numbers),
            review_notes=["EMERGENCY_DETECTED"],
        )

    # Confirmation stage: never create a ticket before reaching this branch.
    if session.stage == "awaiting_confirmation":
        if is_confirmation(text):
            if session.pending_duplicate_id and is_link_request(text):
                existing = store.get(session.pending_duplicate_id)
                if existing:
                    store.add_note(existing.ticket_id, f"LINKED_DUPLICATE:{session.session_id}")
                    session.stage = "linked"
                    session.ticket = to_public_dict(existing)
                    return _response(
                        session,
                        f"تم ربط شكواك بالشكوى القائمة رقم {existing.ticket_id}. "
                        "سيتابع فريق المراجعة الشكوى الأصلية.",
                    )
            return _submit(session, store)
        if is_rejection(text):
            session.stage = "collecting"
            return _response(
                session,
                "تمام، لم يتم الإرسال. ما التعديل الذي تريده؟ اكتب التصحيح وسأحدّث الملخص.",
            )
        # Treat any other message as an edit to the draft, then show the summary again.
        session.draft = _extract(text, session.draft, llm, extractor)
        session.stage = "awaiting_confirmation"
        return _confirmation_response(session, store)

    # Collecting stage.
    session.draft = _extract(text, session.draft, llm, extractor)
    if session.draft.missing_fields and session.turn_count < session.max_turns:
        question = follow_up_question(session.draft)
        return _response(session, question or "هل يمكنك إضافة تفاصيل أكثر عن المشكلة؟")

    return _confirmation_response(session, store)


def _extract(
    text: str, previous: ComplaintDraft, llm: Any | None, extractor: Any | None
) -> ComplaintDraft:
    if extractor is not None:
        return _finalise(extractor(text, previous))
    if llm is not None:
        draft, _notes = extract_with_llm(llm, text, previous)
        return draft
    return extract_with_rules(text, previous)


def _is_question(text: str) -> bool:
    normalized = normalize_arabic(text).strip().lower()
    return normalized.startswith(_QUESTION_STARTS) or "؟" in normalized or normalized.endswith("?")


def _confirmation_response(session: ComplaintSession, store: InMemoryTicketStore) -> dict[str, Any]:
    draft = session.draft
    duplicate = store.find_similar(
        category=draft.category or "",
        description=draft.description,
        location=draft.location.model_dump(),
    )
    session.pending_duplicate_id = duplicate[0].ticket_id if duplicate else None
    session.pending_duplicate_similarity = duplicate[1] if duplicate else None
    session.stage = "awaiting_confirmation"

    reply = summary_ar(draft)
    if duplicate:
        ticket, similarity = duplicate
        reply += (
            f"\n\nتوجد شكوى مشابهة مفتوحة برقم {ticket.ticket_id} "
            f"(نسبة التشابه {similarity:.0%}). إذا أردت ربط شكواك بها بدل إنشاء شكوى جديدة، "
            "اكتب: نعم اربطها."
        )
    reply += "\n\nهل تأكد إرسال الشكوى؟"
    return _response(session, reply, requires_confirmation=True)


def _draft_fingerprint(draft: ComplaintDraft) -> str:
    """Stable key for the submitted draft (no request id, so retries deduplicate)."""
    payload = "|".join(
        [
            draft.title,
            draft.description,
            draft.category or "",
            draft.location.governorate,
            draft.location.city,
            draft.location.street,
            draft.location.landmark,
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _submit(session: ComplaintSession, store: InMemoryTicketStore) -> dict[str, Any]:
    draft = session.draft
    current = store.get(session.pending_duplicate_id) if session.pending_duplicate_id else None
    if current and is_link_request(session.history[-1]["content"] if session.history else ""):
        store.add_note(current.ticket_id, f"LINKED_DUPLICATE:{session.session_id}")
        session.stage = "linked"
        session.ticket = to_public_dict(current)
        return _response(
            session,
            f"تم ربط شكواك بالشكوى القائمة رقم {current.ticket_id}.",
        )

    ticket = store.create(
        title=draft.title or "شكوى بدون عنوان",
        description=draft.description,
        category=draft.category or "Environment",
        authority=draft.authority or authority_for_category(draft.category) or "المديرية العامة",
        location=draft.location.model_dump(),
        urgency=draft.urgency,
        urgency_reason=draft.urgency_reason,
        incident_date=draft.incident_date,
        attachments_mentioned=draft.attachments_mentioned,
        contact_preference=draft.contact_preference,
        linked_to=current.ticket_id if current else None,
        review_notes=[f"MISSING_FIELD:{field}" for field in draft.missing_fields],
        # A client retry or a double confirmation of the same draft returns the same ticket.
        idempotency_key=f"{session.session_id}:{_draft_fingerprint(draft)}",
    )
    session.stage = "submitted"
    session.ticket = to_public_dict(ticket)
    reply = (
        f"تم إرسال شكواك بنجاح. رقم الشكوى: {ticket.ticket_id}. "
        f"الحالة الحالية: قيد المراجعة ({STATUS_PENDING}). "
        "يمكنك استخدام رقم الشكوى لمتابعة الحالة."
    )
    return _response(session, reply, ticket=to_public_dict(ticket))


def _response(
    session: ComplaintSession,
    reply: str,
    *,
    ticket: dict[str, Any] | None = None,
    handoff_to: str | None = None,
    requires_confirmation: bool = False,
    review_notes: list[str] | None = None,
) -> dict[str, Any]:
    draft = session.draft
    for note in review_notes or []:
        if note not in session.review_notes:
            session.review_notes.append(note)
    response = {
        "session_id": session.session_id,
        "stage": session.stage,
        "reply_ar": reply,
        "draft": draft.model_dump(mode="json"),
        "missing_fields": list(draft.missing_fields),
        "requires_confirmation": requires_confirmation,
        "ticket": ticket or session.ticket,
        "handoff_to": handoff_to,
        "review_notes": list(session.review_notes),
    }
    session.history.append({"role": "assistant", "content": reply})
    return response


__all__ = [
    "ComplaintDraft",
    "ComplaintLocation",
    "ComplaintSession",
    "extract_with_llm",
    "extract_with_rules",
    "follow_up_question",
    "handle_message",
    "is_confirmation",
    "is_rejection",
    "looks_like_complaint",
    "missing_fields",
    "new_session",
    "summary_ar",
]
