"""d20 sleep: a body lies down (`sleep`, or `away(sleep=true)` as its seat goes idle), mends twice as fast for the
same water, hears only what is loud or done to it, and is easy prey: a blow lands with advantage, a quiet hand can
search it, and a blow, a word to it, a noise, thirst or its own next deed wakes it."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "camp", "name": "Camp", "seed": 11, "description": "A camp by a well and a tent beside it.",
         "requires": ["d20", "village"]}

from packs.d20.pack import install_rules

def define(s):
    s.define_schema("person", extends="combatant",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"},
                             "take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here"}})

def populate(s):
    root = s.summary()["root"]
    install_rules(s, root)
    well = s.spawn("place", root, "Well", state={"water_source": True})["id"]
    tent = s.spawn("place", root, "Tent")["id"]
    s.connect(well, tent)
    ada = s.spawn("person", tent, "Ada", state={"wits": 1, "hp": 2, "max_hp": 8})["id"]
    s.spawn("thing", ada, "Purse", state={"portable": True})
    s.spawn("person", tent, "Bel", state={"wits": 2, "skills": {"stealth": 3}})
    s.spawn("person", tent, "Cass")
    s.clock(run=False)
'''


@pytest.fixture
def camp(tmp_path):
    for p in ("village", "d20"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "packs" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "worlds" / "camp").mkdir(parents=True)
    (tmp_path / "worlds" / "camp" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "camp")
    ada, bel = eng.session("ada"), eng.session("bel")
    ada.join("camp", "Ada")
    bel.join("camp", "Bel")
    return eng, gm, ada, bel


def kinds(eng, kind):
    w = eng.world("camp")
    return [e for e in w.store.query("event", "world_id=? AND kind=?", (w.id, kind))]


def test_away_with_sleep_lies_down_and_the_card_says_so(camp):
    eng, gm, ada, bel = camp
    r = ada.away(sleep=True)
    assert r["asleep"]
    ada_card = [c for c in bel.perceive()["present"] if c["name"] == "Ada"][0]
    assert ada_card["asleep"]
    with pytest.raises(Rejected):
        ada.act("sleep")


def test_asleep_it_mends_twice_as_fast_for_the_same_water(camp):
    eng, gm, ada, bel = camp
    gm.clock(step=600)
    awake = gm.inspect("Ada")["state"]
    assert awake["hp"] == 3
    ada.act("sleep")
    gm.clock(step=600)
    gm.clock(step=600)
    st = gm.inspect("Ada")["state"]
    assert st["hp"] == 7  # 3, then 5, then 7
    mended = [e for e in kinds(eng, "mended")]
    assert [e["payload"]["hp"] for e in mended] == [3, 5, 7]
    assert st["mend_owed"] == 1  # water is owed by the beat, not the point: three beats paid one, owe one, asleep or not


def test_a_sleeper_hears_only_what_is_loud_or_done_to_it(camp):
    eng, gm, ada, bel = camp
    ada.act("sleep")
    ada.perceive()
    bel.say("she is out cold")
    w = eng.world("camp")
    tent = w.find(name="Tent")[0]["id"]
    w.emit("scene", target=tent, reach=1, payload={"text": "The lamp gutters."})
    assert not any(e["kind"] in ("say", "scene") for e in ada.perceive()["events"])
    assert gm.inspect("Ada")["state"].get("asleep")
    w.emit("thunder", target=tent, reach=2, payload={"text": "Thunder over the flats."})
    seen = ada.perceive()["events"]
    assert any(e["kind"] == "thunder" for e in seen) and any(e["kind"] == "woke" for e in seen)
    assert not gm.inspect("Ada")["state"].get("asleep")
    bel.say("awake now?")
    assert any(e["kind"] == "say" for e in ada.perceive()["events"])


def test_a_word_to_a_sleeper_or_a_shake_wakes_them_and_their_own_deed_does(camp):
    eng, gm, ada, bel = camp
    ada.act("sleep")
    bel.say("Ada, the water", to="Ada")
    assert not gm.inspect("Ada")["state"].get("asleep")
    ada.act("sleep")
    bel.act("wake", "Ada")
    assert not gm.inspect("Ada")["state"].get("asleep")
    ada.act("sleep")
    ada.act("go", "Well")
    assert not gm.inspect("Ada")["state"].get("asleep")
    assert kinds(eng, "woke")[-1]["payload"]["why"] == "rose"


def test_a_blow_on_a_sleeper_lands_with_advantage_and_wakes_them(camp):
    eng, gm, ada, bel = camp
    ada.act("sleep")
    r = bel.act("attack", "Ada")
    blow = [e for e in r["events"] if e["kind"] in ("hit", "missed")][0]["payload"]
    assert blow["asleep"] and len(blow["rolls"]) == 2
    assert not gm.inspect("Ada")["state"].get("asleep")


def test_a_quiet_hand_searches_a_sleeper_and_a_clumsy_one_wakes_them(camp):
    eng, gm, ada, bel = camp
    ada.act("sleep")
    gm.patch("Bel", {"wits": 25})  # cannot fail
    r = bel.act("search", "Ada")
    assert [e for e in r["events"] if e["kind"] == "lifted"]
    assert gm.inspect("Ada")["state"].get("asleep")  # she slept through it
    assert not any(e["kind"] == "lifted" for e in ada.perceive()["events"])
    gm.move("Purse", "Ada")
    gm.patch("Bel", {"wits": -30, "skills": {}})  # cannot succeed
    r = bel.act("search", "Ada")
    assert [e for e in r["events"] if e["kind"] == "caught"]
    assert not gm.inspect("Ada")["state"].get("asleep")
    assert gm.inspect("Purse")["parent"] == gm.inspect("Ada")["id"]
    with pytest.raises(Rejected):
        bel.act("search", "Ada")  # awake now: she would not let you


def test_thirst_wakes_a_sleeper(camp):
    eng, gm, ada, bel = camp
    ada.act("sleep")
    gm.patch("Ada", {"water": 4})
    gm.clock(step=60)
    assert gm.inspect("Ada")["state"]["asleep"]  # asleep, a beat in the shade is half a point
    gm.clock(step=60)
    assert not gm.inspect("Ada")["state"].get("asleep")
    assert kinds(eng, "woke")[-1]["payload"]["why"] == "thirst"
