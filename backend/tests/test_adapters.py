"""T0.4 adapter checks. CoStar runs against the local kit (skipped when the kit is absent)."""
import pytest

from app.adapters import cache as cache_mod
from app.adapters import costar
from app.config import get_settings

SAMPLE_ID = 23347  # 333 Northbelt, Houston office (adapters/README.md)

needs_kit = pytest.mark.skipif(not costar._jsonl().exists(), reason="CoStar kit not found at COSTAR_KIT_DIR")


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("CACHE_MODE", "read_write")
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def _read_only(monkeypatch):
    monkeypatch.setenv("CACHE_MODE", "read_only")
    get_settings.cache_clear()


def test_format_address():
    pa = {"streetNumber": "333", "streetName": "Sam Houston", "streetType": "Pky", "city": "Houston",
          "state": "TX", "postcode": "770602414"}
    assert costar.format_address(pa) == "333 Sam Houston Pky, Houston, TX 77060"


def test_year_built_uses_construction_complete():
    rec = {"constructionEvents": [{"eventType": 4, "year": 2024}, {"eventType": 2, "year": 1980}]}
    assert costar.year_built(rec) == 1980
    assert costar.year_built({"constructionEvents": []}) is None


@needs_kit
async def test_get_property_then_cache_hit(isolated_cache, monkeypatch):
    rec = await costar.get_property(SAMPLE_ID)
    assert rec["id"] == SAMPLE_ID
    assert rec["primaryAddress"]["researchMarketId"] == costar.MARKET_ID["Houston"]

    _read_only(monkeypatch)
    monkeypatch.setattr(costar, "_find_record", lambda pid: pytest.fail("should be a cache hit"))
    assert (await costar.get_property(str(SAMPLE_ID)))["id"] == SAMPLE_ID


@needs_kit
async def test_matterport_ids_match_record_attachments(isolated_cache):
    ids = await costar.matterport_model_ids(SAMPLE_ID)
    rec = await costar.get_property(SAMPLE_ID)
    assert ids and sorted(ids) == costar.matterport_keys(rec)


@needs_kit
async def test_search_houston_offices_cached(isolated_cache, monkeypatch):
    hits = await costar.search_properties("Houston", property_types=["Office"], min_sqft=100_000, limit=10)
    assert 0 < len(hits) <= 10
    assert all(h["market_id"] == 14 and h["property_type"] == "Office" and h["rba_sqft"] >= 100_000 for h in hits)
    assert [h["rba_sqft"] for h in hits] == sorted((h["rba_sqft"] for h in hits), reverse=True)

    _read_only(monkeypatch)
    monkeypatch.setattr(costar, "_iter_records", lambda: pytest.fail("should be a cache hit"))
    again = await costar.search_properties("Houston", property_types=["Office"], min_sqft=100_000, limit=10)
    assert again == hits


async def test_read_only_miss_never_reads_kit(isolated_cache, monkeypatch):
    _read_only(monkeypatch)
    monkeypatch.setattr(costar, "_find_record", lambda pid: pytest.fail("kit touched in read_only"))
    with pytest.raises(cache_mod.CacheMiss):
        await costar.get_property(1)
