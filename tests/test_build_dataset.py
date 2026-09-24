import json

from project.build_dataset import assign_splits, quality_tier, stable_rank


def rec(rid, source="src_a"):
    return {"record_id": rid, "source_id": source, "title": rid, "clean_text": "x" * 200}


def test_quality_tier():
    assert quality_tier({"parsed_annotation": None}) == "quarantine"
    assert quality_tier({"parsed_annotation": {}, "review_status": "approved"}) == "gold"
    assert quality_tier({"parsed_annotation": {}, "needs_human_review": True}) == "quarantine"
    assert quality_tier({"parsed_annotation": {}}) == "silver"


def test_stable_rank_deterministic():
    assert stable_rank("a", "salt") == stable_rank("a", "salt")
    assert stable_rank("a", "salt") != stable_rank("b", "salt")


def test_splits_keep_duplicate_groups_together():
    records = [rec(f"r{i}", f"src_{i % 3}") for i in range(100)]
    # fake a duplicate group linking r0 and r99 (different "titles")
    import pathlib
    import tempfile

    groups = [{
        "canonical_record_id": "r0",
        "members": [{"record_id": "r0"}, {"record_id": "r99"}],
    }]
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "duplicate_groups.json"
        p.write_text(json.dumps(groups), encoding="utf-8")
        import project.build_dataset as bd

        original = bd.GROUPS_PATH
        bd.GROUPS_PATH = p
        try:
            splits, held_out = assign_splits(records, "classify")
        finally:
            bd.GROUPS_PATH = original

    all_splits = {**{k: [r["record_id"] for r in v] for k, v in splits.items()}}
    train, test = all_splits["train"], all_splits["test"]
    assert not ("r0" in train and "r99" in test), "duplicate group leaked across splits"
    assert held_out, "unseen-source split should hold out at least one source"
    for held in held_out:
        assert all(
            r["source_id"] == held for r in splits["unseen_sources_test"] if r["source_id"] == held
        )
    total = sum(len(v) for v in splits.values())
    assert total == 100
