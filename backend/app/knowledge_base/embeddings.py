"""Configurable embedding providers for the RAG knowledge base.

Two providers ship with the project:

* ``hashing`` (default): deterministic, offline, dependency-free. It hashes word and
  character n-gram features into a fixed-size vector. Good enough for tests and demos, and
  it needs no API key. It is NOT a semantic model; switch to a real provider in production.
* ``openai_compatible``: any OpenAI-compatible ``/embeddings`` endpoint (NVIDIA NIM, OpenAI,
  a local server). Configure model, base URL and key with environment variables.

The vector dimension is configuration, not guesswork: ``EMBEDDING_DIMENSION`` must match the
pgvector column in ``migrations/001_knowledge_base.sql`` (default: 1024).
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from app.core.config import Settings, get_settings

DEFAULT_DIMENSION = 1024


class EmbeddingProvider(Protocol):
    dimension: int

    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


def _normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


class HashingEmbeddingProvider:
    """Deterministic feature-hashing embedder (offline, no key, no model download).

    Uses word unigrams plus character trigrams of the normalized text. Character n-grams
    make it tolerant of Arabic spelling variants (ة/ه, alef forms) once the text has passed
    through ``normalize_arabic``. Cosine scores from this provider are on a lower scale than
    a real model, so it advertises its own ``default_threshold``.
    """

    # Cosine scores for short Arabic questions are typically 0.1-0.5.
    default_threshold = 0.15
    # Retrieval from this provider is lexical-ish; require at least one shared content word
    # before treating a passage as supporting evidence.
    requires_lexical_overlap = True

    def __init__(self, dimension: int = DEFAULT_DIMENSION):
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.dimension = dimension

    @staticmethod
    def _features(text: str) -> list[str]:
        words = re.findall(r"\w+", text.lower())
        features = [f"w:{word}" for word in words]
        for word in words:
            padded = f" {word} "
            for i in range(len(padded) - 2):
                features.append(f"c:{padded[i : i + 3]}")
        return features

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for feature in self._features(text or ""):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimension
            sign = 1.0 if (value >> 63) & 1 else -1.0
            vector[index] += sign
        return _normalise(vector)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class OpenAICompatibleEmbeddingProvider:
    """Thin wrapper around the OpenAI embeddings API (works with NVIDIA NIM and others)."""

    # Real embedding models separate relevant/irrelevant text around 0.5-0.6 cosine.
    default_threshold = 0.55
    requires_lexical_overlap = False

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        dimension: int = DEFAULT_DIMENSION,
        timeout_seconds: float = 30.0,
        client: object | None = None,
    ):
        if not api_key or api_key.strip().lower() in {"", "changeme", "your-nvidia-nim-api-key"}:
            raise ValueError("EMBEDDING_API_KEY is missing or still a placeholder")
        self.dimension = dimension
        self._model = model
        if client is not None:
            self._client = client
        else:
            import openai

            self._client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout_seconds,
                max_retries=0,
            )

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(model=self._model, input=texts)  # type: ignore[attr-defined]
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [list(item.embedding) for item in ordered]
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: got {len(vector)}, expected {self.dimension}. "
                    "Update EMBEDDING_DIMENSION and the pgvector migration together."
                )
        return vectors

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]


def build_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Build the provider selected by ``EMBEDDING_PROVIDER``."""
    settings = settings or get_settings()
    provider = settings.embedding_provider.strip().lower()
    dimension = int(settings.embedding_dimension)

    if provider in {"hashing", "offline", "local"}:
        return HashingEmbeddingProvider(dimension=dimension)
    if provider in {"openai", "openai_compatible", "nvidia_nim", "nim"}:
        return OpenAICompatibleEmbeddingProvider(
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            base_url=settings.embedding_base_url,
            dimension=dimension,
            timeout_seconds=float(settings.embedding_timeout_seconds),
        )
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {settings.embedding_provider!r}")
