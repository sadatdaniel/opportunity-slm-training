import pytest

from project.sources.registry import build_registry, domain_of, load_raw_sources, slugify


def test_slugify():
    assert slugify("Youth Opportunities") == "youth_opportunities"
    assert slugify("Erasmus+ / Erasmus Mundus Joint Masters") == "erasmus_erasmus_mundus_joint_masters"
    assert slugify("Türkiye Scholarships") == "turkiye_scholarships"


def test_domain_strips_www():
    assert domain_of("https://www.youthop.com/wp-json/wp/v2/posts") == "youthop.com"
    assert domain_of("http://opportunitydesk.org") == "opportunitydesk.org"


@pytest.fixture(scope="module")
def registry():
    return build_registry(load_raw_sources())


def test_registry_shape(registry):
    assert len(registry) >= 80  # the curated list has ~90 sources
    ids = [s["source_id"] for s in registry]
    assert len(ids) == len(set(ids)), "source ids must be unique"
    for source in registry:
        assert source["name"] and source["domain"] and source["postings_page"]
        assert source["origin_file"] == "100_academic_sources.md"
        assert not source["domain"].startswith("http")


def test_registry_scopes_preserved(registry):
    by_id = {s["source_id"]: s for s in registry}
    assert "scholarships" in by_id["youth_opportunities"]["scope"]
    assert "postdoc" in by_id["euraxess"]["scope"]
