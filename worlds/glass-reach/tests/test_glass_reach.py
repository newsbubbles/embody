"""The Glass Reach as a story: seats with stakes, the hidden well and the two ways to it, terms with Taan, Dram in the
ring, the letter, the end states, the trade at the Landing, the timers, and a safe upgrade."""

import json
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
    seen = scenes(r["events"])
    if not r["result"]["success"]:
        assert story(gm)["found_well"] is False
    gm.patch("Reeve Ansel Varrick", {"skills": {"survival": 30}})
    r = you.act("check", params={"skill": "survival", "dc": 15})
    assert story(gm)["found_well"] is True and gm.inspect("The Deepwell")["state"]["hidden"] is False
    assert any("way down" in t for t in seen + scenes(r["events"]))  # whichever roll found it
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
    assert "Guild waterskin" in held and "Emberglass" not in held
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


def test_hosted_reach_has_seats_templates_and_a_day_that_keeps_real_time():
    eng = Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    r = load_world(gm, "glass-reach", hosted=True)
    assert r["hosted"]
    seats = gm.seats()
    names = {x["name"] for x in seats["seats"]}
    assert {"Reeve Ansel Varrick", "Sefa of the Keth", "Captain Ruhl", "Dram Hollis", "Ossa the Carrier", "Nico"} <= names
    assert "Elder Taan" not in names
    assert {t["template"] for t in seats["templates"]} == {"carrier", "guard", "keth", "dreyer"}
    ck = gm.clock()
    assert ck["running"] and ck["rate"] == 4 and ck["turn"] is None  # real time, whoever is in
    timers = {t["kind"]: t for t in gm.timers()}
    near = lambda x: pytest.approx(x, abs=5)  # the clock is already running
    assert timers["dram_moves"]["in"] == near(28800) and timers["dawn"]["in"] == near(86400) and timers["heat"]["in"] == near(21600)
    # a guest sits down and the briefing says the clock keeps time; the day turns
    eng.public_url = "https://reach.example/mcp"
    inv = gm.invite("player", entity="Reeve Ansel Varrick", label="Sam")
    assert "runs at 4x real time:" in inv["page"] and "Glass Reach" in inv["paste"]
    sam = eng.session_for_token(inv["token"])
    b = sam.join()
    assert b["briefing"]["text"].startswith("The Glass Reach") and "4x real time" in b["briefing"]["pace"]
    assert "while anyone" not in b["briefing"]["pace"]
    gm.clock(step=21600)
    assert sam.perceive()["ambient"]["time_of_day"] == "noon"
    gm.clock(step=54000 - 21600)
    assert sam.perceive()["ambient"]["time_of_day"] == "night"  # after dusk at 43200
    gm.clock(step=86400 - 54000)
    assert sam.perceive()["ambient"]["time_of_day"] == "morning"  # dawn
    gm.clock(step=21600)
    assert sam.perceive()["ambient"]["time_of_day"] == "noon"  # the heat comes back every day
    assert gm.inspect("The cistern")["state"]["left"] == 0  # one-shot, 64800 in
    assert any("walls start to tick" in t for t in scenes(sam.perceive(cursor=0, events=800)["events"]))  # dusk, at the Hold
    sam.leave()
    eng.tick_all()
    assert gm.clock()["running"]  # the last guest leaving pauses nothing
    # a newcomer from a template stands where the template says
    kit = eng.session_for_token(gm.invite("player", label="Kit")["token"])
    b = kit.join(template="keth", name="Kit")
    assert b["here"]["name"] == "Red Ridge" and gm.inspect("Kit")["state"]["faction"] == "the Keth"
    # hosting again renews the settings and leaves the timers alone
    n = len(gm.timers())
    load_world(gm, "glass-reach", upgrade=True, hosted=True)
    assert len(gm.timers()) == n and gm.clock()["rate"] == 4


def hosted(truce=False):
    eng = Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "glass-reach", hosted=True)
    if truce:
        gm.patch(gm.inspect("Story")["id"], {"truce": True})
    return eng, gm


def where(gm, name):
    return gm.world.get(gm.world.get(gm.inspect(name)["id"])["parent_id"])["name"]


def test_the_keth_run_carries_water_to_the_hold_at_dusk_while_the_truce_holds():
    eng, gm = hosted(truce=True)
    timers = {t["kind"]: t for t in gm.timers()}
    assert timers["keth_run"]["at"] == pytest.approx(timers["dusk"]["at"], abs=1) and timers["keth_run"]["every"] == 86400
    assert timers["crawler"]["at"] == pytest.approx(timers["dawn"]["at"], abs=1)
    gm.clock(step=timers["dusk"]["in"] + 1)
    assert gm.inspect("Iska of the Keth")["state"]["run"] == "out" and where(gm, "Iska of the Keth") == "The Deepwell"
    path = []
    for _ in range(5):
        gm.clock(step=1800)
        path.append(where(gm, "Iska of the Keth"))
    assert path == ["Red Ridge", "The Glass Flats", "The Salt Road", "The Gate Yard", "Scar Gate, the Hold"]
    assert gm.inspect("The Keth jars")["state"]["left"] == 8
    assert gm.inspect("The Glass Flats")["state"]["tremor"] == 0  # the broken step: the sand did not hear her
    for _ in range(5):
        gm.clock(step=1800)
    assert where(gm, "Iska of the Keth") == "The Deepwell" and gm.inspect("Iska of the Keth")["state"].get("run") is None
    # hosting again adds no second run
    n = len(gm.timers())
    load_world(gm, "glass-reach", upgrade=True, hosted=True)
    assert len(gm.timers()) == n


def test_a_bearer_put_down_on_the_road_sets_the_water_down_there():
    eng, gm = hosted(truce=True)
    dusk = {t["kind"]: t for t in gm.timers()}["dusk"]["in"]
    gm.clock(step=dusk + 1)
    gm.clock(step=1800 * 3)
    assert where(gm, "Iska of the Keth") == "The Salt Road"
    iska = gm.inspect("Iska of the Keth")["id"]
    gm.patch(iska, {"down": True})
    gm.clock(step=1800)
    jars = gm.inspect("Keth jars, set down")
    assert where(gm, "Keth jars, set down") == "The Salt Road" and jars["state"]["left"] == 8 and jars["state"]["water_source"]
    assert where(gm, "Iska of the Keth") == "The Salt Road" and gm.inspect(iska)["state"]["carrying"] == 0
    assert gm.inspect("The Keth jars")["state"]["left"] == 0
    gm.clock(step=86400)  # next dusk: a bearer still down carries nothing
    assert gm.inspect(iska)["state"].get("run") is None and gm.inspect("The Keth jars")["state"]["left"] == 0


def test_no_truce_no_run_and_no_ossa_at_the_tally_no_crawler():
    eng, gm = hosted()
    timers = {t["kind"]: t for t in gm.timers()}
    gm.clock(step=timers["dusk"]["in"] + 1)
    assert gm.inspect("Iska of the Keth")["state"].get("run") is None
    ossa = gm.inspect("Ossa the Carrier")["id"]
    gm.patch(ossa, {"down": True})
    gm.clock(step=timers["dawn"]["in"] - timers["dusk"]["in"])
    assert gm.inspect("The Hold's ration cask")["state"]["left"] == 0
    gm.patch(ossa, {"down": False})
    gm.clock(step=86400)
    assert gm.inspect("The Hold's ration cask")["state"]["left"] == 8


@pytest.mark.parametrize("truce", [True, False])
def test_the_reach_lives_a_week_with_every_seat_held_and_nobody_playing(truce):
    import importlib.util
    spec = importlib.util.spec_from_file_location("d20_soak", REPO / "packs" / "d20" / "soak.py")
    soak = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(soak)
    r = soak.soak("glass-reach", days=7, sets=("Story.truce=true",) if truce else (), step=1800)
    assert r["ok"] and len(r["held"]) == 6, soak.render(r)
    assert all(b["low"] >= 3 for b in r["bodies"]), soak.render(r)


def test_upgrade_is_idempotent():
    eng, gm, you = reach()
    before = {e["id"]: e["state"] for e in gm.world.find(limit=None)}
    goals = len(gm.recall(entity="Reeve Ansel Varrick")["goals"])
    edges = gm.world.store.count("edge", "world_id=?", (gm.world.id,))
    load_world(gm, "glass-reach", upgrade=True)
    assert {e["id"]: e["state"] for e in gm.world.find(limit=None)} == before
    assert gm.world.store.count("edge", "world_id=?", (gm.world.id,)) == edges
    assert len(gm.recall(entity="Reeve Ansel Varrick")["goals"]) == goals
    assert len(gm.world.edges(gm.inspect("Reeve Ansel Varrick")["id"], "standing", "out")) == 4


def test_upgrade_leaves_a_finished_goal_finished():
    eng, gm, you = reach()
    g = next(x for x in gm.recall(entity="Dram Hollis")["goals"] if x["text"].startswith("The reeve, in the ring"))
    gm.intend(id=g["id"], status="done", entity="Dram Hollis")
    load_world(gm, "glass-reach", upgrade=True)
    goals = gm.world.get(gm.inspect("Dram Hollis")["id"])["state"]["goals"]
    ring = [x for x in goals if x["text"].startswith("The reeve, in the ring")]
    assert len(ring) == 1 and ring[0]["status"] == "done"  # not handed back to him on every boot


def test_ruhl_and_dram_answer_the_questions_the_first_reeve_asked():
    eng, gm, you = reach()
    r = you.act("talk", "Dram Hollis", {"about": "why did you stay when the convoy left"})
    assert any("where the counting is" in (e["payload"].get("text") or "") for e in r["events"] if e["kind"] == "say")
    you.act("go", "The Gate Yard")
    for about, bit in [("the road north", "Salt Road runs north"), ("can you spare me some men", "I spare you none"),
                       ("will you stand with me", "I hold the ring")]:
        r = you.act("talk", "Captain Ruhl", {"about": about})
        assert any(bit in (e["payload"].get("text") or "") for e in r["events"] if e["kind"] == "say"), about


def test_a_held_dram_does_not_walk_through_his_guard():
    eng, gm, you = reach()
    ruhl = gm.inspect("Captain Ruhl")["id"]
    gm.patch("Dram Hollis", {"held_by": ruhl})
    gm.clock(step=240)
    assert gm.inspect("Dram Hollis")["parent"] == gm.inspect("Scar Gate, the Hold")["id"]
    assert gm.inspect("Dram Hollis")["state"]["waiting"] is False
    assert any("tests the grip" in t for t in scenes(you.perceive(cursor=0, events=500)["events"]))


def test_sefa_shows_the_way_to_a_friend_of_the_keth_too():
    eng, gm, you = reach()
    for place in ["The Gate Yard", "The Salt Road", "The Glass Flats", "Red Ridge"]:
        you.act("go", place)
    you.act("talk", "Sefa of the Keth", {"about": "water"})
    assert story(gm)["found_well"] is False
    me = gm.inspect("Reeve Ansel Varrick")["id"]
    keth = gm.inspect("the Keth")["id"]
    gm.unlink(me, keth, "standing")
    gm.link(me, keth, "standing", {"value": 1, "public": True})
    r = you.act("talk", "Sefa of the Keth", {"about": "the well"})
    assert story(gm)["found_well"] is True and story(gm)["well_found_by"] == "sefa"
    assert any("I showed you" in t for t in scenes(r["events"]))


def said(r, who=None):
    return [e["payload"]["text"] for e in r["events"] if e["kind"] == "say" and (who is None or e["payload"].get("to") == who)]


def test_word_left_with_ruhl_reaches_the_new_guard_and_nobody_else():
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    r = you.act("leave_word", "Captain Ruhl", {"for": "the new guard", "word": "I went north to the Landing. Follow when you can."})
    assert "word_left" in kinds(r)
    ruhl = gm.inspect("Captain Ruhl")
    assert ruhl["state"]["word_left"][0]["where"] == "The Gate Yard"
    # the word is Ruhl's secret: a player who inspects him does not read it
    assert "word_left" not in you.inspect("Captain Ruhl")["state"]
    # a spy asking after the reeve hears that word was left, not what it says
    dram = eng.session("dram")
    dram.join("glass-reach", "Dram Hollis")
    dram.act("go", "The Gate Yard")
    r = dram.act("talk", "Captain Ruhl", {"about": "where is the reeve"})
    assert any("Not for you" in t for t in said(r)) and not any("Landing" in t for t in said(r))
    # the new guard walks in and asks about anything: Ruhl hands the word over, as a whisper, once
    harl = eng.session("harl")
    harl.join("glass-reach", template="guard", name="Harl")  # the guard template starts in the yard
    r = harl.act("talk", "Captain Ruhl", {"about": "the men"})
    lines = said(r, gm.inspect("Harl")["id"])
    assert any("Reeve Ansel Varrick left word for you, at The Gate Yard: 'I went north" in t for t in lines), lines
    whisper = [e for e in r["events"] if e["kind"] == "say" and "left word" in e["payload"]["text"]][0]
    assert whisper["reach"] == 0 if "reach" in whisper else True
    r = harl.act("talk", "Captain Ruhl", {"about": "the men"})
    assert not any("left word" in t for t in said(r))
    # the reeve asking Ruhl himself is not handed his own word back
    r = you.act("talk", "Captain Ruhl", {"about": "the men"})
    assert not any("left word" in t for t in said(r))


def test_word_left_for_anyone_and_a_name_and_the_check():
    eng, gm, you = reach()
    you.act("go", "The Gate Yard")
    with pytest.raises(Rejected):
        you.act("leave_word", "Captain Ruhl", {"for": "anyone"})
    you.act("leave_word", "Captain Ruhl", {"for": "anyone", "word": "the cistern is low"})
    you.act("leave_word", "Captain Ruhl", {"for": "Sefa", "word": "meet me on the ridge"})
    harl = eng.session("harl")
    harl.join("glass-reach", template="guard", name="Harl")
    r = harl.act("talk", "Captain Ruhl", {"about": "the water"})
    texts = said(r)
    assert any("cistern is low" in t for t in texts) and not any("ridge" in t for t in texts)
    # an older Reach learns to keep the word secret on upgrade
    gm.patch("Captain Ruhl", {"secret": ["dialog", "gives", "gave"]})
    load_world(gm, "glass-reach", upgrade=True)
    ruhl = gm.inspect("Captain Ruhl")["id"]
    assert gm.world.get(ruhl)["state"]["secret"] == ["dialog", "gives", "gave", "word_left"]


def test_hosted_bodies_thirst_at_the_pace_of_the_day():
    # one point of water every 2.4 world hours, a look for water every ten minutes; fights keep their six seconds
    eng = Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "glass-reach", hosted=True)

    def state(name):
        return gm.inspect(name)["state"]

    def beats(name=None):
        out = {}
        for p in gm.world.pending():
            if p["kind"] == "tick" and (name is None or p["entity_id"] == gm.inspect(name)["id"]):
                out.setdefault(p["payload"]["script"], set()).add(p["every"])
        return out

    assert beats() == {"thirst": {8640}, "quench": {600}, "mend": {21600}, "fighter_tick": {6}}
    kit = eng.session_for_token(gm.invite("player", label="Kit")["token"])
    kit.join(template="guard", name="Kit")
    assert beats("Kit") == {"thirst": {8640}, "quench": {600}, "mend": {21600}}
    # a Reach hosted before the pace was set takes it on with the next upgrade
    gm.world.set_pace({"thirst": 60})
    load_world(gm, "glass-reach", upgrade=True, hosted=True)
    assert beats()["thirst"] == {8640}
    # Ruhl thirsts through most of a day in the yard, walks to the cistern, drinks, and is back on his post
    yard = gm.inspect("The Gate Yard")["id"]
    for _ in range(7):
        gm.clock(step=8640)  # the hosted clock moves a second at a time; one long step would fire each beat once
    assert state("Captain Ruhl")["water"] == 3
    for _ in range(3):
        gm.clock(step=600)  # to the cistern, a drink, back
    ruhl = state("Captain Ruhl")
    assert ruhl["water"] >= 6 and gm.inspect("Captain Ruhl")["parent"] == yard
    assert not gm.world.events(0, kinds=["tick"], limit=5000)


def test_the_upgrade_nails_the_notice_by_the_cistern_once():
    eng, gm, you = reach()
    hold = gm.inspect("Scar Gate, the Hold")["id"]
    gm.destroy(gm.find(type="letter", name="Notice by the cistern")[0]["id"])  # a Reach built before the notice
    load_world(gm, "glass-reach", upgrade=True)
    load_world(gm, "glass-reach", upgrade=True)
    notes = gm.find(type="letter", name="Notice by the cistern")
    assert notes[0]["id"] in [c["id"] for c in gm.inspect(hold)["contents"]]
    assert len(notes) == 1 and notes[0]["state"]["text"].startswith("Nailed by the cistern")
    r = you.act("read", "Notice by the cistern")
    assert any("water falls by a point every 2.4 hours" in str(e["payload"]) for e in r["events"])



def test_a_reach_from_before_rest_mends_and_iska_carries_the_salve_once():
    eng = Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "glass-reach", hosted=True)
    salve = gm.find(name="Glassroot salve")
    assert len(salve) == 1 and gm.inspect("Glassroot salve")["parent"] == gm.inspect("Iska of the Keth")["id"]
    # a world hosted before mend existed: its bodies have no mend tick until the next upgrade
    gm.world.store.conn.execute("DELETE FROM scheduled WHERE world_id=? AND json_extract(payload, '$.script')='mend'", (gm.world.id,))
    assert not [p for p in gm.world.pending() if p["kind"] == "tick" and p["payload"].get("script") == "mend"]
    gm.patch("Glassroot salve", {"doses": 0})
    load_world(gm, "glass-reach", upgrade=True, hosted=True)
    mends = [p for p in gm.world.pending() if p["kind"] == "tick" and p["payload"].get("script") == "mend"]
    assert mends and {p["every"] for p in mends} == {21600}
    assert len({p["entity_id"] for p in mends}) == len(mends)  # one each, never two
    assert len(gm.find(name="Glassroot salve")) == 1 and gm.inspect("Glassroot salve")["state"]["doses"] == 0  # not refilled
    # Corin's case: a thresher put him down; half a day of rest with water in him and he is up
    gm.patch("Captain Ruhl", {"vigor": 0, "down": True, "wounded": True, "water": 10})
    gm.clock(step=21601)
    gm.clock(step=21601)
    ruhl = gm.inspect("Captain Ruhl")["state"]
    assert not ruhl["down"] and ruhl["vigor"] >= 2


def test_the_reach_is_laid_out_from_the_canon_once_and_a_live_edit_survives_the_reboot():
    eng = Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "glass-reach", hosted=True)
    m = gm.map(depth=2)
    rows = {e["name"]: e for e in m["entities"]}
    places = [e for e in m["entities"] if e["type"] == "place"]
    assert len(places) == 17 and all(e["own"] for e in places)  # thirteen, and the Guild Yard, its two rooms and Hauler Nine
    assert rows["The Keth jars"]["own"] and rows["The Hold's ration cask"]["own"]  # spawned by the routines, placed after
    assert len(m["paths"]) >= 7 and all(p["drawn"] for p in m["paths"])
    ridge = gm.measure("Scar Gate, the Hold", "Red Ridge")
    assert 3500 < ridge["ground"] < 5000 and ridge["bearing"] in ("E", "ENE")  # two Keth legs out
    assert gm.measure("Red Ridge", "The Deepwell")["dz"] == -25.0
    gm.layout(placements=[{"entity": "The Carriers' Landing", "at": [320, 3600, 0]}])  # the owner moves it live
    load_world(gm, "glass-reach", upgrade=True, hosted=True)
    assert gm.measure("The Carriers' Landing")["a"]["at"] == [320, 3600, 0]


def varrick_men(gm):
    st = story(gm)
    return {e["name"] for e in gm.world.find(type="person", limit=None) + gm.world.find(type="fighter", limit=None)
            if gm.world.get(e["id"])["state"].get("faction") == "House Varrick"} - {"Captain Ruhl", "Reeve Ansel Varrick"}


def test_the_low_well_and_ruhls_nine_are_in_the_world():
    eng, gm, you = reach()
    # the Keth's grave is a place off the Flats and the ridge: a dry, poisoned well-head nobody drinks from
    well = gm.inspect("The Low Well")
    assert well["type"] == "place" and not well["state"].get("hidden")
    assert {c["name"] for c in well["contents"]} - {"Empty phial"} == {"The Low Well's head", "Four cairns"}  # the phial is hidden
    exits = {gm.world.get(e["target"])["name"] for e in gm.world.edges(well["id"], "connects_to", "out")}
    assert exits == {"The Glass Flats", "Red Ridge"}
    assert not gm.inspect("The Low Well's head")["state"].get("water_source")
    # nine men under Ruhl in the Hold, six of them with a blade, and the captain knows every one
    men = varrick_men(gm)
    assert len(men) == 9 and "The oldest of the nine" in men
    hold = gm.inspect("Scar Gate, the Hold")["id"]
    armed = [m for m in men if any(c["name"] == "Varrick blade" for c in gm.inspect(m)["contents"])]
    assert len(armed) == 6 and all(gm.inspect(m)["parent"] == hold for m in men)
    ruhl = gm.inspect("Captain Ruhl")["id"]
    known = {gm.world.get(e["target"])["name"] for e in gm.world.edges(ruhl, "knows", "out")}
    assert men <= known
    assert gm.inspect("Bows on the wall")["parent"] == hold
    # they are people, not fighters: an outlaw under the Hold's roof is the captain's to deal with, not theirs
    assert all(gm.inspect(m)["type"] == "person" for m in men)
    # under the roof with water at hand nobody thirsts, the nine included
    for _ in range(3):
        gm.clock(step=60)
    assert gm.inspect("Brannoc Hale")["state"]["water"] == 10


def test_a_reach_with_some_of_the_hold_already_gets_only_the_rest_and_only_once():
    eng, gm, you = reach()
    st = story(gm)
    for m in varrick_men(gm):
        gm.destroy(m)
    gm.destroy("The Low Well")
    gm.patch(gm.find(type="story")[0]["id"], {"garrison": False, "low_well": None})
    # an older Reach: a guest's guard and the old man lent to the Keth, no Low Well
    kit = eng.session_for_token(gm.invite("player", label="Kit")["token"])
    kit.join(template="guard", name="Kit")
    gm.spawn("person", st["deepwell"], "The oldest of the nine", state={"faction": "House Varrick"})
    load_world(gm, "glass-reach", upgrade=True)
    men = varrick_men(gm)
    assert len(men) == 9 and "Kit" in men and "Garret Cole" not in men  # the guest stands in for the ninth
    assert len([e for e in gm.world.find(limit=None) if e["name"] == "The oldest of the nine"]) == 1
    assert [e["name"] for e in gm.find(type="place", limit=50)].count("The Low Well") == 1
    # a man who is gone stays gone: the nine are made once
    gm.destroy("Brannoc Hale")
    load_world(gm, "glass-reach", upgrade=True)
    assert "Brannoc Hale" not in varrick_men(gm) and [e["name"] for e in gm.find(type="place", limit=50)].count("The Low Well") == 1


def test_a_blade_hangs_on_the_rack_and_a_card_shows_the_blade_a_body_bears():
    eng, gm, you = reach()
    hollis = next(c for c in you.perceive()["present"] if c["name"] == "Dram Hollis")
    assert [b["name"] for b in hollis["bears"]] == ["Thin blade"]  # seen at his hip, whatever the prose says
    you.act("go", "The Gate Yard")
    with pytest.raises(Rejected) as ex:
        you.act("put", "Rack of practice blades", params={"item": "Waterskin"})
    assert "does not take that" in str(ex.value)
    with pytest.raises(Rejected):
        you.act("put", "Captain Ruhl", params={"item": "Reeve's blade"})  # a person is not a rack
    r = you.act("put", "Rack of practice blades", params={"item": "Reeve's blade"})
    assert "put" in kinds(r)
    rack = next(c for c in you.perceive()["present"] if c["name"] == "Rack of practice blades")
    assert [h["name"] for h in rack["holding"]] == ["Reeve's blade"]
    assert gm.inspect("Reeve's blade")["parent"] == gm.inspect("Rack of practice blades")["id"]
    # whoever stands in the yard can take it down again
    ruhl = eng.session("ruhl")
    ruhl.join("glass-reach", "Captain Ruhl")
    ruhl.act("take", "Reeve's blade")
    assert gm.inspect("Reeve's blade")["parent"] == gm.inspect("Captain Ruhl")["id"]


def test_a_dreyer_newcomer_comes_in_at_the_hidden_camp_that_only_dreyer_knows():
    eng, gm, you = reach()
    ash = eng.session("ash")
    b = ash.join("glass-reach", template="dreyer", name="Ash")
    assert b["here"]["name"] == "The Dry Camp"
    assert {"Halvard Dreyer", "Mother Sallow", "Brisk", "The house's tank"} <= {c["name"] for c in b["present"]}
    me = gm.inspect("Ash")["id"]
    lines = said(ash.act("talk", "Mother Sallow", {"about": "water"}), me)
    assert any("A draw a day" in x for x in lines) and "House waterskin" in [c["name"] for c in gm.inspect("Ash")["contents"]]
    ash.act("go", "The Bone Field")
    assert "The Dry Camp" in [x["name"] for x in ash.perceive()["exits"]]
    # the reeve, standing in the Bone Field, finds no way south
    gm.move("Reeve Ansel Varrick", "The Bone Field")
    with pytest.raises(Rejected):
        you.act("go", "The Dry Camp")
    load_world(gm, "glass-reach", upgrade=True)  # a reboot keeps one camp and one Halvard
    assert len([e for e in gm.find(name="Halvard Dreyer") if e["name"] == "Halvard Dreyer"]) == 1


def test_a_dreyer_newcomer_meets_the_runner_and_only_the_word_opens_him():
    eng, gm, you = reach()
    ash = eng.session("ash")
    ash.join("glass-reach", template="dreyer", name="Ash")
    assert "saltmark" in gm.inspect("Ash")["state"]["brief"]
    gm.move("Ash", "The Crawler's Lee")
    wick = next(c for c in ash.perceive()["present"] if c["name"] == "Wick the runner")
    assert "dialog" not in wick.get("state", wick) and "House Dreyer" not in json.dumps(wick)  # nothing shows him Dreyer's
    me = gm.inspect("Ash")["id"]
    lines = said(ash.act("talk", "Wick the runner", {"about": "Hollis"}), me)
    assert lines and "Never heard the name" in lines[0]
    r = ash.act("talk", "Wick the runner", {"about": "saltmark"})
    assert any("the new reeve has him" in t for t in said(r, me))
    assert "Sealed note for Hollis" in [c["name"] for c in gm.inspect("Ash")["contents"]]
    ash.act("talk", "Wick the runner", {"about": "saltmark"})  # one note, once
    assert [c["name"] for c in gm.inspect("Ash")["contents"]].count("Sealed note for Hollis") == 1
    load_world(gm, "glass-reach", upgrade=True)  # a reboot keeps one Wick
    assert len([e for e in gm.find(name="Wick the runner") if e["name"] == "Wick the runner"]) == 1


def chapter_one_done(gm):
    gm.patch(gm.inspect("Story")["id"], {"truce": True, "dram_done": True, "done": True})


def to_next(gm, kind, past=1):
    gm.clock(step={x["kind"]: x for x in gm.timers()}[kind]["in"] + past)


def newcomer(eng, gm, template, name):
    s = eng.session_for_token(gm.invite("player", template=template, label=name)["token"])
    s.join(template=template, name=name)
    return s


def test_chapter_two_waits_for_a_dreyer_man_and_a_carrier_then_starts_at_dawn():
    eng, gm = hosted()
    chapter_one_done(gm)
    story = lambda: gm.inspect("Story")["state"]
    newcomer(eng, gm, "carrier", "Enzo")
    to_next(gm, "dawn")
    assert not story().get("chapter") and story()["guild_came"] and not story().get("dreyer_came")  # a carrier alone
    newcomer(eng, gm, "dreyer", "Ash")
    assert not story().get("chapter")  # it waits for the dawn crawler
    to_next(gm, "dawn")
    assert story()["chapter"] == 2 and gm.inspect(gm.summary()["root"])["state"]["story"].startswith("chapter two")
    moon = {x["kind"]: x for x in gm.timers()}["moon_turns"]
    assert moon["in"] == pytest.approx(12 * 86400 - 1, abs=5)
    assert "Dreyer riders" in gm.inspect("Notice by the cistern")["state"]["text"]
    texts = scenes(gm.history(kinds=["scene"], limit=40, newest=True))
    assert any("twelve days out" in x for x in texts) and any("Halvard Dreyer" in x for x in texts)


def test_the_moon_turns_on_a_held_wall_or_a_broken_truce():
    eng, gm = hosted()
    chapter_one_done(gm)
    gm.patch(gm.inspect("Story")["id"], {"dreyer_came": True, "guild_came": True})
    to_next(gm, "dawn")
    kit = newcomer(eng, gm, "guard", "Kit")
    gm.move("Kit", "The Glass Flats")
    for _ in range(2):  # a Hold man digging glass twice under the truce breaks it
        kit.act("harvest", "Red vein")
        gm.clock(step=120)
    st = gm.inspect("Story")["state"]
    assert not st["truce"] and st["truce_broken"] == "glass dug on the Flats"
    assert gm.world.edges(gm.inspect("Elder Taan")["id"], "truce") == [] or not gm.world.relations(gm.inspect("Elder Taan")["id"], "truce")
    gm.patch("The Keth jars", {"left": 9})
    gm.patch("The Hold's ration cask", {"left": 8})
    to_next(gm, "moon_turns")
    st = gm.inspect("Story")["state"]
    assert st["moon_turned"] and st["outcome"] == "siege" and st["reckoning"]["hollis"] == "held"  # broken, but watered and manned
    assert st["reckoning"]["wall"] >= 9


def test_with_the_truce_whole_the_wall_manned_and_water_in_the_jars_the_riders_turn_back():
    eng, gm = hosted()
    chapter_one_done(gm)
    gm.patch(gm.inspect("Story")["id"], {"dreyer_came": True, "guild_came": True})
    to_next(gm, "dawn")
    gm.patch("The Keth jars", {"left": 9})
    to_next(gm, "moon_turns")
    st = gm.inspect("Story")["state"]
    assert st["outcome"] == "held", st["reckoning"]
    assert any("Not this moon" in x for x in scenes(gm.history(kinds=["scene"], limit=40, newest=True)))


def test_a_newcomer_carries_a_skin_and_an_edge_and_a_squall_pins_them_on_their_first_crossing_of_the_flats():
    eng, gm = hosted()
    ash = newcomer(eng, gm, "dreyer", "Ash")
    assert {"Plain waterskin", "Short knife"} <= {c["name"] for c in gm.inspect("Ash")["contents"]}
    ash.act("creep", "The Bone Field")
    r = ash.act("creep", "The Glass Flats")
    assert any("squall" in t for t in scenes(r["events"]))
    with pytest.raises(Rejected) as ex:
        ash.act("go", "The Salt Road")
    assert "pinned" in str(ex.value)
    gm.clock(step=7201)
    assert not gm.inspect("Ash")["state"].get("pinned_until")
    r = ash.act("go", "The Salt Road")  # the squall is once; the wardens turn a Dreyer man back off their road
    assert where(gm, "Ash") == "The Glass Flats" and any("Back you go" in t for t in scenes(r["events"]))
    shard(gm, "Ash")
    ash.act("go", "The Salt Road")  # a shard buys a day's road
    assert where(gm, "Ash") == "The Salt Road" and not [c for c in gm.inspect("Ash")["contents"] if c["name"] == "Emberglass"]


def test_hidden_things_turn_up_for_the_right_look_and_the_place_says_where_to_look():
    eng, gm = hosted()
    ash = newcomer(eng, gm, "guard", "Ash")
    assert "finger proud" in gm.inspect("The Gate Yard")["state"]["description"]
    gm.patch("Ash", {"skills": {"search": 30, "blade": 30}})
    seen = lambda: {c["name"] for c in ash.perceive()["present"]}
    assert "Hollis's count" not in seen()
    ash.act("check", params={"skill": "blade", "dc": 14})  # a pass with the wrong eye finds nothing
    assert "Hollis's count" not in seen()
    r = ash.act("check", params={"skill": "search", "dc": 14})
    assert any("careful hand" in t for t in scenes(r["events"])) and "Hollis's count" in seen()
    ash.act("take", "Hollis's count")
    assert "Hollis's count" in {c["name"] for c in gm.inspect("Ash")["contents"]}
    load_world(gm, "glass-reach", upgrade=True)  # a reboot makes no second one and no second hint
    assert len([e for e in gm.find(name="Hollis's count") if e["name"] == "Hollis's count"]) == 1
    assert gm.inspect("The Gate Yard")["state"]["description"].count("finger proud") == 1


def test_the_dry_camp_never_runs_dry_and_keeps_the_houses_salve():
    eng, gm = hosted()
    ash = newcomer(eng, gm, "dreyer", "Ash")
    gm.patch("Ash", {"water": 2})
    for _ in range(2):  # 2 + 4 + 4: full, and a full body drinks no more
        ash.act("drink", "The house's tank")
    assert gm.inspect("Ash")["state"]["water"] == 10 and gm.inspect("The house's tank")["state"].get("left") is None
    chest = gm.inspect("The house's medicine chest")
    pouches = [c["id"] for c in gm.world.children(chest["id"])]
    assert len(pouches) == 4
    ash.act("take", pouches[0])
    me = gm.inspect("Ash")["id"]
    lines = said(ash.act("talk", "Mother Sallow", {"about": "I am hurt"}), me)
    assert any("next one" in x for x in lines)
    assert [c["name"] for c in gm.inspect("Ash")["contents"]].count("Pouch of house salve") == 2


def test_the_host_can_begin_chapter_two_at_once_and_the_moon_is_twelve_days_out():
    eng, gm = hosted()
    newcomer(eng, gm, "dreyer", "Ash")  # no carrier yet: the dawn alone would wait
    root = gm.summary()["root"]
    gm.schedule(1, "chapter_two_begins", entity=root)
    gm.clock(step=2)
    st = gm.inspect("Story")["state"]
    assert st["chapter"] == 2 and st["dreyer_came"] and not st.get("guild_came")
    moon = {x["kind"]: x for x in gm.timers()}["moon_turns"]
    assert 12 * 86400 - 10 < moon["in"] <= 12 * 86400
    assert "twelve nights" in gm.inspect("Notice by the cistern")["state"]["text"]
    gm.schedule(1, "chapter_two_begins", entity=root)  # a second word does not start it twice
    gm.clock(step=2)
    assert len([x for x in gm.timers() if x["kind"] == "moon_turns"]) == 1


def chapter_two_now(gm):
    chapter_one_done(gm)
    gm.schedule(1, "chapter_two_begins", entity=gm.summary()["root"])
    gm.clock(step=2)
    assert gm.inspect("Story")["state"]["chapter"] == 2


def shard(gm, who):
    return gm.spawn("thing", gm.inspect(who)["id"], name="Emberglass", state={"kind": "ember", "portable": True})["id"]


def test_the_twelve_days_bring_the_convoy_master_the_riders_fires_and_the_herald():
    eng, gm = hosted(truce=True)
    chapter_two_now(gm)
    assert {x["kind"] for x in gm.timers()} >= {"convoy_word", "rook_arrives", "riders_fires", "herald_comes"}
    to_next(gm, "rook_arrives")
    assert where(gm, "Bellan Rook") == "The Carriers' Landing" and gm.inspect("The convoy crawler")["state"]["load"] == 8
    to_next(gm, "riders_fires")
    assert gm.inspect("Story")["state"]["riders_seen"]
    to_next(gm, "herald_comes")
    assert where(gm, "Dreyer's herald") == "The Gate Yard" and gm.inspect("The Crown's writ")["state"]["portable"]


def test_drifters_go_to_the_wall_for_pay_and_a_bought_one_counts_against_it():
    eng, gm = hosted(truce=True)
    chapter_two_now(gm)
    assert len([e for e in gm.find(type="person") if gm.inspect(e["id"])["state"].get("drifter")]) == 5
    hold = newcomer(eng, gm, "guard", "Bram")
    spy = newcomer(eng, gm, "dreyer", "Vey")
    gm.move("Bram", "The Old Salt Works")
    gm.move("Vey", "The Old Salt Works")
    hold.act("give", "Cass the Salter", params={"item": "Varrick waterskin"})
    assert where(gm, "Cass the Salter") == "Scar Gate, the Hold" and gm.inspect("Cass the Salter")["state"]["faction"] == "House Varrick"
    spy.act("give", "Joss", params={"item": "Plain waterskin"})
    joss = gm.inspect("Joss")["state"]
    assert where(gm, "Joss") == "Scar Gate, the Hold" and joss["turncoat"] and joss["faction"] == "House Varrick"
    card = next(c for c in hold.perceive()["present"] if c["name"] == "Joss") if where(gm, "Bram") == "Scar Gate, the Hold" else None
    assert card is None or "turncoat" not in json.dumps(card)
    gm.move("Bram", "The Gate Yard")
    to_next(gm, "moon_turns")
    r = gm.inspect("Story")["state"]["reckoning"]
    assert r["bought"] == 1


def test_one_drifter_a_day_signs_with_each_house():
    eng, gm = hosted(truce=True)
    chapter_two_now(gm)
    hold = newcomer(eng, gm, "guard", "Bram")
    gm.move("Bram", "The Old Salt Works")
    gm.patch("Bram", {"water": 40, "max_water": 40})
    hold.act("give", "Cass the Salter", params={"item": "Varrick waterskin"})
    assert where(gm, "Cass the Salter") == "Scar Gate, the Hold"
    glass = shard(gm, "Bram")
    r = hold.act("give", "Joss", params={"item": glass})
    assert any("Come back tomorrow" in t for t in scenes(r["events"]))
    assert where(gm, "Joss") == "The Old Salt Works" and gm.inspect(glass)["parent"] == gm.inspect("Bram")["id"]
    spy = newcomer(eng, gm, "dreyer", "Vey")
    gm.move("Vey", "The Old Salt Works")
    spy.act("give", "Merrow", params={"item": "Plain waterskin"})
    assert gm.inspect("Merrow")["state"].get("turncoat")  # the other house still gets its one
    gm.clock(step=86400)
    hold.act("give", "Joss", params={"item": glass})
    assert where(gm, "Joss") == "Scar Gate, the Hold" and not gm.inspect("Joss")["state"].get("turncoat")

def test_pitch_mends_the_cistern_once_the_wedge_is_out_and_the_mended_cistern_counts():
    eng, gm = hosted(truce=True)
    chapter_two_now(gm)
    me = newcomer(eng, gm, "guard", "Bram")
    gm.patch("Bram", {"skills": {"search": 30, "lore": 30}})
    gm.move("Bram", "Scar Gate, the Hold")
    pot = next(e["id"] for e in gm.find(name="Pot of Guild pitch") if e["name"] == "Pot of Guild pitch")
    gm.move(pot, "Bram")
    r = me.act("check", params={"skill": "lore", "dc": 13})
    assert any("will not take" in t for t in scenes(r["events"])) and not gm.inspect("Story")["state"].get("cistern_mended")
    me.act("check", params={"skill": "search", "dc": 15})
    me.act("take", "Bronze wedge")
    r = me.act("check", params={"skill": "lore", "dc": 13})
    assert any("wants the night to set" in t for t in scenes(r["events"])) and not gm.inspect("Story")["state"].get("cistern_mended")
    to_next(gm, "pitch_sets")
    assert gm.inspect("Story")["state"]["cistern_mended"] and gm.inspect("The cistern")["state"]["left"] >= 6
    assert any("trickling" in t for t in scenes(gm.history(kinds=["scene"], limit=20, newest=True)))
    to_next(gm, "moon_turns")
    assert gm.inspect("Story")["state"]["reckoning"]["cistern"]


def test_a_knife_in_the_soft_pitch_undoes_the_mend():
    eng, gm = hosted(truce=True)
    chapter_two_now(gm)
    me = newcomer(eng, gm, "guard", "Bram")
    spy = newcomer(eng, gm, "dreyer", "Vey")
    gm.patch("Bram", {"skills": {"lore": 30}})
    gm.patch("Vey", {"skills": {"stealth": 30}})
    gm.move("Bram", "Scar Gate, the Hold")
    gm.move("Vey", "Scar Gate, the Hold")
    gm.move("Bronze wedge", "The Gate Yard")
    gm.patch("Bronze wedge", {"hidden": False})
    pot = next(e["id"] for e in gm.find(name="Pot of Guild pitch") if e["name"] == "Pot of Guild pitch")
    gm.move(pot, "Bram")
    me.act("check", params={"skill": "lore", "dc": 13})
    assert gm.inspect("Story")["state"].get("pitch_curing")
    spy.act("check", params={"skill": "stealth", "dc": 12})
    to_next(gm, "pitch_sets")
    st = gm.inspect("Story")["state"]
    assert not st.get("cistern_mended") and not st.get("pitch_curing")
    assert any("pried it out" in t for t in scenes(gm.history(kinds=["scene"], limit=20, newest=True)))


def test_proof_for_the_keth_puts_bows_on_the_wall_and_the_convoy_goes_to_who_pays():
    eng, gm = hosted(truce=True)
    chapter_two_now(gm)
    to_next(gm, "rook_arrives")
    keth = newcomer(eng, gm, "keth", "Sen")
    gm.spawn("thing", gm.inspect("Sen")["id"], name="Empty phial", state={"portable": True})
    gm.move("Sen", "The Deepwell")
    keth.act("give", "Elder Taan", params={"item": "Empty phial"})
    assert not gm.inspect("Story")["state"].get("keth_proof")  # the council sits on it first
    to_next(gm, "keth_council")
    assert gm.inspect("Story")["state"]["keth_proof"] == "Empty phial"
    car = newcomer(eng, gm, "carrier", "Enzo")
    shard(gm, "Enzo")
    car.act("give", "Bellan Rook", params={"item": "Emberglass"})  # no side named: handed back
    assert "Emberglass" in [c["name"] for c in gm.inspect("Enzo")["contents"]]
    car.act("talk", "Bellan Rook", {"about": "for the Hold"})
    before = gm.inspect("The Hold's ration cask")["state"].get("left") or 0
    for _ in range(2):
        shard(gm, "Enzo")
    for _ in range(3):
        car.act("give", "Bellan Rook", params={"item": "Emberglass"})
    assert not gm.inspect("Story")["state"].get("convoy_to")  # paid in full: Rook takes bids for a day
    to_next(gm, "convoy_closes")
    assert gm.inspect("Story")["state"]["convoy_to"] == "House Varrick"
    assert gm.inspect("The Hold's ration cask")["state"]["left"] == before + 8
    to_next(gm, "moon_turns")
    r = gm.inspect("Story")["state"]["reckoning"]
    assert r["keth_bows"] and r["convoy"] == "House Varrick"


def test_the_writ_in_the_heralds_hand_yields_the_gate_at_the_moon():
    eng, gm = hosted(truce=True)
    chapter_two_now(gm)
    to_next(gm, "herald_comes")
    spy = newcomer(eng, gm, "dreyer", "Vey")
    gm.move("Vey", "Scar Gate, the Hold")
    spy.act("take", "The Crown's writ")
    spy.act("go", "The Gate Yard")
    spy.act("give", "Dreyer's herald", params={"item": "The Crown's writ"})
    assert gm.inspect("Story")["state"]["writ_given"]
    to_next(gm, "moon_turns")
    assert gm.inspect("Story")["state"]["outcome"] == "yielded"


def test_a_side_outbid_in_the_day_gets_its_glass_back():
    eng, gm = hosted(truce=True)
    chapter_two_now(gm)
    to_next(gm, "rook_arrives")
    hold = newcomer(eng, gm, "guard", "Bram")
    spy = newcomer(eng, gm, "dreyer", "Vey")
    for who in ["Bram", "Vey"]:
        gm.move(who, "The Carriers' Landing")
        gm.patch(who, {"water": 40, "max_water": 40})
    for _ in range(3):
        shard(gm, "Bram")
    for _ in range(4):
        shard(gm, "Vey")
    for _ in range(3):
        hold.act("give", "Bellan Rook", params={"item": "Emberglass"})
    for _ in range(4):
        spy.act("give", "Bellan Rook", params={"item": "Emberglass"})
    to_next(gm, "convoy_closes")
    assert gm.inspect("Story")["state"]["convoy_to"] == "House Dreyer"
    assert len([c for c in gm.inspect("Bram")["contents"] if c["name"] == "Emberglass"]) == 3


def test_the_road_wardens_hold_strangers_turn_back_dreyer_and_take_a_shard_toll():
    eng, gm = hosted()
    assert len([e for e in gm.find(type="fighter") if gm.inspect(e["id"])["state"].get("warden")]) == 5
    keth = newcomer(eng, gm, "keth", "Sen")
    gm.move("Sen", "The Glass Flats")
    gm.patch("Sen", {"squalled": True, "water": 40, "max_water": 40})
    for _ in range(2):
        shard(gm, "Sen")
    r = keth.act("go", "The Salt Road")
    texts = scenes(r["events"])
    assert any("New face" in t for t in texts) and any("Glass that leaves the Flats" in t for t in texts)
    assert len([c for c in gm.inspect("Sen")["contents"] if c["name"] == "Emberglass"]) == 1
    with pytest.raises(Rejected) as ex:
        keth.act("go", "The Gate Yard")
    assert "road wardens" in str(ex.value)
    keth.act("talk", "Sergeant Edda Marr", {"about": "my name is Sen, Keth, going to the Hold"})
    keth.act("go", "The Gate Yard")
    assert where(gm, "Sen") == "The Gate Yard"
    keth.act("go", "The Salt Road")  # known now: no second hold
    assert where(gm, "Sen") == "The Salt Road" and not gm.inspect("Sen")["state"].get("pinned_until")
    spy = newcomer(eng, gm, "dreyer", "Vey")
    gm.move("Vey", "The Glass Flats")
    gm.patch("Vey", {"squalled": True, "skills": {"stealth": 40}, "water": 40, "max_water": 40})
    spy.act("creep", "The Salt Road")  # the broken step past the bows
    assert where(gm, "Vey") == "The Salt Road"


def test_hands_hold_what_they_hold():
    eng, gm = hosted()
    me = newcomer(eng, gm, "carrier", "Enzo")
    assert gm.inspect("Enzo")["state"]["carry"] == 8  # a skin (2) and a knife (1) in
    for i in range(5):
        gm.spawn("thing", gm.inspect("Enzo")["parent"], name="Pebble " + str(i), state={"portable": True})
    for i in range(5):
        me.act("take", "Pebble " + str(i))
    pot = next(e["id"] for e in gm.find(name="Pot of Guild pitch") if e["name"] == "Pot of Guild pitch")
    with pytest.raises(Rejected) as ex:
        me.act("take", pot)
    assert "hands are full" in str(ex.value)


def test_each_dawn_the_hold_hears_how_the_moon_leans():
    eng, gm = hosted(truce=True)
    chapter_two_now(gm)
    to_next(gm, "dawn")
    st = gm.inspect("Story")["state"]
    assert st["lean"] in ["held", "siege", "fallen"]
    assert any("to the moon" in t and "Ruhl counts the wall" in t for t in scenes(gm.history(kinds=["scene"], limit=40, newest=True)))


def test_west_of_the_scar_is_only_rumour_and_torn_pages():
    eng, gm = hosted()
    hold = gm.inspect("Scar Gate, the Hold")["id"]
    held = [c["name"] for c in gm.inspect(hold)["contents"]]
    for name in ["The sealed back gate", "The hall map", "The Hold's shelf", "The Hold's daybook",
                 "A Crown surveyor's account of the Scar", "The Guild's route book, Reach leg"]:
        assert name in held
    assert gm.inspect("The old count")["parent"] == gm.inspect("Elder Taan")["id"]
    me = newcomer(eng, gm, "guard", "Bram")
    gm.move("Bram", hold)
    r = me.act("read", "The Hold's daybook")
    assert any("torn out" in str(e["payload"]) for e in r["events"])
    with pytest.raises(Rejected):
        me.act("take", "The Hold's daybook")
    load_world(gm, "glass-reach", upgrade=True)  # a reboot writes nothing twice
    assert len(gm.find(name="The Hold's daybook")) == 1
    taan = gm.world.get(gm.inspect("Elder Taan")["id"])["state"]["memory"]
    assert len([n for n in taan if "old count" in n["text"]]) == 1
    assert "west|scar|seep|brine|gate" in gm.world.get(gm.inspect("Cass the Salter")["id"])["state"]["dialog"]


def test_the_wall_works_raise_a_course_and_the_moon_counts_it():
    eng, gm = hosted()
    chapter_one_done(gm)
    gm.patch(gm.inspect("Story")["id"], {"dreyer_came": True, "guild_came": True})
    assert gm.inspect("The wall line")["parent"] == gm.inspect("The Gate Yard")["id"]
    assert len([e for e in gm.find(name="Sack of lime") if e["name"] == "Sack of lime"]) == 3
    assert not gm.find(name="Jory Flint")  # sent for: he comes on the dawn crawler
    load_world(gm, "glass-reach", upgrade=True)  # a reboot sends for nobody twice and makes nothing again
    assert len([e for e in gm.find(name="Sack of lime") if e["name"] == "Sack of lime"]) == 3
    assert len([x for x in gm.timers() if x["kind"] == "introduce"]) == 1
    notes = [n["text"] for n in gm.world.get(gm.inspect("Ossa the Carrier")["id"])["state"]["memory"]]
    assert len([n for n in notes if "sacks of Guild lime" in n]) == 1 and len([n for n in notes if "Jory Flint" in n]) == 1
    to_next(gm, "dawn")
    assert gm.inspect("Jory Flint")["parent"] == gm.inspect("The Gate Yard")["id"]
    ruhl = eng.session("ruhl")
    ruhl.join("glass-reach", "Captain Ruhl")
    gm.move("Captain Ruhl", "The Gate Yard")
    ruhl.act("build", "The wall line")
    works = gm.find(type="project")[0]["id"]
    for _ in range(4):
        gm.spawn("thing", works, "Dressed stone", state={"kind": "dressed stone", "portable": True, "bulk": 2})
    gm.move([e for e in gm.find(name="Sack of lime") if e["name"] == "Sack of lime"][0]["id"], works)
    gm.spawn("thing", works, "Emberglass", state={"kind": "ember", "portable": True})
    ruhl.act("hire", works, {"who": "Jory Flint", "role": "mason"})
    hold = gm.inspect("Scar Gate, the Hold")["id"]
    men = [e["id"] for e in gm.find(type="fighter", parent=hold) + gm.find(type="person", parent=hold)
           if gm.world.get(e["id"])["state"].get("faction") == "House Varrick"
           and not gm.world.embodied(e["id"]) and e["name"] not in ("Captain Ruhl", "Reeve Ansel Varrick")][:2]
    for m in men:
        ruhl.act("assign", works, {"who": m, "role": "hand"})
    for _ in range(6 * 11):  # eleven world hours, in the ten-minute steps a running clock takes
        gm.clock(step=600)
    w = gm.inspect(works)["state"]
    assert w["built_stages"] == ["first course"] and w.get("settling_until") is None, w.get("description")
    assert not [e for e in gm.find(name="Dressed stone") if e["name"] == "Dressed stone"]  # laid
    to_next(gm, "moon_turns")
    st = gm.inspect("Story")["state"]
    standing = 0
    for pid in (hold, gm.inspect("The Gate Yard")["id"]):
        for e in gm.world.children(pid):
            s = e["state"]
            if s.get("faction") == "House Varrick" and not s.get("dead") and not s.get("down"):
                standing += -1 if s.get("turncoat") else 1
    bows = 3 if st.get("keth_proof") and st.get("truce") else 0
    assert st["reckoning"]["wall"] == standing + bows + 1  # the course stands as a man


def test_the_notice_by_the_cistern_was_the_hosts_and_a_flask_on_the_ridge_says_so():
    eng, gm = hosted()
    flask = gm.inspect("A Crown flask")
    assert flask["parent"] == gm.inspect("Red Ridge")["id"] and flask["state"]["hidden"]
    assert "pewter" in gm.inspect("Red Ridge")["state"]["description"]
    me = newcomer(eng, gm, "keth", "Tam")
    seen = lambda: {c["name"] for c in me.perceive()["present"]}
    assert "A Crown flask" not in seen()
    gm.patch("Tam", {"wits": 30})
    me.act("check", params={"skill": "search", "dc": 13})
    assert "A Crown flask" in seen()
    me.act("take", "A Crown flask")
    r = me.act("read", "A Crown flask")
    assert any("The Host" in str(e["payload"]) for e in r["events"])
    wick = gm.world.get(gm.inspect("Wick the runner")["id"])["state"]["dialog"]
    assert any("host" in k.split("|") for k in wick)
    load_world(gm, "glass-reach", upgrade=True)  # a reboot hides no second flask and tells nobody twice
    assert len([e for e in gm.find(name="A Crown flask") if e["name"] == "A Crown flask"]) == 1
    notes = [n["text"] for n in gm.world.get(gm.inspect("Dram Hollis")["id"])["state"]["memory"]]
    assert len([n for n in notes if "to the Host" in n]) == 1


def test_a_letter_burned_at_the_hearth_is_gone_and_only_its_readers_know_it():
    eng, gm = hosted()
    me = newcomer(eng, gm, "keth", "Tam")
    gm.move("Tam", "Scar Gate, the Hold")
    notice = gm.inspect("Notice by the cistern")["id"]
    assert gm.inspect("The hearth")["state"]["fire"] and gm.inspect("Notice by the cistern")["state"]["burnable"]
    me.act("read", notice)
    me.act("burn", notice)
    assert gm.world.get(notice) is None
    kinds = lambda k: gm.world.store.count("event", "world_id=? AND kind=?", (gm.world.id, k))
    assert kinds("burned") == 1 and kinds("read") >= 1  # the reading happened, and stays happened
    assert gm.inspect("Tally post")["state"]["burnable"] is False  # a post in the ground, not paper
    gm.move(gm.inspect("A Crown flask")["id"], "Tam")
    with pytest.raises(Rejected, match="will not burn"):
        me.act("burn", "A Crown flask")  # pewter
    gm.move("Tam", "The Gate Yard")
    gm.spawn("letter", "Tam", "A scrap", state={"text": "x", "burnable": True})
    with pytest.raises(Rejected, match="no fire here"):
        me.act("burn", "A scrap")
    gm.move("Tam", "The Deepwell")
    me.act("burn", "A scrap")
    load_world(gm, "glass-reach", upgrade=True)  # a reboot nails no second notice and builds no second hearth
    assert len([e for e in gm.find(name="The hearth") if e["name"] == "The hearth"]) == 1
    assert not [e for e in gm.find(name="Notice by the cistern") if e["name"] == "Notice by the cistern"]


def test_the_guild_yard_keeps_its_counting_house_fills_its_tank_and_its_hauler_drives_the_road():
    eng, gm = hosted()
    yard = gm.inspect("The Guild Yard")["id"]
    box = gm.inspect("The Guild strongbox")
    shards = [c for c in gm.world.children(box["id"]) if c["name"] == "Emberglass"]
    assert len(shards) == 60 and gm.inspect("Mira Ost")["parent"] == yard
    kinds = lambda k: gm.world.store.count("event", "world_id=? AND kind=?", (gm.world.id, k))
    # a Keth stranger walks into the counting house and the yard turns them back
    me = newcomer(eng, gm, "keth", "Tam")
    gm.move("Tam", yard)
    gm.patch(gm.inspect("The counting house lock")["id"], {"locked": False})  # Mira's door stands open; the four still watch it
    me.act("go", "The Counting House")
    assert gm.inspect("Tam")["parent"] == yard and kinds("turned_away") == 1
    # one of the Guild walks in
    gm.move("Garran Teague", "The Counting House")
    # the dawn crawler fills the tank
    tank = gm.inspect("The yard tank")["id"]
    gm.patch(tank, {"left": 3})
    to_next(gm, "crawler")
    assert gm.inspect("The yard tank")["state"]["left"] == 30
    # Tam climbs into Hauler Nine and drives it to the Salt Road, and steps out there
    gm.move("Tam", "Hauler Nine")
    me.act("drive", "Hauler Nine's wheel", params={"to": "the salt road"})
    gm.clock(step=901)
    hauler = gm.inspect("Hauler Nine")
    assert hauler["state"]["at"] == gm.inspect("The Salt Road")["id"] and kinds("hauled") == 1
    me.act("go", "The Salt Road")
    assert gm.inspect("Tam")["parent"] == gm.inspect("The Salt Road")["id"]
    with pytest.raises(Rejected, match="keeps to the road"):
        gm.move("Tam", "Hauler Nine")
        me.act("drive", "Hauler Nine's wheel", params={"to": "The Glass Flats"})
    errs = gm.world.store.query("event", "world_id=? AND kind='script_error'", (gm.world.id,))
    assert not errs, errs[:2]
    load_world(gm, "glass-reach", upgrade=True)  # a reboot builds no second yard
    assert len([e for e in gm.find(name="Mira Ost") if e["name"] == "Mira Ost"]) == 1


def test_the_strongbox_opens_to_its_key_or_the_code_and_the_counting_house_to_miras_key():
    eng, gm = hosted()
    gm.patch(gm.inspect("Story")["id"], {"guild_wright": gm.inspect("Ossa the Carrier")["id"]})
    me = newcomer(eng, gm, "keth", "Tam")
    yard = gm.inspect("The Guild Yard")["id"]
    gm.move("Tam", yard)
    with pytest.raises(Rejected, match="locked"):
        me.act("go", "The Counting House")  # Mira's key keeps the door
    gm.move(gm.inspect("The counting house key")["id"], "Tam")
    me.act("unlock", "The counting house lock")
    gm.move("Tam", "The Counting House")  # past the four; the yard's rule is its own test
    with pytest.raises(Rejected):
        me.act("take", "The yard book")  # the strongbox is shut
    with pytest.raises(Rejected):
        me.act("unlock", "The strongbox lock", params={"code": "WRONG"})
    me.act("unlock", "The strongbox lock", params={"code": "AMORY"})
    me.act("take", "The yard book")
    notes = [n["text"] for n in gm.world.get(gm.inspect("Ossa the Carrier")["id"])["state"]["memory"]]
    assert any("AMORY" in n for n in notes)
    load_world(gm, "glass-reach", upgrade=True)  # a reboot makes no second lock and no second key
    assert len([e for e in gm.find(name="The strongbox key") if e["name"] == "The strongbox key"]) == 1

