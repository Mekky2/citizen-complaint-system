"""Read the official emergency numbers from ``data/emergency_numbers.json``.

The agents must never invent phone numbers. This provider is the only source they use, and
it also implements the ``EmergencyNumbersProvider`` protocol the RAG agent expects.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "emergency_numbers.json"

# The JSON keeps the official English labels; the citizen-facing text must be Arabic.
ARABIC_NAMES: dict[str, str] = {
    "police": "الشرطة",
    "ambulance": "الإسعاف",
    "fire": "الحماية المدنية (المطافئ)",
    "gas": "طوارئ الغاز الطبيعي",
    "electricity": "طوارئ الكهرباء",
    "water": "طوارئ المياه",
    "complaints": "الخط الموحد للشكاوى الحكومية",
}
ARABIC_DESCRIPTIONS: dict[str, str] = {
    "police": "للجرائم والحوادث الأمنية",
    "ambulance": "للحالات الطبية الطارئة",
    "fire": "لحرائق وخدمات الإطفاء",
    "gas": "لتسريبات الغاز",
    "electricity": "للأعطال والمخاطر الكهربائية",
    "water": "لكسر المواسير وتلوث المياه",
    "complaints": "لغير حالات الطوارئ",
}


def arabic_name(item: dict) -> str:
    return ARABIC_NAMES.get(str(item.get("id", "")), str(item.get("name", "")))


def arabic_description(item: dict) -> str:
    return ARABIC_DESCRIPTIONS.get(str(item.get("id", "")), "")


@lru_cache(maxsize=4)
def _load_numbers(path: str) -> tuple[dict, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(raw.get("numbers", []))


@lru_cache(maxsize=4)
def _load_metadata(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class FileEmergencyNumbers:
    def __init__(self, path: str | Path = DEFAULT_PATH):
        self.path = Path(path)

    def _load(self) -> tuple[dict, ...]:
        return _load_numbers(str(self.path))

    def get_all_numbers(self) -> list[dict]:
        return [dict(item) for item in self._load()]

    def get_numbers_by_category(self, category: str) -> list[dict]:
        return [dict(item) for item in self._load() if item.get("category") == category]

    def source(self) -> str:
        return str(_load_metadata(str(self.path)).get("source", ""))

    def last_verified(self) -> str:
        return str(_load_metadata(str(self.path)).get("last_verified", ""))


def emergency_numbers_singleton() -> FileEmergencyNumbers:
    return _SINGLETON


_SINGLETON = FileEmergencyNumbers()
