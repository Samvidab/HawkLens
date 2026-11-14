"""Agentic annotation of commercial interiors: room labels as verified claims, pins, widget rooms."""
import json

from PIL import Image

from app.adapters.types import ImageRef, PanoramaRef
from app.agents import interior, verifier
from app.agents.aerial import Box
from app.config import get_settings
from app.events import load_events, reset_run
from app.widgets.registry import Room
from tests.test_aerial import profile
from tests.test_interior import MODEL, ROOMS, obs, panos

ROOM_INFO = [
    {"room_id": "r_small", "tags": ["unfurnished"], "keywords": [], "classifications": [],
     "dimensions": {"areaFloor": 10.4, "height": 2.7}, "pano_ids": ["p0", "p1"]},
    {"room_id": "r_big", "tags": ["unfurnished"], "keywords": [], "classifications": [],
     "dimensions": {"areaFloor": 73.6, "height": 2.7}, "pano_ids": ["p2", "p3", "p4", "p5"]},
    {"room_id": "r_none", "tags": [], "keywords": [], "classifications": [], "dimensions": {}, "pano_ids": ["p6"]},
]


def room_images():
    return {"r_small": [interior.image_id(MODEL, "p0", f) for f in (1, 2, 3, 4)],
            "r_big": [interior.image_id(MODEL, "p2", f) for f in (1, 2, 3, 4)],
            "r_none": [interior.image_id(MODEL, "p6", 1)]}


def room_obs():
    return interior.RoomLabelsObservation(rooms=[
        interior.RoomObs(room_id="r_small", type="private_office", confidence=0.8,
                         evidence_note="Single enclosed room with one door and a window",
                         marks=[Box(image_id=interior.image_id(MODEL, "p0", 1), label="door", x0=.1, y0=.1, x1=.3, y1=.9),
                                Box(image_id=interior.image_id(MODEL, "p2", 1), label="wrong room", x0=0, y0=0, x1=1, y1=1)]),
        interior.RoomObs(room_id="r_big", type="open_office", confidence=0.6,
                         evidence_note="Room for 12 desks"),  # invented number → note dropped
    ])


def base_findings():
    p = profile()
    ps = panos(9)
    imgs = [ImageRef(image_id=interior.image_id(MODEL, x.pano_id, f), source="matterport_pano", local_path="x")
            for x in ps for f in interior.FACES]
    return p, ps, interior.build_findings(p, MODEL, obs(), imgs, ps, interior.scan_areas(ROOMS, p))


def test_add_rooms_claims_pins_labels():
    p, ps, (f, claims) = base_findings()
    f2, claims2 = interior.add_rooms(p, f, claims, ROOM_INFO, room_images(), room_obs(), ps)
    rooms = {r.room_id: r for r in f2.rooms}
    assert rooms["r_small"].type == "private_office" and rooms["r_small"].confidence == 0.8
    assert rooms["r_small"].evidence_note == "Single enclosed room with one door and a window"
    assert rooms["r_big"].type == "open_office" and rooms["r_big"].evidence_note is None
    assert rooms["r_none"].type == "unknown" and rooms["r_none"].confidence == 0  # not answered
    assert rooms["r_small"].matterport_tags == ["unfurnished"]
    assert rooms["r_small"].area_sqft == round(10.4 * 10.763910416709722, 1)

    by = {c.field: c for c in claims2}
    c = by["interior.room.r_small"]
    assert c.value == "private_office" and c.agent == "interior" and c.claim_id == rooms["r_small"].claim_id
    assert c.evidence_ids == sorted(room_images()["r_small"])
    assert [m.label for m in c.marks] == ["door"]  # mark on another room's image dropped
    assert {"interior.lighting", "interior.hvac", "interior.window"} <= set(by)  # base claims kept

    pin = next(x for x in f2.pins if x.claim_id == c.claim_id)
    xs = [x.xyz for x in ps if x.pano_id in ("p0", "p1")]
    assert pin.xyz == tuple(sum(v[k] for v in xs) / 2 for k in range(3))
    assert pin.label == "Private office: Single enclosed room with one door and a window"
    assert len([x for x in f2.pins if ".interior.room." in x.claim_id]) == 3
    # idempotent: re-adding replaces, never duplicates
    f3, claims3 = interior.add_rooms(p, f2, claims2, ROOM_INFO, room_images(), room_obs(), ps)
    assert len(claims3) == len(claims2) and len(f3.pins) == len(f2.pins)


def test_widget_rooms_match_registry_room():
    p, ps, (f, claims) = base_findings()
    f2, _ = interior.add_rooms(p, f, claims, ROOM_INFO, room_images(), room_obs(), ps)
    rows = interior.widget_rooms(f2)
    assert [Room.model_validate(r).type for r in rows] == ["Private office", "Open office", "Unlabelled room"]
    # scan rooms (fallback for the resolver) must also be Room-shaped
    for r in interior.scan_areas(ROOMS, p)["rooms"]:
        Room.model_validate(r)


def test_rooms_prompt_lists_each_rooms_images():
    text = interior.rooms_prompt(profile(), ROOM_INFO, room_images(), question="- room_id `r_big`: desks?")
    assert "{{" not in text and "`r_small`" in text and interior.image_id(MODEL, "p2", 3) in text
    assert "desks?" in text


def test_verifier_prompt_and_labels_for_room_claims():
    p, ps, (f, claims) = base_findings()
    _, claims2 = interior.add_rooms(p, f, claims, ROOM_INFO, room_images(), room_obs(), ps)
    c = next(x for x in claims2 if x.field == "interior.room.r_small")
    text = verifier.prompt_for({"profile": p}, [(1, c)])
    assert "open_office, private_office, conference" in text and "this room's images:" in text
    assert verifier._label(c) == "private office (room r_sm)"
    assert verifier.safe_question("Is this one of 47 offices?", c, {"profile": p}).startswith(
        "Re-check the label of room r_sm")


async def test_inspect_and_reinspect_rooms(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    img = tmp_path / "face.jpg"
    Image.new("RGB", (32, 32), "grey").save(img)
    p = profile().model_copy(update={"matterport_model_id": MODEL, "showcase_url": "https://my.matterport.com/show/?m=hu9"})
    calls = []

    async def fake_rooms(m):
        return ROOMS

    async def fake_room_panos(m):
        return ROOM_INFO

    async def fake_panos(m):
        return panos(9)

    async def fake_face(pano, face):
        return img

    async def fake_vision(prompt, images, schema):
        calls.append(schema.__name__)
        if schema is interior.RoomLabelsObservation:
            if "Verifier questions" in prompt:  # re-check only the asked room
                return interior.RoomLabelsObservation(rooms=[
                    interior.RoomObs(room_id="r_big", type="conference", confidence=0.9,
                                     evidence_note="Long table with chairs around it")])
            return room_obs()
        return obs()

    async def no_mesh(m):
        raise interior.mp.MatterportError("unavailable")

    for name, fn in [("rooms", fake_rooms), ("room_panos", fake_room_panos), ("panoramas", fake_panos),
                     ("pano_face", fake_face), ("matterpak", no_mesh)]:
        monkeypatch.setattr(interior.mp, name, fn)
    monkeypatch.setattr(interior.llm, "vision_json", fake_vision)
    reset_run("ir1")
    try:
        res = await interior.inspect(p, "ir1")
        assert calls == ["InteriorObservation", "RoomLabelsObservation"]
        assert [r.type for r in res.findings.rooms] == ["private_office", "open_office", "unknown"]
        msgs = [e.message for e in load_events("ir1")]
        assert "room 1 (r_sm): private office" in msgs and "room 2 (r_bi): open office" in msgs

        big = next(c for c in res.claims if c.field == "interior.room.r_big")
        res2 = await interior.reinspect(p, res, [(big, "Is the long table a conference table?")])
        assert [r.type for r in res2.findings.rooms] == ["private_office", "conference", "unknown"]
        assert calls[-1] == "RoomLabelsObservation"  # base observation not re-asked

        by_id = {c.claim_id: c.model_copy(update={"status": "verified"}) for c in res2.claims}
        res3 = interior.with_statuses(res2, by_id)
        assert all(r.status == "verified" for r in res3.findings.rooms)
        interior.save(p, res3)
        d = tmp_path / "data" / "buildings" / "23551"
        rooms_json = json.loads((d / "rooms.json").read_text())
        assert [r["type"] for r in rooms_json] == ["Private office", "Conference room", "Unlabelled room"]
        saved = json.loads((d / "interior.json").read_text())
        assert saved["rooms"][1]["evidence_note"] == "Long table with chairs around it"
        assert json.loads((d / "interior_scan.json").read_text())["rooms"] == rooms_json
    finally:
        get_settings.cache_clear()


async def test_room_labelling_failure_leaves_rooms_unlabelled(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    img = tmp_path / "face.jpg"
    Image.new("RGB", (32, 32), "grey").save(img)
    p = profile().model_copy(update={"matterport_model_id": MODEL})

    async def fake_vision(prompt, images, schema):
        if schema is interior.RoomLabelsObservation:
            raise RuntimeError("boom")
        return obs()

    monkeypatch.setattr(interior.mp, "rooms", lambda m: _ret(ROOMS))
    monkeypatch.setattr(interior.mp, "room_panos", lambda m: _ret(ROOM_INFO))
    monkeypatch.setattr(interior.mp, "panoramas", lambda m: _ret(panos(9)))
    monkeypatch.setattr(interior.mp, "pano_face", lambda pano, face: _ret(img))
    monkeypatch.setattr(interior.mp, "matterpak", lambda m: _raise(interior.mp.MatterportError("x")))
    monkeypatch.setattr(interior.llm, "vision_json", fake_vision)
    reset_run("ir2")
    try:
        res = await interior.inspect(p, "ir2")
        assert [r.type for r in res.findings.rooms] == ["unknown"] * 3
        assert all(c.confidence == 0 for c in res.claims if c.field.startswith("interior.room."))
        assert "room labelling failed (RuntimeError); rooms left unlabelled" in [e.message for e in load_events("ir2")]
        assert res.findings.lighting_type == "fluorescent"  # the rest of the interior stands
    finally:
        get_settings.cache_clear()


async def _ret(v):
    return v


async def _raise(e):
    raise e


def test_merged_region_label():
    p, ps, (f, claims) = base_findings()
    o = room_obs()
    o.rooms[1] = interior.RoomObs(room_id="r_big", type="corridor", also_contains=["private_office", "corridor"],
                                  confidence=0.8, evidence_note="Hallway with office doors off it")
    f2, claims2 = interior.add_rooms(p, f, claims, ROOM_INFO, room_images(), o, ps)
    big = next(r for r in f2.rooms if r.room_id == "r_big")
    assert big.type == "corridor" and big.also_contains == ["private_office"]
    assert next(c for c in claims2 if c.field == "interior.room.r_big").value == "corridor + private_office"
    assert interior.widget_rooms(f2)[1]["type"] == "Corridor + private offices"
    assert verifier._label(next(c for c in claims2 if c.field == "interior.room.r_big")) == \
        "corridor + private office (room r_bi)"


async def test_big_rooms_get_more_panoramas(monkeypatch, tmp_path):
    img = tmp_path / "f.jpg"
    Image.new("RGB", (8, 8)).save(img)

    async def fake_face(pano, face):
        return img

    monkeypatch.setattr(interior.mp, "pano_face", fake_face)
    imgs, _ = await interior.fetch_room_images(MODEL, ROOM_INFO, panos(9))
    assert len(imgs["r_small"]) == 4  # 10 m2 → 1 pano × 4 faces
    assert len(imgs["r_big"]) == 4 + 2 + 2 + 2  # 74 m2 → 4 panos
