"""inspect on someone else: whom they know, what they think of anyone and what passed between them stays theirs. Another
body sees the relations marked public and the groups it is part of, and whether it has met them; the body's own seat
and the owner see it all."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "flats", "name": "Salt flats", "seed": 2, "description": "Open ground.", "requires": ["village"]}

def define(s):
    s.define_schema("person", extends="creature")

def populate(s):
    root = s.summary()["root"]
    flats = s.spawn("place", root, "Flats")["id"]
    camp = s.spawn("place", root, "Camp")["id"]
    arlo = s.spawn("person", flats, "Arlo")["id"]
    s.spawn("person", flats, "Sefa")
    boss = s.spawn("person", camp, "Halvard")["id"]
    side = s.spawn("entity", root, "House Dreyer", state={"hidden": True})["id"]
    s.link(arlo, boss, "knows", {"standing": 3, "notes": "my master: watch the Keth"})
    s.link(boss, arlo, "knows", {"standing": 2})
    s.link(arlo, side, "standing", {"value": 2, "public": True})
    s.relate("crew", [arlo, boss], {"job": "spy on the Keth"})
    s.clock(run=False)
'''


@pytest.fixture
def flats(tmp_path):
    shutil.copytree(REPO / "packs" / "village", tmp_path / "packs" / "village",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "flats").mkdir(parents=True)
    (tmp_path / "worlds" / "flats" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "flats")
    arlo, sefa = eng.session("arlo"), eng.session("sefa")
    arlo.join("flats", "Arlo")
    sefa.join("flats", "Sefa")
    return eng, gm, arlo, sefa


def test_someone_who_inspects_a_stranger_does_not_learn_whom_they_know(flats):
    eng, gm, arlo, sefa = flats
    seen = sefa.inspect("Arlo")
    assert "knows" not in seen
    assert seen["relations"] == []  # not whom he knows, not his crew, not his side's standing
    assert seen["met"] is False
    assert "spy" not in str(seen) and "Halvard" not in str(seen) and "Dreyer" not in str(seen)
    gm.relate("duel", ["Arlo", "Halvard"], {"public": True})
    assert [r["relation"] for r in sefa.inspect("Arlo")["relations"]] == ["duel"]  # a ring everyone can see


def test_the_body_itself_and_the_owner_see_it_all(flats):
    eng, gm, arlo, sefa = flats
    mine = arlo.inspect("Arlo")
    assert {r["relation"] for r in mine["relations"]} == {"knows", "standing", "crew"}
    assert [k["name"] for k in mine["knows"]] == ["Halvard"]
    owner = gm.inspect("Arlo")
    assert [k["name"] for k in owner["knows"]] == ["Halvard"] and len(owner["relations"]) == 4


def test_meeting_someone_shows_as_met_and_nothing_more(flats):
    eng, gm, arlo, sefa = flats
    gm.link("Sefa", "Arlo", "knows", {"standing": -1})
    seen = sefa.inspect("Arlo")
    assert seen["met"] is True
    assert "knows" not in [r["relation"] for r in seen["relations"]]
