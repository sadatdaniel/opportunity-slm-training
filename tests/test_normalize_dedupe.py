
from project.dedupe import find_duplicate_groups, normalize_title, prefer_canonical
from project.normalize import clean_text, is_english, normalize_record


def rec(i, title, text, source="s1", url=None, published="2026-01-01"):
    from collectors.records import content_hash, stable_record_id

    url = url or f"https://{source}.test/{i}"
    return {
        "record_id": stable_record_id(url),
        "source_id": source,
        "title": title,
        "clean_text": text,
        "content_hash": content_hash(f"{title}\n{text}"),
        "canonical_url": url,
        "published_at": published,
    }


def test_clean_text_removes_share_junk():
    text = "Eligibility\nShare this:\nFacebook\nLinkedIn\n\n\n\nOpen to students under 30."
    cleaned = clean_text(text)
    assert "Share this" not in cleaned
    assert "Eligibility" in cleaned
    assert "students under 30" in cleaned


def test_clean_text_preserves_deadline():
    text = "Benefits\nDeadline: 30 November 2026\nApply online."
    assert "Deadline: 30 November 2026" in clean_text(text)


def test_is_english():
    assert is_english("The scholarship is open to students who must apply before the deadline")
    assert not is_english("Das Stipendium richtet sich an Studierende aller Fachrichtungen")


def test_normalize_record_drops_short():
    assert normalize_record(rec(1, "t", "too short " * 5)) is None
    kept = normalize_record(rec(2, "t", "word " * 60))
    assert kept is not None and kept["word_count"] == 60


def test_dedupe_exact_hash_group():
    a = rec(1, "Same Title", "body " * 50)
    b = rec(2, "Same Title", "body " * 50, source="s2")
    c = rec(3, "Different Thing", "other " * 50)
    groups = find_duplicate_groups([a, b, c])
    assert sorted(len(g) for g in groups) == [1, 2]


def test_dedupe_near_title_group():
    a = rec(1, "Fully Funded PhD Positions in Quantum Computing 2026", "text a " * 50)
    b = rec(2, "Fully Funded PhD Positions in Quantum Computing 2026!", "text b " * 50, source="s2")
    c = rec(3, "Call for Papers: Workshop on Ethics", "text c " * 50)
    groups = find_duplicate_groups([a, b, c])
    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 2]


def test_prefer_canonical_most_complete():
    short = rec(1, "T", "word " * 50)
    long = rec(2, "T", "word " * 120, source="s2")
    assert prefer_canonical([0, 1], [short, long]) == 1


def test_normalize_title_strips_noise():
    assert "2026" not in normalize_title("Great Scholarship 2026")
    assert normalize_title("Apply Now: MBA Fellowship") == "mba fellowship"
