"""Compatibility entry point for knowledge ingestion.

There is exactly one implementation: :mod:`app.knowledge_base.ingest`. This package used to
be empty; it now forwards to the real CLI/API so nobody has to guess which module to call.

    python -m app.knowledge_base.ingest --path data/knowledge --backend memory
    python -m app.knowledge_base.ingestion --path data/knowledge --backend memory
"""

from app.knowledge_base.ingest import DEFAULT_KNOWLEDGE_DIR, dry_run, ingest, main

__all__ = ["DEFAULT_KNOWLEDGE_DIR", "dry_run", "ingest", "main"]


if __name__ == "__main__":  # pragma: no cover - module entry point
    main()
