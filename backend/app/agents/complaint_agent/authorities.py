"""Category -> authority mapping and Arabic keyword extraction for the Complaint Agent.

The taxonomy follows the code that actually validates tickets (Water, Electricity, Roads,
Environment). Municipal topics that do not have their own category are mapped explicitly:

* street lighting      -> Electricity
* sewage               -> Water
* garbage / noise      -> Environment
* buildings / transport-> Roads

This mapping is configuration, not prompt text, so it can be changed without touching the
LLM prompts. It is an ASSUMPTION based on the repository taxonomy, not an official decree.
"""

from __future__ import annotations

import re

from app.agents.complaint_agent.schemas import CATEGORIES
from app.utils.arabic_normalizer import normalize_arabic

CATEGORY_AUTHORITY: dict[str, str] = {
    "Water": "مديرية المياه",
    "Electricity": "مديرية الكهرباء",
    "Roads": "مديرية الطرق",
    "Environment": "مديرية البيئة",
}

CATEGORY_LABEL_AR: dict[str, str] = {
    "Water": "المياه والصرف",
    "Electricity": "الكهرباء والإنارة",
    "Roads": "الطرق والبناء",
    "Environment": "النظافة والبيئة",
}

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Water": (
        "مياه",
        "ميه",
        "مايه",
        "ماء",
        "ماسوره",
        "ماسورة",
        "تسريب",
        "حنفيه",
        "حنفية",
        "صرف",
        "مجاري",
        "مجارى",
        "بلاعه",
        "بلاعة",
        "طفح",
        "طفحت",
        "مياه صرف",
        "شبكه مياه",
        "water",
        "leak",
        "pipe",
        "sewage",
        "drain",
    ),
    "Electricity": (
        "كهرباء",
        "كهربا",
        "سلك",
        "اسلاك",
        "أسلاك",
        "كابل",
        "محول",
        "عمود نور",
        "اناره",
        "إنارة",
        "كشاف",
        "لمبه",
        "لمبة",
        "ماس كهربائي",
        "عداد",
        "عدادات",
        "انقطاع الكهرباء",
        "مقطوع",
        "مقطوعه",
        "مقطوعة",
        "electricity",
        "electric",
        "power",
        "wire",
        "cable",
        "lamp",
    ),
    "Roads": (
        "طريق",
        "حفره",
        "حفرة",
        "حفر",
        "اسفلت",
        "أسفلت",
        "رصيف",
        "مطب",
        "كوبري",
        "اشاره",
        "إشارة",
        "رصف",
        "ترميم",
        "بناء",
        "مخالفه",
        "مخالفة",
        "مخالفات",
        "مواصلات",
        "نقل",
        "اتوبيس",
        "مترو",
        "road",
        "street",
        "pothole",
        "sidewalk",
        "asphalt",
        "bridge",
        "building",
        "transport",
    ),
    "Environment": (
        "زباله",
        "زبالة",
        "قمامه",
        "قمامة",
        "نفايات",
        "مخلفات",
        "تلوث",
        "دخان",
        "ضوضاء",
        "ضجيج",
        "صوت عالي",
        "رائحه",
        "رائحة",
        "حديقه",
        "حديقة",
        "اشجار",
        "أشجار",
        "صحي",
        "مستشفى",
        "garbage",
        "trash",
        "waste",
        "noise",
        "pollution",
        "smoke",
        "dump",
    ),
}

GOVERNORATES: tuple[str, ...] = (
    "القاهرة",
    "الجيزة",
    "الإسكندرية",
    "الاسكندرية",
    "القليوبية",
    "الشرقية",
    "الدقهلية",
    "المنوفية",
    "الغربية",
    "كفر الشيخ",
    "البحيرة",
    "دمياط",
    "بورسعيد",
    "الإسماعيلية",
    "الاسماعيلية",
    "السويس",
    "شمال سيناء",
    "جنوب سيناء",
    "الفيوم",
    "بني سويف",
    "المنيا",
    "أسيوط",
    "اسيوط",
    "سوهاج",
    "قنا",
    "الأقصر",
    "الاقصر",
    "أسوان",
    "اسوان",
    "البحر الأحمر",
    "الوادي الجديد",
    "مطروح",
)

_CRITICAL = (
    "اسلاك مكشوفه",
    "أسلاك مكشوفة",
    "ماس كهربائي",
    "شرار",
    "بتفرقع",
    "حريق",
    "بيولع",
    "ولعت",
    "انفجار",
    "انفجرت",
    "تسريب غاز",
    "غاز",
    "صعق",
    "انهيار",
    "سقوط",
    "هبوط",
    "غرق",
    "فيضان",
    "خطر على الحياه",
    "خطر على الحياة",
    "اطفال",
    "أطفال",
    "مستشفى",
    "طوارئ",
    "خطر",
)
_HIGH = (
    "انقطاع",
    "مقطوعه",
    "مقطوعة",
    "مقطوع",
    "طفح",
    "مجاري",
    "تسريب كبير",
    "غرقان",
    "حفره كبيره",
    "حفرة كبيرة",
    "عميقه",
    "عميقة",
    "بدون اناره",
    "بدون إنارة",
    "مفيش نور",
    "مفيش اناره",
    "مفيش إناره",
    "مفيش إنارة",
    "مظلم",
    "ظلام",
    "رئيسيه",
    "رئيسية",
    "تلف",
    "مكسوره",
    "مكسورة",
    "بقاله",
    "بقالها",
    "من اسبوع",
    "من أسبوع",
    "من شهر",
)
_LOW = (
    "بسيط",
    "بسيطه",
    "بسيطة",
    "صغير",
    "صغيره",
    "صغيرة",
    "خفيف",
    "خفيفه",
    "خفيفة",
    "تجميلي",
    "دهان",
    "بهتان",
    "لمبه",
    "لمبة",
    "نقطه",
    "نقطة",
    "رشه",
    "رشة",
    "drip",
    "minor",
)

_STREET = re.compile(
    r"(?<!ال)(?:شارع|ش\.|طريق|ط\.|street|road|rd\.)\s*([^\n،,.؛;]+)",
    re.IGNORECASE,
)
_LANDMARK = re.compile(
    r"(?:امام|أمام|جنب|بجوار|جانب|قدام|خلف|قريب من)\s*([^\n،,.؛;]+)",
    re.IGNORECASE,
)
_DISTRICT = re.compile(
    r"(?:حي|حى|منطقه|منطقة|قريه|قرية|مدينه|مدينة)\s*([^\n،,.؛;]+)", re.IGNORECASE
)
_DATE = re.compile(
    r"(?:من|بقاله|بقالها|بقالي|منذ|قبل)\s+"
    r"(?:يومين|اسبوعين|أسبوعين|شهرين|سنتين|ساعات|ساعه|ساعة|"
    r"يوم|اسبوع|أسبوع|شهر|سنه|سنة)"
    r"|(?:امبارح|أمس|اليوم|النهارده|النهاردة|الصبح)"
)
_STREET_STOP = re.compile(r"\s+(?:في|فى|بال|بـ|من|عند|جنب|أمام|امام|بجوار|خلف|قريب|اللي|اللى)\s+")


def _normalized_keywords(keywords: tuple[str, ...]) -> set[str]:
    return {
        normalized
        for keyword in keywords
        if (normalized := normalize_arabic(keyword, fold_taa_marbuta=True))
    }


def _is_word_start_match(normalized: str, keyword: str) -> bool:
    """Match at the start of an Arabic word, allowing proclitics (و/ف/ب/ك/ل + ال).

    Single-word keywords may be preceded by ``وال``/``بال`` etc. Conjunctions are only
    allowed for multi-word phrases, so a keyword like ``رشة`` does not match inside ``ورشة``.
    """
    if " " in keyword:
        pattern = r"(?:^|[^\w])(?:[وف])?(?:ال)?" + re.escape(keyword)
    else:
        pattern = r"(?:^|[^\w])(?:(?:[وفبكل])?ال)?" + re.escape(keyword)
    return re.search(pattern, normalized) is not None


def _keyword_score(normalized: str, keywords: tuple[str, ...]) -> int:
    """Count distinct matched keywords, collapsing inflection pairs like مقطوع/مقطوعة."""
    matched = [kw for kw in _normalized_keywords(keywords) if _is_word_start_match(normalized, kw)]
    return sum(
        1
        for keyword in matched
        if not any(keyword != other and other.startswith(keyword) for other in matched)
    )


def category_for_text(text: str) -> str | None:
    """Return the taxonomy category with the most keyword hits, or None when unclear."""
    normalized = normalize_arabic(text, fold_taa_marbuta=True)
    scores = {
        category: _keyword_score(normalized, keywords)
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    best = max(scores.values())
    if best == 0:
        return None
    winners = [category for category, score in scores.items() if score == best]
    return winners[0] if len(winners) == 1 else None


def authority_for_category(category: str | None) -> str | None:
    return CATEGORY_AUTHORITY.get(category or "")


def urgency_for_text(text: str) -> tuple[str, str]:
    """Return (urgency, short Arabic reason)."""
    normalized = normalize_arabic(text, fold_taa_marbuta=True)
    if any(
        _is_word_start_match(normalized, normalize_arabic(word, fold_taa_marbuta=True))
        for word in _CRITICAL
    ):
        return "critical", "الوصف يشير إلى خطر مباشر على السلامة أو الأمن العام."
    if any(
        _is_word_start_match(normalized, normalize_arabic(word, fold_taa_marbuta=True))
        for word in _HIGH
    ):
        return "high", "المشكلة تسبب تعطلًا كبيرًا أو تتفاقم بمرور الوقت."
    # A broken/leaking water pipe is a service interruption even when the wording puts the
    # leak before the pipe ("تسريب مياه") or the pipe before the leak ("ماسورة مكسورة").
    water = any(_is_word_start_match(normalized, word) for word in ("ماسور", "مياه", "ميه"))
    leak = any(
        _is_word_start_match(normalized, word) for word in ("مكسور", "تسرب", "بتسرب", "تسريب")
    )
    if water and leak:
        return "high", "تسريب أو كسر في شبكة المياه قد يتفاقم ويؤثر على إمداد المياه."
    if any(
        _is_word_start_match(normalized, normalize_arabic(word, fold_taa_marbuta=True))
        for word in _LOW
    ):
        return "low", "المشكلة محدودة الأثر وليست خطرًا مباشرًا."
    return "medium", "المشكلة حقيقية ولكنها ليست خطرًا مباشرًا."


def extract_location(text: str) -> dict[str, str]:
    """Extract governorate/city/street/landmark. Missing values stay empty strings."""
    normalized = normalize_arabic(text)
    location = {"governorate": "", "city": "", "street": "", "landmark": ""}

    for governorate in GOVERNORATES:
        if normalize_arabic(governorate) in normalized:
            location["governorate"] = governorate
            break

    district = _DISTRICT.search(text)
    if district:
        location["city"] = district.group(1).strip()

    street = _STREET.search(text)
    if street:
        value = street.group(1).strip()
        value = _STREET_STOP.split(value, maxsplit=1)[0].strip()
        location["street"] = value

    landmark = _LANDMARK.search(text)
    if landmark:
        value = landmark.group(1).strip()
        value = _STREET_STOP.split(value, maxsplit=1)[0].strip()
        location["landmark"] = value

    return location


def extract_incident_date(text: str) -> str | None:
    match = _DATE.search(text)
    return match.group(0).strip() if match else None


def mentions_attachments(text: str) -> list[str]:
    normalized = normalize_arabic(text, fold_taa_marbuta=True)
    found: list[str] = []
    if "صور" in normalized or "صوره" in normalized:
        found.append("صور")
    if "فيديو" in normalized:
        found.append("فيديو")
    if "مرفق" in normalized or "مرفقات" in normalized:
        found.append("مرفقات")
    return found


def contact_preference(text: str) -> str | None:
    normalized = normalize_arabic(text, fold_taa_marbuta=True)
    if "واتساب" in normalized or "whatsapp" in normalized.lower():
        return "whatsapp"
    if "ايميل" in normalized or "بريد" in normalized or "email" in normalized.lower():
        return "email"
    if "هاتف" in normalized or "اتصال" in normalized or "تليفون" in normalized:
        return "phone"
    return None


def short_title(description: str, category: str | None) -> str:
    """A short, faithful title: the first sentence, never invented details."""
    text = re.sub(r"\s+", " ", description).strip()
    if not text:
        return ""
    first = re.split(r"[.!?؟\n]", text, maxsplit=1)[0].strip()
    if len(first) > 70:
        first = first[:67].rstrip() + "..."
    return first


def categories() -> tuple[str, ...]:
    return CATEGORIES
