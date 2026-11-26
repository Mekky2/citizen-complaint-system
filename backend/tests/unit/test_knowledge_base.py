"""Unit tests for chunking, loading, embeddings, ingestion and retrieval."""

import math
from pathlib import Path

import pytest

from app.core.config import Settings
from app.knowledge_base import HashingEmbeddingProvider, InMemoryKnowledgeBase
from app.knowledge_base.chunking import chunk_text, estimate_tokens
from app.knowledge_base.embeddings import build_embedding_provider
from app.knowledge_base.loaders import (
    DocumentError,
    UnsupportedDocumentError,
    iter_documents,
    load_document,
)
from app.utils.arabic_normalizer import normalize_arabic

BACKEND = Path(__file__).resolve().parents[2]
KNOWLEDGE = BACKEND / "data" / "knowledge"


# --------------------------------------------------------------------- chunking
def test_chunking_splits_on_headings_and_keeps_them():
    text = "# العنوان\n\n## القسم الأول\nنص عربي قصير.\n\n## القسم الثاني\nنص آخر."
    chunks = chunk_text(text, max_tokens=50, overlap_tokens=5)

    assert [c.section for c in chunks] == ["القسم الأول", "القسم الثاني"]
    assert all(c.token_estimate <= 50 for c in chunks)


def test_chunking_respects_token_budget_and_overlap():
    sentences = " ".join(f"هذه جملة رقم {i} عن الشارع والخدمات." for i in range(80))
    chunks = chunk_text(sentences, max_tokens=60, overlap_tokens=10)

    assert len(chunks) > 1
    assert all(c.token_estimate <= 60 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_chunking_rejects_impossible_limits():
    with pytest.raises(ValueError):
        chunk_text("نص", max_tokens=0)
    with pytest.raises(ValueError):
        chunk_text("نص", max_tokens=10, overlap_tokens=10)
    assert chunk_text("   ") == []


def test_estimate_tokens_is_conservative():
    assert estimate_tokens("كلمة واحدة") >= 2
    assert estimate_tokens("") == 0


# ----------------------------------------------------------------------- loaders
def test_markdown_front_matter_and_stable_hash(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text(
        '---\ntitle: "الإنارة"\nauthority: "مديرية الكهرباء"\n---\n\n# الإنارة\n\nنص.',
        encoding="utf-8",
    )
    first = load_document(path, root=tmp_path)
    second = load_document(path, root=tmp_path)

    assert first.title == "الإنارة"
    assert first.authority == "مديرية الكهرباء"
    assert first.content.startswith("# الإنارة")
    assert first.source == "doc.md"
    assert first.content_hash == second.content_hash
    assert first.doc_id == second.doc_id


def test_title_falls_back_to_h1_then_filename(tmp_path):
    with_h1 = tmp_path / "a.md"
    with_h1.write_text("# عنوان من المستند\n\nنص", encoding="utf-8")
    assert load_document(with_h1, root=tmp_path).title == "عنوان من المستند"

    no_h1 = tmp_path / "b.md"
    no_h1.write_text("نص فقط", encoding="utf-8")
    assert load_document(no_h1, root=tmp_path).title == "b"


def test_empty_and_unsupported_documents_are_rejected(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("---\ntitle: x\n---\n", encoding="utf-8")
    with pytest.raises(DocumentError):
        load_document(empty, root=tmp_path)

    bad = tmp_path / "file.csv"
    bad.write_text("a,b", encoding="utf-8")
    with pytest.raises(UnsupportedDocumentError):
        load_document(bad, root=tmp_path)


def test_iter_documents_is_sorted_and_skips_unsupported(tmp_path):
    (tmp_path / "b.md").write_text("# ب\nنص", encoding="utf-8")
    (tmp_path / "a.md").write_text("# أ\nنص", encoding="utf-8")
    (tmp_path / "x.csv").write_text("a,b", encoding="utf-8")

    documents = iter_documents(tmp_path)
    assert [d.source for d in documents] == ["a.md", "b.md"]


def test_real_knowledge_directory_loads():
    documents = iter_documents(KNOWLEDGE)
    assert len(documents) == 15
    assert all(d.language == "ar" and d.content for d in documents)


# -------------------------------------------------------------------- embeddings
def test_hashing_embeddings_are_deterministic_and_normalized():
    provider = HashingEmbeddingProvider(128)
    first = provider.embed(normalize_arabic("تسريب مياه في الشارع"))
    second = provider.embed(normalize_arabic("تسريب مياه في الشارع"))
    other = provider.embed(normalize_arabic("ضوضاء من ورشة"))

    assert first == second
    assert first != other
    assert len(first) == 128
    assert math.isclose(math.sqrt(sum(v * v for v in first)), 1.0, rel_tol=1e-9)


def test_build_embedding_provider_selects_hashing_offline():
    settings = Settings(embedding_provider="hashing", embedding_dimension=64)
    provider = build_embedding_provider(settings)
    assert isinstance(provider, HashingEmbeddingProvider)
    assert provider.dimension == 64
    assert provider.requires_lexical_overlap is True


def test_build_embedding_provider_rejects_bad_configuration():
    with pytest.raises(ValueError):
        build_embedding_provider(Settings(embedding_provider="unknown"))
    with pytest.raises(ValueError):
        build_embedding_provider(
            Settings(embedding_provider="openai_compatible", embedding_api_key="")
        )


# --------------------------------------------------------------------- ingestion
def _write_doc(root: Path, name: str, title: str, body: str) -> None:
    (root / name).write_text(
        f'---\ntitle: "{title}"\nlanguage: "ar"\n---\n\n# {title}\n\n{body}',
        encoding="utf-8",
    )


def test_ingestion_is_idempotent_and_updates_changed_documents(tmp_path):
    _write_doc(tmp_path, "garbage.md", "النظافة", "إزالة الزبال من الشارع.")
    kb = InMemoryKnowledgeBase(HashingEmbeddingProvider(64))

    first = kb.ingest_directory(str(tmp_path))
    assert first == {"inserted": 1, "updated": 0, "skipped": 0, "documents": 1}
    chunks_after_first = kb.chunk_count

    second = kb.ingest_directory(str(tmp_path))
    assert second == {"inserted": 0, "updated": 0, "skipped": 1, "documents": 1}
    assert kb.chunk_count == chunks_after_first

    _write_doc(tmp_path, "garbage.md", "النظافة", "إزالة الزبال والقمامة من الشارع يوميًا.")
    third = kb.ingest_directory(str(tmp_path))
    assert third == {"inserted": 0, "updated": 1, "skipped": 0, "documents": 1}
    assert len(kb.documents) == 1
    assert kb.chunk_count >= 1


def test_real_knowledge_ingestion_and_hybrid_search():
    kb = InMemoryKnowledgeBase(HashingEmbeddingProvider(1024))
    stats = kb.ingest_directory(str(KNOWLEDGE))
    assert stats["inserted"] == 15
    assert stats["documents"] == 15
    assert kb.chunk_count > 100

    query = "الزبال متراكم في الشارع"
    embedding = kb.embedding_provider.embed(normalize_arabic(query, fold_taa_marbuta=True))
    results = kb.search(embedding, top_k=3, threshold=0.05, query_text=normalize_arabic(query))

    assert results[0].title == "النظافة والزبال"
    titles = [r.title for r in results]
    assert len(titles) == len(set(titles)), "search must not return duplicate documents"


def test_search_honours_threshold_and_top_k():
    kb = InMemoryKnowledgeBase(HashingEmbeddingProvider(64))
    kb.ingest_directory(str(KNOWLEDGE))
    embedding = kb.embedding_provider.embed(normalize_arabic("القمامة"))

    assert kb.search(embedding, top_k=2, threshold=0.99) == []
    assert len(kb.search(embedding, top_k=2, threshold=0.0)) <= 2
