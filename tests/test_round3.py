"""Round three: the privacy leak, speech into the room, opinion payloads, timers, ambient facts, goals, recall."""

from pathlib import Path

import pytest

from embody.cli import load_world_file
from embody.ops import AUTHOR, OBSERVER, Engine, Rejected

WORLDS = Path(__file__).resolve().parent.parent / "worlds"


def ferry():
    eng = Engine()
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world_file(gm, WORLDS / "ferry_at_dusk.py")
    return eng, gm


def test_author_ops_while_embodied_do_not_leak_into_the_players_feed():
    """The bug from playtest two: the narrator embodied the Traveler and also authored; spawn, patch and
    remember were stamped with the Traveler as actor, so Tam's secret memory and the hidden Story's patches
    showed up in the player's own perceive."""
    eng, gm = ferry()
    gm.join("ferry-at-dusk", "Traveler")  # one principal, both hats
    gm.perceive()
    gm.remember("Tam owes Hob three jugs and knows it.", entity="Old Tam")
    gm.patch("Story", {"stage": "secretly_elsewhere"})
    gm.patch("Mara", {"dialog": {"owl": "An owl? At this hour?"}, "mood": "tired"})
    gm.spawn("thing", "Ashford Square", "Stray cat", state={"improvised": True})
    # as the player (a second principal with no author rights) nothing secret shows
    gm.leave()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    b = you.perceive(cursor=0, events=500)
    kinds = [e["kind"] for e in b["events"]]
    assert "remembered" not in kinds
    for e in b["events"]:
        if e["kind"] == "patched":
            assert "dialog" not in e["payload"]["changes"], e
            assert e["target"] != gm.world.find(name="Story")[0]["id"]
    # the public part of the patch on Mara still shows; the spawn shows and names no character as its doer
    pub = [e for e in b["events"] if e["kind"] == "patched" and e["payload"]["changes"].get("mood")]
    assert pub and pub[0]["actor"] is None
    sp = [e for e in b["events"] if e["kind"] == "spawned" and e["payload"]["name"] == "Stray cat"]
    assert sp and sp[0]["actor"] is None
    # Tam's own mind sees its own note
    tam = eng.session("tam-mind")
    tam.join("ferry-at-dusk", "Old Tam")
    tb = tam.perceive(cursor=0, events=500)
    assert any(e["kind"] == "remembered" for e in tb["events"])
    # the author's history shows everything
    assert any(e["kind"] == "remembered" for e in gm.history(limit=500))


def test_unaddressed_say_is_said_into_the_room():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    me = gm.world.find(name="Traveler")[0]["id"]
    square = gm.world.find(name="Ashford Square")[0]["id"]
    r = you.say("Evening, all.")
    assert r["event"]["target"] == square and r["event"]["actor"] == me
    # Mara, in the square, hears it; Hob at the mill does not
    mara = eng.session("mara-mind")
    mara.join("ferry-at-dusk", "Mara")
    assert any(e["kind"] == "say" and e["payload"]["text"] == "Evening, all." for e in mara.perceive(cursor=0)["events"])
    hob = eng.session("hob-mind")
    hob.join("ferry-at-dusk", "Hob")
    assert not any(e["kind"] == "say" and e["payload"]["text"] == "Evening, all." for e in hob.perceive(cursor=0)["events"])
    # addressed speech still targets the listener
    r = you.say("Mara, an ale.", to="Mara")
    assert r["event"]["target"] == gm.world.find(name="Mara")[0]["id"]


def test_opinion_event_names_whose_edge_moved():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.act("go", "Pell's Mill")
    you.act("take", "Sack of flour")
    you.act("give", "Hob", {"item": "Sack of flour"})
    me = gm.world.find(name="Traveler")[0]["id"]
    hob = gm.world.find(name="Hob")[0]["id"]
    ops = [e for e in gm.history(kinds=["opinion"], limit=100) if e["payload"]["kind"] == "given"]
    assert ops
    edges = ops[-1]["payload"]["edges"]
    assert {"holder": hob, "of": me, "delta": 2, "standing": 2} in edges
    assert any(x["holder"] == me and x["of"] == hob and x["delta"] == 0 for x in edges)


def test_timers_list_what_is_scheduled_and_worlds_show_lineage():
    eng, gm = ferry()
    ts = gm.timers()
    assert [t["kind"] for t in ts if t["kind"] == "fog"]
    fog = next(t for t in ts if t["kind"] == "fog")
    assert fog["name"] == "The Landing" and fog["in"] == pytest.approx(fog["at"] - gm.world.t)
    assert not any(t["kind"] == "tick" for t in ts)
    assert gm.clock()["timers"] == ts
    gm.fork_world("ferry-at-dusk", "ferry-3")
    ws = {w["id"]: w for w in gm.worlds()}
    assert ws["ferry-at-dusk"]["forked_from"] is None
    assert ws["ferry-3"]["forked_from"]["world"] == "ferry-at-dusk"


def test_ambient_facts_come_from_root_and_place():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    root = gm.summary()["root"]
    gm.patch(root, {"ambient": {"time_of_day": "dusk", "weather": "clear"}}, replace=True)
    gm.patch("Ashford Square", {"ambient": {"light": "inn lamps"}})
    b = you.perceive()
    assert b["ambient"] == {"time_of_day": "dusk", "weather": "clear", "light": "inn lamps"}
    assert b["clock"]["turn"] == 3 and b["clock"]["running"] is False
    you.act("go", "Pell's Mill")
    assert you.perceive()["ambient"] == {"time_of_day": "dusk", "weather": "clear"}


def test_goals_are_secret_and_managed_by_the_mind():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    r = you.intend("Cross the river tonight", why="Someone is waiting on the far bank")
    g = r["goal"]
    assert g["id"] == "g1" and g["status"] == "active" and g["why"].startswith("Someone")
    you.intend("Find the dog a home", priority=2)
    b = you.perceive()
    assert [x["text"] for x in b["goals"]] == ["Cross the river tonight", "Find the dog a home"]
    you.intend(id="g2", status="dropped")
    assert [x["id"] for x in you.perceive()["goals"]] == ["g1"]
    you.intend(id="g1", why="Someone is waiting, and the fog is coming", priority=0)
    assert you.perceive()["goals"][0]["why"].endswith("coming")
    with pytest.raises(Rejected):
        you.intend(id="g9", status="done")
    with pytest.raises(Rejected):
        you.intend("x", status="later")
    # nobody else sees them: not the card, not the events
    mara = eng.session("mara-mind")
    mara.join("ferry-at-dusk", "Mara")
    mb = mara.perceive(cursor=0, events=500)
    trav = next(c for c in mb["present"] if c["name"] == "Traveler")
    assert "goals" not in trav["state"]
    assert not any(e["kind"] == "intended" for e in mb["events"])
    # authors set goals for NPC minds
    gm.intend("Keep the Traveler drinking so he misses the raft", why="Tam owes me", entity="Mara")
    assert mara.perceive()["goals"][0]["why"] == "Tam owes me"


def test_recall_is_a_graph_query_within_the_minds_permissions():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.say("Any way across tonight?", to="Mara")
    you.act("talk", "Mara", {"about": "the ferry"})
    you.remember("Mara knows more than she says about Tam.")
    you.intend("Get Mara to say where Tam is", why="Mara is the one who knows")
    mara = gm.world.find(name="Mara")[0]["id"]
    me = gm.world.find(name="Traveler")[0]["id"]
    gm.link(mara, me, "knows", {"standing": -1, "note": "pushy"})  # her private view of him
    # around me
    r = you.recall()
    k = [e for e in r["edges"] if e["relation"] == "knows"]
    out = next(e for e in k if e["direction"] == "out" and e["with"] == mara)
    assert "data" in out and out["here"] is True
    inn = next(e for e in k if e["direction"] == "in" and e["with"] == mara)
    assert "data" not in inn  # what Mara thinks of me is hers
    assert r["goals"][0]["text"].startswith("Get Mara")
    # about her
    r = you.recall(about="Mara")
    assert r["about"]["name"] == "Mara" and "dialog" not in r["about"]["state"]
    assert [x["text"] for x in r["exchanges"]][0] == "Any way across tonight?"
    assert any(e["kind"] == "talked" for e in r["between"])
    assert r["notes"][0]["text"].startswith("Mara knows") and r["goals"][0]["why"].startswith("Mara")
    # an author reads her side too
    ra = gm.recall(about="Traveler", entity="Mara")
    assert any(e["direction"] == "out" and e["data"]["note"] == "pushy" for e in ra["edges"])
    # a hidden thing that never crossed your path is nothing to a mind; someone merely elsewhere, you may ask
    # about (you heard the name) and get what you know; an observer may ask anything
    with pytest.raises(Rejected):
        you.recall(about="Story")
    assert you.recall(about="Old Tam")["here"] is False
    obs = eng.session("watch", capabilities=[OBSERVER])
    obs.use("ferry-at-dusk")
    assert obs.recall(about="Story", entity="Traveler")["about"]["name"] == "Story"
