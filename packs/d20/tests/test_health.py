"""One health bar (hp), one readable condition on every body, death by thirst after a few dry days, and "you are
dead" before any other refusal (Nate, 2026-11-14)."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected
from embody.store import Store
from embody.world import World

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "flats", "name": "Flats", "seed": 5, "description": "Open sand and a well.", "requires": ["d20", "village"]}

from packs.d20.pack import install_rules

def define(s):
    s.define_schema("person", extends="combatant",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"}})

def populate(s):
    root = s.summary()["root"]
    install_rules(s, root)
    well = s.spawn("place", root, "Well", state={"water_source": True})["id"]
    sand = s.spawn("place", root, "Sand", state={"open": True})["id"]
    s.connect(well, sand)
    for name, body in (("Ada", 2), ("Bel", 3), ("Cass", 4)):
        s.spawn("person", sand, name, state={"body": body})
    s.spawn("person", well, "Dov")
    s.clock(run=False)
'''


@pytest.fixture
def flats(tmp_path):
    for p in ("village", "d20"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "packs" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "worlds" / "flats").mkdir(parents=True)
    (tmp_path / "worlds" / "flats" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "flats")
    eng.world("flats").set_meta({"day_seconds": 600})  # ten thirst beats a day
    return eng, gm


def events(eng, kind):
    w = eng.world("flats")
    return [e for e in w.store.query("event", "world_id=? AND kind=?", (w.id, kind), order="seq")]


def cond(gm, name):
    c = gm.inspect(name)
    return c["condition"], c.get("way_out")


def test_one_bar_called_hp():
    w = World.create(Store(), "Bare")
    cr = w.spawn("creature", w.root_id, "Someone")
    assert w.get(cr)["state"]["hp"] == 10 and "vigor" not in w.get(cr)["state"]  # the core's bar is the same one


def test_conditions_and_their_ways_out(flats):
    eng, gm = flats
    assert cond(gm, "Dov") == ("fine", None)
    gm.patch("Dov", {"hp": 3, "max_hp": 6})
    assert cond(gm, "Dov")[0] == "hurt" and "-2" in cond(gm, "Dov")[1]
    gm.patch("Dov", {"down": True, "hp": 0})
    assert cond(gm, "Dov") == ("down (wounds)", "rest with water, or someone tends you")
    gm.patch("Dov", {"downed_by": "thirst"})
    assert cond(gm, "Dov")[0] == "down (thirst)" and cond(gm, "Dov")[1].startswith("drink")
    gm.patch("Dov", {"dead": True})
    assert cond(gm, "Dov") == ("dead", None)
    gm.patch(gm.summary()["root"], {"condition_notes": {"hurt": "see the leech"}})
    gm.patch("Dov", {"dead": None, "down": None, "downed_by": None, "hp": 1})
    assert cond(gm, "Dov") == ("hurt", "see the leech")
    # in a look too, not only an inspect
    p = eng.session("p")
    p.join("flats", "Ada")
    assert {c["name"]: c["condition"] for c in p.perceive()["present"]}["Bel"] == "fine"


def test_the_dead_hear_you_are_dead_first(flats):
    eng, gm = flats
    p = eng.session("p")
    p.join("flats", "Ada")
    gm.patch("Ada", {"dead": True, "down": True, "hp": 0})
    for verb, target in (("go", "Well"), ("check", None), ("drink", "Well")):
        with pytest.raises(Rejected) as r:
            p.act(verb, target)
        assert r.value.reason == "you are dead"
    with pytest.raises(Rejected) as r:
        p.say("help")
    assert r.value.reason == "you are dead"
    assert p.perceive()["you"]["condition"] == "dead"  # still in the seat, still seeing


def beats(gm, seconds):
    # a long step fires each periodic tick once and skips the gap, so walk the clock a thirst beat at a time
    for _ in range(int(seconds // 60)):
        gm.clock(step=60)


def dry_down(gm, names):
    for n in names:
        gm.patch(n, {"water": 0, "hp": 0, "down": True, "wounded": True, "downed_by": "thirst"})


def test_left_dry_a_body_fades_and_dies_in_its_days(flats):
    eng, gm = flats
    dry_down(gm, ("Ada", "Bel", "Cass"))
    beats(gm, 60)  # the first dry beat starts the count for bodies down before it existed
    beats(gm, 600)
    died = {e["target_id"] for e in events(eng, "died")}
    names = {gm.inspect(n)["id"]: n for n in ("Ada", "Bel", "Cass")}
    assert {names[i] for i in died} == {"Ada"}  # body 2: one day
    assert any(e["payload"]["day"] == 1 and e["payload"]["of"] == 2 for e in events(eng, "fading"))
    assert gm.inspect("Bel")["fading"] == 1
    beats(gm, 600)
    assert {names[i] for i in {e["target_id"] for e in events(eng, "died")}} == {"Ada", "Bel"}
    beats(gm, 600)
    assert {names[i] for i in {e["target_id"] for e in events(eng, "died")}} == {"Ada", "Bel", "Cass"}
    assert all(e["payload"]["why"] == "thirst" for e in events(eng, "died"))
    assert cond(gm, "Ada")[0] == "dead"


def test_water_in_time_saves_and_a_world_may_turn_it_off(flats):
    eng, gm = flats
    dry_down(gm, ("Cass",))
    beats(gm, 60 + 600)
    assert gm.inspect("Cass")["fading"] == 1
    gm.spawn("thing", "Cass", "Waterskin", state={"left": 3})
    p = eng.session("p")
    p.join("flats", "Cass")
    p.act("drink", "Waterskin")  # down from thirst, a drink is still yours to take
    st = gm.inspect("Cass")["state"]
    assert not st.get("down") and "dry_since" not in st and "fading" not in st
    gm.patch(gm.summary()["root"], {"thirst_death_days": False})
    dry_down(gm, ("Cass",))
    beats(gm, 3000)
    assert not events(eng, "died")


def test_vigor_becomes_hp_on_install():
    from packs.d20.pack import hp_from_vigor
    w = World.create(Store(), "Old")
    a = w.spawn("creature", w.root_id, "Ruhl", state={"vigor": 8, "max_vigor": 8, "body": 3})
    sp = w.spawn("thing", w.root_id, "goat", state={"stages": [{"name": "kid", "state": {"max_vigor": 2}}]})
    w.patch(w.root_id, {"templates": {"guard": {"state": {"vigor": 6, "max_vigor": 6}}}})
    assert hp_from_vigor(w) == 3
    st = w.get(a)["state"]
    assert (st["hp"], st["max_hp"], st["body"]) == (8, 8, 3) and "vigor" not in st and "max_vigor" not in st
    assert w.get(sp)["state"]["stages"][0]["state"] == {"max_hp": 2}
    assert w.get(w.root_id)["state"]["templates"]["guard"]["state"] == {"hp": 6, "max_hp": 6}
    assert hp_from_vigor(w) == 0  # idempotent
