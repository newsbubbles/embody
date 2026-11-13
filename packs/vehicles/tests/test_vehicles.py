"""Vehicles: board and alight, a trip with a middle that people along the road see and can stop, blockers, a run on
a timetable with no mind, the costs a world turns on, and a trip that outlives the server."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "road", "name": "The road", "seed": 5, "description": "Two yards and a road between.", "requires": ["vehicles"]}

def define(s):
    s.define_schema("person", extends="creature")

def populate(s):
    root = s.summary()["root"]
    yard = s.spawn("place", root, "Yard")["id"]
    road = s.spawn("place", root, "Road")["id"]
    gate = s.spawn("place", root, "Gate")["id"]
    s.connect(yard, road)
    s.connect(road, gate)
    cart = s.spawn("vehicle", yard, "Cart", state={"stops": ["Yard", "Gate"], "route": ["Yard", "Road", "Gate"],
                                                   "leg_time": 100, "seats": 2, "cargo": 4})["id"]
    s.spawn("wheel", cart, "Reins")
    s.spawn("person", yard, "Ada")
    s.spawn("person", yard, "Cy")
    s.spawn("person", road, "Bel", state={"body": 2})
    s.spawn("thing", yard, "Sack", state={"portable": True, "bulk": 3})
    s.clock(run=False)
'''


def world(tmp_path, db=None):
    ws = tmp_path / "ws"
    if not ws.exists():
        shutil.copytree(REPO / "packs" / "vehicles", ws / "packs" / "vehicles",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        (ws / "worlds" / "road").mkdir(parents=True)
        (ws / "worlds" / "road" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(str(db) if db else None, workspace=ws, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "road")
    return eng, gm


def roll(w, secs):
    # the clock as a host runs it, a few seconds at a time: a periodic tick fires once a step, however long the step
    for _ in range(int(secs) // 5):
        w.step(5)


def seat(eng, who):
    s = eng.session(who.lower())
    s.join("road", who)
    return s


def where(gm, name):
    return gm.world.get(gm.world.get(gm.inspect(name)["id"])["parent_id"])["name"]


def cart(gm):
    return gm.world.get(gm.inspect("Cart")["id"])["state"]


def kinds(eng, who, since=0):
    return [e["kind"] for e in eng.world("road").events(since=since, limit=500, touching=eng.world("road").find(name=who)[0]["id"])]


def test_board_and_alight_and_the_cart_is_seen_from_outside(tmp_path):
    eng, gm = world(tmp_path)
    ada, cy = seat(eng, "Ada"), seat(eng, "Cy")
    seen = {c["name"]: c for c in ada.perceive()["present"]}
    assert seen["Cart"]["type"] == "vehicle"  # a thing in the yard, with its card
    with pytest.raises(Rejected, match="aboard Cart first"):
        ada.act("drive", "Cart", params={"to": "Gate"})
    r = ada.act("board", "Cart")
    assert any(e["kind"] == "boarded" for e in r["events"]) and where(gm, "Ada") == "Cart"
    assert ada.perceive()["here"]["name"] == "Cart"
    cy.act("board", "Cart")
    gm.spawn("person", gm.inspect("Yard")["id"], "Dov")
    dov = seat(eng, "Dov")
    with pytest.raises(Rejected, match="full"):
        dov.act("board", "Cart")
    with pytest.raises(Rejected, match="already aboard"):
        ada.act("board", "Cart")
    ada.act("alight", "Cart")
    assert where(gm, "Ada") == "Yard"


def test_a_trip_has_a_middle_that_the_road_sees_and_can_stop(tmp_path):
    eng, gm = world(tmp_path)
    w = gm.world
    ada, bel = seat(eng, "Ada"), seat(eng, "Bel")
    ada.act("board", "Cart")
    with pytest.raises(Rejected, match="one of Road, Gate"):
        ada.act("drive", "Cart", params={"to": "the moon"})
    r = ada.act("drive", "Reins", params={"to": "gate"})  # the wheel drives the cart it stands in
    assert any(e["kind"] == "departed" for e in r["events"])
    assert cart(gm)["moving"] and cart(gm)["trip"]["eta"] == pytest.approx(w.t + 200)
    roll(w, 30)
    assert where(gm, "Cart") == "Yard"  # still pulling out
    roll(w, 40)
    assert where(gm, "Cart") == "Road" and where(gm, "Ada") == "Cart"  # halfway through the leg: in the road
    bf = bel.perceive()
    assert "Cart" in [c["name"] for c in bf["present"]]
    assert {"passing", "scene"} <= {e["kind"] for e in bf["events"]}
    card = next(c for c in bf["present"] if c["name"] == "Cart")
    assert card["state"]["trip"]["to"] == gm.inspect("Gate")["id"] and "fault" not in card["state"]  # no peeking at the dice
    with pytest.raises(Rejected, match="already on the road"):
        ada.act("drive", "Cart", params={"to": "Yard"})
    r = bel.act("halt", "Cart")  # someone in its road stops it
    assert cart(gm)["moving"] is False and cart(gm)["stopped"] == "halted"
    roll(w, 300)
    assert where(gm, "Cart") == "Road"  # a trip someone drove waits for its driver
    ada.act("drive", "Cart", params={"to": "Gate"})
    roll(w, 120)
    assert where(gm, "Cart") == "Gate" and not cart(gm)["moving"]
    assert "pulled_in" in kinds(eng, "Ada")
    ada.act("alight", "Cart")
    assert where(gm, "Ada") == "Gate"


def test_alighting_on_the_road_leaves_you_there_and_the_cart_stops_without_its_driver(tmp_path):
    eng, gm = world(tmp_path)
    w = gm.world
    ada, cy = seat(eng, "Ada"), seat(eng, "Cy")
    ada.act("board", "Cart")
    cy.act("board", "Cart")
    ada.act("drive", "Cart", params={"to": "Gate"})
    roll(w, 60)
    cy.act("alight", "Cart")
    assert where(gm, "Cy") == "Road"
    ada.act("alight", "Cart")
    roll(w, 20)
    assert cart(gm)["moving"] is False and cart(gm)["stopped"] == "nobody at the wheel" and where(gm, "Cart") == "Road"


def test_a_blocker_stops_it_and_the_load_counts(tmp_path):
    eng, gm = world(tmp_path)
    w = gm.world
    ada = seat(eng, "Ada")
    gm.spawn("thing", gm.inspect("Road")["id"], "Barricade", state={"blocks_road": True})
    gm.move(gm.inspect("Sack")["id"], gm.inspect("Cart")["id"])
    gm.spawn("thing", gm.inspect("Cart")["id"], "Second sack", state={"portable": True, "bulk": 3})
    ada.act("board", "Cart")
    with pytest.raises(Rejected, match="overloaded"):
        ada.act("drive", "Cart", params={"to": "Gate"})
    gm.destroy(gm.inspect("Second sack")["id"])
    ada.act("drive", "Cart", params={"to": "Gate"})
    roll(w, 200)
    assert where(gm, "Cart") == "Road" and cart(gm)["stopped"] == "blocked by Barricade"
    assert where(gm, "Sack") == "Cart"  # the load rode along


def test_a_run_on_a_timetable_needs_no_mind_and_halts_when_its_driver_falls(tmp_path):
    eng, gm = world(tmp_path)
    w = gm.world
    cid = gm.inspect("Cart")["id"]
    gm.spawn("person", cid, "Garran")
    gm.patch(cid, {"timetable": {"every": 300}, "driver": "Garran"})
    roll(w, 20)
    assert cart(gm)["next_departure"] == 300
    roll(w, 290)
    assert cart(gm)["moving"] and cart(gm)["trip"]["run"] and cart(gm)["trip"]["to"] == gm.inspect("Gate")["id"]
    roll(w, 210)
    assert where(gm, "Cart") == "Gate" and where(gm, "Garran") == "Cart"
    roll(w, 100)  # the next slot (600): back the other way
    assert cart(gm)["moving"] and cart(gm)["trip"]["to"] == gm.inspect("Yard")["id"]
    roll(w, 60)
    assert where(gm, "Cart") == "Road"
    gm.patch(gm.inspect("Garran")["id"], {"down": True})
    roll(w, 20)
    assert not cart(gm)["moving"] and cart(gm)["stopped"] == "nobody at the wheel" and where(gm, "Cart") == "Road"
    roll(w, 600)
    assert where(gm, "Cart") == "Road"  # a driver down halts the run
    gm.patch(gm.inspect("Garran")["id"], {"down": False})
    roll(w, 150)
    assert where(gm, "Cart") == "Yard" and not cart(gm)["moving"]  # back on his feet, he takes it on where it was going


def test_a_world_dispatches_and_holds_it(tmp_path):
    eng, gm = world(tmp_path)
    w = gm.world
    cid = gm.inspect("Cart")["id"]
    gm.patch(cid, {"hold": "the factor keeps it in"})
    ada = seat(eng, "Ada")
    ada.act("board", "Cart")
    with pytest.raises(Rejected, match="the factor keeps it in"):
        ada.act("drive", "Cart", params={"to": "Gate"})
    gm.patch(cid, {"hold": None, "dispatch": {"to": "Gate"}})
    roll(w, 20)
    assert cart(gm)["moving"] and cart(gm)["trip"]["run"] and "dispatch" not in cart(gm)
    gm.patch(cid, {"hold": True})
    roll(w, 20)
    assert not cart(gm)["moving"] and cart(gm)["stopped"] == "held"
    gm.patch(cid, {"hold": None})
    roll(w, 400)
    assert where(gm, "Cart") == "Gate"  # a run takes up its trip again once nothing stops it


def test_fuel_breakdowns_and_a_hull(tmp_path):
    eng, gm = world(tmp_path)
    w = gm.world
    cid = gm.inspect("Cart")["id"]
    gm.patch(cid, {"fuel_per_leg": 1, "fuel": 1, "fuel_kind": "oil", "fuel_max": 4})
    ada = seat(eng, "Ada")
    ada.act("board", "Cart")
    ada.act("drive", "Cart", params={"to": "Gate"})
    roll(w, 200)
    assert where(gm, "Cart") == "Road" and cart(gm)["stopped"] == "out of fuel"
    with pytest.raises(Rejected, match="no fuel"):
        ada.act("drive", "Cart", params={"to": "Gate"})
    gm.spawn("thing", gm.inspect("Ada")["id"], "Oil", state={"portable": True, "kind": "oil", "count": 6})
    ada.act("refuel", "Cart", params={"item": "Oil"})
    assert cart(gm)["fuel"] == 4 and gm.world.get(gm.inspect("Oil")["id"])["state"]["count"] == 2
    gm.patch(cid, {"breakdown": 1.0})
    ada.act("drive", "Cart", params={"to": "Gate"})
    roll(w, 60)
    assert cart(gm)["broken"] and not cart(gm)["moving"] and where(gm, "Cart") == "Gate"
    with pytest.raises(Rejected, match="repair it first"):
        ada.act("drive", "Cart", params={"to": "Yard"})
    gm.patch(cid, {"breakdown": None})
    ada.act("repair", "Cart")
    roll(w, 1800)
    assert not cart(gm)["broken"]
    bel = seat(eng, "Bel")
    gm.move(gm.inspect("Bel")["id"], gm.inspect("Gate")["id"])
    with pytest.raises(Rejected, match="too much for your hands"):
        bel.act("strike", "Cart")
    gm.patch(cid, {"hull": 3, "hull_max": 10})
    r = bel.act("strike", "Cart")
    assert r["result"]["hull"] == 0 and cart(gm)["broken"]  # 1d6 + 2 from a hull of 3


def test_a_trip_outlives_the_server(tmp_path):
    db = tmp_path / "embody.db"
    eng, gm = world(tmp_path, db)
    ada = seat(eng, "Ada")
    ada.act("board", "Cart")
    ada.act("drive", "Cart", params={"to": "Gate"})
    roll(gm.world, 60)
    assert where(gm, "Cart") == "Road"
    eng.store.close() if hasattr(eng.store, "close") else None
    del eng, gm, ada
    eng2 = Engine(str(db), workspace=tmp_path / "ws", record=False)
    gm2 = eng2.session("gm", capabilities=[AUTHOR])
    gm2.use("road")
    roll(gm2.world, 200)
    assert where(gm2, "Cart") == "Gate" and where(gm2, "Ada") == "Cart"


def test_followers_of_followers_board_and_alight_together(tmp_path):
    eng, gm = world(tmp_path)
    gm.patch("Cart", {"seats": 3})
    gm.spawn("person", gm.inspect("Yard")["id"], "Dov")
    gm.patch("Cy", {"follows": gm.inspect("Ada")["id"]})
    gm.patch("Dov", {"follows": gm.inspect("Cy")["id"]})
    ada = seat(eng, "Ada")
    ada.act("board", "Cart")
    assert [where(gm, n) for n in ["Ada", "Cy", "Dov"]] == ["Cart"] * 3
    ada.act("alight", "Cart")
    assert [where(gm, n) for n in ["Ada", "Cy", "Dov"]] == ["Yard"] * 3
