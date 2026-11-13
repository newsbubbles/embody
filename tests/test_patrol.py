"""A mind's orders for its body while it waits: a patrol the body walks by its own go, and its own lines over the
author's table. Both secret to everyone else; the seat's first deed takes the body off its patrol."""

import itertools
import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "hold", "name": "The Hold", "seed": 5, "description": "A walled hold.", "requires": ["village"]}

def define(s):
    s.define_schema("person", extends="creature",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"},
                             "talk": {"script": "talk", "doc": "Talk", "targets": "creature", "scope": "here",
                                      "params": {"about": "topic"}}},
                    listeners=[{"script": "person_on", "kinds": ["talked"], "unless_embodied": True}])

def populate(s):
    root = s.summary()["root"]
    for name in ("Gate", "Wall", "Tower", "Yard"):
        s.spawn("place", root, name)
    s.connect("Gate", "Wall")
    s.connect("Wall", "Tower")
    s.connect("Tower", "Gate")
    s.connect("Yard", "Gate")
    s.spawn("person", "Gate", "Warden", state={"dialog": {"gate": "The gate shuts at dusk."}})
    s.spawn("person", "Yard", "Ada")
    s.clock(run=False)
'''


@pytest.fixture
def hold(tmp_path):
    shutil.copytree(REPO / "packs" / "village", tmp_path / "packs" / "village",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "hold").mkdir(parents=True)
    (tmp_path / "worlds" / "hold" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "hold")
    mind = eng.session("warden-mind")
    mind.join("hold", "Warden")
    ada = eng.session("ada")
    ada.join("hold", "Ada")
    return eng, gm, mind, ada


def where(gm, name):
    return gm.inspect(gm.inspect(name)["parent"])["name"]


def test_a_patrol_walks_its_loop_and_wakes_the_mind_where_the_body_stands(hold):
    eng, gm, mind, ada = hold
    with pytest.raises(Rejected, match="no way from Wall to Yard"):
        mind.away(patrol=["Wall", "Yard"])
    r = mind.away(patrol=["Gate", "Wall", "Tower"], dwell=60)
    assert r["patrol"]["stops"] == ["Gate", "Wall", "Tower"] and r["patrol"]["loop"] is True
    gm.move("Ada", "Gate")
    assert "idle_orders" not in ada.inspect("Warden")["state"]  # the route is the mind's own
    gm.move("Ada", "Yard")

    seen = []
    for _ in range(4):
        gm.clock(step=60)
        seen.append(where(gm, "Warden"))
    assert seen == ["Wall", "Tower", "Gate", "Wall"]

    # the mind's watch sees what the body sees wherever it stands now
    gm.move("Ada", "Gate")
    ticks = itertools.count()
    r = mind.wait(until="came('Ada')", timeout=1000, clock=lambda: float(next(ticks)),
                  sleep=lambda s: gm.clock(step=60))
    assert r["fired"] and r["here"]["name"] == "Gate"

    # the seat's first deed takes the body off its patrol
    mind.say("Who goes there?")
    assert "patrol" not in (gm.inspect("Warden")["state"].get("idle_orders") or {})
    for _ in range(3):
        gm.clock(step=60)
    assert where(gm, "Warden") == "Gate"


def test_two_stops_walk_back_and_forth_and_a_shut_way_holds_the_step(hold):
    eng, gm, mind, ada = hold
    gm.move("Warden", "Yard")
    r = mind.away(patrol=["Yard", "Gate"], dwell=30)
    assert r["patrol"]["loop"] is False
    seen = []
    for _ in range(4):
        gm.clock(step=30)
        seen.append(where(gm, "Warden"))
    assert seen == ["Gate", "Yard", "Gate", "Yard"]
    with pytest.raises(Rejected, match="dwell"):
        mind.away(patrol=["Yard", "Gate"], dwell=5)
    mind.away()  # clears every order
    gm.clock(step=60)
    assert where(gm, "Warden") == "Yard" and not gm.inspect("Warden")["state"].get("idle_orders")


def test_the_minds_own_lines_answer_while_it_is_idle_over_the_authors(hold):
    eng, gm, mind, ada = hold
    gm.move("Ada", "Gate")
    mind.away(dialog={"water|well": "Ask at the well, not me."}, answer="On watch. Speak plainly.")
    card = str(ada.inspect("Warden")["state"])
    assert "idle_orders" not in card and "the well" not in card  # others hear lines, never the table
    lines = lambda: [e["payload"]["text"] for e in gm.history(kinds=["say"]) if e["actor"] == gm.inspect("Warden")["id"]]

    ada.act("talk", "Warden", {"about": "where is the water"})
    ada.act("talk", "Warden", {"about": "the gate"})  # the author's line still answers its own topic
    assert lines() == ["Ask at the well, not me.", "The gate shuts at dusk."]
    ada.say("Any water up here?", to="Warden")  # a line said to the body: its own line before its standing answer
    assert lines()[-1] == "Ask at the well, not me."

    # once the mind acts, it answers for itself
    mind.say("Move along.")
    ada.act("talk", "Warden", {"about": "water"})
    assert lines()[-1] == "Move along."
