-- RAG knowledge base schema (Supabase / PostgreSQL + pgvector)
-- Apply with the Supabase SQL editor or: psql "$DATABASE_URL" -f migrations/001_knowledge_base.sql
--
-- Vector dimension: 1024. It MUST match EMBEDDING_DIMENSION in backend/.env.
-- If you change the embedding model to one with another dimension, change both this
-- column and the function signature below, then re-ingest.

create extension if not exists vector;
create extension if not exists pgcrypto;

-- One row per source document. `source` is the stable relative path used by the loader,
-- which makes re-ingestion idempotent (upsert instead of duplicate rows).
create table if not exists public.knowledge_documents (
    id            uuid primary key default gen_random_uuid(),
    source        text not null unique,
    title         text not null,
    authority     text not null default 'المديرية العامة',
    language      text not null default 'ar',
    updated_date  text,
    category      text not null default 'general',
    source_type   text not null default 'sample',
    content       text not null,
    content_hash  text not null,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

-- Retrievable chunks. The original text is stored for display; `normalized_content`
-- is the Arabic-normalized text used to build the embedding.
create table if not exists public.knowledge_chunks (
    id                 bigserial primary key,
    document_id        uuid not null references public.knowledge_documents(id) on delete cascade,
    chunk_index        integer not null,
    section            text,
    content            text not null,
    normalized_content text not null,
    token_estimate     integer not null default 0,
    embedding          vector(1024) not null,
    created_at         timestamptz not null default now(),
    unique (document_id, chunk_index)
);

-- Approximate nearest-neighbour index (cosine distance). HNSW gives good recall without
-- training; pgvector >= 0.5 is required (Supabase provides it).
create index if not exists knowledge_chunks_embedding_hnsw
    on public.knowledge_chunks
    using hnsw (embedding vector_cosine_ops)
    with (m = 16, ef_construction = 64);

create index if not exists knowledge_chunks_document_id_idx
    on public.knowledge_chunks (document_id);

-- RPC used by app/knowledge_base/store.py (PgVectorKnowledgeBase.search).
create or replace function public.match_knowledge_chunks(
    query_embedding vector(1024),
    match_threshold float default 0.55,
    match_count int default 5
)
returns table (
    document_id uuid,
    title text,
    content text,
    similarity float
)
language sql
stable
as $$
    select
        c.document_id,
        d.title,
        c.content,
        1 - (c.embedding <=> query_embedding) as similarity
    from public.knowledge_chunks c
    join public.knowledge_documents d on d.id = c.document_id
    where 1 - (c.embedding <=> query_embedding) >= match_threshold
    order by c.embedding <=> query_embedding
    limit match_count;
$$;

-- The API uses the server-side service role key; if you expose these tables through
-- Supabase's anon key, keep RLS enabled and add a read-only policy for chunks/documents.
alter table public.knowledge_documents enable row level security;
alter table public.knowledge_chunks enable row level security;

-- Public read access for the knowledge base (safe: it is non-personal reference content).
drop policy if exists "knowledge documents are readable" on public.knowledge_documents;
create policy "knowledge documents are readable"
    on public.knowledge_documents for select using (true);

drop policy if exists "knowledge chunks are readable" on public.knowledge_chunks;
create policy "knowledge chunks are readable"
    on public.knowledge_chunks for select using (true);
