"""Offline retrieval quality on the Arabic golden question set.

The numbers are measured on the sample knowledge base shipped with the project and on the
deterministic hashing embedder. They are a regression guard, not a claim of production
quality: with a real embedding model the same test should be re-run.
"""

import json
from pathlib import Path

import pytest

from app.knowledge_base import HashingEmbeddingProvider, InMemoryKnowledgeBase
from app.utils.arabic_normalizer import normalize_arabic

BACKEND = Path(__file__).resolve().parents[2]
GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "rag_questions.json"
KNOWLEDGE = BACKEND / "data" / "knowledge"


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def kb() -> InMemoryKnowledgeBase:
    store = InMemoryKnowledgeBase(HashingEmbeddingProvider(1024))
    store.ingest_directory(str(KNOWLEDGE))
    return store


def _retrieve(kb: InMemoryKnowledgeBase, question: str, k: int = 5):
    embedding = kb.embedding_provider.embed(normalize_arabic(question, fold_taa_marbuta=True))
    return kb.search(embedding, top_k=k, threshold=0.05, query_text=normalize_arabic(question))


def test_golden_dataset_has_enough_cases(data):
    assert len(data["questions"]) >= 30
    assert len(data["unanswerable"]) >= 4
    assert all(q["expected_documents"] for q in data["questions"])


def test_hit_at_3_and_recall_at_5(data, kb):
    hit_at_1 = hit_at_3 = 0
    reciprocal_ranks: list[float] = []
    recalls: list[float] = []
    misses: list[str] = []

    for case in data["questions"]:
        results = _retrieve(kb, case["question"])
        titles = [r.title for r in results]
        expected = set(case["expected_documents"])

        hit_at_1 += bool(expected & set(titles[:1]))
        hit_at_3 += bool(expected & set(titles[:3]))
        recalls.append(len(expected & set(titles)) / len(expected))
        rank = next((i + 1 for i, title in enumerate(titles) if title in expected), None)
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        if not expected & set(titles[:3]):
            misses.append(f"{case['id']}: {case['question']} -> {titles[:3]}")

    total = len(data["questions"])
    hit_1 = hit_at_1 / total
    hit_3 = hit_at_3 / total
    recall_5 = sum(recalls) / total
    mrr = sum(reciprocal_ranks) / total

    print(
        f"\nRAG golden metrics: hit@1={hit_at_1}/{total} ({hit_1:.1%}) "
        f"hit@3={hit_at_3}/{total} ({hit_3:.1%}) "
        f"recall@5={recall_5:.1%} MRR={mrr:.3f}"
    )

    assert hit_3 >= 0.95, misses
    assert recall_5 >= 0.95, misses
    assert hit_1 >= 0.80, misses
    assert mrr >= 0.85, misses


def test_unanswerable_offline_cases_have_no_lexical_support(data, kb):
    from app.agents.rag_agent import run_rag_agent
    from app.services.emergency_numbers import emergency_numbers_singleton
    from app.services.offline_llm import GroundedTemplateLLM

    class History:
        def add_turn(self, *args, **kwargs):
            pass

        def get_recent_turns(self, n=5):
            return []

        def clear(self):
            pass

    agent_llm = GroundedTemplateLLM()
    for case in data["unanswerable"]:
        if case.get("requires_llm"):
            continue
        result = run_rag_agent(
            {
                "query": case["question"],
                "ticket_id": "GOLDEN",
                "session_id": "GOLDEN",
                "conversation_history": [],
                "tool_calls": 0,
            },
            agent_llm,
            kb,
            kb.embedding_provider,
            History(),
            emergency_numbers_singleton(),
        )
        assert result["found_in_kb"] is False, case["id"]
        assert "المعلومات غير متوفرة" in result["answer"]
