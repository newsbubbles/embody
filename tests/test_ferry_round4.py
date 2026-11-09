"""Round four of the ferry world, from the third playtest: gifts per asker, a mug that stays, tipsy, words that
change with the world, chores and the debt they square, villagers with goals and opinions."""

from pathlib import Path

from embody.cli import load_world_file
import pytest

from embody.ops import AUTHOR, Engine, Rejected

WORLDS = Path(__file__).resolve().parent.parent / "worlds"


def ferry():
    eng = Engine()
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world_file(gm, WORLDS / "ferry_at_dusk.py")
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    return eng, gm, you


def texts(r):
    return [e["payload"].get("text") for e in r["events"] if e["kind"] == "say"]


def test_mara_pours_one_ale_per_asker_not_per_lifetime():
    eng, gm, you = ferry()
    gm.spawn("person", "Ashford Square", "Pedlar")
    other = eng.session("pedlar")
    other.join("ferry-at-dusk", "Pedlar")
    you.act("talk", "Mara", {"about": "an ale"})
    assert [c["name"] for c in you.perceive()["holding"]] == ["Dark ale"]
    r = other.act("talk", "Mara", {"about": "ale"})
    assert [c["name"] for c in other.perceive()["holding"]] == ["Dark ale"]
    assert any(t and t.startswith("She sets") for t in texts(r))
    r = you.act("talk", "Mara", {"about": "another ale"})
    assert any(t and t.startswith("One was the deal") for t in texts(r))
    assert len(you.perceive()["holding"]) == 1
    me = gm.world.find(name="Traveler")[0]["id"]
    ped = gm.world.find(name="Pedlar")[0]["id"]
    assert sorted(gm.inspect("Mara")["state"]["gave"]["ale|drink|beer|pint"]) == sorted([me, ped])


def test_a_story_is_the_fare_and_three_drinks_make_you_tipsy():
    eng, gm, you = ferry()
    you.say("Let me tell you how I came to be here.", to="Mara")
    r = you.act("talk", "Mara", {"about": "my story, the one I owe you"})
    assert any(t and "three mugs" in t for t in texts(r))
    mugs = next(c for c in you.perceive()["holding"] if c["name"].startswith("Three"))
    for _ in range(3):
        you.act("drink", mugs["id"])
    me = gm.inspect("Traveler")["state"]
    assert me["drinks"] == 3 and me["tipsy"] is True
    r = you.act("check", "Traveler", {"skill": "walk a straight line"})
    ck = next(e for e in r["events"] if e["kind"] == "checked")
    assert ck["payload"]["mod"] == -2 and ck["payload"]["total"] == ck["payload"]["roll"] - 2
    for _ in range(3):
        you.act("drink", mugs["id"])
    # the mug stays, empty, and says so
    held = next(c for c in you.perceive()["holding"] if c["id"] == mugs["id"])
    assert held["state"]["left"] == 0 and held["state"]["description"].startswith("An empty mug")


def test_the_world_changes_its_words_when_you_change_it():
    eng, gm, you = ferry()
    you.act("take", "Bone")
    assert gm.inspect("Bench")["state"]["description"] == "A plank bench by the well, worn pale."
    you.act("go", "Pell's Mill")
    you.act("give", "Biscuit", {"item": "Bone"})
    assert "FOUND: the grey dog" in gm.inspect("Notice board")["state"]["text"]
    you.act("take", "Coil of rope")
    you.act("go", "Ashford Square")
    you.act("go", "The Landing")
    you.act("tie", "Landing bell")
    assert "new rope" in gm.inspect("Landing bell")["state"]["description"]
    assert "t=" not in " ".join(gm.inspect(gm.summary()["root"])["state"]["policy"]["fixed"])


def test_work_at_the_mill_squares_tams_debt():
    eng, gm, you = ferry()
    hob = gm.world.find(name="Hob")[0]["id"]
    tam = gm.world.find(name="Old Tam")[0]["id"]
    debts = [r for r in gm.inspect(hob)["relations"] if r["relation"] == "debt"]
    assert debts and debts[0]["participants"] == [tam, hob]
    you.act("go", "Pell's Mill")
    with pytest.raises(Rejected, match="pot of grease"):
        you.act("work", "Mill wheel")
    aff = {a["verb"] for a in you.perceive()["affordances"]}
    assert "work" in aff
    you.act("take", "Pot of grease")
    r = you.act("work", "Mill wheel")
    assert r["elapsed"] == 20
    kinds = [e["kind"] for e in r["events"]]
    assert "worked" in kinds and "chore_done" in kinds and "debt_settled" in kinds
    assert any(t and t.startswith("That squares Old Tam's three jugs") for t in texts(r))
    assert not [x for x in gm.inspect(hob)["relations"] if x["relation"] == "debt"]
    assert gm.inspect("Mill wheel")["state"]["chore"]["done"] is True
    assert "smooth" in gm.inspect("Mill wheel")["state"]["description"]
    with pytest.raises(Rejected, match="done already"):
        you.act("work", "Mill wheel")
    r = you.act("work", "Heap of empty sacks")
    assert r["ok"] is True and "stacked" in gm.inspect("Heap of empty sacks")["state"]["description"]
    with pytest.raises(Rejected, match="nothing to be done"):
        you.act("work", "Sack of flour")


def test_villagers_start_with_goals_and_opinions_and_upgrade_is_idempotent():
    eng, gm, you = ferry()
    hob = eng.session("hob-mind")
    hob.join("ferry-at-dusk", "Hob")
    b = hob.perceive()
    assert [g["text"] for g in b["goals"]][0].startswith("Get Tam's three jugs")
    k = {x["name"]: x for x in b["knows"]}
    assert k["Old Tam"]["standing"] == -1 and k["Mara"]["standing"] == 1
    rel = hob.recall(about="Old Tam")
    assert any(g["relation"] == "debt" for g in rel["groups"])
    h0 = gm.world.state_hash()
    load_world_file(gm, WORLDS / "ferry_at_dusk.py", upgrade=True)
    load_world_file(gm, WORLDS / "ferry_at_dusk.py", upgrade=True)
    assert gm.world.state_hash() == h0
    assert len([g for g in gm.inspect("Hob")["state"]["goals"]]) == 2


def test_upgrade_converts_an_old_gave_list_and_promotes_improvised_chores():
    eng, gm, you = ferry()
    mara = gm.world.find(name="Mara")[0]["id"]
    me = gm.world.find(name="Traveler")[0]["id"]
    gm.patch(mara, {"gave": ["ale|drink|beer|pint"]}, replace=False)
    gm.world.patch(mara, {"gave": ["ale|drink|beer|pint"]})
    pot = gm.world.find(name="Pot of grease")[0]["id"]
    gm.patch(pot, {"improvised": True})
    gm.destroy("Mill wheel")
    load_world_file(gm, WORLDS / "ferry_at_dusk.py", upgrade=True)
    assert gm.inspect(mara)["state"]["gave"] == {"ale|drink|beer|pint": [me]}
    assert gm.inspect(pot)["state"].get("improvised") is None
    assert gm.world.find(name="Mill wheel")
    r = you.act("talk", "Mara", {"about": "ale"})
    assert any(t and t.startswith("One was the deal") for t in texts(r))
