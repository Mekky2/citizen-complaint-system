import pytest

from app.agents.complaint_agent.rules import categorize_rules, severity_rules


@pytest.mark.parametrize(
    ("text", "authority", "expected"),
    [
        ("Large pothole on the main road", "Roads", "Roads"),
        ("في حفرة كبيرة في الطريق", "Roads", "Roads"),
        ("Garbage not collected for a week", "Water", "Environment"),
        ("القمامة متكومة قدام البيت", "Water", "Environment"),
        ("Water pipe leak in the street", "Water", "Water"),
        ("ماسورة المية مكسورة", "Water", "Water"),
        ("Cable hanging from the transformer", "Electricity", "Electricity"),
        ("help", "Roads", "Roads"),  # no keywords: falls back to authority
    ],
)
def test_categorize_rules(text, authority, expected):
    assert categorize_rules(text, authority) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Exposed live wires sparking near a school", "Critical"),
        ("أسلاك مكشوفة وشرار قدام المدرسة", "Critical"),
        ("Faded paint on the crosswalk", "Weak"),
        ("Street light is dim", "Weak"),
        ("Bins overflow every few days", "Medium"),
        ("هناك مشكلة", "Medium"),
    ],
)
def test_severity_rules(text, expected):
    assert severity_rules(text) == expected
