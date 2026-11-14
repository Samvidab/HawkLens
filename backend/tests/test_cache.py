import pytest

from app.adapters.cache import CacheMiss, cache_key, cached, cached_bytes


def test_key_ignores_param_order():
    assert cache_key("x", {"a": 1, "b": 2}) == cache_key("x", {"b": 2, "a": 1})
    assert cache_key("x", {"a": 1}) != cache_key("y", {"a": 1})


async def test_read_only_miss_raises(tmp_path):
    with pytest.raises(CacheMiss):
        await cached("costar.get_property", {"id": "1"}, lambda: {"x": 1},
                     mode="read_only", root=tmp_path)


async def test_read_write_then_read_only_hit(tmp_path):
    calls = []

    async def fetch():
        calls.append(1)
        return {"x": 1}

    params = {"id": "1"}
    assert await cached("ns", params, fetch, mode="read_write", root=tmp_path) == {"x": 1}
    assert await cached("ns", params, fetch, mode="read_write", root=tmp_path) == {"x": 1}
    assert await cached("ns", params, fetch, mode="read_only", root=tmp_path) == {"x": 1}
    assert len(calls) == 1


async def test_off_always_calls_and_never_writes(tmp_path):
    calls = []

    def fetch():
        calls.append(1)
        return 5

    for _ in range(2):
        assert await cached("ns", {}, fetch, mode="off", root=tmp_path) == 5
    assert len(calls) == 2
    assert not any(tmp_path.iterdir())


async def test_bytes_saved_under_media(tmp_path):
    path = await cached_bytes("vexcel.overhead", {"p": 1}, lambda: b"img",
                              ext=".jpg", mode="read_write", root=tmp_path)
    assert path.parent == tmp_path / "media" and path.read_bytes() == b"img"
    again = await cached_bytes("vexcel.overhead", {"p": 1}, lambda: b"other",
                               ext=".jpg", mode="read_only", root=tmp_path)
    assert again == path and again.read_bytes() == b"img"
    with pytest.raises(CacheMiss):
        await cached_bytes("vexcel.overhead", {"p": 2}, lambda: b"x",
                           ext=".jpg", mode="read_only", root=tmp_path)
