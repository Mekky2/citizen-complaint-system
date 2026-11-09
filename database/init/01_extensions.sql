-- =============================================================================
-- EG Civic Operations — Database Extensions
-- =============================================================================
-- pgcrypto: gen_random_uuid() for UUID primary keys (also provides digest/hash
--           functions that may be useful later, e.g. content_hash on embeddings).
-- vector:   pgvector — vector type + similarity search (cosine, L2, inner product)
--           and ANN indexes (ivfflat / hnsw) used by the RAG tables.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
