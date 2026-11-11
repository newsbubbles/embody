"""d20 thirst and work: asleep a body dries at half the pace, and heavy deeds (a blow, a harvest, a heavy walk on open
ground) cost a point of water each, by a table a world can tune or turn off on its root."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "pan", "name": "Pan", "seed": 5, "description": "A tent at the edge of a salt pan.",
         "requires": ["d20", "village"]}

from packs.d20.pack import install_rules

def define(s):
    s.define_schema("person", extends="combatant",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"},
                             "take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here"}})

def populate(s):
    root = s.summary()["root"]
    install_rules(s, root)
    tent = s.spawn("place", root, "Tent")["id"]
    pan = s.spawn("place", root, "Salt pan", state={"open": True})["id"]
    s.connect(tent, pan)
    ada = s.spawn("person", tent, "Ada", state={"water": 8, "carry": 4})["id"]
    s.spawn("thing", ada, "Sack of salt", state={"portable": True, "bulk": 3})
    s.spawn("person", tent, "Bel", state={"water": 8, "carry": 4})
    s.spawn("thing", tent, "Stone", state={"portable": True})
    s.clock(run=False)
'''


@pytest.fixture
def pan(tmp_path):
    for p in ("village", "d20"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "packs" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "worlds" / "pan").mkdir(parents=True)
    (tmp_path / "worlds" / "pan" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "pan")
    ada, bel = eng.session("ada"), eng.session("bel")
    ada.join("pan", "Ada")
    bel.join("pan", "Bel")
    return eng, gm, ada, bel


def water(gm, who):
    return gm.inspect(who)["state"]["water"]


def test_asleep_a_body_dries_at_half_the_pace(pan):
    eng, gm, ada, bel = pan
    ada.act("sleep")
    gm.clock(step=60)
    assert water(gm, "Ada") == 8  # half a point owed
    gm.clock(step=60)
    assert water(gm, "Ada") == 7 and water(gm, "Bel") == 6  # awake in the same tent: a point a beat


def test_a_blow_costs_the_one_who_swings_it(pan):
    eng, gm, ada, bel = pan
    bel.act("attack", "Ada")
    assert water(gm, "Bel") == 7 and water(gm, "Ada") == 8
    ev = gm.history(kinds=["sweated"], limit=5, newest=True)
    assert ev and ev[0]["payload"]["by"] == "fight"


def test_a_heavy_walk_onto_open_ground_costs_a_point_and_a_light_one_does_not(pan):
    eng, gm, ada, bel = pan
    ada.act("go", "Salt pan")  # 3 in hand, more than half her carry of 4
    bel.act("go", "Salt pan")
    assert water(gm, "Ada") == 7 and water(gm, "Bel") == 8


def test_a_world_tunes_the_table_or_turns_it_off(pan):
    eng, gm, ada, bel = pan
    root = gm.summary()["root"]
    gm.patch(root, {"sweat": {"fight": 0, "take": 2}})
    bel.act("attack", "Ada")
    bel.act("take", "Stone")
    assert water(gm, "Bel") == 6  # the blow free, the take two
    gm.patch(root, {"sweat": False})
    ada.act("go", "Salt pan")
    assert water(gm, "Ada") == 8
