"""Arabic-aware chunking for the knowledge base.

Chunks are built on paragraph and sentence boundaries (Arabic punctuation ، ؛ ؟ and
English . ! ?) with a configurable token budget and overlap. Token counts are estimated
from words (Arabic has no whitespace tokenizer that matches LLM tokens); the estimate is
deliberately conservative so a 300-500 token target stays in range.

The original text is kept untouched in ``TextChunk.text``. Normalization happens later,
when the search index is built.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

DEFAULT_MAX_TOKENS = 420
DEFAULT_OVERLAP_TOKENS = 60
# Arabic words are often split into 2-3 model tokens; 1.35 is a safe average estimate.
TOKENS_PER_WORD = 1.35

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_SENTENCE_END = re.compile(r"(?<=[.!?؟])\s+|\n+")


@dataclass(frozen=True)
class TextChunk:
    """One retrievable chunk of a document."""

    index: int
    text: str
    section: str | None
    token_estimate: int
    metadata: dict[str, str] = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """Approximate the number of model tokens in ``text``."""
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    if not words:
        return 0
    # Very short strings still need at least one token.
    return max(1, math.ceil(len(words) * TOKENS_PER_WORD))


def _split_sentences(text: str) -> list[str]:
    """Split on Arabic/English sentence punctuation and line breaks, keeping punctuation."""
    parts = [p.strip() for p in _SENTENCE_END.split(text)]
    return [p for p in parts if p]


def _split_long_sentence(sentence: str, max_tokens: int) -> list[str]:
    """Split a single over-long sentence on word boundaries."""
    words = sentence.split()
    if len(words) <= 1:
        return [sentence]
    pieces: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and estimate_tokens(candidate) > max_tokens:
            pieces.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


def _sections(text: str) -> list[tuple[str | None, str]]:
    """Return (heading, body) blocks. Text before the first heading has heading=None."""
    matches = list(_HEADING.finditer(text))
    if not matches:
        return [(None, text)]

    blocks: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            blocks.append((None, preamble))

    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            blocks.append((heading, body))
        elif heading:
            blocks.append((heading, ""))
    return blocks


def chunk_text(
    text: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[TextChunk]:
    """Split ``text`` into overlapping chunks that never exceed ``max_tokens``.

    Raises:
        ValueError: if the limits are impossible (max_tokens <= 0 or overlap >= max).
    """
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be >= 0 and smaller than max_tokens")
    if not text or not text.strip():
        return []

    chunks: list[TextChunk] = []
    for section, body in _sections(text):
        if not body.strip():
            continue

        sentences: list[str] = []
        for sentence in _split_sentences(body):
            if estimate_tokens(sentence) > max_tokens:
                sentences.extend(_split_long_sentence(sentence, max_tokens))
            else:
                sentences.append(sentence)
        if not sentences:
            continue

        current: list[str] = []
        for sentence in sentences:
            candidate = " ".join([*current, sentence])
            if current and estimate_tokens(candidate) > max_tokens:
                chunk_body = " ".join(current).strip()
                if chunk_body:
                    chunks.append(
                        TextChunk(
                            index=len(chunks),
                            text=chunk_body,
                            section=section,
                            token_estimate=estimate_tokens(chunk_body),
                        )
                    )
                # Carry the tail of the previous chunk for context.
                overlap: list[str] = []
                for previous in reversed(current):
                    if estimate_tokens(" ".join([previous, *overlap])) > overlap_tokens:
                        break
                    overlap.insert(0, previous)
                current = [*overlap, sentence]
            else:
                current.append(sentence)

        final = " ".join(current).strip()
        if final:
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    text=final,
                    section=section,
                    token_estimate=estimate_tokens(final),
                )
            )

    return [c for c in chunks if c.text.strip()]
