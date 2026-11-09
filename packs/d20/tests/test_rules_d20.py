"""The table rules of packs/d20, played in the Glass Reach: checks against a difficulty, opposed blows,
wards and the slow stroke, brace, yield, down and dead, water, the ring, factions that remember, the Thresher."""

from pathlib import Path

from embody.cli import load_world
import pytest

from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def reach(seat="Reeve Ansel Varrick"):
    eng = Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "glass-reach")
    you = eng.session("you")
    you.join("glass-reach", seat)
    return eng, gm, you


def kinds(r):
    return [e["kind"] for e in r["events"]]


def state(gm, name):
    return gm.inspect(name)["state"]


def strong(gm, name, body=25, blade=0):
    """A fighter who cannot miss: d20 + 25 beats any defence."""
    gm.patch(name, {"body": body, "skills": {"blade": blade}})


def weak(gm, name):
    gm.patch(name, {"body": 0, "skills": {}})


def test_check_rolls_against_a_difficulty_and_says_so():
    eng, gm, you = reach()
    r = you.act("check", params={"skill": "lore", "dc": 10})
    res = r["result"]
    assert res["mod"] == 4  # wits 3 + lore 1
    assert res["total"] == res["roll"] + res["mod"]
    assert res["success"] == (res["total"] >= 10)
    ev = [e for e in r["events"] if e["kind"] == "checked"][0]["payload"]
    assert ev["skill"] == "lore" and ev["dc"] == 10 and ev["margin"] == res["total"] - 10
    # no dc: twelve; an unknown skill rolls on wits
    r = you.act("check", params={"skill": "juggling"})
    assert r["result"]["dc"] == 12 and r["result"]["mod"] == 3


def test_attack_needs_a_standing_foe_here_and_not_yourself():
    eng, gm, you = reach()
    with pytest.raises(Rejected):
        you.act("attack", "Reeve Ansel Varrick")
    with pytest.raises(Rejected):
        you.act("attack", "Captain Ruhl")  # in the yard, not the hold
    you.act("go", "The Gate Yard")
    gm.patch("Captain Ruhl", {"down": True})
    with pytest.raises(Rejected) as ex:
        you.act("attack", "Captain Ruhl")
    assert "spare" in str(ex.value)


def test_a_ward_stops_the_fast_blow_and_the_slow_stroke_passes_it():
    eng, gm, you = reach("Captain Ruhl")
    gm.act_as("Reeve Ansel Varrick", "go", "The Gate Yard")
    strong(gm, "Captain Ruhl")
    r = you.act("attack", "Reeve Ansel Varrick")
    assert r["result"]["warded"] is True and "warded" in kinds(r)
    assert state(gm, "Reeve Ansel Varrick")["vigor"] == 6
    r = you.act("attack", "Reeve Ansel Varrick", {"slow": True})
    assert r["result"]["hit"] is True and r["result"]["dmg"] == 2
    assert state(gm, "Reeve Ansel Varrick")["vigor"] == 4
    # the ward off, the fast blow lands
    gm.act_as("Reeve Ansel Varrick", "toggle", "Belt ward")
    r = you.act("attack", "Reeve Ansel Varrick")
    assert r["result"]["hit"] is True


def test_blows_wound_then_down_and_the_down_can_only_yield_drink_or_crawl():
    eng, gm, you = reach("Captain Ruhl")
    gm.act_as("Reeve Ansel Varrick", "go", "The Gate Yard")
    gm.act_as("Reeve Ansel Varrick", "toggle", "Belt ward")
    strong(gm, "Captain Ruhl")
    r = you.act("attack", "Reeve Ansel Varrick")
    assert state(gm, "Reeve Ansel Varrick")["vigor"] == 4
    r = you.act("attack", "Reeve Ansel Varrick")
    assert "wounded" in kinds(r) and state(gm, "Reeve Ansel Varrick")["wounded"] is True
    r = you.act("attack", "Reeve Ansel Varrick")
    assert "downed" in kinds(r)
    reeve = state(gm, "Reeve Ansel Varrick")
    assert reeve["down"] is True and reeve["dead"] is False
    with pytest.raises(Rejected) as ex:
        gm.act_as("Reeve Ansel Varrick", "go", "Scar Gate, the Hold")
    assert "down" in str(ex.value).lower()
    r = gm.act_as("Reeve Ansel Varrick", "crawl", "Scar Gate, the Hold")
    assert gm.inspect("Reeve Ansel Varrick")["parent"] == gm.inspect("Scar Gate, the Hold")["id"]
    # a wounded fighter swings at -2
    weak(gm, "Captain Ruhl")
    gm.patch("Captain Ruhl", {"wounded": True})
    gm.act_as("Reeve Ansel Varrick", "crawl", "The Gate Yard")
    gm.patch("Reeve Ansel Varrick", {"down": False})
    r = you.act("attack", "Reeve Ansel Varrick")
    assert r["result"]["attack"] <= 20 - 2


def test_kill_needs_a_downed_foe_and_the_dead_do_nothing():
    eng, gm, you = reach("Captain Ruhl")
    gm.act_as("Reeve Ansel Varrick", "go", "The Gate Yard")
    with pytest.raises(Rejected):
        you.act("kill", "Reeve Ansel Varrick")
    gm.patch("Reeve Ansel Varrick", {"down": True, "vigor": 0})
    r = you.act("kill", "Reeve Ansel Varrick")
    assert "killed" in kinds(r) and state(gm, "Reeve Ansel Varrick")["dead"] is True
    with pytest.raises(Rejected):
        gm.act_as("Reeve Ansel Varrick", "yield", "Captain Ruhl")
    with pytest.raises(Rejected):
        you.act("attack", "Reeve Ansel Varrick")


def test_brace_adds_three_to_defence_until_your_next_deed():
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    r = you.act("brace")
    assert "braced" in kinds(r) and state(gm, "Reeve Ansel Varrick")["braced"] is True
    you.act("check", params={"skill": "lore"})
    assert state(gm, "Reeve Ansel Varrick")["braced"] is False
    you.act("brace")
    weak(gm, "Captain Ruhl")
    gm.patch("Captain Ruhl", {"body": 0})
    gm.act_as("Reeve Ansel Varrick", "toggle", "Belt ward")
    r = gm.act_as("Captain Ruhl", "attack", "Reeve Ansel Varrick")
    # defence = d20 + body 2 + blade 1 + brace 3 >= 7
    assert r["result"]["defence"] >= 7


def test_yield_ends_the_fight_and_striking_the_yielded_costs_standing_everywhere():
    eng, gm, you = reach("Captain Ruhl")
    gm.act_as("Reeve Ansel Varrick", "go", "The Gate Yard")
    r = gm.act_as("Reeve Ansel Varrick", "yield", "Captain Ruhl")
    assert "yielded" in kinds(r)
    assert state(gm, "Reeve Ansel Varrick")["yielded"] == gm.inspect("Captain Ruhl")["id"]
    varrick = [f for f in gm.find(type="faction") if f["name"] == "House Varrick"][0]["id"]
    gm.link(gm.inspect("Captain Ruhl")["id"], varrick, "standing", {"value": 3, "public": True})
    # striking the yielded is allowed, and everyone hears what it is
    r = you.act("attack", "Reeve Ansel Varrick")
    assert "dishonor" in kinds(r)
    gm.patch("Reeve Ansel Varrick", {"down": True})
    r = you.act("kill", "Reeve Ansel Varrick")
    assert "dishonor" in kinds(r)
    edges = gm.world.edges(gm.inspect("Captain Ruhl")["id"], "standing", "out")
    values = {e["target"]: e["data"]["value"] for e in edges}
    assert values[varrick] == 3 - 4
    assert all(v == -4 for t, v in values.items() if t != varrick)


def test_thirst_on_the_open_road_and_water_from_a_skin_or_a_source():
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    you.act("go", "The Salt Road")
    gm.patch("Reeve Ansel Varrick", {"water": 5})
    gm.clock(step=60)
    me = state(gm, "Reeve Ansel Varrick")
    assert me["water"] == 3 and me["thirsty"] is True  # the open road costs two a minute
    gm.clock(step=60)  # a periodic tick fires once per step, so two steps for two minutes
    gm.clock(step=60)
    me = state(gm, "Reeve Ansel Varrick")
    assert me["water"] == 0
    ev = [e["kind"] for e in you.perceive(cursor=0, events=500)["events"]]
    assert "parched" in ev and me["vigor"] == 5
    # a thirsty check is two worse
    r = you.act("check", params={"skill": "lore", "dc": 10})
    assert r["result"]["mod"] == 2
    r = you.act("drink", "Waterskin")
    me = state(gm, "Reeve Ansel Varrick")
    assert me["water"] == 4 and me["thirsty"] is False and state(gm, "Waterskin")["left"] == 1
    you.act("drink", "Waterskin")
    assert state(gm, "Waterskin")["left"] == 0
    with pytest.raises(Rejected):
        you.act("drink", "Waterskin")
    you.act("go", "The Gate Yard")
    you.act("go", "Scar Gate, the Hold")
    r = you.act("fill", "Waterskin")
    assert state(gm, "Waterskin")["left"] == 3 and state(gm, "The cistern")["left"] == 11
    # under the ridge the rock itself is the source: the Keth do not thirst there, and thirsty, Taan drinks from it
    gm.patch("Elder Taan", {"water": 2})
    gm.clock(step=60)
    assert state(gm, "Elder Taan")["water"] == 6


def test_the_ring_holds_during_a_duel():
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    gm.spawn("fighter", "The Gate Yard", "Bystander", state={"faction": "the Carriers"})
    r = you.act("challenge", "Captain Ruhl")
    assert "challenged" in kinds(r) and r["events"][-1]["payload"].get("ring") in (True, None)
    duels = gm.world.hyperedges(gm.inspect("Captain Ruhl")["id"], "duel")
    assert len(duels) == 1 and duels[0]["data"]["place"] == gm.inspect("The Gate Yard")["id"]
    with pytest.raises(Rejected) as ex:
        gm.act_as("Bystander", "attack", "Captain Ruhl")
    assert "ring holds" in str(ex.value)
    with pytest.raises(Rejected):
        you.act("attack", "Bystander")
    strong(gm, "Reeve Ansel Varrick")
    gm.patch("Captain Ruhl", {"vigor": 1})
    r = you.act("attack", "Captain Ruhl")
    assert "downed" in kinds(r) and "duel_over" in kinds(r)
    over = [e for e in r["events"] if e["kind"] == "duel_over"][0]["payload"]
    assert over["winner"] == gm.inspect("Reeve Ansel Varrick")["id"] and over["how"] == "downed"
    assert gm.world.hyperedges(gm.inspect("Captain Ruhl")["id"], "duel") == []


def test_fighters_strike_back_and_in_a_duel_they_strike_on_their_own():
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    gm.act_as("Reeve Ansel Varrick", "toggle", "Belt ward")
    weak(gm, "Reeve Ansel Varrick")
    strong(gm, "Captain Ruhl")
    you.act("attack", "Captain Ruhl")
    gm.clock(step=6)
    assert state(gm, "Reeve Ansel Varrick")["vigor"] < 6
    assert any(e["kind"] == "hit" and e["payload"]["by"] == gm.inspect("Captain Ruhl")["id"]
               for e in you.perceive(cursor=0, events=500)["events"])


def test_factions_remember_and_outlaw_and_their_fighters_act_on_it():
    eng, gm, you = reach("Sefa of the Keth")
    gm.patch("The Deepwell", {"hidden": False})
    gm.patch("Sefa of the Keth", {"water": 10})
    for place in ["The Glass Flats", "The Salt Road", "The Gate Yard"]:
        you.act("creep", place)
    varrick = [f for f in gm.find(type="faction") if f["name"] == "House Varrick"][0]
    me = gm.inspect("Sefa of the Keth")["id"]
    standing = lambda: {e["target"]: e["data"]["value"] for e in gm.world.edges(me, "standing", "out")}[varrick["id"]]
    assert standing() == -2
    strong(gm, "Sefa of the Keth")
    gm.patch("Captain Ruhl", {"vigor": 20, "max_vigor": 20, "body": 0, "skills": {}})
    r = you.act("attack", "Captain Ruhl")
    assert "hit" in kinds(r) and standing() == -4
    assert "outlawed" in kinds(r)
    assert gm.inspect("House Varrick")["state"]["hostile"].get(me) is True
    # Ruhl's tick now turns on her even without a duel; another Varrick fighter would too
    gm.spawn("fighter", "The Gate Yard", "Hold guard", state={"faction": "House Varrick", "body": 25})
    gm.patch("Sefa of the Keth", {"vigor": 30, "max_vigor": 30})
    gm.clock(step=6)
    assert state(gm, "Sefa of the Keth")["vigor"] < 30
    events = you.perceive(cursor=0, events=500)["events"]
    assert any(e["kind"] == "hit" and e["payload"]["by"] == gm.inspect("Hold guard")["id"] for e in events)


def test_threaten_and_parley_are_opposed_rolls_with_a_record():
    eng, gm, you = reach()
    gm.patch("Reeve Ansel Varrick", {"will": 30})
    r = you.act("threaten", "Dram Hollis")
    assert "cowed" in kinds(r) and state(gm, "Dram Hollis")["cowed_by"] == gm.inspect("Reeve Ansel Varrick")["id"]
    with pytest.raises(Rejected):
        you.act("parley", "Dram Hollis")
    r = you.act("parley", "Dram Hollis", {"offer": "leave the Reach tonight and keep your blade"})
    assert "agreed" in kinds(r)
    agreed = [e for e in r["events"] if e["kind"] == "agreed"][0]["payload"]
    assert agreed["offer"].startswith("leave the Reach")
    gm.patch("Reeve Ansel Varrick", {"will": -30})
    r = you.act("parley", "Dram Hollis", {"offer": "confess"})
    assert "refused" in kinds(r)


def test_search_the_downed_and_harvest_the_vein():
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    gm.patch("Captain Ruhl", {"down": True})
    r = you.act("search", "Captain Ruhl")
    assert "searched" in kinds(r)
    assert "Guard's blade" in [c["name"] for c in you.perceive()["holding"]]
    you.act("go", "The Salt Road")
    you.act("go", "The Glass Flats")
    r = you.act("harvest", "Red vein")
    assert r["duration"] == 20
    gm.clock(step=20)
    assert "Emberglass" in [c["name"] for c in you.perceive()["holding"]]
    assert state(gm, "Red vein")["ember"] == 2


def test_loud_steps_and_digging_wake_the_thresher_the_broken_step_does_not():
    eng, gm, you = reach()
    for place in ["The Gate Yard", "The Salt Road", "The Glass Flats"]:
        you.act("go", place)
    flats = state(gm, "The Glass Flats")
    assert flats["tremor"] == 1
    you.act("creep", "The Bone Field")
    you.act("creep", "The Glass Flats")
    assert state(gm, "The Glass Flats")["tremor"] == 1
    you.act("harvest", "Red vein")
    gm.clock(step=20)
    assert state(gm, "The Glass Flats")["tremor"] == 3
    assert state(gm, "The Glass Flats")["thresher_coming"] is True
    assert any(e["payload"]["tremor"] == 3 for e in gm.world.events(since=0, kinds=["tremor"], limit=5000))
    assert gm.inspect("The Thresher")["parent"] == gm.inspect("The Deep")["id"]
    gm.clock(step=30)
    assert gm.world.events(since=0, kinds=["thresher_surfaces"], limit=5000)
    assert any("sand" in e["payload"]["text"].lower() for e in gm.world.events(since=0, kinds=["scene"], limit=5000))
    me = gm.inspect("Reeve Ansel Varrick")
    assert me["parent"] in (gm.inspect("The Salt Road")["id"], gm.inspect("Red Ridge")["id"])
    assert state(gm, "The Glass Flats")["tremor"] == 0
    gm.clock(step=10)
    assert gm.inspect("The Thresher")["parent"] == gm.inspect("The Deep")["id"]

def test_a_fighter_on_his_own_keeps_out_of_a_ring_he_is_not_in():
    # Ruhl is a Varrick fighter; Dram struck the reeve, so Varrick outlawed him. Inside the reeve's duel Ruhl waits.
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    gm.spawn("fighter", "The Gate Yard", "Hired blade", state={"faction": "House Dreyer"})
    strong(gm, "Captain Ruhl")
    gm.patch("Hired blade", {"vigor": 1})
    varrick = gm.inspect("House Varrick")["id"]
    blade = gm.inspect("Hired blade")["id"]
    gm.patch(varrick, {"hostile": {blade: True}})
    gm.patch("Captain Ruhl", {"attacked_by": blade})
    you.act("challenge", "Hired blade")
    gm.clock(step=6)
    assert state(gm, "Hired blade")["down"] is False  # Ruhl's tick did not reach into the ring
    ev = gm.world.events(0, kinds=["hit", "missed"], limit=5000)
    assert not any(e["payload"]["by"] == gm.inspect("Captain Ruhl")["id"] for e in ev)
    # the ring over, the outlaw is fair game
    gm.unrelate(gm.world.hyperedges(blade, "duel")[0]["id"])
    gm.clock(step=6)
    assert state(gm, "Hired blade")["down"] is True


def test_crawl_is_for_the_down_and_self_verbs_are_not_done_to_others():
    eng, gm, you = reach()
    with pytest.raises(Rejected, match="on your feet"):
        you.act("crawl", "The Gate Yard")
    you.act("go", "The Gate Yard")
    aff = [(a["verb"], a["target"]) for a in you.perceive()["affordances"]]
    for verb in ["brace", "check"]:
        assert (verb, None) in aff
        assert not any(v == verb and t is not None for v, t in aff), verb
    assert all(gm.world.is_a(gm.inspect(t)["type"], "place") for v, t in aff if v == "crawl")
    assert not any(v == "attack" and t is None for v, t in aff)


def test_a_body_nobody_embodies_drinks_when_it_is_thirsty_and_water_is_in_reach():
    # Ruhl with a skin on his belt: thirsty, he drinks from it on his own. Ossa beside her casks never thirsts, and
    # thirsty beside them she drinks from them. The reeve, embodied, decides for himself.
    eng, gm, you = reach()
    gm.spawn("waterskin", "Captain Ruhl", "Ruhl's skin", state={"left": 2})
    gm.patch("Captain Ruhl", {"water": 4})
    gm.clock(step=60)
    gm.clock(step=60)
    ruhl = state(gm, "Captain Ruhl")
    assert ruhl["water"] >= 6 and ruhl["thirsty"] is False and state(gm, "Ruhl's skin")["left"] == 1
    ruhl_id = gm.inspect("Captain Ruhl")["id"]
    assert any(e["payload"]["by"] == ruhl_id for e in gm.world.events(0, kinds=["drank"], limit=5000))
    gm.patch("Ossa the Carrier", {"water": 2})
    gm.clock(step=60)
    assert state(gm, "Ossa the Carrier")["water"] == 6 and state(gm, "Water casks")["left"] == 5
    you.act("go", "The Gate Yard")
    you.act("go", "The Salt Road")
    gm.patch("Reeve Ansel Varrick", {"water": 3, "thirsty": True})
    gm.clock(step=60)
    assert state(gm, "Reeve Ansel Varrick")["water"] == 1 and state(gm, "Waterskin")["left"] == 2


def test_the_tremor_settles_after_two_quiet_minutes():
    eng, gm, you = reach()
    for place in ["The Gate Yard", "The Salt Road", "The Glass Flats"]:
        you.act("go", place)
    assert state(gm, "The Glass Flats")["tremor"] == 1
    gm.clock(step=60)
    assert state(gm, "The Glass Flats")["tremor"] == 1
    gm.clock(step=70)
    flats = state(gm, "The Glass Flats")
    assert flats["tremor"] == 0 and flats["settling"] is False
    assert any(e["payload"].get("why") == "quiet" for e in gm.world.events(0, kinds=["tremor"], limit=5000))
    # a second footfall before the first has settled keeps the count, and the quiet is counted from the last one
    you.act("go", "The Salt Road")
    you.act("go", "The Glass Flats")
    assert state(gm, "The Glass Flats")["tremor"] == 1
    gm.clock(step=60)
    you.act("go", "The Salt Road")
    you.act("go", "The Glass Flats")
    assert state(gm, "The Glass Flats")["tremor"] == 2
    gm.clock(step=100)
    assert state(gm, "The Glass Flats")["tremor"] == 2
    gm.clock(step=30)
    assert state(gm, "The Glass Flats")["tremor"] == 1


def test_walking_out_of_the_ring_ends_the_duel_and_your_own_side_marks_it():
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    weak(gm, "Captain Ruhl")
    you.act("challenge", "Captain Ruhl")
    me = gm.inspect("Reeve Ansel Varrick")["id"]
    assert len(gm.world.hyperedges(me, "duel")) == 1
    you.act("go", "Scar Gate, the Hold")
    # the ring's end is called in the yard you just left: the log has it, your eyes did not
    over = gm.world.events(0, kinds=["duel_over"], limit=5000)
    assert over and over[0]["payload"]["how"] == "left" and over[0]["payload"]["loser"] == me
    assert gm.world.hyperedges(me, "duel") == []
    st = [e for e in gm.world.events(0, kinds=["standing"], limit=5000) if e["target_id"] == me]
    assert st and st[-1]["payload"]["faction"] == "House Varrick" and st[-1]["payload"]["delta"] == -2
    # out of the ring, Ruhl is nobody's duelist: the yard may be struck into again
    gm.act_as("Reeve Ansel Varrick", "go", "The Gate Yard")
    gm.spawn("fighter", "The Gate Yard", "Hired blade", state={"faction": "House Dreyer"})
    gm.act_as("Hired blade", "attack", "Captain Ruhl")


def test_terms_agreed_in_the_ring_are_a_yield():
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    you.act("challenge", "Captain Ruhl")
    gm.patch("Reeve Ansel Varrick", {"will": 25})
    r = you.act("parley", "Captain Ruhl", {"offer": "stand down and keep your post"})
    assert r["result"]["agreed"] is True
    ks = kinds(r)
    assert "agreed" in ks and "yielded" in ks and "duel_over" in ks
    me = gm.inspect("Reeve Ansel Varrick")["id"]
    assert state(gm, "Captain Ruhl")["yielded"] == me
    assert gm.world.hyperedges(me, "duel") == []
    over = [e for e in r["events"] if e["kind"] == "duel_over"][0]["payload"]
    assert over["how"] == "yielded" and over["winner"] == me


def test_a_trade_and_a_return_are_not_gifts():
    eng, gm, you = reach()
    for place in ["The Gate Yard", "The Salt Road", "The Carriers' Landing"]:
        you.act("go", place)
    me = gm.inspect("Reeve Ansel Varrick")["id"]
    ossa = gm.inspect("Ossa the Carrier")["id"]
    gm.spawn("thing", me, "Emberglass", state={"kind": "ember", "portable": True})
    r = you.act("give", "Ossa the Carrier", {"item": "Emberglass"})
    assert "traded" in kinds(r) and not any(e["kind"] == "standing" and e["target"] == me for e in r["events"])
    # the ward she keeps is a gift
    r = you.act("give", "Ossa the Carrier", {"item": "Belt ward"})
    gifts = [e for e in r["events"] if e["kind"] == "standing" and e["target"] == me]
    assert gifts and gifts[0]["payload"]["delta"] == 1 and gifts[0]["payload"]["faction"] == "the Carriers"
    assert state(gm, "Belt ward")["given_by"] == me
    # handing it back moves nothing for her
    r = gm.act_as("Ossa the Carrier", "give", "Reeve Ansel Varrick", {"item": "Belt ward"})
    assert not any(e["kind"] == "standing" and e["target"] == ossa for e in r["events"])
    assert gm.inspect("Belt ward")["parent"] == me


def test_show_follow_stay_and_watch():
    eng, gm, you = reach()
    me = gm.inspect("Reeve Ansel Varrick")["id"]
    # show: Dram reads the writ's words off the page in your hand, and the page stays yours
    gm.spawn("letter", me, "Letter of credit", state={"text": "Pay the bearer twelve skins."})
    r = you.act("show", "Dram Hollis", {"item": "Letter of credit"})
    shown = [e for e in r["events"] if e["kind"] == "shown"][0]["payload"]
    assert shown["text"] == "Pay the bearer twelve skins." and r["result"]["text"] == shown["text"]
    assert gm.inspect("Letter of credit")["parent"] == me
    with pytest.raises(Rejected):
        you.act("show", "Dram Hollis", {"item": "The cistern"})
    # watch: who is in the yard, seen from the hold, for your eyes only
    r = you.act("watch", "The Gate Yard")
    assert r["result"]["who"] == ["Captain Ruhl"] and "Rack of practice blades" in r["result"]["things"]
    with pytest.raises(Rejected):
        you.act("watch", "The Glass Flats")
    assert not any(e["kind"] == "watched" for e in gm.perceive(from_entity="Captain Ruhl", cursor=0, events=500)["events"])
    # follow: Dram comes along when you go, and stays put after stay
    gm.act_as("Dram Hollis", "follow", "Reeve Ansel Varrick")
    r = you.act("go", "The Gate Yard")
    assert gm.inspect("Dram Hollis")["parent"] == gm.inspect("The Gate Yard")["id"]
    assert any(e["kind"] == "arrived" and e["payload"].get("following") == me for e in r["events"])
    gm.act_as("Dram Hollis", "stay")
    you.act("go", "Scar Gate, the Hold")
    assert gm.inspect("Dram Hollis")["parent"] == gm.inspect("The Gate Yard")["id"]
