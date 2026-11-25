"""Three seams in positions a second world's playtest found: a body made from a template stands somewhere of its own
(verify does not flag it later), `at` in a patch places the entity instead of writing a state key, and a quiet move
may give a body with no spot its first one."""

import pytest

from embody.layout import ground
from embody.ops import Rejected
from tests.test_positions import _laid


def test_a_template_newcomer_gets_its_own_spot_and_verify_finds_nothing(tmp_path):
    eng, gm = _laid_with_template(tmp_path, {"type": "person", "place": "Ashford Square"})
    guest = eng.session_for_token(gm.invite("player", label="wren")["token"])
    me = guest.join(template="villager", name="Wren")["you"]["id"]
    assert eng.world("ferry-at-dusk").need(me)["state"]["layout"]["at"]  # its own spot, not the square's centre
    assert not [p for p in gm.verify(under="Ashford Square", limit=200)["page"] if p["id"] == me]


def test_a_template_may_name_where_newcomers_arrive_and_a_bad_name_refuses_before_anyone_is_made(tmp_path):
    eng, gm = _laid_with_template(tmp_path / "a", {"type": "person", "place": "Ashford Square", "at": "the notice board"})
    guest = eng.session_for_token(gm.invite("player", label="wren")["token"])
    me = guest.join(template="villager", name="Wren")["you"]["id"]
    assert ground(gm.measure(me)["a"]["at"], [-10, 0, 0]) <= 4

    eng2, gm2 = _laid_with_template(tmp_path / "b", {"type": "person", "place": "Ashford Square", "at": "the gallows"})
    g2 = eng2.session_for_token(gm2.invite("player", label="moss")["token"])
    with pytest.raises(Rejected):
        g2.join(template="villager", name="Moss")
    assert not eng2.world("ferry-at-dusk").find(name="Moss")


def test_at_in_a_patch_places_the_entity_and_writes_no_state_key(tmp_path):
    eng, gm = _laid(tmp_path)
    out = gm.patch("Mara", {"at": "the well", "mood": "tired"})
    assert "at" not in out["state"] and out["state"]["mood"] == "tired"
    assert ground(gm.measure("Mara")["a"]["at"], [5, 5, 0]) <= 3
    with pytest.raises(Rejected) as r:
        gm.patch("Mara", {"at": "the gallows", "mood": "cross"})
    assert "the well" in r.value.hint
    assert gm.inspect("Mara")["state"]["mood"] == "tired"  # a bad name changes nothing


def test_a_quiet_move_may_give_a_body_with_no_spot_its_first_one(tmp_path):
    eng, gm = _laid(tmp_path)
    gm.spawn("thing", "Pell's Mill", "Crate")
    gm.move("Crate", "Ashford Square", quiet=True, at="the notice board")
    assert ground(gm.measure("Crate")["a"]["at"], [-10, 0, 0]) <= 4
    with pytest.raises(Rejected) as r:  # now it has one, and a quiet move keeps it
        gm.move("Crate", "Pell's Mill", quiet=True, at=[100, 5, 0])
    assert "keeps the spot" in r.value.reason


def _laid_with_template(tmp, template):
    tmp.mkdir(exist_ok=True)
    eng, gm = _laid(tmp)
    w = eng.world("ferry-at-dusk")
    gm.patch(w.root_id, {"templates": {"villager": template}})
    return eng, gm


def test_an_arrival_by_a_way_with_no_route_lands_by_the_door_or_near_the_centre(tmp_path):
    # a world builder, 2026-11-24: every body that walked in by an undrawn way stood nowhere, and verify flagged it
    eng, gm = _laid(tmp_path)
    w = eng.world("ferry-at-dusk")
    root = w.root_id
    gm.spawn("place", root, "Back Lane")
    gm.spawn("place", root, "Loft")
    gm.connect("Pell's Mill", "Back Lane")
    gm.connect("Pell's Mill", "Loft")
    gm.layout(placements=[
        {"entity": "Back Lane", "at": [100, 60, 0], "radius": 15,
         "landmarks": {"the mill gate": {"at": [100, 50, 0], "radius": 2}, "Pell's Mill": {"at": [95, 48, 0], "radius": 2}}},
        {"entity": "Loft", "at": [140, 0, 0], "radius": 10}])
    for name in ("Crate", "Sack"):
        gm.spawn("thing", "Pell's Mill", name)
    gm.move("Crate", "Back Lane")
    assert ground(gm.measure("Crate")["a"]["at"], [95, 48, 0]) <= 2.5  # the landmark named for where it came from
    gm.move("Sack", "Loft")
    assert ground(gm.measure("Sack")["a"]["at"], [140, 0, 0]) <= 3  # no landmark: near the centre
    assert not [p for p in gm.verify(limit=500)["page"] if p["name"] in ("Crate", "Sack")]
    gm.spawn("place", root, "Nowhere")  # a place with no spot of its own: nothing to stand by
    gm.connect("Pell's Mill", "Nowhere")
    gm.spawn("thing", "Pell's Mill", "Barrel")
    gm.move("Barrel", "Nowhere")
    assert "at" not in (w.need(w.find(name="Barrel")[0]["id"])["state"].get("layout") or {})
