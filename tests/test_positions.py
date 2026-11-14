"""Positions: one rule for where everything is (own, a grid cell, or what carries it), landmarks to place by name,
verify() to audit a subtree with a fix for each problem, and true spots for what is put down or walks in."""

from pathlib import Path

import pytest

from embody.cli import load_world
from embody.layout import ground
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def _laid(tmp_path):
    eng = Engine(tmp_path / "w.db", workspace=REPO, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, REPO / "examples" / "ferry-at-dusk")
    gm.layout(frame={"units": "m"}, placements=[
        {"entity": "Ashford Square", "at": [0, 0, 0], "radius": 30,
         "landmarks": {"the well": {"at": [5, 5, 0], "radius": 3}, "the notice board": {"at": [-10, 0, 0], "radius": 2}}},
        {"entity": "Pell's Mill", "at": [100, 0, 0], "radius": 20}],
        paths=[{"a": "Ashford Square", "b": "Pell's Mill", "route": [[25, 0, 0], [85, 0, 0]]}])
    gm.layout(placements=[{"entity": "Well", "at": [5, 5, 0], "radius": 1}])
    return eng, gm


def test_every_entity_resolves_own_or_inherited_and_map_says_which(tmp_path):
    eng, gm = _laid(tmp_path)
    m = gm.map(under="Ashford Square", depth=2)
    rows = {r["name"]: r for r in m["entities"]}
    assert rows["Well"]["how"] == "own" and rows["Well"]["spot"] == "at the well"
    assert rows["Tinderbox"]["how"] == "inherited" and rows["Tinderbox"]["from"] == "Mara"
    assert "Mara" in m["no_spot"]["names"]  # directly in a place, only the square's centre
    assert gm.measure("Tinderbox")["a"]["from"] == "Mara"


def test_verify_lists_each_problem_with_a_fix_and_can_apply_it(tmp_path):
    eng, gm = _laid(tmp_path)
    gm.layout(placements=[{"entity": "Bone", "at": [5, 5, 0]}, {"entity": "Bench", "at": [200, 0, 0]}])
    v = gm.verify(under="Ashford Square", limit=200)
    by = {r["name"]: r for r in v["page"]}
    assert by["Mara"]["problem"] == "no position" and "the well" in by["Mara"]["fix"]["or"]
    assert by["Bone"]["problem"] == "inside something solid" and by["Bone"]["fix"]["or_move_into"] == "Well"
    assert by["Bench"]["problem"] == "outside its container"
    assert "Tinderbox" not in by  # it rides on Mara
    assert v["next"] is None and v["by_problem"]["no position"] >= 1

    assert "Ashford Square" not in v.get("no_landmarks", {}).get("places", [])
    assert "Pell's Mill" in gm.verify()["no_landmarks"]["places"]  # Hob stands there and the mill names no spots
    assert len({tuple(r["fix"]["at"]) for r in v["page"] if isinstance(r.get("fix"), dict)}) == len(
        [r for r in v["page"] if isinstance(r.get("fix"), dict)])  # no two suggestions share a spot

    one = gm.verify(under="Ashford Square", limit=1)
    assert len(one["page"]) == 1 and one["next"] == 1

    fixed = gm.verify(under="Ashford Square", limit=200, apply=True)
    assert fixed["applied"] == v["problems"]
    assert gm.verify(under="Ashford Square")["problems"] == 0


def test_place_by_landmark_and_perceive_names_the_spot(tmp_path):
    eng, gm = _laid(tmp_path)
    lantern = gm.spawn("thing", "Ashford Square", "Lantern", at="the well")
    at = lantern["state"]["layout"]["at"]
    assert ground(at, [5, 5, 0]) <= 3 and ground(at, [5, 5, 0]) > 1  # by the well, not in it
    assert "position_notice" not in lantern
    with pytest.raises(Rejected) as r:
        gm.spawn("thing", "Ashford Square", "Pail", at="the gallows")
    assert "the well" in r.value.hint
    bare = gm.spawn("thing", "Ashford Square", "Pail")
    assert "no spot of its own" in bare["position_notice"] and "the well" in bare["position_notice"]

    gm.move("Traveler", "Ashford Square", at="the notice board")
    p = eng.session("pc")
    p.join("ferry-at-dusk", "Traveler")
    b = p.perceive()
    assert b["you"]["spot"] in ("at the notice board", "by the notice board")
    gm.layout(placements=[{"entity": "Traveler", "at": "Lantern"}])  # beside a thing, by its name
    assert ground(gm.measure("Traveler")["a"]["at"], at) <= 4


def test_what_is_put_down_or_walks_in_keeps_a_true_spot(tmp_path):
    eng, gm = _laid(tmp_path)
    gm.move("Traveler", "Ashford Square", at=[10, -10, 0])
    lantern = gm.spawn("thing", "Traveler", "Lantern")["id"]
    gm.move(lantern, "Ashford Square")  # put down: where the holder stands
    assert ground(gm.measure(lantern)["a"]["at"], [10, -10, 0]) <= 2
    gm.move("Traveler", "Pell's Mill")  # walked in: where the way comes in
    a = gm.measure("Traveler")["a"]
    assert a["how"] == "own" and ground(a["at"], [85, 0, 0]) <= 4
    gm.move("Traveler", "The Reeds")  # no drawn way: no spot, as before
    w = eng.world("ferry-at-dusk")
    assert "at" not in (w.get(gm.inspect("Traveler")["id"])["state"].get("layout") or {})
