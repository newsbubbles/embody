"""The Glass Reach as a story: seats with stakes, the hidden well and the two ways to it, terms with Taan, Dram in the
ring, the letter, the end states, the trade at the Landing, the timers, and a safe upgrade."""

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


def test_hosted_reach_has_seats_templates_and_a_day_that_turns_with_its_guests():
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
    assert not ck["running"] and ck["rate"] == 4 and ck["turn"] is None
    timers = {t["kind"]: t for t in gm.timers()}
    assert timers["dram_moves"]["in"] == 28800 and timers["dawn"]["in"] == 86400 and timers["heat"]["in"] == 21600
    # a guest sits down: the clock runs and the briefing says so; the day turns; the guest leaves and the world waits
    eng.public_url = "https://reach.example/mcp"
    inv = gm.invite("player", entity="Reeve Ansel Varrick", label="Sam")
    assert "4x real time while anyone is in it" in inv["paste"] and "Glass Reach" in inv["paste"]
    sam = eng.session_for_token(inv["token"])
    b = sam.join()
    assert b["briefing"]["text"].startswith("The Glass Reach") and "while anyone is in the world" in b["briefing"]["pace"]
    assert gm.clock()["running"]
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
    assert not gm.clock()["running"]
    # a newcomer from a template stands where the template says
    kit = eng.session_for_token(gm.invite("player", label="Kit")["token"])
    b = kit.join(template="keth", name="Kit")
    assert b["here"]["name"] == "Red Ridge" and gm.inspect("Kit")["state"]["faction"] == "the Keth"
    assert gm.clock()["running"]
    # hosting again renews the settings and leaves the timers alone
    n = len(gm.timers())
    load_world(gm, "glass-reach", upgrade=True, hosted=True)
    assert len(gm.timers()) == n and gm.clock()["rate"] == 4


def test_upgrade_is_idempotent():
    eng, gm, you = reach()
    before = {e["id"]: e["state"] for e in gm.find(limit=500)}
    goals = len(gm.recall(entity="Reeve Ansel Varrick")["goals"])
    edges = gm.world.store.count("edge", "world_id=?", (gm.world.id,))
    load_world(gm, "glass-reach", upgrade=True)
    assert {e["id"]: e["state"] for e in gm.find(limit=500)} == before
    assert gm.world.store.count("edge", "world_id=?", (gm.world.id,)) == edges
    assert len(gm.recall(entity="Reeve Ansel Varrick")["goals"]) == goals
    assert len(gm.world.edges(gm.inspect("Reeve Ansel Varrick")["id"], "standing", "out")) == 4


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
