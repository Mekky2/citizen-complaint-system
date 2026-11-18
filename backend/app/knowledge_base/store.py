"""Knowledge-base stores: an in-memory store for tests/demos and a Supabase pgvector store.

Both implement the same tiny interface used by the RAG agent:

    search(query_embedding, top_k, threshold) -> list[RetrievalResult]
    ingest_document(...) / get_document_content(...) / get_all_documents()

Idempotency: a document is identified by its ``source`` path. Re-ingesting unchanged content
is skipped; changed content replaces the old chunks atomically (same document id).
"""

from __future__ import annotations

import math
from typing import Any

from app.agents.rag_agent.schemas import RetrievalResult
from app.knowledge_base.chunking import DEFAULT_MAX_TOKENS, DEFAULT_OVERLAP_TOKENS, chunk_text
from app.knowledge_base.embeddings import EmbeddingProvider
from app.knowledge_base.keywords import BM25Index, tokenize_for_search
from app.knowledge_base.loaders import KnowledgeDocument, load_document
from app.utils.arabic_normalizer import normalize_arabic

# Domain routing aliases: common citizen wording -> the document that actually answers it.
# These are synonyms, not answers; they only lift an already-relevant document. Keeping them
# here (next to the index) makes retrieval behaviour reviewable and testable offline.
_RAW_TITLE_ALIASES: dict[str, str] = {
    "كيفية تقديم شكوى": "تقديم شكوى رفع شكوى تسجيل شكوى",
    "حالات الشكوى ومعانيها": "حالة حالات معنى معاني مقبولة مرفوضة قيد المراجعة مكتملة",
    "المعلومات اللازمة لتقديم شكوى": "معلومات مستندات ورق أوراق مطلوب لازم بيانات مرفقات",
    "الزمن المتوقع للاستجابة": "مدة وقت يستغرق معالجة استجابة رد أيام ساعات",
    "المسالك والطرق": "طرق مسالك رصيف حفر أسفلت مطب طريق",
    "الإنارة العامة": "إنارة نور كشاف لمبة عمود ظلام",
    "المياه والصرف الصحي": "مياه ميه ماسورة تسريب صرف مجاري طفح",
    "النظافة والزبال": "نظافة زبال قمامة نفايات مخلفات إزالة",
    "الكهرباء والأسلاك": "كهرباء كهربا أسلاك سلك محول انقطاع",
    "الضوضاء": "ضوضاء ضجيج إزعاج صوت",
    "الترميم والبناء": "ترميم بناء مخالفات ترخيص رخصة",
    "النقل العام": "نقل مواصلات أتوبيس مترو مواعيد",
    "كيفية متابعة الشكوى": "متابعة أتابع أعرف حالة شكوتي وضع تتبع",
    "كيفية إرفاق الصور": "إرفاق صور صورة مرفق رفع",
    "خصوصية المعلومات": "خصوصية سرية بيانات حماية",
}

TITLE_ALIASES: dict[str, set[str]] = {
    title: set(tokenize_for_search(words)) for title, words in _RAW_TITLE_ALIASES.items()
}


def _cosine(left: list[float], right: list[float]) -> float:
    """Cosine similarity for already-normalized or arbitrary vectors."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return dot / (norm_left * norm_right)


def _chunk_rows(
    document: KnowledgeDocument,
    provider: EmbeddingProvider,
    *,
    max_tokens: int,
    overlap_tokens: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in chunk_text(document.content, max_tokens=max_tokens, overlap_tokens=overlap_tokens):
        normalized = normalize_arabic(chunk.text, fold_taa_marbuta=True)
        rows.append(
            {
                "document_id": document.doc_id,
                "source": document.source,
                "title": document.title,
                "section": chunk.section,
                "chunk_index": chunk.index,
                "content": chunk.text,
                "normalized_content": normalized,
                "token_estimate": chunk.token_estimate,
                "embedding": provider.embed(normalized),
                "metadata": document.metadata,
            }
        )
    return rows


class InMemoryKnowledgeBase:
    """In-memory vector store. Deterministic, fast, and ideal for offline tests."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    ):
        self.embedding_provider = embedding_provider
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.documents: dict[str, dict[str, Any]] = {}
        self.chunks: list[dict[str, Any]] = []
        self.last_ingest: dict[str, str] = {}
        self._bm25: BM25Index | None = None
        self._bm25_tokens: list[list[str]] = []
        self._title_tokens: list[list[str]] = []

    # ------------------------------------------------------------- ingestion
    def add_document(self, document: KnowledgeDocument) -> str:
        existing = self.documents.get(document.source)
        if existing and existing["content_hash"] == document.content_hash:
            self.last_ingest[document.source] = "skipped"
            return "skipped"

        rows = _chunk_rows(
            document,
            self.embedding_provider,
            max_tokens=self.max_tokens,
            overlap_tokens=self.overlap_tokens,
        )
        if existing:
            self.chunks = [c for c in self.chunks if c["source"] != document.source]

        self.documents[document.source] = {
            "id": document.doc_id,
            "source": document.source,
            "title": document.title,
            "authority": document.authority,
            "language": document.language,
            "updated_date": document.updated_date,
            "category": document.category,
            "source_type": document.source_type,
            "content": document.content,
            "content_hash": document.content_hash,
            "chunk_count": len(rows),
        }
        self.chunks.extend(rows)
        self._bm25 = None  # invalidate the lexical index
        status = "updated" if existing else "inserted"
        self.last_ingest[document.source] = status
        return status

    def ingest_document(
        self,
        file_path: str,
        title: str = "",
        authority: str = "",
        language: str = "",
        updated_date: str = "",
        category: str = "",
        source_type: str = "",
    ) -> str:
        """Load and ingest one file. Empty metadata keeps the file's front matter."""
        document = load_document(file_path)
        document = _with_overrides(
            document,
            title=title,
            authority=authority,
            language=language,
            updated_date=updated_date,
            category=category,
            source_type=source_type,
        )
        self.add_document(document)
        return document.doc_id

    def ingest_directory(self, root: str) -> dict[str, int]:
        """Ingest every supported file under ``root``. Safe to run repeatedly."""
        from app.knowledge_base.loaders import iter_documents

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "documents": 0}
        for document in iter_documents(root):
            status = self.add_document(document)
            stats[status] += 1
            stats["documents"] += 1
        return stats

    # -------------------------------------------------------------- retrieval
    def _ensure_keyword_index(self) -> None:
        if self._bm25 is None:
            self._bm25_tokens = [
                tokenize_for_search(
                    " ".join(
                        [
                            str(chunk.get("title") or ""),
                            str(chunk.get("title") or ""),
                            str(chunk.get("section") or ""),
                            chunk["normalized_content"],
                        ]
                    )
                )
                for chunk in self.chunks
            ]
            self._title_tokens = [
                tokenize_for_search(
                    f"{chunk.get('title') or ''} {chunk.get('section') or ''}"
                )
                for chunk in self.chunks
            ]
            self._bm25 = BM25Index(self._bm25_tokens)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.15,
        *,
        query_text: str | None = None,
    ) -> list[RetrievalResult]:
        """Hybrid search: BM25 over Arabic keywords + cosine over embeddings.

        ``query_text`` is optional so the store still satisfies the minimal vector-only
        interface used by the RAG agent protocol and by simple fakes.
        """
        query_tokens = tokenize_for_search(query_text) if query_text else []
        if query_tokens:
            self._ensure_keyword_index()

        scored: list[tuple[float, dict[str, Any]]] = []
        for index, chunk in enumerate(self.chunks):
            cosine = max(0.0, _cosine(query_embedding, chunk["embedding"]))
            if query_tokens and self._bm25 is not None:
                lexical = self._bm25.normalized(query_tokens, index)
                title_tokens = set(self._title_tokens[index]) if self._title_tokens else set()
                overlap = len(set(query_tokens) & title_tokens) / max(len(set(query_tokens)), 1)
                lexical = 0.65 * lexical + 0.35 * overlap
                similarity = 0.7 * lexical + 0.3 * cosine
                aliases = TITLE_ALIASES.get(str(chunk.get("title") or ""), set())
                if aliases:
                    similarity += 0.12 * len(set(query_tokens) & aliases)
            else:
                similarity = cosine
            if similarity >= threshold:
                scored.append((similarity, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)

        results: list[RetrievalResult] = []
        seen_titles: set[str] = set()
        for similarity, chunk in scored:
            # Prefer document diversity: five chunks from one document are less useful to the
            # answer generator than five different authorities.
            if chunk["title"] in seen_titles:
                continue
            seen_titles.add(chunk["title"])
            excerpt = chunk["content"]
            if len(excerpt) > 600:
                excerpt = excerpt[:597].rstrip() + "..."
            results.append(
                RetrievalResult(
                    document_id=chunk["document_id"],
                    title=chunk["title"],
                    excerpt=excerpt,
                    page=None,
                    similarity=round(min(max(similarity, 0.0), 1.0), 6),
                )
            )
            if len(results) >= max(1, top_k):
                break
        return results

    # ----------------------------------------------------------------- helpers
    def get_document_content(self, document_id: str) -> str | None:
        for doc in self.documents.values():
            if doc["id"] == document_id or doc["source"] == document_id:
                return doc["content"]
        return None

    def get_all_documents(self) -> list[dict[str, Any]]:
        return [{k: v for k, v in doc.items() if k != "content"} for doc in self.documents.values()]

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)


def _with_overrides(document: KnowledgeDocument, **overrides: str) -> KnowledgeDocument:
    data = document.__dict__.copy()
    for key, value in overrides.items():
        if value:
            data[key] = value
    return KnowledgeDocument(**data)


class PgVectorKnowledgeBase:
    """Supabase/PostgreSQL + pgvector store.

    Requires the ``psycopg`` driver and the SQL in ``migrations/001_knowledge_base.sql``.
    The connection string is ``DATABASE_URL`` (keep the ``postgresql+psycopg://`` prefix used
    elsewhere in the project; it is normalized here).
    """

    def __init__(
        self,
        dsn: str,
        embedding_provider: EmbeddingProvider,
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    ):
        if not dsn:
            raise ValueError("DATABASE_URL is required for the pgvector store")
        self.dsn = dsn.replace("postgresql+psycopg://", "postgresql://", 1)
        self.embedding_provider = embedding_provider
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    @staticmethod
    def _vector_literal(vector: list[float]) -> str:
        return "[" + ",".join(f"{value:.7f}" for value in vector) + "]"

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - depends on the environment
            raise RuntimeError(
                "The pgvector store needs 'psycopg'. Install it with: "
                "pip install 'psycopg[binary]>=3.1'"
            ) from exc
        return psycopg.connect(self.dsn)

    def add_document(self, document: KnowledgeDocument) -> str:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "select id, content_hash from knowledge_documents where source = %s",
                (document.source,),
            )
            row = cursor.fetchone()
            if row and row[1] == document.content_hash:
                return "skipped"

            cursor.execute(
                """
                insert into knowledge_documents
                    (source, title, authority, language, updated_date, category,
                     source_type, content, content_hash)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (source) do update set
                    title = excluded.title,
                    authority = excluded.authority,
                    language = excluded.language,
                    updated_date = excluded.updated_date,
                    category = excluded.category,
                    source_type = excluded.source_type,
                    content = excluded.content,
                    content_hash = excluded.content_hash,
                    updated_at = now()
                returning id
                """,
                (
                    document.source,
                    document.title,
                    document.authority,
                    document.language,
                    document.updated_date,
                    document.category,
                    document.source_type,
                    document.content,
                    document.content_hash,
                ),
            )
            document_id = cursor.fetchone()[0]

            rows = _chunk_rows(
                document,
                self.embedding_provider,
                max_tokens=self.max_tokens,
                overlap_tokens=self.overlap_tokens,
            )
            cursor.execute("delete from knowledge_chunks where document_id = %s", (document_id,))
            for row in rows:
                cursor.execute(
                    """
                    insert into knowledge_chunks
                        (document_id, chunk_index, section, content, normalized_content,
                         token_estimate, embedding)
                    values (%s, %s, %s, %s, %s, %s, %s::vector)
                    """,
                    (
                        document_id,
                        row["chunk_index"],
                        row["section"],
                        row["content"],
                        row["normalized_content"],
                        row["token_estimate"],
                        self._vector_literal(row["embedding"]),
                    ),
                )
        return "updated" if row else "inserted"

    def ingest_document(
        self,
        file_path: str,
        title: str = "",
        authority: str = "",
        language: str = "",
        updated_date: str = "",
        category: str = "",
        source_type: str = "",
    ) -> str:
        document = _with_overrides(
            load_document(file_path),
            title=title,
            authority=authority,
            language=language,
            updated_date=updated_date,
            category=category,
            source_type=source_type,
        )
        self.add_document(document)
        return document.doc_id

    def ingest_directory(self, root: str) -> dict[str, int]:
        from app.knowledge_base.loaders import iter_documents

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "documents": 0}
        for document in iter_documents(root):
            stats[self.add_document(document)] += 1
            stats["documents"] += 1
        return stats

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.55,
        *,
        query_text: str | None = None,
    ) -> list[RetrievalResult]:
        # pgvector does the vector part here. A lexical/tsvector arm can be added in SQL
        # later; query_text is accepted so the store matches the in-memory interface.
        _ = query_text
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                select c.document_id, d.title, c.content,
                       1 - (c.embedding <=> %s::vector) as similarity
                from knowledge_chunks c
                join knowledge_documents d on d.id = c.document_id
                where 1 - (c.embedding <=> %s::vector) >= %s
                order by c.embedding <=> %s::vector
                limit %s
                """,
                (
                    self._vector_literal(query_embedding),
                    self._vector_literal(query_embedding),
                    threshold,
                    self._vector_literal(query_embedding),
                    max(1, top_k),
                ),
            )
            rows = cursor.fetchall()

        return [
            RetrievalResult(
                document_id=str(row[0]),
                title=row[1],
                excerpt=row[2][:600],
                page=None,
                similarity=round(min(max(float(row[3]), 0.0), 1.0), 6),
            )
            for row in rows
        ]

    def get_document_content(self, document_id: str) -> str | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "select content from knowledge_documents where id::text = %s or source = %s",
                (document_id, document_id),
            )
            row = cursor.fetchone()
        return row[0] if row else None

    def get_all_documents(self) -> list[dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                select id::text, source, title, authority, language, updated_date,
                       category, source_type, content_hash
                from knowledge_documents order by source
                """
            )
            columns = [c.name for c in cursor.description]
            rows = cursor.fetchall()
        return [dict(zip(columns, row, strict=False)) for row in rows]
