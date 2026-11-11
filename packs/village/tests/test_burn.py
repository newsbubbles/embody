"""village `burn`: a burnable thing, held or here, burned at a fire, a burning thing or a lit light in hand. It is gone,
what it held drops, the room sees it burn, and whoever read it keeps what it said."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "hearth", "name": "Hearth", "seed": 5, "description": "A cold cell and a warm hall.", "requires": ["village"]}

def define(s):
    s.define_schema("person", extends="creature",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"},
                             "take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here"},
                             "burn": {"script": "burn", "doc": "Burn it", "targets": "thing", "duration": 3}})
    s.define_schema("letter", extends="thing", state={"portable": True, "burnable": True},
                    actions={"read": {"script": "read", "doc": "Read it"}})

def populate(s):
    root = s.summary()["root"]
    cell = s.spawn("place", root, "Cell")["id"]
    hall = s.spawn("place", root, "Hall")["id"]
    s.connect(cell, hall)
    s.spawn("thing", hall, "Hearth", state={"portable": False, "fire": True})
    me = s.spawn("person", cell, "Ada")["id"]
    s.spawn("person", hall, "Bel")
    s.spawn("letter", me, "Letter from home", state={"text": "The well at home is poisoned. Tell no one."})
    s.spawn("thing", me, "Lamp", state={"portable": True, "lit": False})
    s.spawn("thing", me, "Iron key", state={"portable": True})
    folded = s.spawn("letter", hall, "Folded note", state={"text": "Meet me at dusk."})["id"]
    s.spawn("thing", folded, "Pressed flower", state={"portable": True})
    s.clock(run=False)
'''


@pytest.fixture
def hearth(tmp_path):
    shutil.copytree(REPO / "packs" / "village", tmp_path / "packs" / "village",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "hearth").mkdir(parents=True)
    (tmp_path / "worlds" / "hearth" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "hearth")
    ada = eng.session("ada")
    ada.join("hearth", "Ada")
    return eng, gm, ada


def test_burning_needs_fire_and_a_thing_that_burns(hearth):
    eng, gm, ada = hearth
    with pytest.raises(Rejected) as r:
        ada.act("burn", "Letter from home")
    assert "no fire here" in r.value.reason
    with pytest.raises(Rejected) as r:
        ada.act("burn", "Iron key")
    assert "will not burn" in r.value.reason
    gm.patch("Lamp", {"lit": True})  # a lit light in hand is fire enough
    ada.act("read", "Letter from home")
    r = ada.act("burn", "Letter from home")
    assert not [e for e in gm.find(name="Letter from home") if e["name"] == "Letter from home"]
    assert any(e["kind"] == "burned" for e in r["events"])
    assert any(e["kind"] == "scene" and "to the lamp" in e["payload"]["text"] for e in r["events"])
    # what was read stays read: the log keeps the read event and its text
    w = eng.world("hearth")
    reads = w.store.query("event", "world_id=? AND kind='read'", (w.id,))
    assert any("poisoned" in str(e["payload"]) for e in reads)


def test_a_thing_burned_at_the_hearth_drops_what_it_held_and_the_room_sees_it(hearth):
    eng, gm, ada = hearth
    ada.act("go", "Hall")
    bel = eng.session("bel")
    bel.join("hearth", "Bel")
    ada.act("burn", "Folded note")
    hall = gm.inspect("Hall")["id"]
    assert gm.inspect("Pressed flower")["parent"] == hall
    assert not [e for e in gm.find(name="Folded note") if e["name"] == "Folded note"]
    seen = bel.perceive(cursor=0, events=200)["events"]
    assert any(e["kind"] == "scene" and "until it is ash" in e["payload"]["text"] for e in seen)
    assert not any("Meet me at dusk" in str(e) for e in seen)  # the room sees it burn, not what it said
