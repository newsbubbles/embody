"""packs/works in a small yard: a portable plan built where its holder stands, materials and roles before work
counts, the crew three ways (assigned, hired, volunteered), wages, a settling stage someone undoes, a stolen plan, and
the finished thing born with who made it."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "yard", "name": "The Yard", "seed": 3, "description": "A yard and a quarry.", "requires": ["village", "works"]}

PLAN = {"portable": True, "where": {"not": ["hidden"]}, "pay_every": 7200,
        "stages": [{"name": "base", "labour": 2, "needs": {"Stone": 2}, "roles": {"mason": 1, "hand": 1}, "settles": 1,
                    "scene": "A ring of stones sits squared in the yard."},
                   {"name": "cap", "labour": 1, "roles": {"mason": 1}}],
        "becomes": {"type": "thing", "name": "Cairn", "state": {"portable": False, "description": "A cairn."},
                    "scene": "A cairn stands in the yard."}}

def define(s):
    s.define_schema("faction", extends="entity", state={"hidden": True})
    s.define_schema("person", extends="creature", state={"water": 10},
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"},
                             "take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here"},
                             "drop": {"script": "drop", "doc": "Put down", "targets": "thing", "scope": "held"}})

def populate(s):
    root = s.summary()["root"]
    yard = s.spawn("place", root, "Yard")["id"]
    quarry = s.spawn("place", root, "Quarry")["id"]
    s.spawn("place", root, "Den", state={"hidden": True})
    s.connect(yard, quarry)
    s.spawn("faction", root, "the Masons", state={"leader": "Boss"})
    boss = s.spawn("person", yard, "Boss", state={"faction": "the Masons"})["id"]
    s.spawn("person", yard, "Pat", state={"faction": "the Masons"})
    s.spawn("person", quarry, "Mute", state={"faction": "the Masons"})
    s.spawn("person", yard, "Hand", state={"for_hire": {"wage": {"kind": "coin", "count": 1}, "roles": ["hand"],
                                                        "line": "A coin a day and I carry anything."}})
    s.spawn("person", yard, "Thief")
    s.spawn("blueprint", boss, "Plan for a cairn", state=dict(PLAN))
    for n in range(2):
        s.spawn("thing", boss, "Stone", state={"portable": True})
    s.spawn("thing", boss, "Purse", state={"portable": True, "kind": "coin", "count": 1})
    s.clock(run=False)
'''


@pytest.fixture
def yard(tmp_path):
    for p in ("village", "works"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "yard").mkdir(parents=True)
    (tmp_path / "worlds" / "yard" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "yard")
    yield eng, gm
    w = eng.world("yard")
    errors = w.store.query("event", "world_id=? AND kind='script_error'", (w.id,))
    assert not errors, [e["payload"] for e in errors]


def seat(eng, name):
    s = eng.session("p-" + name.lower())
    s.join("yard", name)
    return s


def run(gm, seconds):
    """World time in ten-minute steps, as a running clock passes it (one long step fires a periodic tick once)."""
    for _ in range(int(seconds // 600)):
        gm.clock(step=600)
    if seconds % 600:
        gm.clock(step=seconds % 600)


def st(gm, name):
    return gm.inspect(name)["state"]


def test_a_plan_builds_where_it_is_held_and_says_what_it_wants(yard):
    eng, gm = yard
    boss = seat(eng, "Boss")
    assert "base: 2 hours of work" in boss.act("study", "Plan for a cairn")["result"]
    pat = seat(eng, "Pat")
    with pytest.raises(Rejected) as r:
        pat.act("build", "Plan for a cairn")
    assert "not within reach" in r.value.reason  # in Boss's hands, not Pat's
    boss.act("go", "Quarry")
    boss.act("go", "Yard")
    boss.act("build", "Plan for a cairn")
    works = gm.find(type="project")[0]
    assert works["name"] == "Works on the Cairn" and st(gm, "Plan for a cairn")["project"] == works["id"]
    assert gm.inspect("Plan for a cairn")["parent"] == works["id"]  # the plan is in the works
    survey = boss.act("survey", works["id"])["result"]
    assert "needs 2 more Stone" in survey and "no mason at work" in survey
    with pytest.raises(Rejected) as r:
        boss.act("build", "Plan for a cairn")
    assert "already under way" in r.value.reason or "hold the plan" in r.value.reason


def test_a_hidden_place_will_not_take_the_plan(yard):
    eng, gm = yard
    gm.move("Boss", "Den")
    boss = seat(eng, "Boss")
    with pytest.raises(Rejected) as r:
        boss.act("build", "Plan for a cairn")
    assert "hidden" in r.value.reason


def test_the_crew_three_ways_wages_and_the_finished_cairn(yard):
    eng, gm = yard
    boss = seat(eng, "Boss")
    boss.act("build", "Plan for a cairn")
    works = gm.find(type="project")[0]["id"]
    for _ in range(2):
        boss.act("supply", works, params={"item": "Stone"})
    # nobody hires a hand the works cannot pay; a mind is never assigned; the leader puts Mute (one step off) to work
    with pytest.raises(Rejected) as r:
        boss.act("hire", works, params={"who": "Hand", "role": "hand"})
    assert "supply it first" in r.value.reason
    boss.act("supply", works, params={"item": "Purse"})
    boss.act("hire", works, params={"who": "Hand", "role": "hand"})
    seat(eng, "Pat")
    with pytest.raises(Rejected) as r:
        boss.act("assign", works, params={"who": "Pat", "role": "mason"})
    assert "mind of their own" in r.value.reason
    thief = seat(eng, "Thief")
    with pytest.raises(Rejected):
        thief.act("assign", works, params={"who": "Mute", "role": "mason"})
    boss.act("assign", works, params={"who": "Mute", "role": "mason"})
    assert st(gm, "Mute")["works_on"] == works and "put me to work" in st(gm, "Mute")["memory"][-1]["text"]
    run(gm, 600)  # Mute walks in from the quarry
    assert gm.inspect("Mute")["parent"] == gm.inspect("Yard")["id"]
    run(gm, 3000)
    w = st(gm, works)
    assert w["built_stages"] == ["base"] and w["settling_until"]  # two of them, an hour: the base is done and settling
    assert not gm.find(name="Stone")  # used up
    # the boss takes his mason off; at the turn of the pay day the hand gets the one coin the works hold
    boss.act("assign", works, params={"who": "Mute", "role": "none"})
    run(gm, 3600)
    assert any(e["state"].get("kind") == "coin" for e in gm.find(under="Hand"))
    # the next pay day there is nothing, and after two the hand walks off
    run(gm, 7200)
    hand = gm.inspect("Hand")["id"]
    assert st(gm, works)["crew"][hand]["unpaid"] == 1
    run(gm, 7200)
    assert hand not in st(gm, works)["crew"] and not st(gm, "Hand").get("works_on")
    boss.act("assign", works, params={"who": "Mute", "role": "mason"})
    # the cap needs only the mason: it stands, and the cairn is born with who made it
    run(gm, 3600)
    cairn = [e for e in gm.find(name="Cairn") if e["name"] == "Cairn"]  # find matches "Plan for a cairn" too
    assert cairn and not gm.find(type="project")
    prov = gm.inspect("Cairn")["state"]["provenance"]
    assert prov["how"] == "built" and gm.inspect("Mute")["id"] in prov["by"] and prov["patron"] == gm.inspect("Boss")["id"]
    assert "helped build the Cairn" in st(gm, "Mute")["memory"][-1]["text"]
    assert "had the Cairn built" in st(gm, "Boss")["memory"][-1]["text"]
    assert st(gm, "Plan for a cairn")["built"] == cairn[0]["id"]
    with pytest.raises(Rejected) as r:
        boss.act("build", "Plan for a cairn")
    assert "already built" in r.value.reason or "hold the plan" in r.value.reason


def test_a_volunteer_works_by_the_hour_and_a_thief_stops_it(yard):
    eng, gm = yard
    boss = seat(eng, "Boss")
    boss.act("build", "Plan for a cairn")
    works = gm.find(type="project")[0]["id"]
    for _ in range(2):
        boss.act("supply", works, params={"item": "Stone"})
    pat = seat(eng, "Pat")
    r = pat.act("work", works, params={"role": "mason"})
    assert "no hand at work" in str(r)  # one mason is not enough for the base: the hour counts only if a hand comes
    boss.act("work", works, params={"role": "hand"})  # and he does, so both hours count
    run(gm, 3600)
    assert st(gm, works)["labour"] == 2 or st(gm, works)["built_stages"] == ["base"]
    # the base settles for an hour; the thief undoes it (weak guards: none), and the stones are gone with it
    thief = seat(eng, "Thief")
    gm.patch("Thief", {"body": 30})
    thief.act("undo", works)
    run(gm, 60)
    w = st(gm, works)
    assert w["stage"] == 0 and not w["built_stages"] and "needs 2 more Stone" in boss.act("survey", works)["result"]


def test_taking_the_plan_out_stops_the_next_stage(yard):
    eng, gm = yard
    boss = seat(eng, "Boss")
    boss.act("build", "Plan for a cairn")
    works = gm.find(type="project")[0]["id"]
    thief = seat(eng, "Thief")
    thief.act("take", "Plan for a cairn")
    assert any("plan is not in the works" in b for b in [boss.act("survey", works)["result"]])
    thief.act("supply", works, params={"item": "Plan for a cairn"})
    assert "plan is not in the works" not in boss.act("survey", works)["result"]


def test_a_finished_name_with_its_own_article_is_not_doubled(yard):
    eng, gm = yard
    gm.patch("Plan for a cairn", {"becomes": {"type": "thing", "name": "The raised wall", "state": {"portable": False}}})
    boss = seat(eng, "Boss")
    assert "A plan for the raised wall." in boss.act("study", "Plan for a cairn")["result"]
    boss.act("build", "Plan for a cairn")
    works = gm.find(type="project")[0]
    assert works["name"] == "Works on the raised wall"
    run(gm, 60)
    assert gm.inspect(works["id"])["state"]["description"].startswith("The works on the raised wall")
