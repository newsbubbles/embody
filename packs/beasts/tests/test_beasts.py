"""Beasts: a wild herd that settles at what the land carries, taming that takes days of visits, a kept beast that
goes feral when nobody feeds it, following and calling, a guard that takes up its owner's fight, diet, and yields."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
DAY = 86400

BUILD = '''
from packs.beasts.pack import install_rules

WORLD = {"id": "wild", "name": "The wild", "seed": 7, "description": "A brake, a yard, a den.",
         "requires": ["village", "d20", "beasts"]}

THORN = {"eats": ["root", "pulp"], "fed_max": 3, "young_name": "Thornback pup",
         "stages": [{"name": "young", "from": 0, "state": {"body": 1, "vigor": 3, "max_vigor": 3, "skills": {}}},
                    {"name": "adult", "from": 6, "state": {"body": 3, "vigor": 6, "max_vigor": 6, "skills": {"brawl": 1}},
                     "names": {"m": "Thornback boar", "f": "Thornback sow"},
                     "parts": [{"name": "Snout", "state": {"weapon": True, "damage": 1, "portable": False}}]},
                    {"name": "old", "from": 30, "state": {"body": 2}}],
         "lifespan": 40, "tame_dc": {"young": 11, "adult": 14}, "tame_at": {"young": 3, "adult": 5},
         "breed_chance": 0.25, "gestation": 6, "litter": [1, 2], "guards": True}
GOAT = {"eats": ["graze"], "fed_max": 3, "stages": [{"name": "adult", "from": 0, "state": {}}],
        "yields": {"name": "Goat's milk", "state": {"portable": True, "food": "milk"}, "max": 2, "sex": "f"}}

def define(s):
    s.define_schema("person", extends="combatant",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"}})

def populate(s):
    root = s.summary()["root"]
    yard = s.spawn("place", root, "Yard")["id"]
    brake = s.spawn("place", root, "Brake", state={"forage": {"root": {"left": 8, "max": 8, "regrow": 4}}})["id"]
    den = s.spawn("place", root, "Den")["id"]
    s.spawn("place", root, "Ridge", state={"forage": {"graze": {"left": 6, "max": 6, "regrow": 3}}})
    s.connect(yard, brake)
    s.connect(brake, den)
    s.spawn("species", root, "thornback", state=THORN)
    s.spawn("species", root, "goat", state=GOAT)
    s.spawn("person", yard, "Ada", state={"wits": 3, "skills": {"survival": 3}})
    install_rules(s, root)
    s.clock(run=False)
'''


@pytest.fixture
def wild(tmp_path):
    for p in ("village", "d20", "beasts"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "wild").mkdir(parents=True)
    (tmp_path / "worlds" / "wild" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "wild")
    # a day at a time: the bodies' minute ticks would take the test all day
    gm.world.set_pace({"thirst": 10 * DAY, "quench": 10 * DAY, "mend": 10 * DAY, "fighter_tick": 10 * DAY})
    gm.schedule(DAY, "dawn", entity=gm.world.root_id, every=DAY)  # on the root, where the rule hears it
    return eng, gm


def st(gm, name):
    return gm.inspect(name)["state"]


def beast(gm, place, name, **state):
    s = {"species": "thornback", "age": 10, "stage": "adult", "fed": 3}
    s.update(state)
    return gm.spawn("beast", place, name, state=s)["id"]


def dawn(gm, n=1):
    for _ in range(n):
        gm.clock(step=DAY)


def living(gm):
    return [e for e in gm.world.find(type="beast", limit=1000) if not e["state"].get("dead")]


def test_a_wild_herd_settles_at_what_the_land_carries(wild):
    eng, gm = wild
    beast(gm, "Brake", "The boar", sex="m", leader=True, home="Brake")
    beast(gm, "Brake", "The sow", sex="f", home="Brake")
    beast(gm, "Brake", "The yearling", sex="f", age=4, stage="young", home="Brake")
    counts, born = [], 0
    for _ in range(60):
        dawn(gm)
        counts.append(len(living(gm)))
    born = len([e for e in gm.world.find(type="beast", limit=1000) if e["state"].get("mother")])
    # the brake regrows 4 roots a day: the herd grows to about that and no further, and never dies out
    assert born >= 2 and min(counts) >= 2
    assert max(counts) <= 7, counts
    assert 2 <= sum(counts[-20:]) / 20 <= 6, counts
    grown = [e for e in gm.world.find(type="beast", limit=1000) if e["state"].get("mother") and e["state"].get("stage") == "adult"]
    assert grown and grown[0]["name"].startswith(("Thornback boar", "Thornback sow"))
    assert any(c["name"] == "Snout" for c in gm.world.children(grown[0]["id"]))


def test_taming_a_young_beast_takes_days_of_feeding_by_hand(wild):
    eng, gm = wild
    pup = beast(gm, "Brake", "Pup", sex="f", age=0, stage="young", home="Brake")
    gm.spawn("beast", "Brake", "Old boar", state={"species": "thornback", "age": 10, "stage": "adult", "leader": True, "sex": "m"})
    gm.move("Ada", "Brake")
    ada = eng.session("ada")
    ada.join("wild", "Ada")
    for _ in range(12):
        gm.spawn("thing", "Ada", "Glassthorn root", state={"portable": True, "food": "root", "feeds": 1})
    gm.spawn("thing", "Ada", "Grain", state={"portable": True, "food": "grain", "feeds": 2})
    with pytest.raises(Rejected, match="sniffs the grain and turns away"):
        ada.act("feed", pup, {"item": "Grain"})
    gm.patch(pup, {"fed": 2})
    with pytest.raises(Rejected, match="feed Pup from your hand first"):
        ada.act("gentle", pup)
    with pytest.raises(Rejected, match="never be tamed"):
        ada.act("gentle", "Old boar")
    days = 0
    while st(gm, pup).get("owner") is None and days < 10:
        days += 1
        ada.act("feed", pup, {"item": "Glassthorn root"})
        ada.act("gentle", pup)
        if st(gm, pup).get("owner") is None:
            with pytest.raises(Rejected, match="had enough of you today"):
                ada.act("gentle", pup)
        dawn(gm)
    s = st(gm, pup)
    assert s.get("owner") == gm.inspect("Ada")["id"] and s["follows"] == s["owner"] and s["loyalty"] >= 3
    assert days >= 3  # three trust at the least, one a day


def test_a_kept_beast_nobody_feeds_goes_feral_and_home(wild):
    eng, gm = wild
    ada = gm.inspect("Ada")["id"]
    gm.move("Ada", "Den")
    kept = dict(owner=ada, follows=ada, loyalty=3, with_owner=0, home="Brake", sex="f")
    hungry = beast(gm, "Den", "Hungry", **kept)
    loved = beast(gm, "Den", "Loved", **kept)
    for d in range(3):
        if d > 0:  # the first day it is full: a day it wanted nothing costs it nothing
            gm.spawn("thing", "Ada", "Root", state={"portable": True, "food": "root", "feeds": 1})
            gm.act_as("Ada", "feed", loved, {"item": "Root"})
        if d < 2:
            dawn(gm)
            assert st(gm, hungry).get("owner") == ada
    dawn(gm)
    h = st(gm, hungry)
    assert h.get("owner") is None and h["loyalty"] == 0
    assert gm.inspect("Hungry")["parent"] == gm.inspect("Brake")["id"]  # back to the brake it came from
    assert st(gm, loved).get("owner") == ada and st(gm, loved)["loyalty"] == 5


def test_a_kept_beast_follows_stays_and_comes(wild):
    eng, gm = wild
    ada = eng.session("ada")
    ada.join("wild", "Ada")
    me = gm.inspect("Ada")["id"]
    dog = beast(gm, "Yard", "Bristle", owner=me, follows=me, loyalty=4, sex="m")
    ada.act("go", "Brake")
    assert gm.inspect("Bristle")["parent"] == gm.inspect("Brake")["id"]
    ada.act("stay", dog)
    ada.act("go", "Den")
    assert gm.inspect("Bristle")["parent"] == gm.inspect("Brake")["id"]
    ada.act("come", dog)
    assert gm.inspect("Bristle")["parent"] == gm.inspect("Den")["id"] and st(gm, dog)["follows"] == me
    stranger = eng.session("cass")
    gm.spawn("person", "Den", "Cass")
    stranger.join("wild", "Cass")
    with pytest.raises(Rejected, match="not yours"):
        stranger.act("stay", dog)


def test_a_kept_guard_growls_at_strangers_and_takes_up_its_owners_fight(wild):
    eng, gm = wild
    me = gm.inspect("Ada")["id"]
    dog = beast(gm, "Yard", "Bristle", owner=me, follows=me, loyalty=4, sex="m")
    gm.spawn("thing", dog, "Snout", state={"weapon": True, "damage": 1, "portable": False})
    gm.spawn("person", "Brake", "Cutthroat", state={"body": 2})
    cut = eng.session("cut")
    cut.join("wild", "Cutthroat")
    cut.act("go", "Yard")
    assert any(e["kind"] == "growled" for e in gm.perceive(from_entity="Ada", events=40)["events"])
    gm.world.set_pace({"fighter_tick": 6})
    cut.act("attack", "Ada")
    assert st(gm, dog)["attacked_by"] == gm.inspect("Cutthroat")["id"]
    gm.clock(step=12)
    blows = [e for e in gm.perceive(from_entity="Ada", events=60)["events"]
             if e["kind"] in ("hit", "missed") and e.get("payload", {}).get("by") == dog]
    assert blows


def test_a_herd_goat_gives_milk_when_fed_and_herd_beasts_breed_as_keepers_feed(wild):
    eng, gm = wild
    nanny = gm.spawn("beast", "Ridge", "Nanny", state={"species": "goat", "sex": "f", "age": 10, "stage": "adult", "herd": "Ridge", "fed": 3})["id"]
    dawn(gm)
    milk = [c for c in gm.world.children(gm.inspect("Ridge")["id"]) if c["name"] == "Goat's milk"]
    assert len(milk) == 1 and milk[0]["state"]["yield_of"] == nanny
    dawn(gm, 3)
    assert len([c for c in gm.world.children(gm.inspect("Ridge")["id"]) if c["name"] == "Goat's milk"]) == 2  # max 2 lying


def test_a_clumsy_hand_gets_bitten_and_loses_trust(wild):
    eng, gm = wild
    pup = beast(gm, "Brake", "Sow", sex="f", home="Brake")  # an adult: dc 14, and a bite at 9 or less
    gm.spawn("person", "Brake", "Cass", state={"wits": 0, "skills": {}})
    cass = eng.session("cass")
    cass.join("wild", "Cass")
    bit, blows = [], []
    for _ in range(15):
        gm.spawn("thing", "Cass", "Root", state={"portable": True, "food": "root", "feeds": 1})
        cass.act("feed", pup, {"item": "Root"})
        r = cass.act("gentle", pup)
        bit += [e for e in r["events"] if e["kind"] == "beast_bit"]
        blows += [e for e in r["events"] if e["kind"] in ("hit", "missed")]
        if bit:
            break
        dawn(gm)
    assert bit, "a d20 with nothing added fails by 5 often enough"
    assert (st(gm, pup).get("trust") or {}).get(gm.inspect("Cass")["id"], 0) >= 0
    assert blows  # the bite is a d20 blow


def test_a_species_with_a_season_breeds_only_in_it(wild):
    eng, gm = wild
    gm.patch("thornback", {"season": True, "breed_chance": 1.0})
    beast(gm, "Brake", "The boar", sex="m", home="Brake")
    sow = beast(gm, "Brake", "The sow", sex="f", home="Brake")
    dawn(gm, 5)
    assert not st(gm, sow).get("carrying")
    gm.patch("thornback", {"in_season": True})
    dawn(gm)
    assert st(gm, sow)["carrying"]["due"] == gm.world.get(gm.world.root_id)["state"]["beast_day"] + 6


GOAT = {"eats": ["graze"], "fed_max": 3, "young_name": "Kid", "breed_chance": 0.3, "gestation": 5, "litter": [1, 2],
        "lifespan": 70, "carcass": 8,
        "stages": [{"name": "young", "from": 0, "state": {"body": 1, "vigor": 3, "max_vigor": 3}},
                   {"name": "adult", "from": 8, "state": {"body": 2, "vigor": 5, "max_vigor": 5, "skills": {"brawl": 1}},
                    "names": {"m": "Billy", "f": "Nanny"}},
                   {"name": "old", "from": 50, "state": {"body": 1}}]}
JACKAL = {"eats": ["meat", "carrion"], "preys_on": ["goat"], "fed_max": 3, "starve_days": 4, "young_name": "Jackal pup",
          "breed_chance": 0.2, "gestation": 8, "litter": [1, 2], "lifespan": 80, "tame_dc": {"young": 12}, "tame_at": {"young": 4},
          "wanders_in": {"at": "Dunes", "prey": 6, "count": [2, 2]},
          "stages": [{"name": "young", "from": 0, "state": {"body": 1, "vigor": 3, "max_vigor": 3}},
                     {"name": "adult", "from": 10, "state": {"body": 2, "vigor": 5, "max_vigor": 5, "skills": {"brawl": 2}},
                      "names": {"m": "Jackal dog", "f": "Jackal bitch"},
                      "parts": [{"name": "Fangs", "state": {"weapon": True, "damage": 2, "portable": False}}]},
                     {"name": "old", "from": 60, "state": {"body": 1}}]}


def hunting_ground(gm):
    root = gm.world.root_id
    gm.spawn("place", root, "Dunes")
    gm.connect("Ridge", "Dunes")
    gm.patch("Ridge", {"forage": {"graze": {"left": 8, "max": 8, "regrow": 5}}})
    gm.patch("goat", GOAT)
    gm.spawn("species", root, "jackal", state=JACKAL)


def test_hunters_and_their_herd_both_last_ninety_days_and_swing(wild):
    eng, gm = wild
    hunting_ground(gm)
    for i, sex in enumerate(["m", "f", "f", "f"]):
        gm.spawn("beast", "Ridge", f"Goat {i}", state={"species": "goat", "sex": sex, "age": 12 + i * 5, "stage": "adult",
                                                    "fed": 3, "home": "Ridge", "vigor": 5, "max_vigor": 5, "body": 2})
    for i, sex in enumerate(["m", "f", "f"]):
        j = gm.spawn("beast", "Dunes", f"Jackal {i}", state={"species": "jackal", "sex": sex, "age": 15 + i * 5, "stage": "adult",
                                                          "fed": 2, "home": "Dunes", "pack": True, "vigor": 5, "max_vigor": 5,
                                                          "body": 2, "skills": {"brawl": 2}})["id"]
        gm.spawn("thing", j, "Fangs", state={"weapon": True, "damage": 2, "portable": False})
    goats, jackals = [], []
    for _ in range(90):
        dawn(gm)
        alive = living(gm)
        goats.append(len([e for e in alive if e["state"]["species"] == "goat"]))
        jackals.append(len([e for e in alive if e["state"]["species"] == "jackal"]))
    kinds = [e["kind"] for e in gm.world.store.query("event", "world_id=? AND kind IN ('killed','beast_wandered_in')", (gm.world.id,))]
    # the hunters kill, the herd never goes (its last two, and its last grown pair, are out of reach), and a pack that
    # starves out comes back from beyond the map once the herd is big again
    assert kinds.count("killed") >= 5 and min(goats) >= 2 and max(goats) - min(goats) >= 3, goats
    assert sum(1 for j in jackals if j > 0) >= 60 and jackals[-1] > 0, jackals


def test_a_carcass_rots_and_a_tamed_hunter_eats_meat_cut_from_it(wild):
    eng, gm = wild
    hunting_ground(gm)
    me = gm.inspect("Ada")["id"]
    gm.move("Ada", "Dunes")
    goat = gm.spawn("beast", "Dunes", "Old goat", state={"species": "goat", "sex": "f", "age": 40, "stage": "adult",
                                                       "fed": 0, "hungry_days": 1})["id"]
    pup = gm.spawn("beast", "Dunes", "Pup", state={"species": "jackal", "sex": "f", "age": 2, "stage": "young",
                                                 "owner": me, "follows": me, "loyalty": 3, "with_owner": 0, "fed": 0})["id"]
    dawn(gm)  # the goat starves on the bare sand and lies there as meat
    g = st(gm, goat)
    assert g["dead"] and "meat" in g["food"] and g["meals"] == 8
    gm.act_as("Ada", "butcher", goat)
    assert any(c["name"] == "Meat" for c in gm.world.children(me))
    with pytest.raises(Rejected, match="turns away"):
        gm.spawn("thing", "Ada", "Grass", state={"portable": True, "food": "graze", "feeds": 1})
        gm.act_as("Ada", "feed", pup, {"item": "Grass"})
    gm.act_as("Ada", "feed", pup, {"item": "Meat"})
    assert st(gm, pup)["fed"] == 1
    dawn(gm)  # turned, and the pup eats the carrion where it lies
    assert st(gm, goat)["food"] == ["carrion"] and st(gm, goat)["meals"] < 7 and st(gm, pup)["fed"] >= 1
    dawn(gm, 2)
    assert st(gm, goat).get("food") is None and st(gm, goat).get("meals") == 0
    with pytest.raises(Rejected, match="nothing left"):
        gm.act_as("Ada", "butcher", goat)


def test_a_bold_pack_goes_for_a_person_only_when_they_are_alone(wild):
    eng, gm = wild
    hunting_ground(gm)
    gm.patch("jackal", {"attacks_people": True})
    j = gm.spawn("beast", "Dunes", "Lean jackal", state={"species": "jackal", "sex": "m", "age": 20, "stage": "adult", "fed": 0,
                                                  "home": "Dunes", "pack": True})["id"]
    gm.spawn("person", "Ridge", "Cass")
    gm.spawn("person", "Ridge", "Dov")
    dawn(gm)
    assert st(gm, j).get("attacked_by") is None and gm.inspect(j)["parent"] == gm.inspect("Dunes")["id"]
    gm.move("Dov", "Yard")
    dawn(gm)
    assert st(gm, j)["attacked_by"] == gm.inspect("Cass")["id"] and gm.inspect(j)["parent"] == gm.inspect("Ridge")["id"]


def test_a_goat_that_strayed_walks_home_a_way_a_day(wild):
    # the Reach: goats that fled or wandered hungry ended at the Low Well and starved there, ways from the ridge
    eng, gm = wild
    root = gm.world.root_id
    for p in ("Flats", "Scrub", "Low Well"):
        gm.spawn("place", root, p)
    gm.connect("Ridge", "Flats")
    gm.connect("Flats", "Scrub")
    gm.connect("Scrub", "Low Well")
    gm.patch("goat", {"starve_days": 4})
    fed = beast(gm, "Flats", "Nanny", species="goat", sex="f", home="Ridge", fed=3)
    lost = beast(gm, "Low Well", "Billy", species="goat", sex="m", home="Ridge", fed=1)
    dawn(gm)
    assert where(gm, "Nanny") == "Ridge"  # fed, and home has graze where she stands has none
    assert where(gm, "Billy") == "Scrub"  # hungry with nothing near: a way toward home, not a wait to starve
    dawn(gm)
    assert where(gm, "Billy") == "Flats"
    dawn(gm)
    assert where(gm, "Billy") == "Ridge"  # the ridge's graze is next door now: he goes to eat
    assert not gm.world.get(lost)["state"].get("dead") and not gm.world.get(fed)["state"].get("dead")



def test_young_on_the_way_count_against_the_land(wild):
    # the Reach: four goats on a ridge that regrows five, three nannies conceived at one dawn and the herd jumped to seven
    eng, gm = wild
    gm.patch("Ridge", {"forage": {"graze": {"left": 8, "max": 8, "regrow": 5}}})
    gm.patch("goat", {"breed_chance": 1.0, "gestation": 5, "litter": [1, 1]})
    beast(gm, "Ridge", "Billy", species="goat", sex="m", home="Ridge")
    for n in ("Nan", "Dot", "Bess"):
        beast(gm, "Ridge", n, species="goat", sex="f", home="Ridge")
    dawn(gm)
    carrying = [e for e in gm.world.find(type="beast", limit=100) if e["state"].get("carrying")]
    assert len(carrying) == 1  # four here and one on the way fill what the ridge regrows

def where(gm, name):
    return gm.world.get(gm.world.get(gm.inspect(name)["id"])["parent_id"])["name"]
