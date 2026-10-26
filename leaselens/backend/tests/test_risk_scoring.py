import pytest

from app.services.risk_scoring import combine, highest_rule_level


def test_highest_rule_level():
    assert highest_rule_level([]) is None
    assert highest_rule_level(["low", "high", "medium"]) == "high"


@pytest.mark.parametrize(
    ("rule", "ai", "confidence", "level", "agreement"),
    [
        ("medium", None, None, "medium", "low"),        # rules only
        ("high", "uncertain", "low", "high", "low"),   # AI unsure, rules decide
        (None, "uncertain", "medium", "uncertain", "low"),
        (None, "high", "low", "uncertain", "low"),     # AI only, not confident
        (None, "medium", "high", "medium", "medium"),  # AI only
        ("high", "high", "high", "high", "high"),      # agree
        ("medium", "high", "high", "high", "medium"),  # one step apart
        ("high", "low", "high", "high", "low"),        # disagree, higher wins
        ("low", "low", "low", "low", "medium"),        # low confidence lowers agreement
    ],
)
def test_combine_table(rule, ai, confidence, level, agreement):
    result = combine(rule, ai, confidence)
    assert (result.level, result.agreement) == (level, agreement)


def test_disagreement_is_explained():
    notes = combine("high", "low", "high").notes
    assert any("disagree" in n for n in notes)


def test_combine_requires_some_evidence():
    with pytest.raises(ValueError):
        combine(None, None, None)
