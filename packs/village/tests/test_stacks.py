"""Stacks: a thing whose state has a `count` is that many of itself. take, drop, give and put move part of one with
`count`, or all of it without; what arrives joins a like stack; bulk is a unit's; cards and events carry the count."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "yard", "name": "The pile", "seed": 3, "description": "A yard with a pile of glass.", "requires": ["village"]}

GLASS = {"portable": True, "kind": "ember", "bulk": 0.1, "description": "A shard, dull red."}

def define(s):
    s.define_schema("person", extends="creature",
                    actions={"take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here",
                                      "params": {"count": "how many of a stack"}},
                             "drop": {"script": "drop", "doc": "Put down", "targets": "thing", "scope": "held"},
                             "give": {"script": "give", "doc": "Hand over", "targets": "creature", "scope": "here",
                                      "params": {"item": "what", "count": "how many"}},
                             "put": {"script": "put", "doc": "Put it on or in", "targets": "thing",
                                     "params": {"item": "what", "count": "how many"}},
                             "burn": {"script": "burn", "doc": "Burn it", "targets": "thing"},
                             "tally": {"script": "tally", "doc": "Count what you carry"}})
    s.define_script("tally", "def apply(ctx):\\n    return [ctx.count(ctx.actor, 'ember'), ctx.count(ctx.actor, 'Emberglass'), ctx.load(ctx.actor)]\\n")

def populate(s):
    root = s.summary()["root"]
    yard = s.spawn("place", root, "Yard", state={"fire": True})["id"]
    s.spawn("thing", yard, "Emberglass", state=dict(GLASS, count=60))
    s.spawn("thing", yard, "Crate", state={"portable": False, "holds": ["any"], "room": 1})
    s.spawn("thing", yard, "Rope", state={"portable": True, "bulk": 3, "burnable": True, "count": 4})
    s.spawn("person", yard, "Ada", state={"carry": 5})
    bel = s.spawn("person", yard, "Bel")["id"]
    s.spawn("thing", bel, "Emberglass", state=dict(GLASS, count=2))
    s.clock(run=False)
'''


@pytest.fixture
def yard(tmp_path):
    shutil.copytree(REPO / "packs" / "village", tmp_path / "packs" / "village",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "yard").mkdir(parents=True)
    (tmp_path / "worlds" / "yard" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "yard")
    ada = eng.session("ada")
    ada.join("yard", "Ada")
    bel = eng.session("bel")
    bel.join("yard", "Bel")
    return eng, gm, ada, bel


def glass(eng, who):
    w = eng.world("yard")
    me = w.find(name=who)[0]["id"]
    return [(c["id"], c["state"].get("count")) for c in w.children(me) if c["name"] == "Emberglass"]


def test_taking_part_of_a_stack_splits_it_and_the_card_shows_the_count(yard):
    eng, gm, ada, bel = yard
    r = ada.act("take", "Emberglass", params={"count": 12})
    taken = [e for e in r["events"] if e["kind"] == "taken"][0]
    assert taken["payload"]["count"] == 12
    assert glass(eng, "Ada") == [(taken["payload"]["item"], 12)]
    here = {c["name"]: c for c in ada.perceive()["present"]}
    assert here["Emberglass"]["count"] == 48
    held = {c["name"]: c for c in ada.perceive()["holding"]}
    assert held["Emberglass"]["count"] == 12
    # a second take joins the first: one stack in the hand
    ada.act("take", "Emberglass", params={"count": 8})
    assert [n for _, n in glass(eng, "Ada")] == [20]


def test_bulk_is_a_units_and_a_fraction_counts(yard):
    eng, gm, ada, bel = yard
    ada.act("take", "Emberglass", params={"count": 40})  # 40 x 0.1 = 4 of 5
    with pytest.raises(Rejected) as r:
        ada.act("take", "Emberglass", params={"count": 11})
    assert "hands are full" in r.value.reason and "take fewer" in r.value.reason
    ada.act("take", "Emberglass", params={"count": 10})
    assert [n for _, n in glass(eng, "Ada")] == [50]
    with pytest.raises(Rejected) as r:
        ada.act("take", "Rope", params={"count": 1})  # 3 a coil, 5 in hand already
    assert "hands are full" in r.value.reason


def test_a_bad_count_is_refused_with_how_many_there_are(yard):
    eng, gm, ada, bel = yard
    with pytest.raises(Rejected) as r:
        ada.act("take", "Emberglass", params={"count": 61})
    assert "there are 60 of Emberglass" in r.value.reason


def test_no_count_moves_the_whole_stack(yard):
    eng, gm, ada, bel = yard
    gm.patch("Ada", {"carry": 10})
    ada.act("take", "Emberglass")
    assert [n for _, n in glass(eng, "Ada")] == [60]
    ada.act("drop", "Emberglass", params={"count": 25})
    assert [n for _, n in glass(eng, "Ada")] == [35]
    here = [c for c in ada.perceive()["present"] if c["name"] == "Emberglass"]
    assert [c["count"] for c in here] == [25]


def test_given_one_at_a_time_they_end_up_one_stack(yard):
    eng, gm, ada, bel = yard
    bel.act("give", "Ada", params={"item": "Emberglass", "count": 1})
    bel.act("give", "Ada", params={"item": "Emberglass", "count": 1})
    assert glass(eng, "Bel") == []
    assert [n for _, n in glass(eng, "Ada")] == [2]
    w = eng.world("yard")
    assert w.get(glass(eng, "Ada")[0][0])["state"]["given_by"] == w.find(name="Bel")[0]["id"]


def test_gifts_join_what_was_already_there(yard):
    eng, gm, ada, bel = yard
    ada.act("take", "Emberglass", params={"count": 10})
    r = ada.act("give", "Bel", params={"item": "Emberglass", "count": 4})
    ev = [e for e in r["events"] if e["kind"] == "given"][0]
    assert ev["payload"]["count"] == 4
    assert [n for _, n in glass(eng, "Bel")] == [6]  # her two and the four
    assert [n for _, n in glass(eng, "Ada")] == [6]


def test_put_part_of_a_stack_and_a_like_stack_takes_no_new_room(yard):
    eng, gm, ada, bel = yard
    ada.act("take", "Emberglass", params={"count": 10})
    ada.act("put", "Crate", params={"item": "Emberglass", "count": 3})
    ada.act("put", "Crate", params={"item": "Emberglass", "count": 3})  # room 1, but it joins the three
    crate = {c["name"]: c for c in ada.perceive()["present"]}["Crate"]
    assert crate["holding"] == [{"id": crate["holding"][0]["id"], "name": "Emberglass", "count": 6}]
    ada.act("take", crate["holding"][0]["id"], params={"count": 2})
    assert [n for _, n in glass(eng, "Ada")] == [6]


def test_a_stack_burns_as_one_thing_and_count_helpers_add_up(yard):
    eng, gm, ada, bel = yard
    r = ada.act("burn", "Rope")
    burned = [e for e in r["events"] if e["kind"] == "burned"][0]
    assert burned["payload"]["count"] == 4
    ada.act("take", "Emberglass", params={"count": 7})
    assert ada.act("tally")["result"] == [7, 7, 0.7]


def test_unlike_things_do_not_join(yard):
    eng, gm, ada, bel = yard
    gm.patch("Ada", {"carry": None})
    gm.spawn("thing", "Yard", "Emberglass", state={"portable": True, "kind": "ember", "bulk": 0.1,
                                                   "description": "A shard, cracked.", "count": 5})
    for c in [c for c in ada.perceive()["present"] if c["name"] == "Emberglass"]:
        ada.act("take", c["id"])
    assert sorted(n for _, n in glass(eng, "Ada")) == [5, 60]


def test_what_weighs_nothing_fits_in_hands_already_over_their_carry(yard):
    eng, gm, ada, bel = yard
    # a world script left Ada at 6 of her 5; a letter still goes into her hands, taken or given
    gm.spawn("thing", gm.inspect("Ada")["id"], "Stone", state={"portable": True, "bulk": 6})
    gm.spawn("thing", gm.inspect("Yard")["id"], "Leaf", state={"portable": True, "bulk": 0})
    gm.spawn("thing", gm.inspect("Bel")["id"], "Letter", state={"portable": True, "bulk": 0})
    ada.act("take", "Leaf")
    bel.act("give", "Ada", params={"item": "Letter"})
    held = {c["name"] for c in ada.perceive()["holding"]}
    assert {"Stone", "Leaf", "Letter"} <= held
    # what weighs something is still refused
    with pytest.raises(Rejected) as r:
        bel.act("give", "Ada", params={"item": "Emberglass", "count": 1})
    assert "hands are full" in r.value.reason
