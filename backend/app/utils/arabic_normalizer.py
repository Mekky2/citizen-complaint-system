"""Arabic text normalization utility used by both agents.

Normalization is for *matching and search only*. The original text is always stored and
shown to the citizen, so this module never rewrites what the user sees.

It removes diacritics/tatweel, unifies alef and ya forms, converts Arabic-Indic digits to
Western digits, optionally folds taa marbuta/haa (for matching only), collapses whitespace
and strips emojis/noise.
"""

import re
import unicodedata
from typing import Final

# Arabic-Indic (٠-٩) and Extended Arabic-Indic / Persian (۰-۹) digits -> Western digits.
_DIGITS: Final[dict[int, int]] = {
    0x0660: 0x0030,
    0x0661: 0x0031,
    0x0662: 0x0032,
    0x0663: 0x0033,
    0x0664: 0x0034,
    0x0665: 0x0035,
    0x0666: 0x0036,
    0x0667: 0x0037,
    0x0668: 0x0038,
    0x0669: 0x0039,
    0x06F0: 0x0030,
    0x06F1: 0x0031,
    0x06F2: 0x0032,
    0x06F3: 0x0033,
    0x06F4: 0x0034,
    0x06F5: 0x0035,
    0x06F6: 0x0036,
    0x06F7: 0x0037,
    0x06F8: 0x0038,
    0x06F9: 0x0039,
}
_DIGIT_TABLE: Final = str.maketrans(_DIGITS)

# Tashkeel (harakat), superscript alef and tatweel.
_TASHKEEL_TATWEEL: Final = re.compile(r"[\u064B-\u065F\u0670\u0640]")

# Zero-width and other invisible formatting characters.
_INVISIBLE: Final = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2060\uFEFF\u200C\u200D]")

# Keep letters/numbers/whitespace plus the Arabic punctuation marks ، ؛ ؟ ٪.
_NOISE: Final = re.compile(r"[^\w\s\u060C\u061B\u061F\u066A\u066B\u066C\u066D]")

# Basic emoji ranges (emoji are never useful for municipal text matching).
_EMOJI: Final = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U00002600-\U000027bf"
    "\U0001f000-\U0001f0ff"
    "\U00002190-\U000021ff"
    "\U0000fe00-\U0000fe0f"
    "]"
)


def normalize_arabic(text: str, *, fold_taa_marbuta: bool = False) -> str:
    """Return a normalized copy of ``text`` suitable for embeddings and keyword matching.

    Args:
        text: Arabic, dialect, Franco-Arabic or mixed input.
        fold_taa_marbuta: When True, also map ``ة`` to ``ه``. Use this only for matching;
            keep the default for anything that will be displayed.

    Returns:
        The normalized text. An empty/None input returns ``""``.
    """
    if not text:
        return ""

    # 1. Canonical Unicode composition, then drop invisible characters.
    text = unicodedata.normalize("NFC", text)
    text = _INVISIBLE.sub("", text)

    # 2. Remove tashkeel, superscript alef and tatweel.
    text = _TASHKEEL_TATWEEL.sub("", text)

    # 3. Unify alef variants (أ إ آ ٱ -> ا) and ya (ى -> ي).
    text = re.sub(r"[أإآٱ]", "ا", text)
    text = text.replace("ى", "ي")

    # 4. Optional matching-only fold: taa marbuta -> haa.
    if fold_taa_marbuta:
        text = text.replace("ة", "ه")

    # 5. Arabic-Indic digits -> Western digits.
    text = text.translate(_DIGIT_TABLE)

    # 6. Strip emoji, then any remaining symbols we do not need for matching.
    text = _EMOJI.sub("", text)
    text = _NOISE.sub("", text)

    # 7. Collapse whitespace.
    return re.sub(r"\s+", " ", text).strip()


def is_arabic_text(text: str, min_ratio: float = 0.5) -> bool:
    """Return True when at least ``min_ratio`` of the visible characters are Arabic.

    Arabic punctuation and digits are excluded from the denominator so a short Arabic
    sentence followed by a phone number still counts as Arabic.
    """
    if not text:
        return False

    arabic = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text))
    visible = len(re.findall(r"\w", text))
    return arabic / max(visible, 1) >= min_ratio


def contains_arabic(text: str) -> bool:
    """True if the text contains at least one Arabic letter."""
    return re.search(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text or "") is not None


def is_emergency_word(text: str) -> bool:
    """Keyword hint used only to flag possible emergencies, never to decide alone."""
    emergency_keywords = [
        "طوارئ",
        "مستشفي",
        "احتراق",
        "حريق",
        "غاز",
        "شرطه",
        "اسعاف",
        "خطر",
        "انهيار",
        "صعق",
        "غرق",
    ]
    normalized = normalize_arabic(text).lower()
    return any(keyword in normalized for keyword in emergency_keywords)
