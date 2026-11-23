"""The table rules of packs/d20, played in the engine's fixture world (tests/fixtures/worlds/outpost): checks against a
difficulty, opposed blows, wards and the slow stroke, brace, yield, down and dead, water, the ring, factions that
remember, the thresher."""

from pathlib import Path

from embody.cli import load_world
import pytest

from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
OUTPOST = REPO / "tests" / "fixtures" / "worlds" / "outpost"


def outpost(seat="Warden"):
    eng = Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, OUTPOST)
    you = eng.session("you")
    you.join("outpost", seat)
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
    eng, gm, you = outpost()
    r = you.act("check", params={"skill": "lore", "dc": 10})
    res = r["result"]
    assert res["mod"] == 4  # wits 3 + lore 1
    assert res["total"] == res["roll"] + res["mod"]
    assert res["success"] == (res["total"] >= 10)
    ev = [e for e in r["events"] if e["kind"] == "checked"][0]["payload"]
    assert ev["skill"] == "lore" and ev["dc"] == 10 and ev["margin"] == res["total"] - 10
    assert "untrained" not in res
    # no dc: twelve; an unknown skill rolls on wits, untrained, and says so
    r = you.act("check", params={"skill": "juggling"})
    assert r["result"]["dc"] == 12 and r["result"]["mod"] == 3
    assert r["result"]["untrained"] is True and "no skill 'juggling'" in r["result"]["note"]
    assert "lore" in r["result"]["note"] and [e for e in r["events"] if e["kind"] == "checked"][0]["payload"]["untrained"]
    # a skill the body has of its own is trained, whatever the pack's list says
    gm.patch("Warden", {"skills": {"lore": 1, "juggling": 2}, "tried": None})
    r = you.act("check", params={"skill": "juggling"})
    assert r["result"]["mod"] == 5 and "untrained" not in r["result"]


def test_a_check_is_not_rolled_again_and_again_in_one_place():
    # a playtest rolled check until it landed and found everything hidden at any dc: one try a skill, a place, a world hour
    eng, gm, you = outpost()
    you.act("check", params={"skill": "search", "dc": 20})
    with pytest.raises(Rejected) as why:
        you.act("check", params={"skill": "search", "dc": 20})
    assert "tried search here" in why.value.reason and "world minutes" in why.value.reason
    you.act("check", params={"skill": "lore"})  # another skill is another try
    tried = state(gm, "Warden")["tried"]
    assert len(tried) == 2 and all("|" in k for k in tried)
    gm.patch(gm.world.root_id, {"check_again_after": 0})  # a world that wants rerolls says so on its root
    you.act("check", params={"skill": "search", "dc": 20})


def test_an_aid_helps_the_next_matching_check_once():
    # a familiar's `point` leaves {bonus, skill, place, by, why, until} on the body; the next check it fits uses it up
    eng, gm, you = outpost()
    me = gm.inspect("Warden")
    here = me["parent"]
    gm.patch("Warden", {"aid": [
        {"bonus": 5, "skill": "lore", "place": "nowhere", "by": "x", "why": "elsewhere"},
        {"bonus": 9, "skill": "lore", "place": here, "by": "x", "why": "too late", "until": -1},
        {"bonus": 2, "skill": "lore", "place": here, "by": "wisp", "why": "the wisp points under the bench"},
        {"bonus": 3, "skill": "climb", "by": "x", "why": "another skill"}]})
    r = you.act("check", params={"skill": "lore", "dc": 10})
    assert r["result"]["mod"] == 4 + 2 and r["result"]["aid"]["by"] == "wisp"
    ev = [e for e in r["events"] if e["kind"] == "checked"][0]["payload"]
    assert ev["aid"]["why"] == "the wisp points under the bench"
    left = state(gm, "Warden")["aid"]
    assert [a["why"] for a in left] == ["elsewhere", "another skill"]  # used up, and the lapsed one fell away
    gm.patch("Warden", {"tried": None})
    r = you.act("check", params={"skill": "lore", "dc": 10})
    assert r["result"]["mod"] == 4 and "aid" not in r["result"]


def test_attack_needs_a_standing_foe_here_and_not_yourself():
    eng, gm, you = outpost()
    with pytest.raises(Rejected):
        you.act("attack", "Warden")
    with pytest.raises(Rejected):
        you.act("attack", "Captain")  # in the yard, not the hold
    you.act("go", "The Yard")
    gm.patch("Captain", {"down": True})
    with pytest.raises(Rejected) as ex:
        you.act("attack", "Captain")
    assert "spare" in str(ex.value)


def test_a_ward_stops_the_fast_blow_and_the_slow_stroke_passes_it():
    eng, gm, you = outpost("Captain")
    gm.act_as("Warden", "go", "The Yard")
    strong(gm, "Captain")
    r = you.act("attack", "Warden")
    assert r["result"]["warded"] is True and "warded" in kinds(r)
    assert state(gm, "Warden")["hp"] == 6
    r = you.act("attack", "Warden", {"slow": True})
    assert r["result"]["hit"] is True and r["result"]["dmg"] == 2
    assert state(gm, "Warden")["hp"] == 4
    # the ward off, the fast blow lands
    gm.act_as("Warden", "toggle", "Belt ward")
    r = you.act("attack", "Warden")
    assert r["result"]["hit"] is True


def test_blows_wound_then_down_and_the_down_can_only_yield_drink_or_crawl():
    eng, gm, you = outpost("Captain")
    gm.act_as("Warden", "go", "The Yard")
    gm.act_as("Warden", "toggle", "Belt ward")
    strong(gm, "Captain")
    r = you.act("attack", "Warden")
    assert state(gm, "Warden")["hp"] == 4
    r = you.act("attack", "Warden")
    assert "wounded" in kinds(r) and state(gm, "Warden")["wounded"] is True
    r = you.act("attack", "Warden")
    assert "downed" in kinds(r)
    warden = state(gm, "Warden")
    assert warden["down"] is True and warden["dead"] is False
    with pytest.raises(Rejected) as ex:
        gm.act_as("Warden", "go", "The Keep")
    assert "down" in str(ex.value).lower()
    r = gm.act_as("Warden", "crawl", "The Keep")
    assert gm.inspect("Warden")["parent"] == gm.inspect("The Keep")["id"]
    # a wounded fighter swings at -2
    weak(gm, "Captain")
    gm.patch("Captain", {"wounded": True})
    gm.act_as("Warden", "crawl", "The Yard")
    gm.patch("Warden", {"down": False})
    r = you.act("attack", "Warden")
    assert r["result"]["attack"] <= 20 - 2


def test_kill_needs_a_downed_foe_and_the_dead_do_nothing():
    eng, gm, you = outpost("Captain")
    gm.act_as("Warden", "go", "The Yard")
    with pytest.raises(Rejected):
        you.act("kill", "Warden")
    gm.patch("Warden", {"down": True, "hp": 0})
    r = you.act("kill", "Warden")
    assert "killed" in kinds(r) and state(gm, "Warden")["dead"] is True
    with pytest.raises(Rejected):
        gm.act_as("Warden", "yield", "Captain")
    with pytest.raises(Rejected):
        you.act("attack", "Warden")


def test_brace_adds_three_to_defence_until_your_next_deed():
    eng, gm, you = outpost()
    you.act("go", "The Yard")
    r = you.act("brace")
    assert "braced" in kinds(r) and state(gm, "Warden")["braced"] is True
    you.act("check", params={"skill": "lore"})
    assert state(gm, "Warden")["braced"] is False
    gm.act_as("Warden", "toggle", "Belt ward")  # a deed of his own; the brace comes after it
    you.act("brace")
    weak(gm, "Captain")
    gm.patch("Captain", {"body": 0})
    r = gm.act_as("Captain", "attack", "Warden")
    # defence = d20 + body 2 + blade 1 + brace 3 >= 7
    assert r["result"]["defence"] >= 7


def test_yield_ends_the_fight_and_striking_the_yielded_costs_standing_everywhere():
    eng, gm, you = outpost("Captain")
    gm.act_as("Warden", "go", "The Yard")
    r = gm.act_as("Warden", "yield", "Captain")
    assert "yielded" in kinds(r)
    assert state(gm, "Warden")["yielded"] == gm.inspect("Captain")["id"]
    garrison = [f for f in gm.find(type="faction") if f["name"] == "the Garrison"][0]["id"]
    gm.link(gm.inspect("Captain")["id"], garrison, "standing", {"value": 3, "public": True})
    # striking the yielded is allowed, and everyone hears what it is
    r = you.act("attack", "Warden")
    assert "dishonor" in kinds(r)
    gm.patch("Warden", {"down": True})
    r = you.act("kill", "Warden")
    assert "dishonor" in kinds(r)
    edges = gm.world.edges(gm.inspect("Captain")["id"], "standing", "out")
    values = {e["target"]: e["data"]["value"] for e in edges}
    assert values[garrison] == 3 - 4
    assert all(v == -4 for t, v in values.items() if t != garrison)


def test_thirst_on_the_open_road_and_water_from_a_skin_or_a_source():
    eng, gm, you = outpost()
    you.act("go", "The Yard")
    you.act("go", "The Road")
    gm.patch("Warden", {"water": 5})
    gm.clock(step=60)
    me = state(gm, "Warden")
    assert me["water"] == 3 and me["thirsty"] is True  # the open road costs two a minute
    gm.clock(step=60)  # a periodic tick fires once per step, so two steps for two minutes
    gm.clock(step=60)
    me = state(gm, "Warden")
    assert me["water"] == 0
    ev = [e["kind"] for e in you.perceive(cursor=0, events=500)["events"]]
    assert "parched" in ev and me["hp"] == 5
    # a thirsty check is two worse
    r = you.act("check", params={"skill": "lore", "dc": 10})
    assert r["result"]["mod"] == 2
    r = you.act("drink", "Waterskin")
    me = state(gm, "Warden")
    assert me["water"] == 4 and me["thirsty"] is False and state(gm, "Waterskin")["left"] == 1
    you.act("drink", "Waterskin")
    assert state(gm, "Waterskin")["left"] == 0
    with pytest.raises(Rejected):
        you.act("drink", "Waterskin")
    you.act("go", "The Yard")
    you.act("go", "The Keep")
    r = you.act("fill", "Waterskin")
    assert state(gm, "Waterskin")["left"] == 3 and state(gm, "The cistern")["left"] == 11
    with pytest.raises(Rejected) as ex:  # a full skin takes no draw
        you.act("fill", "Waterskin")
    assert "already full" in str(ex.value) and state(gm, "The cistern")["left"] == 11
    with pytest.raises(Rejected) as ex:  # fill on the source itself points at the skin in hand
        you.act("fill", "The cistern")
    assert "fill Waterskin here, or drink from The cistern" in str(ex.value)
    gm.patch("Warden", {"water": 10})
    with pytest.raises(Rejected) as ex:  # a full body takes no draw either: the water is not poured away
        you.act("drink", "The cistern")
    assert "another drop" in str(ex.value) and state(gm, "The cistern")["left"] == 11
    # the spring under the ridge is itself the source: the hill folk do not thirst there, and thirsty, the Elder drinks from it
    gm.patch("Elder", {"water": 2})
    gm.clock(step=60)
    assert state(gm, "Elder")["water"] == 6


def test_the_ring_holds_during_a_duel():
    eng, gm, you = outpost()
    you.act("go", "The Yard")
    gm.spawn("fighter", "The Yard", "Bystander", state={"faction": "the Traders"})
    r = you.act("challenge", "Captain")
    assert "challenged" in kinds(r) and r["events"][-1]["payload"].get("ring") in (True, None)
    duels = gm.world.hyperedges(gm.inspect("Captain")["id"], "duel")
    assert len(duels) == 1 and duels[0]["data"]["place"] == gm.inspect("The Yard")["id"]
    with pytest.raises(Rejected) as ex:
        gm.act_as("Bystander", "attack", "Captain")
    assert "ring holds" in str(ex.value)
    with pytest.raises(Rejected):
        you.act("attack", "Bystander")
    strong(gm, "Warden", body=40)  # a defence roll may reach 27: d20 + 40 beats it whatever the seed
    gm.patch("Captain", {"hp": 1})
    r = you.act("attack", "Captain")
    assert "downed" in kinds(r) and "duel_over" in kinds(r)
    over = [e for e in r["events"] if e["kind"] == "duel_over"][0]["payload"]
    assert over["winner"] == gm.inspect("Warden")["id"] and over["how"] == "downed"
    assert gm.world.hyperedges(gm.inspect("Captain")["id"], "duel") == []


def test_fighters_strike_back_and_in_a_duel_they_strike_on_their_own():
    eng, gm, you = outpost()
    you.act("go", "The Yard")
    gm.act_as("Warden", "toggle", "Belt ward")
    weak(gm, "Warden")
    strong(gm, "Captain")
    you.act("attack", "Captain")
    gm.clock(step=6)
    assert state(gm, "Warden")["hp"] < 6
    assert any(e["kind"] == "hit" and e["payload"]["by"] == gm.inspect("Captain")["id"]
               for e in you.perceive(cursor=0, events=500)["events"])


def test_factions_remember_and_outlaw_and_their_fighters_act_on_it():
    eng, gm, you = outpost("Scout")
    gm.patch("The Spring", {"hidden": False})
    gm.patch("Scout", {"water": 10})
    for place in ["The Flats", "The Road", "The Yard"]:
        you.act("creep", place)
    garrison = [f for f in gm.find(type="faction") if f["name"] == "the Garrison"][0]
    me = gm.inspect("Scout")["id"]
    standing = lambda: {e["target"]: e["data"]["value"] for e in gm.world.edges(me, "standing", "out")}[garrison["id"]]
    assert standing() == -2
    strong(gm, "Scout")
    gm.patch("Captain", {"hp": 20, "max_hp": 20, "body": 0, "skills": {}})
    r = you.act("attack", "Captain")
    assert "hit" in kinds(r) and standing() == -4
    assert "outlawed" in kinds(r)
    assert gm.inspect("the Garrison")["state"]["hostile"].get(me) is True
    # the Captain's tick now turns on her even without a duel; another Garrison fighter would too
    gm.spawn("fighter", "The Yard", "Keep guard", state={"faction": "the Garrison", "body": 25})
    gm.patch("Scout", {"hp": 30, "max_hp": 30})
    for _ in range(5):  # a few ticks: the rolls are seeded by the log, a miss or two is not a failure
        gm.clock(step=6)
        if state(gm, "Scout")["hp"] < 30:
            break
    assert state(gm, "Scout")["hp"] < 30
    events = you.perceive(cursor=0, events=500)["events"]
    assert any(e["kind"] == "hit" and e["payload"]["by"] == gm.inspect("Keep guard")["id"] for e in events)


def test_threaten_and_parley_are_opposed_rolls_with_a_record():
    eng, gm, you = outpost()
    gm.patch("Warden", {"will": 30})
    r = you.act("threaten", "Stranger")
    assert "cowed" in kinds(r) and state(gm, "Stranger")["cowed_by"] == gm.inspect("Warden")["id"]
    with pytest.raises(Rejected):
        you.act("parley", "Stranger")
    r = you.act("parley", "Stranger", {"offer": "leave tonight and keep your blade"})
    assert "agreed" in kinds(r)
    agreed = [e for e in r["events"] if e["kind"] == "agreed"][0]["payload"]
    assert agreed["offer"].startswith("leave tonight")
    gm.patch("Warden", {"will": -30})
    r = you.act("parley", "Stranger", {"offer": "confess"})
    assert "refused" in kinds(r)


def test_search_the_downed_and_harvest_the_vein():
    eng, gm, you = outpost()
    you.act("go", "The Yard")
    gm.patch("Captain", {"down": True})
    r = you.act("search", "Captain")
    assert "searched" in kinds(r)
    assert "Captain's blade" in [c["name"] for c in you.perceive()["holding"]]
    you.act("go", "The Road")
    you.act("go", "The Flats")
    r = you.act("harvest", "Ore vein")
    assert r["duration"] == 20
    gm.clock(step=20)
    assert "Ore" in [c["name"] for c in you.perceive()["holding"]]
    assert state(gm, "Ore vein")["ember"] == 2


def bulk_of(gm, name):
    # as the engine counts it: `bulk` when set (0 weighs nothing: a slate, a leaf), else 2 with a capacity, else 1
    return sum(int(c["state"]["bulk"] if c["state"].get("bulk") is not None else (2 if c["state"].get("capacity") else 1))
               for c in gm.find(parent=gm.inspect(name)["id"], limit=100))


def test_a_search_takes_only_what_your_hands_can_carry():
    # the same bulk count take uses: what does not fit stays on the body, and the searcher hears what was left
    eng, gm, you = outpost()
    you.act("go", "The Yard")
    gm.patch("Captain", {"down": True})
    gm.spawn("thing", "Captain", "Iron strongbox", state={"portable": True, "bulk": 4})
    gm.spawn("thing", "Captain", "Brass button", state={"portable": True})
    before = bulk_of(gm, "Warden")
    gm.patch("Warden", {"carry": before + 3})
    r = you.act("search", "Captain")
    ev = [e for e in r["events"] if e["kind"] == "searched"][0]["payload"]
    on_cap = [c["name"] for c in gm.find(parent=gm.inspect("Captain")["id"], limit=100)]
    assert "Iron strongbox" in on_cap and gm.inspect("Iron strongbox")["id"] in ev["left"]
    assert "Brass button" not in on_cap and ev["found"]
    assert bulk_of(gm, "Warden") <= before + 3
    assert "Iron strongbox" in str(r) and "stay on Captain" in str(r)
    # hands already full: nothing left on him fits, so the search is refused before it starts
    gm.patch("Warden", {"carry": bulk_of(gm, "Warden")})
    with pytest.raises(Rejected) as ex:
        you.act("search", "Captain")
    assert "hands are full" in str(ex.value)


def test_loud_steps_and_digging_wake_the_thresher_the_quiet_step_does_not():
    eng, gm, you = outpost()
    for place in ["The Yard", "The Road", "The Flats"]:
        you.act("go", place)
    flats = state(gm, "The Flats")
    assert flats["tremor"] == 1
    you.act("creep", "The Dunes")
    you.act("creep", "The Flats")
    assert state(gm, "The Flats")["tremor"] == 1
    you.act("harvest", "Ore vein")
    gm.clock(step=20)
    assert state(gm, "The Flats")["tremor"] == 3
    assert state(gm, "The Flats")["thresher_coming"] is True
    assert any(e["payload"]["tremor"] == 3 for e in gm.world.events(since=0, kinds=["tremor"], limit=5000))
    assert gm.inspect("The Burrower")["parent"] == gm.inspect("The Deep")["id"]
    gm.clock(step=30)
    assert gm.world.events(since=0, kinds=["thresher_surfaces"], limit=5000)
    assert any("sand" in e["payload"]["text"].lower() for e in gm.world.events(since=0, kinds=["scene"], limit=5000))
    me = gm.inspect("Warden")
    assert me["parent"] in (gm.inspect("The Road")["id"], gm.inspect("The Ridge")["id"])  # any firm ground off the Flats
    assert state(gm, "The Flats")["tremor"] == 0
    gm.clock(step=10)
    assert gm.inspect("The Burrower")["parent"] == gm.inspect("The Deep")["id"]

def test_a_grudge_holds_while_the_foe_stands_here_and_ends_when_they_walk_away_yield_or_go_quiet():
    eng, gm, you = outpost()
    you.act("go", "The Yard")
    gm.act_as("Warden", "toggle", "Belt ward")
    gm.spawn("fighter", "The Yard", "Brawler", state={"hp": 40, "max_hp": 40})
    gm.patch("Warden", {"hp": 40, "max_hp": 40})
    strong(gm, "Warden")
    me = gm.inspect("Warden")["id"]
    brawler = gm.inspect("Brawler")["id"]

    def blows():
        return len([e for e in gm.world.events(0, kinds=["hit", "missed"], limit=5000) if e["payload"]["by"] == brawler])

    you.act("attack", "Brawler")
    assert state(gm, "Brawler")["attacked_by"] == me and state(gm, "Brawler")["attacked_at"] is not None
    gm.clock(step=6)
    assert blows() == 1  # he strikes back
    # walk away: the grudge is over at his next tick, and coming back starts nothing
    you.act("go", "The Keep")
    gm.clock(step=6)
    assert state(gm, "Brawler").get("attacked_by") is None
    you.act("go", "The Yard")
    gm.clock(step=60)
    gm.clock(step=60)
    assert blows() == 1
    # a yield ends it
    you.act("attack", "Brawler")
    you.act("yield", "Brawler")
    gm.clock(step=60)
    assert state(gm, "Brawler").get("attacked_by") is None and blows() == 1
    # and so does a world hour with no blow from the foe (root grudge_for)
    gm.patch("Warden", {"yielded": None})
    you.act("attack", "Brawler")
    gm.patch("Brawler", {"attacked_at": gm.summary()["t"] - 3601})
    gm.clock(step=60)
    assert state(gm, "Brawler").get("attacked_by") is None and blows() == 1


def test_a_fighter_on_his_own_keeps_out_of_a_ring_he_is_not_in():
    # the Captain is a Garrison fighter; the blade is outlawed by the Garrison. Inside the warden's duel the Captain waits.
    eng, gm, you = outpost()
    you.act("go", "The Yard")
    gm.spawn("fighter", "The Yard", "Hired blade", state={"faction": "the Rivals"})
    strong(gm, "Captain")
    gm.patch("Hired blade", {"hp": 1})
    garrison = gm.inspect("the Garrison")["id"]
    blade = gm.inspect("Hired blade")["id"]
    gm.patch(garrison, {"hostile": {blade: True}})
    gm.patch("Captain", {"attacked_by": blade})
    you.act("challenge", "Hired blade")
    gm.clock(step=6)
    assert state(gm, "Hired blade")["down"] is False  # the Captain's tick did not reach into the ring
    ev = gm.world.events(0, kinds=["hit", "missed"], limit=5000)
    assert not any(e["payload"]["by"] == gm.inspect("Captain")["id"] for e in ev)
    # the ring over, the outlaw is fair game
    gm.unrelate(gm.world.hyperedges(blade, "duel")[0]["id"])
    gm.clock(step=6)
    assert state(gm, "Hired blade")["down"] is True


def test_crawl_is_for_the_down_and_self_verbs_are_not_done_to_others():
    eng, gm, you = outpost()
    with pytest.raises(Rejected, match="on your feet"):
        you.act("crawl", "The Yard")
    you.act("go", "The Yard")
    aff = [(a["verb"], a["target"]) for a in you.perceive()["affordances"]]
    for verb in ["brace", "check"]:
        assert (verb, None) in aff
        assert not any(v == verb and t is not None for v, t in aff), verb
    assert all(gm.world.is_a(gm.inspect(t)["type"], "place") for v, t in aff if v == "crawl")
    assert not any(v == "attack" and t is None for v, t in aff)


def test_a_body_nobody_embodies_drinks_when_it_is_thirsty_and_water_is_in_outpost():
    # the Captain with a skin on his belt: thirsty, he drinks from it on his own. The Trader beside her casks never
    # thirsts, and thirsty beside them she drinks from them. The warden, embodied, decides for himself.
    eng, gm, you = outpost()
    gm.spawn("waterskin", "Captain", "Captain's skin", state={"left": 2})
    gm.patch("Captain", {"water": 4})
    gm.clock(step=60)
    gm.clock(step=60)
    cap = state(gm, "Captain")
    assert cap["water"] >= 6 and cap["thirsty"] is False and state(gm, "Captain's skin")["left"] == 1
    cap_id = gm.inspect("Captain")["id"]
    assert any(e["payload"]["by"] == cap_id for e in gm.world.events(0, kinds=["drank"], limit=5000))
    gm.patch("Trader", {"water": 2})
    gm.clock(step=60)
    assert state(gm, "Trader")["water"] == 6 and state(gm, "Water casks")["left"] == 5
    you.act("go", "The Yard")
    you.act("go", "The Road")
    gm.patch("Warden", {"water": 3, "thirsty": True})
    gm.clock(step=60)
    assert state(gm, "Warden")["water"] == 1 and state(gm, "Waterskin")["left"] == 2


def test_a_thirsty_body_two_steps_from_water_walks_there_drinks_its_fill_and_walks_back():
    # a playtest case: left on the Flats with nothing to drink, two steps from the Oasis. A step a look toward
    # the nearest water it knows, a draw a look until near full, then a step a look back to where it was posted.
    eng, gm, you = outpost()
    gm.spawn("person", "The Flats", "Walker", state={"faction": "the Garrison", "water": 2, "max_water": 10})
    trail = []
    for _ in range(6):
        gm.clock(step=60)
        e = gm.inspect("Walker")
        trail.append((gm.world.get(e["parent"])["name"], e["state"]["water"]))
    names = [n for n, _ in trail]
    assert names[:2] == ["The Road", "The Oasis"]
    assert max(w for n, w in trail if n == "The Oasis") >= 7  # drank its fill before the road back
    assert names[-1] == "The Flats" and not state(gm, "Walker").get("post")
    assert all(not gm.world.get(gm.inspect(n)["id"])["state"].get("hidden") for n in names)



def test_a_thirsty_body_aboard_a_vehicle_steps_down_for_water():
    # a playtest case: two hands aboard a hauler drank its casks dry and stayed aboard to die, because the walk
    # to water followed ways only. A vehicle's way out is alight; anything else says so with `way_out`.
    eng, gm, you = outpost()
    cart = gm.spawn("vehicle", "The Flats", "Dry Cart")["id"]
    gm.spawn("person", cart, "Rider", state={"faction": "the Garrison", "water": 2, "max_water": 10})
    pit = gm.spawn("place", "The Flats", "Sealed Pit", state={"way_out": False})["id"]
    gm.spawn("person", pit, "Prisoner Two", state={"faction": "the Garrison", "water": 2, "max_water": 10})
    trail = []
    for _ in range(3):
        gm.clock(step=60)
        trail.append(gm.world.get(gm.inspect("Rider")["parent"])["name"])
    assert trail[:3] == ["The Flats", "The Road", "The Oasis"]
    assert gm.inspect("Prisoner Two")["parent"] == pit  # a place that says it has no way out keeps its own

def test_the_tremor_settles_after_two_quiet_minutes():
    eng, gm, you = outpost()
    for place in ["The Yard", "The Road", "The Flats"]:
        you.act("go", place)
    assert state(gm, "The Flats")["tremor"] == 1
    gm.clock(step=60)
    assert state(gm, "The Flats")["tremor"] == 1
    gm.clock(step=70)
    flats = state(gm, "The Flats")
    assert flats["tremor"] == 0 and flats["settling"] is False
    assert any(e["payload"].get("why") == "quiet" for e in gm.world.events(0, kinds=["tremor"], limit=5000))
    # a second footfall before the first has settled keeps the count, and the quiet is counted from the last one
    you.act("go", "The Road")
    you.act("go", "The Flats")
    assert state(gm, "The Flats")["tremor"] == 1
    gm.clock(step=60)
    you.act("go", "The Road")
    you.act("go", "The Flats")
    assert state(gm, "The Flats")["tremor"] == 2
    gm.clock(step=100)
    assert state(gm, "The Flats")["tremor"] == 2
    gm.clock(step=30)
    assert state(gm, "The Flats")["tremor"] == 1


def test_walking_out_of_the_ring_ends_the_duel_and_your_own_side_marks_it():
    eng, gm, you = outpost()
    you.act("go", "The Yard")
    weak(gm, "Captain")
    you.act("challenge", "Captain")
    me = gm.inspect("Warden")["id"]
    assert len(gm.world.hyperedges(me, "duel")) == 1
    you.act("go", "The Keep")
    # the ring's end is called in the yard you just left: the log has it, your eyes did not
    over = gm.world.events(0, kinds=["duel_over"], limit=5000)
    assert over and over[0]["payload"]["how"] == "left" and over[0]["payload"]["loser"] == me
    assert gm.world.hyperedges(me, "duel") == []
    st = [e for e in gm.world.events(0, kinds=["standing"], limit=5000) if e["target_id"] == me]
    assert st and st[-1]["payload"]["faction"] == "the Garrison" and st[-1]["payload"]["delta"] == -2
    # out of the ring, the Captain is nobody's duelist: the yard may be struck into again
    gm.act_as("Warden", "go", "The Yard")
    gm.spawn("fighter", "The Yard", "Hired blade", state={"faction": "the Rivals"})
    gm.act_as("Hired blade", "attack", "Captain")


def test_terms_agreed_in_the_ring_are_a_yield():
    eng, gm, you = outpost()
    you.act("go", "The Yard")
    you.act("challenge", "Captain")
    gm.patch("Warden", {"will": 25})
    r = you.act("parley", "Captain", {"offer": "stand down and keep your post"})
    assert r["result"]["agreed"] is True
    ks = kinds(r)
    assert "agreed" in ks and "yielded" in ks and "duel_over" in ks
    me = gm.inspect("Warden")["id"]
    assert state(gm, "Captain")["yielded"] == me
    assert gm.world.hyperedges(me, "duel") == []
    over = [e for e in r["events"] if e["kind"] == "duel_over"][0]["payload"]
    assert over["how"] == "yielded" and over["winner"] == me


def test_terms_and_gifts_buy_standing_once_a_pair_a_world_day():
    # a playtest parleyed the same member over and over to +29: the same deed with the same member counts once a day
    eng, gm, you = outpost()
    for place in ["The Yard", "The Road", "The Market"]:
        you.act("go", place)
    me = gm.inspect("Warden")["id"]
    gm.patch("Warden", {"will": 30})
    gained = []
    for offer in ["safe passage", "water at dusk", "a share of the ember"]:
        r = you.act("parley", "Trader", {"offer": offer})
        assert "agreed" in kinds(r)
        gained += [e["payload"]["delta"] for e in r["events"] if e["kind"] == "standing" and e["target"] == me]
    assert gained == [2]
    for i in range(2):
        gm.spawn("thing", me, f"Ribbon {i}", state={"portable": True})
        r = you.act("give", "Trader", {"item": f"Ribbon {i}"})
        gained += [e["payload"]["delta"] for e in r["events"] if e["kind"] == "standing" and e["target"] == me]
    assert gained == [2, 1]
    assert "courted" in gm.world.get(gm.inspect("the Traders")["id"])["state"]["secret"]  # hidden from cards


def test_a_trade_and_a_return_are_not_gifts():
    eng, gm, you = outpost()
    for place in ["The Yard", "The Road", "The Market"]:
        you.act("go", place)
    me = gm.inspect("Warden")["id"]
    trader = gm.inspect("Trader")["id"]
    gm.spawn("thing", me, "Emberglass", state={"kind": "ember", "portable": True})
    r = you.act("give", "Trader", {"item": "Emberglass"})
    assert "traded" in kinds(r) and not any(e["kind"] == "standing" and e["target"] == me for e in r["events"])
    # the ward she keeps is a gift
    r = you.act("give", "Trader", {"item": "Belt ward"})
    gifts = [e for e in r["events"] if e["kind"] == "standing" and e["target"] == me]
    assert gifts and gifts[0]["payload"]["delta"] == 1 and gifts[0]["payload"]["faction"] == "the Traders"
    assert state(gm, "Belt ward")["given_by"] == me
    # handing it back moves nothing for her
    r = gm.act_as("Trader", "give", "Warden", {"item": "Belt ward"})
    assert not any(e["kind"] == "standing" and e["target"] == trader for e in r["events"])
    assert gm.inspect("Belt ward")["parent"] == me


def test_show_follow_stay_and_watch():
    eng, gm, you = outpost()
    me = gm.inspect("Warden")["id"]
    # show: the Stranger reads the words off the page in your hand, and the page stays yours
    gm.spawn("letter", me, "Letter of credit", state={"text": "Pay the bearer twelve skins."})
    r = you.act("show", "Stranger", {"item": "Letter of credit"})
    shown = [e for e in r["events"] if e["kind"] == "shown"][0]["payload"]
    assert shown["text"] == "Pay the bearer twelve skins." and r["result"]["text"] == shown["text"]
    assert gm.inspect("Letter of credit")["parent"] == me
    with pytest.raises(Rejected):
        you.act("show", "Stranger", {"item": "The cistern"})
    # watch: who is in the yard, seen from the hold, for your eyes only
    r = you.act("watch", "The Yard")
    assert r["result"]["who"] == ["Captain"] and "Rack of practice blades" in r["result"]["things"]
    with pytest.raises(Rejected):
        you.act("watch", "The Flats")
    assert not any(e["kind"] == "watched" for e in gm.perceive(from_entity="Captain", cursor=0, events=500)["events"])
    # follow: the Stranger comes along when you go, and stays put after stay
    gm.act_as("Stranger", "follow", "Warden")
    r = you.act("go", "The Yard")
    assert gm.inspect("Stranger")["parent"] == gm.inspect("The Yard")["id"]
    assert any(e["kind"] == "arrived" and e["payload"].get("following") == me for e in r["events"])
    gm.act_as("Stranger", "stay")
    you.act("go", "The Keep")
    assert gm.inspect("Stranger")["parent"] == gm.inspect("The Yard")["id"]


def test_thirst_puts_a_body_down_and_no_further_and_water_brings_it_up():
    # the Lookout on the ridge, dry: hp falls to the floor and stays there; a skin put in his hand gets him up
    eng, gm, you = outpost()
    gm.patch("Lookout", {"water": 0, "hp": 1, "thirsty": True})
    gm.clock(step=60)
    look = state(gm, "Lookout")
    assert look["down"] and look["hp"] == 0 and look["downed_by"] == "thirst"
    gm.clock(step=60)
    gm.clock(step=60)
    look = state(gm, "Lookout")
    assert look["hp"] == 0 and not look["dead"] and gm.inspect("Lookout")["parent"] == gm.inspect("The Ridge")["id"]
    look_id = gm.inspect("Lookout")["id"]
    assert len([e for e in gm.world.events(0, kinds=["parched"], limit=5000) if e["target_id"] == look_id]) == 1
    gm.spawn("waterskin", "Lookout", "Gift skin", state={"left": 2})
    gm.clock(step=60)
    look = state(gm, "Lookout")
    assert not look["down"] and look["hp"] == 1 and look["water"] == 4 and look.get("downed_by") is None
    assert any(e["target_id"] == look_id for e in gm.world.events(0, kinds=["rose"], limit=5000))
    # a blade's work is not undone by water
    gm.patch("Captain", {"hp": 0, "down": True, "wounded": True, "water": 2, "thirsty": True})
    gm.spawn("waterskin", "Captain", "Captain's skin", state={"left": 2})
    gm.clock(step=60)
    cap = state(gm, "Captain")
    assert cap["down"] and cap["water"] == 5  # 2, less the yard, plus a drink


def test_a_thirsty_body_walks_to_water_one_known_step_away_and_back_to_its_post():
    # the Captain in the yard, no skin, the cistern one room away: he goes, drinks, and comes back to the yard
    eng, gm, you = outpost()
    yard, hold = gm.inspect("The Yard")["id"], gm.inspect("The Keep")["id"]
    gm.patch("Captain", {"water": 3, "thirsty": True})
    gm.clock(step=60)
    assert gm.inspect("Captain")["parent"] == hold and state(gm, "Captain")["post"] == yard
    gm.clock(step=60)
    cap = state(gm, "Captain")
    assert cap["water"] == 6 and cap["thirsty"] is False and state(gm, "The cistern")["left"] == 11
    gm.clock(step=60)  # the cistern is a store with a count: one draw ends his thirst, and he walks back
    assert gm.inspect("Captain")["parent"] == yard and state(gm, "Captain").get("post") is None
    assert state(gm, "The cistern")["left"] == 11
    cap_id = gm.inspect("Captain")["id"]
    walks = [e["payload"] for e in gm.world.events(0, kinds=["arrived"], limit=5000) if e["payload"].get("who") == cap_id]
    assert [x["for_water"] for x in walks] == [True, False] and all(x["quiet"] for x in walks)
    # the Scout knows the way down to the hidden Spring; she goes when her skin is dry and comes back with it full
    ridge, well = gm.inspect("The Ridge")["id"], gm.inspect("The Spring")["id"]
    gm.patch("Scout's skin", {"left": 0})
    gm.patch("Scout", {"water": 2, "thirsty": True})
    gm.clock(step=60)
    assert gm.inspect("Scout")["parent"] == well
    gm.clock(step=60)
    assert state(gm, "Scout's skin")["left"] == 3 and state(gm, "Scout")["water"] == 5
    gm.clock(step=60)
    assert state(gm, "Scout")["water"] == 9 and state(gm, "Scout's skin")["left"] == 3  # her fill from the well
    gm.clock(step=60)
    assert gm.inspect("Scout")["parent"] == ridge
    scout_id = gm.inspect("Scout")["id"]
    walks = [e["payload"] for e in gm.world.events(0, kinds=["arrived"], limit=5000) if e["payload"].get("who") == scout_id]
    # down and back, both quiet: a story rule that takes first sights from arrivals takes none from her walk home
    assert [x["for_water"] for x in walks] == [True, False] and all(x["quiet"] for x in walks)


def test_rest_mends_a_point_a_beat_and_a_wound_put_down_gets_up_at_two():
    eng, gm, you = outpost()
    yard = gm.inspect("Captain")["parent"]
    gm.spawn("thing", yard, "Test well", state={"water_source": True, "portable": False})  # no thirst beside it
    gm.patch("Captain", {"hp": 0, "down": True, "wounded": True, "water": 9})
    gm.clock(step=600)
    cap = state(gm, "Captain")
    assert cap["hp"] == 1 and cap["down"] and cap["water"] == 9
    gm.clock(step=600)
    cap = state(gm, "Captain")
    assert cap["hp"] == 2 and not cap["down"] and cap["wounded"] and cap["water"] == 8  # every second point costs water
    cap_id = gm.inspect("Captain")["id"]
    assert any(e["target_id"] == cap_id and e["payload"].get("by") == "rest" for e in gm.world.events(0, kinds=["rose"], limit=5000))
    for _ in range(3):
        gm.clock(step=600)
    cap = state(gm, "Captain")
    assert cap["hp"] == 5 and not cap["wounded"] and cap["water"] == 7  # above half the wound closes
    # a dry body does not mend; thirst's down is water's
    gm.patch("Lookout", {"water": 2, "hp": 2, "thirsty": True})
    gm.clock(step=600)
    assert state(gm, "Lookout")["hp"] <= 2


def test_tend_gets_the_down_up_and_medicine_heals_anyone_hurt():
    eng, gm, you = outpost()
    here = gm.inspect("Warden")["parent"]
    gm.move("Captain", here)
    gm.patch("Captain", {"hp": 0, "down": True, "wounded": True, "water": 2})
    gm.patch("Warden", {"wits": 25, "skills": {"survival": 0}})
    with pytest.raises(Rejected) as ex:
        gm.act_as("Captain", "tend", "Warden")
    assert "down" in str(ex.value).lower()  # the down cannot tend
    road = gm.inspect("The Road")["id"]  # dry: no cask, no source
    gm.move("Captain", road)
    gm.move("Warden", road)
    for e in gm.find(parent=gm.inspect("Warden")["id"], limit=50):
        if e["type"] == "waterskin":
            gm.patch(e["id"], {"left": 0})
    with pytest.raises(Rejected) as ex:
        you.act("tend", "Captain")
    assert "water" in str(ex.value)  # a wound bound dry festers: the error says where water would come from
    gm.spawn("waterskin", "Warden", "Wash skin", state={"left": 2})
    gm.patch("Warden", {"wits": -25})
    r = you.act("tend", "Captain")
    assert state(gm, "Wash skin")["left"] == 1 and state(gm, "Captain")["down"]  # slipped, and the water is spent
    gm.patch("Warden", {"wits": 25})
    r = you.act("tend", "Captain")
    cap = state(gm, "Captain")
    assert "tended" in kinds(r) and "rose" in kinds(r) and not cap["down"] and cap["hp"] == 1
    assert state(gm, "Wash skin")["left"] == 0
    with pytest.raises(Rejected) as ex:
        you.act("tend", "Captain")
    assert "medicine" in str(ex.value)  # bare hands do nothing for someone on their feet; the error says what would
    gm.spawn("medicine", "Warden", "Herb salve", state={"doses": 1, "heals": 3})
    r = you.act("tend", "Captain")
    cap = state(gm, "Captain")
    assert cap["hp"] == 4 and cap["wounded"] and state(gm, "Herb salve")["doses"] == 0  # half of 8: still wounded
    with pytest.raises(Rejected):
        you.act("tend", "Captain")  # the pouch is empty and he is standing
    gm.patch("Warden", {"hp": 2, "wounded": True})
    gm.spawn("medicine", "Warden", "More salve", state={"doses": 2})
    you.act("tend", "Warden")  # yourself, with medicine
    assert state(gm, "Warden")["hp"] == 5


def test_a_secret_side_is_not_given_away_and_a_loan_is_not_a_gift():
    eng, gm, you = outpost()
    me = gm.inspect("Warden")["id"]
    here = gm.inspect(me)["parent"]
    rivals = [f for f in gm.find(type="faction") if f["name"] == "the Rivals"][0]["id"]
    seen = lambda: {e["target"]: e["data"]["value"] for e in gm.world.edges(me, "standing", "out")}.get(rivals, 0)
    unseen = lambda: (state(gm, "the Rivals").get("unseen") or {}).get(me, 0)
    before = seen()
    gm.spawn("fighter", here, "Drifter", state={"faction": "the Rivals", "secret": ["faction"]})
    gm.spawn("thing", me, "Blank leaf", state={"portable": True})
    # a gift to one who hides their side: the faction counts it, the giver is told nothing about whose it is
    r = you.act("give", "Drifter", {"item": "Blank leaf"})
    assert not any(e["kind"] == "standing" for e in r["events"]) and "the Rivals" not in str(r)
    assert seen() == before and unseen() == 1
    assert {"unseen", "lent"} <= set(gm.world.get(rivals)["state"]["secret"])  # no body reads them on its card
    # handed straight back: a loan, not a gift
    gm.act_as("Drifter", "give", "Warden", {"item": "Blank leaf"})
    assert seen() == before and unseen() == 0
    # the same with one who wears the side openly: the giver reads it both ways
    gm.spawn("fighter", here, "Sworn man", state={"faction": "the Rivals"})
    r = you.act("give", "Sworn man", {"item": "Blank leaf"})
    assert [e["payload"]["delta"] for e in r["events"] if e["kind"] == "standing"] == [1] and seen() == before + 1
    r = gm.act_as("Sworn man", "give", "Warden", {"item": "Blank leaf"})
    back = [e["payload"] for e in r["events"] if e["kind"] == "standing" and e["target"] == me]
    assert back and back[0]["delta"] == -1 and back[0]["why"].startswith("lent") and seen() == before


def test_idle_care_takes_one_draw_from_a_store_and_leaves_water_kept_for_others():
    # a playtest case: an idle body that walked for water drank a store down to full. A store with a count
    # gives one draw; a source `keep_for` another side is not its idle care's to drink; of the rest, the fullest.
    eng, gm, you = outpost()
    gm.spawn("place", gm.world.root_id, "Depot")
    gm.spawn("place", gm.world.root_id, "Post")
    gm.connect("Depot", "Post")
    gm.spawn("thing", "Depot", "Keep jars", state={"water_source": True, "left": 10, "keep_for": "the Garrison"})
    gm.spawn("thing", "Depot", "Ration cask", state={"water_source": True, "left": 3})
    gm.spawn("thing", "Depot", "Spare cask", state={"water_source": True, "left": 6})
    gm.spawn("person", "Post", "Drifter", state={"faction": "the Hill Folk", "water": 2, "max_water": 16})
    gm.spawn("waterskin", "Drifter", "Drifter's skin", state={"left": 0})
    for _ in range(4):
        gm.clock(step=60)
    d = state(gm, "Drifter")
    assert gm.world.get(gm.inspect("Drifter")["parent"])["name"] == "Post" and 4 <= d["water"] <= 7
    assert state(gm, "Keep jars")["left"] == 10 and state(gm, "Ration cask")["left"] == 3
    assert state(gm, "Spare cask")["left"] == 5 and state(gm, "Drifter's skin")["left"] == 0  # no free skinful
    # the jars' own side drinks from them
    gm.spawn("person", "Depot", "Warder", state={"faction": "the Garrison", "water": 2, "max_water": 16})
    gm.patch("Spare cask", {"left": 0})
    gm.patch("Ration cask", {"left": 0})
    gm.clock(step=60)
    assert state(gm, "Keep jars")["left"] == 9 and state(gm, "Warder")["water"] >= 4
    # only a source is drunk from: a stone with no count is not an endless well
    gm.spawn("thing", "Depot", "Flat stone", state={"portable": False})
    with pytest.raises(Rejected, match="empty"):
        gm.act_as("Warder", "drink", "Flat stone")


def test_a_yield_to_one_fighter_stops_his_comrades_too():
    # two guards kept cutting a man who had yielded to the first one, and killed him (a player's report, 2026-11-23)
    eng, gm, you = outpost()
    you.act("go", "The Yard")
    for name in ("First guard", "Second guard"):
        gm.spawn("fighter", "The Yard", name, state={"hp": 40, "max_hp": 40, "faction": "the Garrison"})
    gm.patch("Warden", {"hp": 60, "max_hp": 60})
    strong(gm, "Warden")
    second = gm.inspect("Second guard")["id"]

    def blows(by):
        return len([e for e in gm.world.events(0, kinds=["hit", "missed"], limit=5000) if e["payload"]["by"] == by])

    you.act("attack", "First guard")
    you.act("attack", "Second guard")
    you.act("yield", "First guard")
    before = blows(second)
    for _ in range(5):
        gm.clock(step=6)
    assert blows(second) == before
    gm.spawn("fighter", "The Yard", "Sellsword", state={"hp": 40, "max_hp": 40})
    you.act("attack", "Sellsword")  # one outside the Garrison owes the yield nothing
    for _ in range(5):
        gm.clock(step=6)
    assert blows(gm.inspect("Sellsword")["id"]) >= 1
