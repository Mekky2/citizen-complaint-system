"""Knowledge-base ingestion CLI.

Usage (run from ``backend/``):

    python -m app.knowledge_base.ingest                     # in-memory build, prints stats
    python -m app.knowledge_base.ingest --dry-run           # load + chunk only, no embeddings
    python -m app.knowledge_base.ingest --backend pgvector  # write to Supabase (DATABASE_URL)
    python -m app.knowledge_base.ingest --path data/knowledge --json

Re-running is idempotent: unchanged documents are reported as ``skipped``; changed documents
replace their chunks (no duplicates).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import Settings, get_settings
from app.knowledge_base.chunking import chunk_text
from app.knowledge_base.embeddings import build_embedding_provider
from app.knowledge_base.loaders import iter_documents
from app.knowledge_base.store import InMemoryKnowledgeBase, PgVectorKnowledgeBase

DEFAULT_KNOWLEDGE_DIR = "data/knowledge"


def dry_run(path: str) -> dict:
    documents = iter_documents(path)
    chunks = [chunk for document in documents for chunk in chunk_text(document.content)]
    return {
        "documents": len(documents),
        "chunks": len(chunks),
        "max_tokens": max((chunk.token_estimate for chunk in chunks), default=0),
        "sources": sorted(document.source for document in documents),
    }


def build_store(settings: Settings, backend: str):
    provider = build_embedding_provider(settings)
    if backend == "pgvector":
        return PgVectorKnowledgeBase(settings.database_url, provider)
    return InMemoryKnowledgeBase(provider)


def ingest(path: str, backend: str = "memory", settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    store = build_store(settings, backend)
    stats = store.ingest_directory(path)
    stats["backend"] = backend
    stats["embedding_provider"] = settings.embedding_provider
    stats["embedding_dimension"] = settings.embedding_dimension
    stats["path"] = str(path)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Arabic knowledge documents")
    parser.add_argument("--path", default=DEFAULT_KNOWLEDGE_DIR, help="knowledge folder")
    parser.add_argument(
        "--backend", choices=["memory", "pgvector"], default="memory", help="storage backend"
    )
    parser.add_argument("--dry-run", action="store_true", help="load and chunk without embedding")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if not Path(args.path).exists():
        raise SystemExit(f"Knowledge folder not found: {args.path}")

    stats = dry_run(args.path) if args.dry_run else ingest(args.path, args.backend)

    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    print(f"Ingestion finished ({'dry run' if args.dry_run else args.backend})")
    for key, value in stats.items():
        if key == "sources":
            continue
        print(f"  {key}: {value}")
    if stats.get("sources"):
        print("  sources:")
        for source in stats["sources"]:
            print(f"    - {source}")


if __name__ == "__main__":
    main()
