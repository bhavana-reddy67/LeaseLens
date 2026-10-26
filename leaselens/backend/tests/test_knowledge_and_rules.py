import json

import pytest

from app.schemas.analysis import PageInput
from app.services.clause_segmentation import split_into_clauses
from app.services.knowledge_base import KB_DIR, KnowledgeBase, get_knowledge_base
from app.services.retrieval import TfidfRetriever
from app.services.rule_screening import screen_clauses
from tests.conftest import RENTAL_TEXT


def test_knowledge_base_loads_and_is_consistent():
    kb = get_knowledge_base()
    assert len(kb.categories) >= 9
    assert len(kb.rules) >= 20
    assert all(any(e.category == c.id for e in kb.entries) for c in kb.categories)


def test_knowledge_base_rejects_unknown_category(tmp_path):
    for name in ("categories.json", "risk_rules.json", "guidance.json"):
        (tmp_path / name).write_text((KB_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    rules = json.loads((tmp_path / "risk_rules.json").read_text(encoding="utf-8"))
    rules["rules"].append({"id": "X-1", "category": "nope", "level": "low", "pattern": "x", "description": "x"})
    (tmp_path / "risk_rules.json").write_text(json.dumps(rules), encoding="utf-8")
    with pytest.raises(ValueError):
        KnowledgeBase.load(tmp_path)


@pytest.mark.parametrize(
    ("sentence", "rule_id"),
    [
        ("This agreement will automatically renew each year.", "AR-01"),
        ("The security deposit may be withheld for cleaning.", "SD-02"),
        ("A monthly administrative fee of 25 applies.", "FE-01"),
        ("Tenant shall pay a late fee of 50.", "PE-01"),
        ("Interest of 2% per day applies to overdue amounts.", "PE-02"),
        ("Tenant shall indemnify and hold harmless the landlord.", "LI-01"),
        ("The company reserves the right to modify these terms at any time.", "UC-01"),
        ("The tenant waives any right to a jury trial.", "RR-01"),
        ("The employee shall not compete with the company for two years.", "NC-01"),
        ("The entire balance becomes immediately due and payable.", "IR-03"),
        ("All disputes shall be settled by binding arbitration.", "DR-01"),
    ],
)
def test_rules_match_examples(sentence, rule_id):
    kb = get_knowledge_base()
    clauses = split_into_clauses([PageInput(page=1, text=sentence)])
    hits = screen_clauses(clauses, kb)
    found = {h.rule_id for cats in hits.values() for rule_hits in cats.values() for h in rule_hits}
    assert rule_id in found


def test_neutral_clause_matches_no_rules():
    kb = get_knowledge_base()
    clauses = split_into_clauses([PageInput(page=1, text="Rent is due on the first day of each month by bank transfer.")])
    assert screen_clauses(clauses, kb) == {}


def test_segmentation_keeps_pages_and_headings():
    pages = [PageInput(page=1, text=RENTAL_TEXT), PageInput(page=2, text="5. NOTICES\nNotices must be in writing to the addresses above.")]
    clauses = split_into_clauses(pages)
    assert [c.id for c in clauses] == ["p1-c1", "p1-c2", "p1-c3", "p1-c4", "p2-c1"]
    assert clauses[0].text.startswith("1. TERM This lease")
    assert clauses[-1].page == 2


def test_segmentation_splits_very_long_text():
    long_text = " ".join(["The tenant agrees to keep the premises clean and tidy at all times."] * 60)
    clauses = split_into_clauses([PageInput(page=1, text=long_text)])
    assert len(clauses) > 1
    assert all(len(c.text) <= 1200 for c in clauses)


def test_retrieval_returns_relevant_guidance_with_explanation():
    retriever = TfidfRetriever(get_knowledge_base())
    refs = retriever.search(
        "This lease shall automatically renew unless ninety days written notice is given before expiry.",
        "auto_renewal",
        "rental",
    )
    assert refs and refs[0].source_id == "KB-AR-01"
    assert "Same category" in refs[0].relevance
    assert refs[0].kind == "general_guidance"


def test_retrieval_respects_document_type():
    retriever = TfidfRetriever(get_knowledge_base())
    refs = retriever.search("The employee shall not compete with the employer.", "non_compete", "rental")
    assert all(not r.source_id.startswith("KB-NC") for r in refs)
