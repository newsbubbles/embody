"""The sheet pack: twelve attributes and ranked skills behind d20's one bonus(), a converted body that rolls what it
rolled before, grants, growth only from difficulties the world sets, and what perceive and guide('skills') show."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected
from packs.sheet.pack import to_sheet

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "drill", "name": "Drill Yard", "seed": 7, "description": "A yard, a well, two posts.",
         "requires": ["d20", "village", "sheet"]}

from packs.d20.pack import install_rules

def define(s):
    s.define_schema("person", extends="combatant")
    s.define_schema("post", extends="thing", state={"portable": False},
                    actions={"train": {"script": "train", "doc": "Learn against this post at the world's dc"}})

def populate(s):
    root = s.summary()["root"]
    install_rules(s, root)
    yard = s.spawn("place", root, "Yard", state={"water_source": True})["id"]
    for name in ("Ada", "Bel"):
        s.spawn("person", yard, name, state={"body": 2, "wits": 3, "will": 1, "skills": {"blade": 2, "lore": 1, "parley": 3}})
    s.spawn("post", yard, "North Post")
    s.spawn("post", yard, "South Post")
    s.clock(run=False)
'''

TRAIN = '''use("common")
def apply(ctx):
    p = ctx.params or {}
    return learn(ctx, ctx.actor, str(p.get("skill")), int(p.get("dc")), bool(p.get("success")), ctx.target)
'''


@pytest.fixture
def drill(tmp_path):
    for p in ("village", "d20", "sheet"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "packs" / "__init__.py").write_text("", encoding="utf-8")
    world = tmp_path / "worlds" / "drill"
    (world / "scripts").mkdir(parents=True)
    (world / "build.py").write_text(BUILD, encoding="utf-8")
    (world / "scripts" / "train.py").write_text(TRAIN, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "drill")
    ada = eng.session("ada")
    ada.join("drill", "Ada")
    return eng, gm, ada


def mod(seat, skill):
    return seat.act("check", params={"skill": skill, "dc": 1})["result"]["mod"]


def learned(r):
    return [e["payload"] for e in r["events"] if e["kind"] == "learned"]


SKILLS = ["blade", "brawl", "climb", "stealth", "survival", "lore", "lockpick", "aim", "parley", "resolve", "dodge", "juggling"]


def test_a_converted_body_rolls_the_bonus_it_rolled_before(drill):
    eng, gm, ada = drill
    before = {k: mod(ada, k) for k in SKILLS}
    assert before["blade"] == 4 and before["parley"] == 4 and before["juggling"] == 3  # stat + rank; untrained on wits
    gm.patch("Ada", {"sheet": to_sheet(gm.inspect("Ada")["state"])})
    assert {k: mod(ada, k) for k in SKILLS} == before
    gm.patch("Ada", {"wounded": True, "thirsty": True})
    assert mod(ada, "blade") == before["blade"] - 4
    gm.patch("Ada", {"wounded": False, "thirsty": False})
    # a sheet of its own: force 16 (+3) and poise 13 (+1) average to +2 for a blade, and the rank adds whole
    gm.patch("Ada", {"sheet": {"attributes": {"force": 16, "poise": 13}, "skills": {"blade": 6}}}, replace=True)
    assert mod(ada, "blade") == 8
    note = ada.act("check", params={"skill": "juggling", "dc": 1})["result"]["note"]
    assert "skillbook" in note and "acuity" in note


def test_grants_add_their_bonus_and_one_use_ones_are_spent(drill):
    eng, gm, ada = drill
    gm.patch("Ada", {"sheet": to_sheet(gm.inspect("Ada")["state"])})
    base = mod(ada, "climb")
    gm.patch("Ada", {"grants": [{"source": "rope", "bonus": 2, "skill": "climb"},
                                {"source": "rope", "bonus": 1, "skill": "climb"},  # the same source: only the largest
                                {"source": "Bel", "bonus": 3, "uses": 1},
                                {"source": "old", "bonus": 9, "until": -1}]})
    assert mod(ada, "climb") == base + 5
    assert mod(ada, "climb") == base + 2  # Bel's hand is spent
    assert [g["source"] for g in gm.inspect("Ada")["state"]["grants"]] == ["rope", "rope"]  # the lapsed one fell away
    assert mod(ada, "lore") == mod(ada, "lore")  # a climbing rope is no help with lore


def test_only_a_difficulty_the_world_sets_teaches_and_ranks_come_slowly(drill):
    eng, gm, ada = drill
    gm.patch("Ada", {"sheet": to_sheet(gm.inspect("Ada")["state"])})
    r = ada.act("check", params={"skill": "climb", "dc": 30})
    assert learned(r) == []  # a dc you chose teaches nothing
    # climb rolls force + poise at 14: +2, rank 0. dc 19 needs 17: 3 experience, doubled on a success
    r = ada.act("train", "North Post", params={"skill": "climb", "dc": 19, "success": True})
    got = learned(r)[0]
    assert got["need"] == 17 and got["earned"] == 6 and got["rank"] == 0 and got["xp"] == 6 and got["next"] == 10
    r = ada.act("train", "North Post", params={"skill": "climb", "dc": 19, "success": True})
    got = learned(r)[0]
    assert got["ranked_up"] and got["rank"] == 1 and got["xp"] == 2 and got["next"] == 20
    assert learned(ada.act("train", "North Post", params={"skill": "climb", "dc": 9, "success": True})) == []  # trivial
    # three teaching rolls a skill, a target, a world day: the fourth on this post teaches nothing, another post does
    assert learned(ada.act("train", "North Post", params={"skill": "climb", "dc": 19, "success": False})) == []
    assert learned(ada.act("train", "South Post", params={"skill": "climb", "dc": 19, "success": False}))[0]["earned"] == 2  # rank 1 now: needs 16
    assert learned(ada.act("train", "South Post", params={"skill": "climb", "dc": 40, "success": False})) == []  # out of reach
    # the DM's numbers on the root win
    gm.patch(gm.summary()["root"], {"sheet_rules": {**gm.inspect(gm.summary()["root"])["state"]["sheet_rules"], "success_x": 1}})
    assert learned(ada.act("train", "South Post", params={"skill": "lore", "dc": 19, "success": True}))[0]["earned"] == 2  # lore +4: needs 15
    # a body with no sheet never learns
    bel = eng.session("bel")
    bel.join("drill", "Bel")
    assert learned(bel.act("train", "North Post", params={"skill": "climb", "dc": 19, "success": True})) == []


def test_an_opposed_blow_teaches_both_and_a_weapon_names_its_skill(drill):
    eng, gm, ada = drill
    gm.patch("Ada", {"sheet": {"attributes": {"force": 20}, "skills": {"blade": 3}}})
    gm.spawn("thing", "Ada", "Knife", state={"weapon": True, "skill": "short blades", "damage": 1})
    gm.patch("Bel", {"sheet": to_sheet(gm.inspect("Bel")["state"])})
    gm.spawn("thing", "Bel", "Sabre", state={"weapon": True, "damage": 1})
    ada.act("attack", "Bel")
    ids = {n: gm.inspect(n)["id"] for n in ("Ada", "Bel")}
    # each side's roll counted as a teaching roll on its own weapon's skill, against the other
    assert list(gm.inspect("Ada")["state"]["sheet"]["taught"]) == ["short blades|" + ids["Bel"]]
    assert list(gm.inspect("Bel")["state"]["sheet"]["taught"]) == ["blade|" + ids["Ada"]]
    # related: short blades borrows blade's rank // 3
    gm.patch(gm.find(type="skillbook")[0]["id"], {"skills": {**gm.inspect("Skillbook")["state"]["skills"],
              "short blades": {"primary": "force", "secondary": "poise", "scope": "knives", "related": ["blade"]}}})
    gm.patch("Ada", {"sheet": {"attributes": {}, "skills": {"blade": 9}}}, replace=True)
    assert mod(ada, "short blades") == 3


def test_perceive_shows_ranked_skills_and_guide_has_the_skillbook(drill):
    eng, gm, ada = drill
    gm.patch("Ada", {"sheet": {"attributes": {"force": 12}, "skills": {"blade": 2, "climb": 0}, "xp": {"blade": 4},
                               "taught": {"blade|x": [0, 1]}}})
    gm.patch("Bel", {"sheet": {"attributes": {"poise": 14}, "skills": {"lore": 1}, "xp": {"lore": 7}}})
    b = ada.perceive()
    mine = b["you"]["state"]["sheet"]
    assert mine["skills"] == {"blade": 2} and mine["xp"] == {"blade": "4/30"} and "taught" not in mine
    bel = next(c for c in b["present"] if c["name"] == "Bel")["state"]["sheet"]
    assert bel["skills"] == {"lore": 1} and "xp" not in bel
    g = ada.guide("skills")
    assert "- blade (force + poise)" in g["text"] and g["rules"]["rank_cost"] == 10
    assert "sheet" in ada.guide("changes", since=0)["text"]


def test_a_world_without_the_pack_has_no_skillbook(tmp_path):
    eng = Engine(tmp_path / "w.db", workspace=REPO, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, REPO / "examples" / "ferry-at-dusk")
    with pytest.raises(Rejected) as r:
        gm.guide("skills")
    assert "no skillbook" in str(r.value)
