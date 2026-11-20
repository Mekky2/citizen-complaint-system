"""RAG Agent implementation for citizen inquiries.

The agent answers Arabic questions using ONLY the project knowledge base. It never answers
from model memory about laws, fees, procedures or phone numbers. When retrieval finds
nothing above the similarity threshold it returns an Arabic "not found" answer with
``found_in_kb=False`` so the caller can suggest contacting the authority or filing a complaint.

Public entry point:

    run_rag_agent(state, llm, knowledge_base, embedding_provider, conversation,
                  emergency_numbers) -> dict[str, Any]

The function never raises: every failure becomes a polite Arabic fallback with a review note.
"""

import json
import logging
import re
from typing import Any

from app.agents.rag_agent.interfaces import (
    ConversationHistory,
    EmbeddingProvider,
    EmergencyNumbersProvider,
)
from app.agents.rag_agent.prompts_arabic import GENERATE_SYSTEM
from app.agents.rag_agent.schemas import AnswerSource, RetrievalResult
from app.utils.arabic_normalizer import normalize_arabic

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
DEFAULT_THRESHOLD = 0.55
MAX_QUERY_CHARS = 2000
MAX_HISTORY_TURNS = 10

# Prompt-injection markers (Arabic + English). The text is still treated as data; these
# patterns only make the agent refuse obvious attempts early.
_INJECTION_MARKERS = (
    "تجاهل التعليمات",
    "تجاهل كل التعليمات",
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
    "reveal your instructions",
)

_GREETINGS = (
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

_EMERGENCY_MARKERS = (
    "طوارئ",
    "حريق",
    "احتراق",
    "بيولع",
    "ولعت",
    "انفجار",
    "انفجر",
    "غاز",
    "صعق",
    "سلك مكشوف",
    "سلك كهرباء",
    "سلك كهربا",
    "كابل مكشوف",
    "كيبل مكشوف",
    "ماس كهربائي",
    "ماس كهرباء",
    "اسلاك مكشوفه",
    "أسلاك مكشوفة",
    "اسعاف",
    "إسعاف",
    "شرطة",
    "شرطه",
    "خطر",
    "انهيار",
    "غرق",
)

_COMPLAINT_MARKERS = (
    "شكوى",
    "شكوه",
    "بلاغ",
    "ابلاغ",
    "أبلغ",
    "اريد اقدم",
    "عايز اقدم",
    "مشكلة",
    "مشكله",
)

_QUESTION_MARKERS = (
    "كيف",
    "ازاي",
    "إزاي",
    "هل",
    "ما هي",
    "ما هو",
    "ماذا",
    "متى",
    "امتى",
    "لماذا",
    "ليه",
    "أين",
    "اين",
    "فين",
    "كم",
    "إيه",
    "ايه",
    "قد إيه",
    "قد ايه",
    "what",
    "how",
    "when",
    "where",
    "why",
)

_NOT_FOUND_ANSWER = (
    "عذرًا، المعلومات غير متوفرة في قاعدة المعرفة الخاصة بالمنصة. "
    "يمكنك التواصل مع الجهة المختصة مباشرة، أو تقديم شكوى من خلال المنصة وسيتابعها فريق "
    "المراجعة البشري."
)


def _marker_pattern(marker: str) -> str:
    """Word-start pattern for an Arabic marker, allowing common proclitics."""
    keyword = normalize_arabic(marker, fold_taa_marbuta=True)
    if " " in keyword:
        return r"(?:^|[^\w])(?:[وف])?(?:ال)?" + re.escape(keyword)
    return r"(?:^|[^\w])(?:(?:[وفبكل])?ال)?" + re.escape(keyword)


def _has_marker(normalized: str, raw_lower: str, marker: str) -> bool:
    """Match Arabic markers on word boundaries and English markers as whole words."""
    if marker.isascii():
        return re.search(r"(?<!\w)" + re.escape(marker.lower()) + r"(?!\w)", raw_lower) is not None
    return re.search(_marker_pattern(marker), normalized) is not None


def _has_any_marker(normalized: str, raw_lower: str, markers: tuple[str, ...]) -> bool:
    return any(_has_marker(normalized, raw_lower, marker) for marker in markers)


class RAGAgent:
    """RAG Agent for citizen inquiries."""

    def __init__(
        self,
        llm: Any,
        knowledge_base: Any,
        embedding_provider: EmbeddingProvider,
        conversation: ConversationHistory,
        emergency_numbers: EmergencyNumbersProvider,
        *,
        top_k: int = DEFAULT_TOP_K,
        threshold: float | None = None,
    ):
        self.llm = llm
        self.kb = knowledge_base
        self.embedding_provider = embedding_provider
        self.conversation = conversation
        self.emergency_numbers = emergency_numbers
        self.top_k = top_k
        self.threshold = (
            threshold
            if threshold is not None
            else getattr(embedding_provider, "default_threshold", DEFAULT_THRESHOLD)
        )
        self.tool_calls = 0
        self.tool_call_limit = 4

    # ------------------------------------------------------------------ intent
    def detect_intent(self, message: str) -> str:
        """Classify the message. English/mixed input is still processed (and answered in Arabic)."""
        normalized = normalize_arabic(message).lower()
        raw_lower = (message or "").lower()

        if _has_any_marker(normalized, raw_lower, _INJECTION_MARKERS):
            return "spam"

        if _has_any_marker(normalized, raw_lower, _EMERGENCY_MARKERS):
            return "emergency"

        if _has_any_marker(normalized, raw_lower, _GREETINGS):
            return "greeting"

        # A question about procedures is an inquiry, even when it contains the word "شكوى".
        if _has_any_marker(normalized, raw_lower, _QUESTION_MARKERS):
            return "inquiry"

        if _has_any_marker(normalized, raw_lower, _COMPLAINT_MARKERS):
            return "complaint"

        return "inquiry"

    # --------------------------------------------------------------- emergency
    def handle_emergency(self, message: str) -> dict[str, Any]:
        """Tell the citizen to call the official emergency number, then offer to file later."""
        numbers = self.emergency_numbers.get_all_numbers()

        normalized = normalize_arabic(message).lower()
        category = None
        for num in numbers:
            if num.get("id", "").lower() in normalized:
                category = num["id"]
                break

        relevant = [n for n in numbers if n["id"] == category] if category else numbers

        from app.services.emergency_numbers import arabic_description, arabic_name

        parts = [
            "في حالة الطوارئ، يُرجى الاتصال مباشرة بأرقام الطوارئ الرسمية فورًا، "
            "ولا تنتظر ردًا من المنصة.",
            "إليك الأرقام المتاحة:",
        ]
        for num in relevant:
            description = arabic_description(num)
            suffix = f" — {description}" if description else ""
            parts.append(f"• {arabic_name(num)}: {num['number']}{suffix}")
        parts.append("")
        parts.append(
            "بعد اتخاذ الإجراء الطارئ يمكنك رفع شكوى لاحقًا من خلال المنصة لمتابعة المشكلة."
        )

        sources = [
            AnswerSource(
                title=f"أرقام الطوارئ - {num['id']}",
                excerpt=(
                    f"{arabic_name(num)}: {num['number']}"
                    + (f" - {arabic_description(num)}" if arabic_description(num) else "")
                ),
            )
            for num in relevant
        ]

        return self._result(
            answer="\n".join(parts),
            sources=sources,
            confidence="high",
            found_in_kb=True,
            review_notes=[],
        )

    # ----------------------------------------------------------------- inquiry
    def handle_inquiry(self, query: str) -> dict[str, Any]:
        """Retrieve, then generate an Arabic answer grounded in the retrieved context."""
        try:
            normalized_query = normalize_arabic(query)[:MAX_QUERY_CHARS]
            if not normalized_query:
                return self._not_found("EMPTY_QUERY")

            embedding = self.embedding_provider.embed(normalized_query)
            if not isinstance(embedding, list) or not embedding:
                raise ValueError("embedding provider returned no vector")

            results: list[RetrievalResult] = list(self._search(embedding, normalized_query))
            results = [r for r in results if r.similarity >= self.threshold][: self.top_k]

            if not results:
                return self._not_found("NO_RELEVANT_RESULTS")

            if not self._has_lexical_overlap(normalized_query, results):
                return self._not_found("NO_LEXICAL_SUPPORT")

            context = "\n\n".join(f"[{i}] {r.title}\n{r.excerpt}" for i, r in enumerate(results, 1))
            history = self._history_block()
            system_prompt = GENERATE_SYSTEM.replace("<context>", context)
            user_prompt = (
                (f"{history}\n\n" if history else "")
                + f"<retrieved_context>\n{context}\n</retrieved_context>\n\n"
                + f"الاستفسار: {query}\n\nالإجابة:"
            )

            raw_answer = self.llm.complete(system_prompt, user_prompt)
            answer, used_indexes = self._parse_answer(raw_answer, results)

            if not answer:
                return self._not_found("EMPTY_LLM_ANSWER")

            sources = [
                AnswerSource(
                    title=results[i - 1].title,
                    excerpt=results[i - 1].excerpt,
                    page=results[i - 1].page,
                )
                for i in used_indexes
            ]
            answer = self._with_citation(answer, sources)

            avg_similarity = sum(r.similarity for r in results) / len(results)
            confidence = (
                "high" if avg_similarity >= 0.85 else "medium" if avg_similarity >= 0.7 else "low"
            )

            self._remember("user", query)
            self._remember("assistant", answer)

            notes = ["LOW_SIMILARITY"] if confidence == "low" else []
            return self._result(
                answer=answer,
                sources=sources,
                confidence=confidence,
                found_in_kb=True,
                review_notes=notes,
            )

        except Exception as exc:  # any provider/store failure -> polite fallback, never crash
            logger.error("RAG agent inquiry failed: %s", type(exc).__name__)
            return self._result(
                answer=(
                    "حدث خطأ أثناء محاولة البحث في قاعدة المعرفة. يُرجى المحاولة مرة أخرى "
                    "لاحقًا أو التواصل مع الجهة المختصة."
                ),
                sources=[],
                confidence="low",
                found_in_kb=False,
                review_notes=["RAG_ERROR"],
            )

    # ------------------------------------------------------------------ others
    def handle_greeting(self, message: str) -> dict[str, Any]:
        return self._result(
            answer=(
                "السلام عليكم! كيف يمكنني مساعدتك اليوم؟ يمكنني شرح إجراءات تقديم الشكوى، "
                "أو الإجابة عن الأسئلة الشائعة، أو مساعدتك في متابعة شكوى قائمة."
            ),
            sources=[],
            confidence="high",
            found_in_kb=True,
            review_notes=[],
        )

    def handle_complaint(self, message: str) -> dict[str, Any]:
        return self._result(
            answer=(
                "يبدو أنك تريد تقديم شكوى. يمكنني توجيهك إلى وكيل الشكاوى الذي سيجمع "
                "التفاصيل المطلوبة ويعرض عليك ملخصًا للتأكيد قبل الإرسال."
            ),
            sources=[],
            confidence="high",
            found_in_kb=True,
            handoff_to="complaint",
            review_notes=["USER_WANTS_TO_SUBMIT_COMPLAINT"],
        )

    # -------------------------------------------------------------------- run
    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        query = str(state.get("query", "") or "").strip()
        conversation_history = state.get("conversation_history") or []
        incoming_calls = state.get("tool_calls", 0)
        self.tool_call_limit = int(state.get("tool_call_limit", 4) or 4)

        if isinstance(incoming_calls, int) and incoming_calls > 0:
            self.tool_calls = incoming_calls

        self._restore_history(conversation_history)

        if not query:
            return self._not_found("EMPTY_QUERY")

        if self.tool_calls >= self.tool_call_limit:
            return self._result(
                answer=(
                    "تم الوصول إلى الحد الأقصى لعدد المحاولات في هذه المحادثة. "
                    "يُرجى بدء محادثة جديدة أو التواصل مع الجهة المختصة."
                ),
                sources=[],
                confidence="low",
                found_in_kb=False,
                review_notes=["TOOL_CALL_LIMIT_EXCEEDED"],
            )

        self.tool_calls += 1

        intent = self.detect_intent(query)
        if intent == "emergency":
            return self.handle_emergency(query)
        if intent == "greeting":
            return self.handle_greeting(query)
        if intent == "complaint":
            return self.handle_complaint(query)
        if intent == "spam":
            return self._result(
                answer=(
                    "أعتذر، لا يمكنني التعامل مع هذا الطلب. إذا كان لديك استفسار عن خدمات "
                    "البلدية أو إجراءات تقديم شكوى، فسأكون سعيدًا بمساعدتك."
                ),
                sources=[],
                confidence="high",
                found_in_kb=False,
                review_notes=["PROMPT_INJECTION_OR_SPAM"],
            )
        return self.handle_inquiry(query)

    # ----------------------------------------------------------------- helpers
    def _result(
        self,
        *,
        answer: str,
        sources: list[AnswerSource],
        confidence: str,
        found_in_kb: bool,
        review_notes: list[str],
        handoff_to: str | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "completed",
            "handoff_to": handoff_to,
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
            "found_in_kb": found_in_kb,
            "tool_calls": self.tool_calls,
            "review_notes": review_notes,
        }

    def _not_found(self, note: str) -> dict[str, Any]:
        return self._result(
            answer=_NOT_FOUND_ANSWER,
            sources=[],
            confidence="low",
            found_in_kb=False,
            review_notes=[note],
        )

    def _has_lexical_overlap(self, query: str, results: list[RetrievalResult]) -> bool:
        """Guard against answering from embedding noise with no shared content words.

        Only enforced for providers that declare ``requires_lexical_overlap`` (the offline
        hashing provider). Real embedding models can match paraphrases with no shared words.
        """
        if not getattr(self.embedding_provider, "requires_lexical_overlap", False):
            return True
        try:
            from app.knowledge_base.keywords import tokenize_for_search
        except Exception:  # pragma: no cover - import cycle safety
            return True
        query_tokens = set(tokenize_for_search(query))
        if not query_tokens:
            return True
        context = " ".join(f"{r.title} {r.excerpt}" for r in results)
        return bool(query_tokens & set(tokenize_for_search(context)))

    def _search(self, embedding: list[float], normalized_query: str) -> list[RetrievalResult]:
        """Call the store with hybrid search when it supports it, vector-only otherwise."""
        try:
            return self.kb.search(
                embedding,
                top_k=self.top_k,
                threshold=self.threshold,
                query_text=normalized_query,
            )
        except TypeError:
            return self.kb.search(embedding, top_k=self.top_k, threshold=self.threshold)

    def _remember(self, role: str, content: str) -> None:
        add_turn = getattr(self.conversation, "add_turn", None)
        if callable(add_turn):
            add_turn(role, content)

    def _restore_history(self, history: list[Any]) -> None:
        try:
            if self.conversation.get_recent_turns():
                return
        except Exception:
            return
        for turn in history[-MAX_HISTORY_TURNS:]:
            if isinstance(turn, dict) and turn.get("role") in {"user", "assistant"}:
                self._remember(turn["role"], str(turn.get("content", "")))

    def _history_block(self) -> str:
        try:
            turns = self.conversation.get_recent_turns()[-4:]
        except Exception:
            return ""
        if not turns:
            return ""
        lines = [f"{t.get('role', 'user')}: {t.get('content', '')}" for t in turns]
        return "سياق المحادثة السابقة:\n" + "\n".join(lines)

    @staticmethod
    def _parse_answer(raw: Any, results: list[RetrievalResult]) -> tuple[str, list[int]]:
        """Accept plain text or the JSON shape requested by the prompt."""
        if not isinstance(raw, str):
            return "", []
        text = raw.strip()
        if not text:
            return "", []

        candidate = text
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            candidate = text[start : end + 1]
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            return text, list(range(1, len(results) + 1))

        if not isinstance(data, dict):
            return text, list(range(1, len(results) + 1))

        answer = str(data.get("answer", "")).strip()
        used = data.get("sources_used")
        indexes = (
            [i for i in used if isinstance(i, int) and 1 <= i <= len(results)]
            if isinstance(used, list)
            else []
        )
        return answer, indexes or list(range(1, len(results) + 1))

    @staticmethod
    def _with_citation(answer: str, sources: list[AnswerSource]) -> str:
        if not sources or "المصدر:" in answer or "[Source:" in answer:
            return answer
        titles = "; ".join(dict.fromkeys(s.title for s in sources))
        return f"{answer}\n\nالمصدر: {titles}"


def run_rag_agent(
    state: dict[str, Any],
    llm: Any,
    knowledge_base: Any,
    embedding_provider: Any,
    conversation: ConversationHistory,
    emergency_numbers: EmergencyNumbersProvider,
) -> dict[str, Any]:
    """Entry point for the RAG Agent. Never raises."""
    try:
        agent = RAGAgent(
            llm=llm,
            knowledge_base=knowledge_base,
            embedding_provider=embedding_provider,
            conversation=conversation,
            emergency_numbers=emergency_numbers,
        )
        return agent.run(state)
    except Exception as exc:
        logger.error("RAG agent execution error: %s", type(exc).__name__, exc_info=True)
        return {
            "ticket_id": state.get("ticket_id", ""),
            "status": "completed",
            "handoff_to": None,
            "answer": ("حدث خطأ في الخدمة. يُرجى المحاولة مرة أخرى أو التواصل مع الجهة المختصة."),
            "sources": [],
            "confidence": "low",
            "found_in_kb": False,
            "tool_calls": state.get("tool_calls", 0) + 1,
            "review_notes": ["RAG_AGENT_ERROR"],
        }
