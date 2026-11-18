"""Unit tests for the shared Arabic normalizer (used by both agents)."""

from app.utils.arabic_normalizer import (
    contains_arabic,
    is_arabic_text,
    is_emergency_word,
    normalize_arabic,
)


def test_removes_tashkeel_and_tatweel():
    assert normalize_arabic("مُحَمَّدٌ") == "محمد"
    assert normalize_arabic("مـــحـــمـــد") == "محمد"


def test_unifies_alef_and_ya_forms():
    assert normalize_arabic("أحمد إبراهيم آمال") == "احمد ابراهيم امال"
    assert normalize_arabic("مصطفى") == "مصطفي"


def test_taa_marbuta_fold_is_optional():
    assert normalize_arabic("خدمة") == "خدمة"
    assert normalize_arabic("خدمة", fold_taa_marbuta=True) == "خدمه"


def test_converts_arabic_indic_digits():
    assert normalize_arabic("٠١٢٣٤٥٦٧٨٩") == "0123456789"
    assert normalize_arabic("۰۱۲۳") == "0123"


def test_strips_emoji_and_noise_but_keeps_arabic_punctuation():
    # Alef maqsura is unified to yaa by default, so "شكوى" becomes "شكوي".
    assert normalize_arabic("شكوى 😡🔥 في الشارع!!!") == "شكوي في الشارع"
    assert normalize_arabic("هل تم الرد؟") == "هل تم الرد؟"


def test_collapses_whitespace_and_handles_empty():
    assert normalize_arabic("  شارع   النيل \n الجيزة  ") == "شارع النيل الجيزة"
    assert normalize_arabic("") == ""
    assert normalize_arabic(None) == ""  # type: ignore[arg-type]


def test_arabic_detection_helpers():
    assert contains_arabic("شارع النيل")
    assert not contains_arabic("Street 12")
    assert is_arabic_text("شكوى مياه 12345")
    assert not is_arabic_text("water leak 12345")


def test_emergency_word_is_a_hint_not_a_decision():
    assert is_emergency_word("فيه حريق")
    assert not is_emergency_word("شكوى على القمامة")
