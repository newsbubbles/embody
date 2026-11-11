"""packs/locks in a small guildhouse: a strongbox that does not open without its lock, a key, a code, a pick that
gives and one that is heard, force, a locked door and a locked strongroom."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "guild", "name": "Guildhouse", "seed": 7, "description": "A yard, a hall, a strongroom.", "requires": ["village", "locks"]}

def define(s):
    s.define_schema("person", extends="creature",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"},
                             "take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here"},
                             "put": {"script": "put", "doc": "Put it on or in", "targets": "thing",
                                     "params": {"item": "a thing you hold"}},
                             "read": {"script": "read", "doc": "Read it", "targets": "thing"}})

def populate(s):
    root = s.summary()["root"]
    yard = s.spawn("place", root, "Yard")["id"]
    hall = s.spawn("place", root, "Hall")["id"]
    vault = s.spawn("place", root, "Strongroom")["id"]
    door = s.spawn("thing", yard, "Oak door", state={"portable": False, "open": True})["id"]
    s.connect(yard, hall, via=door)
    s.connect(yard, vault)
    s.spawn("lock", door, "Door lock", state={"key": "Iron key"})
    s.spawn("lock", vault, "Strongroom lock", state={"code": "7-3-1"})
    box = s.spawn("thing", yard, "Strongbox", state={"portable": False, "holds": ["any"], "room": 2})["id"]
    s.spawn("lock", box, "Box lock", state={"key": "Brass key", "pick_dc": 12, "break_dc": 14})
    s.spawn("thing", box, "Emberglass", state={"portable": True, "text": "Guild glass, counted."})
    ada = s.spawn("person", yard, "Ada", state={"wits": 2, "body": 1, "skills": {"craft": 3}})["id"]
    s.spawn("thing", ada, "Brass key", state={"portable": True})
    s.spawn("thing", ada, "Iron key", state={"portable": True})
    s.spawn("thing", ada, "Coin", state={"portable": True})
    s.spawn("person", yard, "Bel", state={"wits": 0, "body": 0})
    s.clock(run=False)
'''


@pytest.fixture
def guild(tmp_path):
    for p in ("village", "locks"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "guild").mkdir(parents=True)
    (tmp_path / "worlds" / "guild" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "guild")
    ada, bel = eng.session("ada"), eng.session("bel")
    ada.join("guild", "Ada")
    bel.join("guild", "Bel")
    return eng, gm, ada, bel


def kinds(eng, kind):
    w = eng.world("guild")
    return [e["payload"] for e in w.store.query("event", "world_id=? AND kind=?", (w.id, kind))]


def wait(gm, seconds):
    for _ in range(int(seconds // 60)):
        gm.clock(step=60)


def test_a_locked_box_keeps_its_contents_and_shows_only_its_lock(guild):
    eng, gm, ada, bel = guild
    for verb, target in (("take", "Emberglass"), ("read", "Emberglass")):
        with pytest.raises(Rejected) as r:
            bel.act(verb, target)
        assert "Strongbox is locked" in r.value.reason and "Box lock" in r.value.reason  # it says what opens it
    with pytest.raises(Rejected) as r:
        ada.act("put", "Strongbox", params={"item": "Coin"})
    assert "locked" in r.value.reason
    card = bel.inspect("Strongbox")
    assert card["locked"] is True and [c["name"] for c in card["holding"]] == ["Box lock"]
    lock = [a for a in bel.perceive()["affordances"] if a["target_name"] == "Box lock"]
    assert {a["verb"] for a in lock} >= {"unlock", "pick", "break"}  # the lock on a box here is in reach
    assert "code" not in bel.inspect("Strongroom lock")["state"]  # a code is never on the card


def test_the_key_in_hand_unlocks_and_locks_and_nothing_else_does(guild):
    eng, gm, ada, bel = guild
    with pytest.raises(Rejected) as r:
        bel.act("unlock", "Box lock")
    assert "its key in your hand" in r.value.reason and "pick it" in r.value.reason
    ada.act("unlock", "Box lock")
    assert kinds(eng, "unlocked")[0]["by"] == gm.inspect("Ada")["id"]
    assert bel.act("take", "Emberglass")["ok"]  # open to anyone here now
    ada.act("put", "Strongbox", params={"item": "Coin"})
    ada.act("lock", "Box lock")
    with pytest.raises(Rejected):
        bel.act("take", "Coin")
    assert kinds(eng, "locked")[0]["holder"] == gm.inspect("Strongbox")["id"]


def test_a_code_opens_and_a_wrong_code_spends_nothing(guild):
    eng, gm, ada, bel = guild
    with pytest.raises(Rejected) as r:
        bel.act("go", "Strongroom")
    assert "Strongroom is locked" in r.value.reason
    assert [x for x in bel.perceive()["exits"] if x["name"] == "Strongroom"][0]["locked"] is True
    with pytest.raises(Rejected) as r:
        bel.act("unlock", "Strongroom lock")
    assert "its code" in r.value.reason
    t0 = gm.clock()["t"]
    with pytest.raises(Rejected) as r:
        bel.act("unlock", "Strongroom lock", params={"code": "1-2-3"})
    assert r.value.reason == "the code is wrong"
    assert gm.inspect("Strongroom lock")["state"]["locked"] and gm.clock()["t"] == t0 and not kinds(eng, "unlocked")
    bel.act("unlock", "Strongroom lock", params={"code": "7-3-1"})
    assert bel.act("go", "Strongroom")["ok"]


def test_a_pick_gives_when_the_time_is_out_and_a_failed_one_is_heard(guild):
    eng, gm, ada, bel = guild
    gm.patch("Box lock", {"pick_dc": 30})
    bel.act("pick", "Box lock")
    wait(gm, 660)
    assert gm.inspect("Box lock")["state"]["locked"]
    failed = kinds(eng, "pick_failed")
    assert failed and failed[0]["dc"] == 30
    assert any(e["kind"] == "pick_failed" for e in ada.perceive()["events"])  # the room heard it
    gm.patch("Box lock", {"pick_dc": 2})
    ada.act("pick", "Box lock")  # d20 + wits 2 + craft 3 against 2 cannot fail
    wait(gm, 660)
    assert not gm.inspect("Box lock")["state"]["locked"] and kinds(eng, "lock_picked")[0]["mod"] == 5
    gm.patch("Box lock", {"locked": True})
    bel.act("pick", "Box lock")
    gm.move("Bel", "Hall")  # whoever walks away before it gives gets nothing
    wait(gm, 660)
    assert gm.inspect("Box lock")["state"]["locked"] and len(kinds(eng, "lock_picked")) == 1


def test_force_breaks_a_lock_open_for_good(guild):
    eng, gm, ada, bel = guild
    gm.patch("Box lock", {"break_dc": 1})
    bel.act("break", "Box lock")
    wait(gm, 180)
    assert gm.inspect("Box lock")["state"]["broken"] and kinds(eng, "lock_broken")
    assert bel.act("take", "Emberglass")["ok"]
    with pytest.raises(Rejected) as r:
        ada.act("lock", "Box lock")
    assert "broken" in r.value.reason


def test_a_locked_door_refuses_the_way_through_from_either_side(guild):
    eng, gm, ada, bel = guild
    with pytest.raises(Rejected) as r:
        bel.act("go", "Hall")
    assert "Oak door is locked" in r.value.reason and "Door lock" in r.value.reason
    assert [x for x in bel.perceive()["exits"] if x["name"] == "Hall"][0]["locked"] is True
    ada.act("unlock", "Door lock")
    ada.act("go", "Hall")
    ada.act("lock", "Door lock")  # the lock on a door is in reach from both sides
    with pytest.raises(Rejected):
        bel.act("go", "Hall")
    with pytest.raises(Rejected):
        ada.act("go", "Yard")


def test_a_lockpick_counts_before_stealth_or_craft(guild):
    eng, gm, ada, bel = guild
    gm.patch("Bel", {"wits": 1, "skills": {"lockpick": 3, "stealth": 1}})
    gm.patch("Box lock", {"pick_dc": 2})
    bel.act("pick", "Box lock")  # d20 + wits 1 + lockpick 3: the trade beats a quiet hand
    wait(gm, 660)
    assert kinds(eng, "lock_picked")[0]["mod"] == 4
