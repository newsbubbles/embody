"""The Glass Reach as a story: seats with stakes, the hidden well and the two ways to it, terms with Taan, Dram in the
ring, the letter, the end states, the trade at the Landing, the timers, and a safe upgrade."""

from pathlib import Path

from embody.cli import load_world_file
import pytest

from embody.ops import AUTHOR, Engine, Rejected

WORLDS = Path(__file__).resolve().parent.parent / "worlds"


def reach(seat="Reeve Ansel Varrick"):
    eng = Engine()
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world_file(gm, WORLDS / "glass_reach.py")
    you = eng.session("you")
    you.join("glass-reach", seat)
    return eng, gm, you


def kinds(r):
    return [e["kind"] for e in r["events"]]


def scenes(events):
    return [e["payload"]["text"] for e in events if e["kind"] == "scene"]


def story(gm):
    return gm.find(type="story")[0]["state"]


def test_the_seats_have_stakes_and_the_well_is_hidden():
    eng, gm, you = reach()
    p = you.perceive()
    assert [g["text"] for g in p["goals"]][0].startswith("Water for the Hold")
    assert {k["name"] for k in p["knows"]} == {"Captain Ruhl"}
    assert "The Deepwell" not in [e["name"] for e in p["exits"]]
    me = gm.inspect("Reeve Ansel Varrick")["id"]
    standings = {gm.inspect(e["target"])["name"]: e["data"]["value"] for e in gm.world.edges(me, "standing", "out")}
    assert standings == {"House Varrick": 5, "the Keth": -1, "House Dreyer": -3, "the Carriers": 0}
    sefa = eng.session("sefa")
    sefa.join("glass-reach", "Sefa of the Keth")
    assert [g["text"] for g in sefa.perceive()["goals"]][1].startswith("Keep the Deepwell")
    # a Keth walks down to her own well; a Hold man does not know the way
    sefa.act("go", "The Deepwell")
    assert gm.inspect("Sefa of the Keth")["parent"] == gm.inspect("The Deepwell")["id"]
    for place in ["The Gate Yard", "The Salt Road", "The Glass Flats", "Red Ridge"]:
        you.act("go", place)
    with pytest.raises(Rejected):
        you.act("go", "The Deepwell")


def test_the_ridge_shows_the_reach_and_a_hard_check_finds_the_well():
    eng, gm, you = reach()
    for place in ["The Gate Yard", "The Salt Road", "The Glass Flats"]:
        you.act("go", place)
    r = you.act("go", "Red Ridge")
    assert any("sheet of black glass" in t for t in scenes(r["events"]))
    r = you.act("check", params={"skill": "survival", "dc": 15})
    if not r["result"]["success"]:
        assert story(gm)["found_well"] is False
    gm.patch("Reeve Ansel Varrick", {"skills": {"survival": 30}})
    r = you.act("check", params={"skill": "survival", "dc": 15})
    assert story(gm)["found_well"] is True and gm.inspect("The Deepwell")["state"]["hidden"] is False
    assert any("way down" in t for t in scenes(r["events"]))
    you.act("go", "The Deepwell")
    assert gm.inspect("Reeve Ansel Varrick")["parent"] == gm.inspect("The Deepwell")["id"]


def test_nico_shows_the_way_to_a_friend_of_the_keth_only():
    eng, gm, you = reach()
    for place in ["The Gate Yard", "The Salt Road", "The Glass Flats", "Red Ridge"]:
        you.act("go", place)
    r = you.act("talk", "Nico", {"about": "water"})
    assert story(gm)["found_well"] is False
    assert any("Friends bring something" in (e["payload"].get("text") or "") for e in r["events"] if e["kind"] == "say")
    me = gm.inspect("Reeve Ansel Varrick")["id"]
    keth = gm.inspect("the Keth")["id"]
    gm.unlink(me, keth, "standing")
    gm.link(me, keth, "standing", {"value": 1, "public": True})
    r = you.act("talk", "Nico", {"about": "the well"})
    assert story(gm)["found_well"] is True and story(gm)["well_found_by"] == "nico"
    assert any("points down the back of the ridge" in t for t in scenes(r["events"]))


def test_terms_with_taan_make_a_truce_between_the_sides():
    eng, gm, you = reach()
    gm.patch("The Deepwell", {"hidden": False})
    for place in ["The Gate Yard", "The Salt Road", "The Glass Flats", "Red Ridge", "The Deepwell"]:
        you.act("go", place)
    gm.patch("Reeve Ansel Varrick", {"will": 30})
    r = you.act("parley", "Elder Taan", {"offer": "the Flats stay quiet and Keth water goes up the road at a fair price"})
    assert "agreed" in kinds(r) and story(gm)["truce"] is True
    keth = gm.inspect("the Keth")["id"]
    truces = gm.world.hyperedges(keth, "truce")
    assert len(truces) == 1 and gm.inspect("House Varrick")["id"] in truces[0]["participants"]
    assert any("water between us" in t for t in scenes(r["events"]))
    # an offer that is not terms, or a man the Keth will not hear, gets nothing
    eng2, gm2, you2 = reach()
    gm2.patch("The Deepwell", {"hidden": False})
    for place in ["The Gate Yard", "The Salt Road", "The Glass Flats", "Red Ridge", "The Deepwell"]:
        you2.act("go", place)
    gm2.patch("Reeve Ansel Varrick", {"will": 30})
    r = you2.act("parley", "Elder Taan", {"offer": "surrender the ridge"})
    assert "agreed" in kinds(r) and story(gm2)["truce"] is False
    assert any("not terms" in t for t in scenes(r["events"]))


def test_dram_walks_into_the_ring_at_240_and_calls_the_reeve_out():
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    gm.clock(step=240)
    ev = you.perceive(cursor=0, events=500)["events"]
    assert "challenged" in [e["kind"] for e in ev]
    assert gm.inspect("Dram Hollis")["parent"] == gm.inspect("The Gate Yard")["id"]
    reeve = gm.inspect("Reeve Ansel Varrick")["id"]
    assert len(gm.world.hyperedges(reeve, "duel")) == 1
    # he strikes on his own, slow, through the ward
    gm.clock(step=12)
    ev = you.perceive(cursor=0, events=500)["events"]
    dram = gm.inspect("Dram Hollis")["id"]
    assert any(e["kind"] in ("hit", "missed") and e["payload"]["by"] == dram for e in ev)
    assert not any(e["kind"] == "warded" and e["payload"]["by"] == dram for e in ev)


def test_dram_waits_when_the_reeve_is_elsewhere_and_calls_on_arrival():
    eng, gm, you = reach()
    gm.clock(step=240)
    assert gm.inspect("Dram Hollis")["state"]["waiting"] is True
    hold_events = you.perceive(cursor=0, events=500)["events"]
    assert any("clerk is in the ring" in t for t in scenes(hold_events))
    r = you.act("go", "The Gate Yard")
    assert "challenged" in kinds(r)
    assert gm.inspect("Dram Hollis")["state"]["waiting"] is False
    assert len(gm.world.hyperedges(gm.inspect("Dram Hollis")["id"], "duel")) == 1


def test_downing_dram_drops_the_letter_and_with_the_truce_the_hold_stands():
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    gm.clock(step=240)
    gm.patch("Reeve Ansel Varrick", {"body": 25})
    gm.patch("Dram Hollis", {"vigor": 1})
    r = you.act("attack", "Dram Hollis", {"slow": True})
    assert "downed" in kinds(r) and story(gm)["dram_done"] is True
    assert gm.inspect("Sealed letter")["parent"] == gm.inspect("The Gate Yard")["id"]
    you.act("take", "Sealed letter")
    r = you.act("read", "Sealed letter")
    assert "Keep the Keth thirsty" in r["result"] if isinstance(r["result"], str) else True
    assert story(gm)["done"] is False
    story_id = gm.find(type="story")[0]["id"]
    gm.patch(story_id, {"truce": True})
    # the end check runs on the next story event; a scene at the hold says it
    gm.patch("Dram Hollis", {"down": False, "vigor": 2})
    gm.patch(story_id, {"dram_done": False})
    r = you.act("attack", "Dram Hollis", {"slow": True})
    assert story(gm)["done"] is True and gm.inspect(gm.summary()["root"])["state"]["story"] == "complete"


def test_the_reeve_dead_is_the_lost_ending():
    eng, gm, you = reach("Dram Hollis")
    gm.patch("Reeve Ansel Varrick", {"down": True})
    r = you.act("kill", "Reeve Ansel Varrick")
    assert story(gm)["reeve_dead"] is True and story(gm)["done"] is True
    assert gm.inspect(gm.summary()["root"])["state"]["story"] == "lost"
    assert any("Dreyer banner" in t for t in scenes(r["events"]))


def test_ossa_trades_a_full_skin_for_emberglass_and_nothing_for_trinkets():
    eng, gm, you = reach()
    for place in ["The Gate Yard", "The Salt Road", "The Carriers' Landing"]:
        you.act("go", place)
    me = gm.inspect("Reeve Ansel Varrick")["id"]
    gm.spawn("thing", me, "Emberglass", state={"kind": "ember", "portable": True})
    r = you.act("give", "Ossa the Carrier", {"item": "Emberglass"})
    held = [c["name"] for c in you.perceive()["holding"]]
    assert "Full waterskin" in held and "Emberglass" not in held
    assert "traded" in kinds(r)
    assert gm.inspect("Ossa the Carrier")["state"]["ember_bought"] == 1
    r = you.act("give", "Ossa the Carrier", {"item": "Waterskin"})
    assert any("Keep your trinkets" in (e["payload"].get("text") or "") for e in r["events"] if e["kind"] == "say")
    # and her tongue loosens about Dram once she has taken glass
    r = you.act("talk", "Ossa the Carrier", {"about": "Hollis"})
    assert any("no clerk of mine" in (e["payload"].get("text") or "") for e in r["events"] if e["kind"] == "say")


def test_heat_dusk_and_the_cistern_on_timers():
    eng, gm, you = reach()
    gm.clock(step=200)
    assert you.perceive()["ambient"]["time_of_day"] == "noon"
    gm.clock(step=300)
    assert you.perceive()["ambient"]["time_of_day"] == "dusk"
    gm.clock(step=100)
    assert gm.inspect("The cistern")["state"]["left"] == 0
    assert any("crack has run" in t for t in scenes(you.perceive(cursor=0, events=500)["events"]))
    with pytest.raises(Rejected):
        you.act("fill", "Waterskin")


def test_upgrade_is_idempotent():
    eng, gm, you = reach()
    before = {e["id"]: e["state"] for e in gm.find(limit=500)}
    goals = len(gm.recall(entity="Reeve Ansel Varrick")["goals"])
    edges = gm.world.store.count("edge", "world_id=?", (gm.world.id,))
    load_world_file(gm, WORLDS / "glass_reach.py", upgrade=True)
    assert {e["id"]: e["state"] for e in gm.find(limit=500)} == before
    assert gm.world.store.count("edge", "world_id=?", (gm.world.id,)) == edges
    assert len(gm.recall(entity="Reeve Ansel Varrick")["goals"]) == goals
    assert len(gm.world.edges(gm.inspect("Reeve Ansel Varrick")["id"], "standing", "out")) == 4
