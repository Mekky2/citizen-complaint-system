"""Keyword baseline for category and severity (English + Egyptian Arabic).

Not used in the production pipeline. It exists so that (a) the evaluation runner works
without an LLM key, and (b) the LLM tools have a baseline to beat. The severity keywords
are an ASSUMED baseline, not an official municipal policy. Known limits: no negation
handling ("no danger"), no spelling variants beyond the normalisation below.
"""

import re

from app.agents.complaint_agent.schemas import CATEGORIES

_ARABIC_FIX = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"})
_DIACRITICS = re.compile("[ً-ْـ]")


def _norm(text: str) -> str:
    return _DIACRITICS.sub("", text.lower()).translate(_ARABIC_FIX)


_CATEGORY_WORDS: dict[str, list[str]] = {
    "Water": [
        "water",
        "pipe",
        "leak",
        "tap",
        "sewage",
        "drain",
        "مياه",
        "ميه",
        "مايه",
        "ماء",
        "ماسوره",
        "تسريب",
        "حنفيه",
        "مجاري",
        "صرف",
    ],
    "Electricity": [
        "electric",
        "power",
        "wire",
        "cable",
        "transformer",
        "street light",
        "lamp",
        "blackout",
        "كهرباء",
        "كهربا",
        "سلك",
        "اسلاك",
        "كابل",
        "محول",
        "ماس",
        "انارة",
        "عمود نور",
        "النور",
    ],
    "Roads": [
        "road",
        "pothole",
        "asphalt",
        "sidewalk",
        "pavement",
        "traffic",
        "speed bump",
        "crack",
        "حفره",
        "حفر",
        "طريق",
        "اسفلت",
        "رصيف",
        "مطب",
        "اشاره",
        "كوبري",
    ],
    "Environment": [
        "garbage",
        "trash",
        "waste",
        "litter",
        "rubbish",
        "pollution",
        "smoke",
        "noise",
        "dump",
        "زباله",
        "زبالة",
        "قمامه",
        "نفايات",
        "مخلفات",
        "تلوث",
        "دخان",
        "ضوضاء",
        "كوم",
    ],
}

_CRITICAL_WORDS = [
    "exposed wire",
    "live wire",
    "spark",
    "fire",
    "explosion",
    "flood",
    "gas leak",
    "electrocut",
    "injur",
    "collapse",
    "sinkhole",
    "danger",
    "accident",
    "life-threatening",
    "burst",
    "overflowing into",
    "children",
    "hospital",
    "اسلاك مكشوفه",
    "اسلاك عاريه",
    "ماس كهربائي",
    "شرار",
    "حريق",
    "انفجار",
    "غرق",
    "غمر",
    "فيضان",
    "غاز",
    "خطر",
    "صعق",
    "حادثه",
    "انهيار",
    "هبوط",
    "اطفال",
    "مستشفي",
    "كسر ماسوره",
]
_WEAK_WORDS = [
    "minor",
    "small",
    "faded",
    "cosmetic",
    "paint",
    "slightly",
    "a little",
    "dim",
    "when you have time",
    "بسيط",
    "صغير",
    "خفيف",
    "بهتان",
    "دهان",
    "لما تفضوا",
]


def categorize_rules(description: str, authority: str) -> str:
    """Highest keyword count wins; a tie or no match falls back to the authority."""
    text = _norm(description)
    scores = {c: sum(w in text for w in _CATEGORY_WORDS[c]) for c in CATEGORIES}
    best = max(scores.values())
    winners = [c for c, s in scores.items() if s == best]
    return winners[0] if best > 0 and len(winners) == 1 else authority


def severity_rules(description: str) -> str:
    """Critical keywords beat weak keywords; no keyword means Medium (conservative default)."""
    text = _norm(description)
    if any(w in text for w in _CRITICAL_WORDS):
        return "Critical"
    if any(w in text for w in _WEAK_WORDS):
        return "Weak"
    return "Medium"


# Emergency wording used ONLY to flag a possible under-estimate for human review.
# It cannot tell "no sparks" from "sparks" (negation) or past from present, so it never
# changes the model's severity; it only asks a human to look.
_EMERGENCY_HINTS = re.compile(
    r"(?<!\w)(?:exposed wire|live wire|spark|fire|explosion|explod|flood|gas|electrocut|injur|"
    r"collapse|sinkhole|burst|"
    r"اسلاك مكشوفه|اسلاك عاريه|شرار|حريق|حرق|بيولع|ولعت|انفجار|انفجر|غرق|غمر|غاز|صعق|انهيار|هبوط|"
    r"بتفرقع|ماس كهربائي)"
)


def has_emergency_hint(description: str) -> bool:
    return _EMERGENCY_HINTS.search(_norm(description)) is not None


def severity_review_notes(description: str, severity: str, confidence: str) -> list[str]:
    """ "CODE: explanation" notes asking a human to check the severity. Used by the agent and
    by the evaluation runner so both apply exactly the same logic."""
    notes = []
    if confidence == "low":
        notes.append("SEVERITY_LOW_CONFIDENCE: the model was not confident; please confirm.")
    if severity != "Critical" and has_emergency_hint(description):
        notes.append(
            "POSSIBLE_UNDERESTIMATED_SEVERITY: the text contains emergency wording but was "
            "not rated Critical (it may be negated or about a past event); please check."
        )
    return notes
