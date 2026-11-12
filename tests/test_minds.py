"""Round two: forks, addressed speech, memory, opinions, patch merging, scoped affordances, turns, minds."""

from pathlib import Path

import pytest

from embody.cli import load_world
from embody.mcp_server import Hub
from embody.ops import AUTHOR, OBSERVER, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def ferry():
    eng = Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, REPO / "examples" / "ferry-at-dusk")
    return eng, gm


def test_fork_copies_state_and_history_but_not_principals():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.act("talk", "Mara", {"about": "the ferry"})
    t_before = gm.world.t
    h_before = gm.world.state_hash()
    f = gm.fork_world("ferry-at-dusk", "ferry-2", "Second night")
    assert f["id"] == "ferry-2" and f["name"] == "Second night"
    w2 = eng.world("ferry-2")
    assert w2.state_hash() == h_before
    assert w2.meta()["forked_from"]["world"] == "ferry-at-dusk"
    assert w2.embodied(w2.find(name="Traveler")[0]["id"]) is None
    assert gm.world.embodied(gm.world.find(name="Traveler")[0]["id"]) is not None
    assert gm.world.t == t_before  # the source is untouched
    # the copy carries the log and a `forked` mark of its own
    kinds = [e["kind"] for e in w2.events(since=0, limit=10_000)]
    assert "talked" in kinds and kinds[-1] == "forked"
    # and plays on independently
    p2 = eng.session("p2")
    p2.join("ferry-2", "Traveler")
    p2.act("go", "Pell's Mill")
    assert eng.world("ferry-2").state_hash() != gm.world.state_hash()
    assert gm.world.state_hash() == h_before


def test_addressed_speech_lands_in_both_logs():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    mara = gm.world.find(name="Mara")[0]["id"]
    me = gm.world.find(name="Traveler")[0]["id"]
    r = you.say("Evening. Anything to drink?", to="Mara")
    assert r["event"]["payload"]["to"] == mara
    assert any(e["kind"] == "say" for e in gm.history(touching=mara))
    assert any(e["kind"] == "say" for e in gm.history(touching=me))
    # the table answers a talk; a free line needs an author
    r = gm.say_as("Mara", "Sit down then.", to="Traveler")
    assert r["event"]["actor"] == mara and r["event"]["payload"]["to"] == me
    with pytest.raises(Rejected):
        you.say_as("Mara", "no")
    ex = gm.world.exchanges(mara, me)
    assert len(ex) == 2 and ex[-1]["payload"]["text"] == "Sit down then."


def test_remember_is_secret_and_survives_a_change_of_mind():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.remember("I owe Mara a story.")
    me = you.perceive()["you"]
    assert me["state"]["memory"][0]["text"] == "I owe Mara a story."
    # others never see it
    obs = eng.session("o")
    obs.join("ferry-at-dusk", "Mara")
    trav = next(p for p in obs.perceive()["present"] if p["name"] == "Traveler")
    assert "memory" not in trav["state"]
    # whoever embodies the Traveler next reads the same notes
    you.leave()
    again = eng.session("again")
    first = again.join("ferry-at-dusk", "Traveler")
    assert first["you"]["state"]["memory"][0]["text"] == "I owe Mara a story."
    # authors write for anyone; nobody else does
    gm.remember("Wants the Traveler gone before the fog.", entity="Mara")
    assert gm.inspect("Mara")["state"]["memory"][0]["text"].startswith("Wants")
    with pytest.raises(Rejected):
        again.remember("x", entity="Mara")


def test_opinion_floor_builds_knows_edges_from_exchanges():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.act("talk", "Mara", {"about": "the ferry"})
    you.act("talk", "Mara", {"about": "a light"})
    b = you.perceive()
    k = {x["name"]: x for x in b["knows"]}
    assert "Mara" in k and k["Mara"]["here"] is True and k["Mara"]["count"] >= 2
    assert k["Mara"]["last_exchanges"]
    # Mara's side: a gift given raises standing on the receiver
    you.act("give", "Mara", {"item": "Tinderbox"})
    mb = gm.perceive(from_entity="Mara")
    mine = next(x for x in mb["knows"] if x["name"] == "Traveler")
    assert mine["standing"] >= 2
    # the floor can be switched off
    gm.world.set_meta({"opinion_floor": False})
    before = gm.world.find(name="Mara")[0]["id"]
    n = len(gm.world.edges(before, "knows", "out"))
    you.act("talk", "Mara", {"about": "the fog"})
    assert len(gm.world.edges(before, "knows", "out")) == n


def test_patch_merges_dicts_replaces_on_request_and_deletes_with_none():
    eng, gm = ferry()
    before = gm.inspect("Mara")["state"]["dialog"]
    gm.patch("Mara", {"dialog": {"weather": "Cold tonight."}})
    after = gm.inspect("Mara")["state"]["dialog"]
    assert after["weather"] == "Cold tonight." and all(k in after for k in before)
    gm.patch("Mara", {"dialog": {"only": "this"}}, replace=True)
    assert gm.inspect("Mara")["state"]["dialog"] == {"only": "this"}
    gm.patch("Mara", {"default_line": None})
    assert "default_line" not in gm.inspect("Mara")["state"]


def test_destroyed_event_targets_the_destroyed_entity():
    eng, gm = ferry()
    bone = gm.world.find(name="Bone")[0]["id"]
    gm.destroy("Bone")
    ev = [e for e in gm.world.events(since=0, limit=10_000) if e["kind"] == "destroyed"][-1]  # internal kind, raw log
    assert (ev.get("target") or ev.get("target_id")) == bone and ev["payload"]["name"] == "Bone"


def test_scope_keeps_impossible_pairs_out_of_affordances():
    eng, gm = ferry()
    you = eng.session("you")
    first = you.join("ferry-at-dusk", "Traveler")
    pairs = {(a["verb"], a["target_name"]) for a in first["affordances"]}
    assert ("go", "Ashford Square") not in pairs          # you stand in it
    assert ("drop", "Bone") not in pairs                  # you do not hold it
    assert ("take", "Notice board") in pairs              # here, listed, with the reason it will not budge
    assert ("go", "Pell's Mill") in pairs
    you.act("take", "Bone")
    pairs = {(a["verb"], a["target_name"]) for a in you.perceive()["affordances"]}
    assert ("drop", "Bone") in pairs and ("take", "Bone") not in pairs


def test_turns_move_the_world_while_paused():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    assert gm.clock()["running"] is False and gm.clock()["turn"] == 3
    t0 = gm.world.t
    r = you.act("talk", "Mara", {"about": "tam"})
    assert r["elapsed"] == 3 and r["t"] == pytest.approx(t0 + 3)
    r = you.act("go", "Pell's Mill")            # duration 5 beats the 3 s turn
    assert r["elapsed"] == 5
    gm.clock(turn=0)
    t1 = gm.world.t
    r = you.act("go", "Ashford Square")
    assert "turn" not in r and gm.world.t == t1


def test_dialog_matches_whole_words_aliases_and_state():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    r = you.act("talk", "Mara", {"about": "a song of the pale moon"})   # no "ale" in there
    said = [e["payload"]["text"] for e in r["events"] if e["kind"] == "say"]
    assert any("Ask me something" in s for s in said)
    r = you.act("talk", "Mara", {"about": "an ale, please"})
    said = [e["payload"]["text"] for e in r["events"] if e["kind"] == "say"]
    assert any("One, mind" in s for s in said)
    assert any(h["name"] == "Dark ale" for h in you.perceive()["holding"])
    r = you.act("talk", "Mara", {"about": "another beer"})
    said = [e["payload"]["text"] for e in r["events"] if e["kind"] == "say"]
    assert any("One was the deal" in s for s in said)
    assert sum(1 for h in you.perceive()["holding"] if h["name"] == "Dark ale") == 1
    you.act("drink", "Dark ale")
    r = you.act("drink", "Dark ale")
    mug = next(h for h in you.perceive()["holding"] if h["name"] == "Dark ale")
    assert mug["state"]["left"] == 0  # the mug stays; Mara wants it back
    # the dialog table is secret to other players
    mara = next(p for p in you.perceive()["present"] if p["name"] == "Mara")
    assert "dialog" not in mara["state"] and "gives" not in mara["state"]


def test_mind_on_top_of_the_table():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    mind = eng.session("mara-mind")
    mind.join("ferry-at-dusk", "Mara")
    r = you.act("talk", "Mara", {"about": "the ferry"})
    # the table is quiet while a mind embodies her; the mind hears the question
    assert not any(e["kind"] == "say" for e in r["events"])
    heard = mind.perceive()["events"]
    assert any(e["kind"] == "talked" and e["payload"]["about"] == "the ferry" for e in heard)
    mind.say("Tam's gone up the mill. Ring for him.", to="Traveler")
    assert any(e["kind"] == "say" for e in you.perceive()["events"])
    mind.leave()
    r = you.act("talk", "Mara", {"about": "the fog"})
    assert any(e["kind"] == "say" for e in r["events"])   # the table is back


def test_hub_hands_out_principals_without_author_caps():
    eng, gm = ferry()
    hub = Hub(eng, gm)
    assert hub.session(None) is gm and hub.session("gm") is gm
    m = hub.session("mara")
    assert m.pid == "mara" and m.capabilities == [] and m.world_id == "ferry-at-dusk"
    assert hub.session("mara") is m
    m.join("ferry-at-dusk", "Mara")
    with pytest.raises(Rejected):
        m.spawn("thing", gm.summary()["root"], "x")
    names = {p["principal"]: p["main"] for p in hub.principals()}
    assert names == {"gm": True, "mara": False}


def test_upgrade_redefines_code_and_keeps_state():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.act("take", "Bone")
    h = gm.world.state_hash()
    gm.define_script("read", "def apply(ctx):\n    return 'scribbles'\n")
    r = load_world(gm, REPO / "examples" / "ferry-at-dusk", upgrade=True)
    assert r["upgraded"] is True
    assert gm.world.state_hash() == h
    assert "nothing is written" in gm.script_source("read")["source"]
    assert any(h2["name"] == "Bone" for h2 in you.perceive()["holding"])
    fresh = eng.session("fresh", capabilities=[AUTHOR])
    with pytest.raises(Rejected):
        load_world(fresh, REPO / "examples" / "ferry-at-dusk", upgrade=True)
