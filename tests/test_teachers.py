"""Tests for the teacher pool plumbing — no network, no real keys."""


import pytest

from project import annotate, teachers


@pytest.fixture
def no_env(monkeypatch):
    for key in ("GEMINI_API_KEY", "GEMINI_API_KEY2", "OPENROUTER_API_KEY", "ZAI_API_KEY", "TEACHER_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_pool_skips_unconfigured_providers(no_env):
    pool = teachers.TeacherPool()
    assert pool.providers == []


def test_pool_loads_configured_providers(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k1")
    monkeypatch.setenv("ZAI_API_KEY", "k2")
    pool = teachers.TeacherPool()
    names = [p["name"] for p in pool.providers]
    assert names == ["gemini_1", "zai"]
    assert all(p["api_key"] for p in pool.providers)


def test_budget_left_respects_daily_cap():
    usage = teachers._Usage({"rpm": 10, "rpd": 100}, safety_margin=0.85)
    usage.requests_today = 85  # 100 * 0.85
    assert not usage.budget_left()
    usage.requests_today = 10
    assert usage.budget_left()


def test_available_after_unblocks_next_day():
    usage = teachers._Usage({"rpm": 10, "rpd": 100}, 0.85)
    usage.available_after = "2000-01-01"  # long past
    assert usage.budget_left()


def test_usage_roundtrip(tmp_path):
    usage = teachers._Usage({"rpm": 10, "rpd": 100}, 0.85)
    assert usage.try_reserve()
    usage.record_result(ok=True, tokens=42)
    revived = teachers._Usage.from_dict(usage.to_dict(), {"rpm": 10, "rpd": 100}, 0.85)
    assert revived.requests_today == 1 and revived.tokens_today == 42


def test_validate_classify():
    assert annotate.validate("classify", {"primary_category": "scholarships"}) == "valid"
    # secondary listed with low stated ambiguity: review note, not a routing trigger
    assert annotate.validate("classify", {"primary_category": "scholarships", "secondary_plausible_categories": ["grants"]}) == "valid"
    assert annotate.validate(
        "classify",
        {"primary_category": "scholarships", "secondary_plausible_categories": ["grants"], "classification_ambiguity": 0.5},
    ) == "ambiguous"
    assert annotate.validate("classify", {"primary_category": "scholarships", "classification_ambiguity": 0.7}) == "ambiguous"
    assert annotate.validate("classify", {"primary_category": "not_a_category"}) == "invalid"
    assert annotate.validate("classify", None) == "invalid"


def test_validate_summarize():
    assert annotate.validate("summarize", {"summary": "MANDATORY\n- x " + "word " * 50}) == "valid"
    assert annotate.validate("summarize", {"summary": "word " * 400}) == "invalid"


def test_agreement_classify():
    assert annotate.agreement("classify", {"primary_category": "phd"}, {"primary_category": "phd"}) == "agree"
    assert annotate.agreement("classify", {"primary_category": "phd"}, {"primary_category": "postdoc"}) == "disagree"
    assert annotate.agreement("summarize", {"summary": "x"}, {"summary": "y"}) is None


def test_stratified_sample_round_robin():
    records = []
    for i in range(30):
        records.append({"record_id": f"r{i}", "title": f"Scholarship {i}" if i < 10 else f"Thing {i}", "clean_text": "x" * 100})
    sample = annotate.stratified_sample(records, 12)
    assert len(sample) == 12
    kinds = [r["title"].split()[0] for r in sample]
    assert kinds.count("Scholarship") == 6, "round-robin mixes signal and no-signal buckets"
