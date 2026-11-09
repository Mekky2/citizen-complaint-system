"""
The "Legal RAG Service" layer the AI integration boundary sits on top of:

    AI Service -> FastAPI Backend -> Legal RAG Service -> legal_knowledge_chunks

This is the ONLY place in the codebase that queries legal_knowledge_chunks /
legal_knowledge_documents for similarity search. It never touches tickets —
"Search only official/legal knowledge sources. Do NOT include historical
tickets as legal evidence" is enforced simply by this module having no
import of, or query against, the Ticket model at all. Similar-case search
(which DOES query tickets) lives entirely separately, in
app/services/ai.py:list_similar_case_candidates().

Embedding dimension: legal_knowledge_chunks.embedding is an UNCONSTRAINED
pgvector `vector` column (see app/models/rag.py) — there is no fixed
dimension to validate the query embedding against globally. Instead, each
chunk's own embedding_dim column (set whenever its embedding was written) is
used to filter the comparison to only chunks whose embedding has the SAME
dimension as the caller's query_embedding — pgvector itself raises a hard
error if asked to compute a distance between two vectors of different
dimensions, so this filter is not just tidiness, it is what keeps the query
from raising a 500 the moment two different embedding models' output ends
up in the same table (an explicitly anticipated situation, per the
database's own migration-path notes in database/init/04_indexes.sql).
"""
import uuid

from sqlalchemy.orm import Session

from app.models.enums import LegalSourceType
from app.models.rag import LegalKnowledgeChunk, LegalKnowledgeDocument


def search_legal_knowledge(
    db: Session,
    query_embedding: list[float],
    *,
    limit: int = 5,
    source_type: LegalSourceType | None = None,
    department_id: uuid.UUID | None = None,
) -> list[dict]:
    """
    Cosine-similarity search over legal_knowledge_chunks, joined to their
    parent document for title/source metadata. Returns plain dicts (mapped
    to LegalSearchResultOut by the router) rather than ORM instances, because
    the result includes a computed `distance` column that has no home on
    the model itself.
    """
    query_dim = len(query_embedding)
    distance_expr = LegalKnowledgeChunk.embedding.cosine_distance(query_embedding)

    query = (
        db.query(
            LegalKnowledgeChunk.id.label("chunk_id"),
            LegalKnowledgeChunk.document_id.label("document_id"),
            LegalKnowledgeChunk.chunk_index.label("chunk_index"),
            LegalKnowledgeChunk.content.label("content"),
            LegalKnowledgeDocument.title.label("title"),
            LegalKnowledgeDocument.source_type.label("source_type"),
            LegalKnowledgeDocument.reference_number.label("reference_number"),
            LegalKnowledgeDocument.department_id.label("department_id"),
            distance_expr.label("distance"),
        )
        .join(LegalKnowledgeDocument, LegalKnowledgeDocument.id == LegalKnowledgeChunk.document_id)
        .filter(LegalKnowledgeChunk.embedding.isnot(None))
        .filter(LegalKnowledgeChunk.embedding_dim == query_dim)
    )
    if source_type is not None:
        query = query.filter(LegalKnowledgeDocument.source_type == source_type)
    if department_id is not None:
        query = query.filter(LegalKnowledgeDocument.department_id == department_id)

    rows = query.order_by(distance_expr.asc()).limit(limit).all()

    return [
        {
            "chunk_id": row.chunk_id,
            "document_id": row.document_id,
            "chunk_index": row.chunk_index,
            "content": row.content,
            "title": row.title,
            "source_type": row.source_type,
            "reference_number": row.reference_number,
            "department_id": row.department_id,
            # Cosine distance is in [0, 2]; similarity_score is a convenience
            # projection into [0, 1] (0 = unrelated/opposite, 1 = identical),
            # clamped defensively rather than trusted to always land in range.
            "similarity_score": max(0.0, min(1.0, 1.0 - (row.distance / 2.0))),
        }
        for row in rows
    ]
