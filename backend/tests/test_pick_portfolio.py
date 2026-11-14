import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "pick_portfolio", Path(__file__).resolve().parent.parent / "scripts" / "pick_portfolio.py")
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)


def cand(pid, lat, lon, aerial=1, mp=1, **kw):
    base = {"property_id": pid, "name": f"B{pid}", "lat": lat, "lon": lon, "year_built": 1980,
            "matterport_model_ids": [f"m{pid}_{i}" for i in range(mp)], "aerial_attachments": aerial,
            "rba_sqft": 200_000, "stories": 10}
    return base | kw


def test_eligible_filters():
    assert pp.eligible(cand(1, 29.7, -95.4))
    assert not pp.eligible(cand(1, 29.7, -95.4, mp=0))
    assert not pp.eligible(cand(1, 29.7, -95.4, aerial=0))
    assert not pp.eligible(cand(1, 29.7, -95.4, stories=40))
    assert not pp.eligible(cand(1, 29.7, -95.4, rba_sqft=50_000))
    assert not pp.eligible(cand(1, 29.7, -95.4, name=None))


def test_pick_ranks_by_imagery_and_enforces_spacing():
    a = cand(1, 29.70, -95.40, aerial=9)
    near_a = cand(2, 29.7001, -95.4001, aerial=8)  # ~15 m from a: dropped
    b = cand(3, 29.80, -95.40, aerial=2)
    c = cand(4, 29.90, -95.40, aerial=1)
    assert [h["property_id"] for h in pp.pick([c, near_a, b, a], 3)] == [1, 3, 4]
