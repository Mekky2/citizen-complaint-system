"""Arabic keyword search helpers (BM25) used for hybrid retrieval.

Vector search alone is weak for short Arabic questions and dialect wording. This module
adds a small, transparent lexical layer:

1. normalize with the shared ``normalize_arabic`` (taa marbuta folded for matching only);
2. remove common stopwords;
3. strip the definite article and common possessive suffixes (light stemming);
4. expand frequent Egyptian/MSA synonyms to the wording used in the knowledge base;
5. rank with BM25 over the chunk tokens.

The expansion map is deliberately small and domain-specific. It is a baseline, not a
linguistic model; it exists so retrieval works offline and needs no API key.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from app.utils.arabic_normalizer import normalize_arabic

STOPWORDS: frozenset[str] = frozenset(
    """من في علي على عن الي إلى الى هو هي هم ما ماذا هل كيف ازاي إزاي ايه ايش مين متى
    امتى ليه لماذا كان كانت يكون هذا هذه ذلك التي الذي مع او أو و يا ان أن إن لا لم لن
    قد كل بعض بعد قبل عند بين حتي حتى ثم لكن ولكن كما اي أي انا أنت نحن عليه عليها فيه
    فيها بتاع عشان علشان مش مفيش عندنا عندي به بها له لها لي لنا هن اكون أكون يكون تكون
    هناك هنا ايضا أيضا اى رقم هاتف بدون""".split()
)

_RAW_EXPANSIONS: dict[str, str] = {
    # procedure / question wording
    "اقدم": "تقديم",
    "أقدم": "تقديم",
    "مقدم": "تقديم",
    "مقدمه": "تقديم",
    "اعمل": "تقديم",
    "طريقه": "كيفية",
    "انترنت": "منصة",
    "اونلاين": "منصة",
    "أونلاين": "منصة",
    "موقع": "منصة",
    "الكتروني": "منصة",
    "مستندات": "معلومات",
    "ورق": "معلومات",
    "اوراق": "معلومات",
    "أوراق": "معلومات",
    "مطلوب": "معلومات",
    "لازم": "معلومات",
    "يستغرق": "مدة",
    "يستغرقها": "مدة",
    "مده": "مدة",
    "مدة": "مدة",
    "تاخد": "مدة",
    "بتاخد": "مدة",
    "ياخد": "مدة",
    "وقت": "مدة",
    "زمن": "مدة",
    "رد": "استجابة",
    "يرد": "استجابة",
    "اعرف": "متابعة",
    "أعرف": "متابعة",
    "معرفه": "متابعة",
    "معرفة": "متابعة",
    "شكوتي": "شكوى",
    "شكوتك": "شكوى",
    "شكوته": "شكوى",
    # services
    "زبال": "نظافة",
    "زباله": "نظافة",
    "قمامه": "نظافة",
    "قمامة": "نظافة",
    "نفايات": "نظافة",
    "مخلفات": "نظافة",
    "رفع": "إزالة",
    "ازاله": "إزالة",
    "ازالة": "إزالة",
    "ميه": "مياه",
    "ماسورة": "مياه",
    "ماسوره": "مياه",
    "تسريب": "مياه",
    "مجاري": "صرف",
    "كهربا": "كهرباء",
    "سلك": "كهرباء",
    "أسلاك": "كهرباء",
    "اسلاك": "كهرباء",
    "محول": "كهرباء",
    "اناره": "إنارة",
    "إنارة": "إنارة",
    "نور": "إنارة",
    "كشاف": "إنارة",
    "لمبة": "إنارة",
    "حفره": "طرق",
    "حفرة": "طرق",
    "حفر": "طرق",
    "طريق": "طرق",
    "رصيف": "طرق",
    "اسفلت": "طرق",
    "مطب": "طرق",
    "اتابع": "متابعة",
    "تابع": "متابعة",
    "متابعه": "متابعة",
    "حاله": "حالة",
    "وضع": "حالة",
    "ارفاق": "صور",
    "إرفاق": "صور",
    "ارفق": "صور",
    "أرفق": "صور",
    "ارفع": "إرفاق",
    "أرفع": "إرفاق",
    "مرفق": "صور",
    "صوره": "صور",
    "صورة": "صور",
    "خصوصيه": "خصوصية",
    "بيانات": "خصوصية",
    "بياناتي": "خصوصية",
    "بياناتك": "خصوصية",
    "بياناته": "خصوصية",
    "سريه": "خصوصية",
    "سرية": "خصوصية",
    "تتحل": "معالجة",
    "بتتحل": "معالجة",
    "تحل": "معالجة",
    "ترميم": "بناء",
    "مخالفات": "بناء",
    "مخالفه": "بناء",
    "ترخيص": "بناء",
    "مواصلات": "نقل",
    "اتوبيس": "نقل",
    "أتوبيس": "نقل",
    "مترو": "نقل",
    "تاكسي": "نقل",
    "ضوضه": "ضوضاء",
    "ضجيج": "ضوضاء",
    "صوت": "ضوضاء",
    "ازعاج": "ضوضاء",
    "مسؤول": "جهة",
    "مسئول": "جهة",
    "جهه": "جهة",
    "تبع": "جهة",
}

EXPANSIONS: dict[str, str] = {
    normalize_arabic(key, fold_taa_marbuta=True): normalize_arabic(value, fold_taa_marbuta=True)
    for key, value in _RAW_EXPANSIONS.items()
}

_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
# Single-letter possessive suffixes (ه/ك) are deliberately omitted: stripping them would
# turn feminine words like "قمامة" into "قمام" and break synonym lookup.
_SUFFIXES = ("ها", "هم", "هن", "نا", "كم", "كن")
_WORD = re.compile(r"\w+")


def normalize_for_search(text: str) -> str:
    return normalize_arabic(text, fold_taa_marbuta=True)


def stem_arabic_word(word: str) -> str:
    """Very light stemmer: remove a leading article and a possessive suffix."""
    for prefix in _PREFIXES:
        if word.startswith(prefix) and len(word) > len(prefix) + 1:
            word = word[len(prefix) :]
            break
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            word = word[: -len(suffix)]
            break
    return word


def tokenize_for_search(text: str) -> list[str]:
    """Tokenize, drop stopwords, stem, then apply domain synonyms."""
    normalized = normalize_for_search(text)
    tokens: list[str] = []
    for raw in _WORD.findall(normalized):
        if len(raw) <= 1 or raw in STOPWORDS:
            continue
        stemmed = stem_arabic_word(raw)
        tokens.append(EXPANSIONS.get(stemmed, EXPANSIONS.get(raw, stemmed)))
    return tokens


class BM25Index:
    """A tiny in-memory BM25 index over a list of token lists."""

    def __init__(self, documents: list[list[str]], *, k1: float = 1.5, b: float = 0.75):
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.document_frequency: Counter[str] = Counter()
        for tokens in documents:
            self.document_frequency.update(set(tokens))
        self.total = len(documents)
        total_length = sum(len(tokens) for tokens in documents)
        self.average_length = (total_length / self.total) if self.total else 0.0

    def score(self, query_tokens: list[str], index: int) -> float:
        tokens = self.documents[index]
        if not tokens or not query_tokens:
            return 0.0
        frequencies = Counter(tokens)
        score = 0.0
        for term in query_tokens:
            term_frequency = frequencies.get(term, 0)
            if not term_frequency:
                continue
            document_frequency = self.document_frequency.get(term, 0)
            idf = math.log(1 + (self.total - document_frequency + 0.5) / (document_frequency + 0.5))
            denominator = term_frequency + self.k1 * (
                1 - self.b + self.b * len(tokens) / max(self.average_length, 1e-9)
            )
            score += idf * term_frequency * (self.k1 + 1) / denominator
        return score

    def normalized(self, query_tokens: list[str], index: int) -> float:
        """Map BM25 to 0..1 so it can be combined with cosine similarity."""
        raw = self.score(query_tokens, index)
        return raw / (raw + 3.0) if raw > 0 else 0.0
