"""Document loaders for the knowledge-base ingestion pipeline.

Supported formats: Markdown (.md), plain text (.txt), PDF (.pdf) and Word (.docx).
PDF/DOCX support uses optional packages; if they are not installed a clear error tells
you exactly what to install instead of silently skipping the file.

Every document keeps its ORIGINAL text. Metadata comes from YAML front matter when
present, otherwise safe defaults are used.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # PyYAML is already a project dependency (used by the golden datasets).
    import yaml
except ImportError:  # pragma: no cover - only if the environment is incomplete
    yaml = None  # type: ignore[assignment]

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".pdf", ".docx"}
DEFAULT_LANGUAGE = "ar"
DEFAULT_AUTHORITY = "المديرية العامة"
DEFAULT_CATEGORY = "general"
DEFAULT_SOURCE_TYPE = "sample"

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


class DocumentError(Exception):
    """Base class for ingestion input problems."""


class UnsupportedDocumentError(DocumentError):
    """The file extension is not supported."""


class MissingDependencyError(DocumentError):
    """A reader for this format needs an optional package that is not installed."""


@dataclass(frozen=True)
class KnowledgeDocument:
    """One source document, before chunking."""

    doc_id: str
    source: str  # stable relative path or file name
    title: str
    authority: str
    language: str
    updated_date: str
    category: str
    source_type: str
    content: str
    content_hash: str
    path: str

    @property
    def metadata(self) -> dict[str, str]:
        return {
            "source": self.source,
            "title": self.title,
            "authority": self.authority,
            "language": self.language,
            "updated_date": self.updated_date,
            "category": self.category,
            "source_type": self.source_type,
        }


def _split_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    match = _FRONT_MATTER.match(raw)
    if not match:
        return {}, raw
    data: dict[str, Any] = {}
    if yaml is not None:
        try:
            parsed = yaml.safe_load(match.group(1)) or {}
            if isinstance(parsed, dict):
                data = {str(k): v for k, v in parsed.items()}
        except yaml.YAMLError:
            data = {}
    return data, raw[match.end() :]


def _read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - depends on the environment
            raise MissingDependencyError(
                "Reading PDF files needs 'pypdf'. Install it with: pip install pypdf"
            ) from exc
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:  # pragma: no cover - depends on the environment
            raise MissingDependencyError(
                "Reading DOCX files needs 'python-docx'. Install it with: pip install python-docx"
            ) from exc
        document = Document(str(path))
        return "\n\n".join(p.text for p in document.paragraphs if p.text.strip()).strip()
    raise UnsupportedDocumentError(f"Unsupported document type: {path.suffix or '(none)'}")


def _stable_id(source: str) -> str:
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]


def load_document(path: str | Path, *, root: str | Path | None = None) -> KnowledgeDocument:
    """Load one file and its front matter.

    ``root`` makes ``source`` a stable path relative to the knowledge folder, so moving the
    project directory does not change document identities.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    raw = _read_text(path)
    front, body = _split_front_matter(raw)
    body = body.strip()
    if not body:
        raise DocumentError(f"Document is empty: {path}")

    source = path.relative_to(root).as_posix() if root else path.name
    title = str(front.get("title") or "").strip()
    if not title:
        heading = _H1.search(body)
        title = heading.group(1).strip() if heading else path.stem

    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return KnowledgeDocument(
        doc_id=_stable_id(source),
        source=source,
        title=title,
        authority=str(front.get("authority") or DEFAULT_AUTHORITY),
        language=str(front.get("language") or DEFAULT_LANGUAGE),
        updated_date=str(front.get("updated_date") or ""),
        category=str(front.get("category") or DEFAULT_CATEGORY),
        source_type=str(front.get("source_type") or DEFAULT_SOURCE_TYPE),
        content=body,
        content_hash=content_hash,
        path=str(path),
    )


def iter_documents(root: str | Path) -> list[KnowledgeDocument]:
    """Load every supported file under ``root`` in a deterministic order.

    Empty/unreadable files are skipped; the returned list only contains valid documents.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(root)
    if root.is_file():
        return [load_document(root, root=root.parent)]

    documents: list[KnowledgeDocument] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            documents.append(load_document(path, root=root))
    return documents
