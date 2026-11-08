"""The ferry world after round three: facts not stages, the Reeds, sleep and wake, followers, night and dawn."""

from pathlib import Path

import pytest

from embody.cli import load_world_file
from embody.ops import AUTHOR, Engine, Rejected

WORLDS = Path(__file__).resolve().parent.parent / "worlds"


def ferry():
    eng = Engine()
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world_file(gm, WORLDS / "ferry_at_dusk.py")
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    return eng, gm, you


def test_reeds_route_wakes_tam_and_he_walks_to_the_raft():
    eng, gm, you = ferry()
    you.act_many([{"verb": "go", "target": "Pell's Mill"}, {"verb": "go", "target": "The Reeds"}])
    here = you.perceive()
    tam = next(p for p in here["present"] if p["name"] == "Old Tam")
    assert tam["state"]["asleep"] is True
    with pytest.raises(Rejected) as rej:
        you.act("talk", "Old Tam", {"about": "the ferry"})
    assert "asleep" in rej.value.reason
    r = you.act("wake", "Old Tam")
    assert any(e["kind"] == "scene" and "Raft is this way" in e["payload"]["text"] for e in r["events"])
    assert not any(p["name"] == "Old Tam" for p in you.perceive()["present"])
    you.act_many([{"verb": "go", "target": "Pell's Mill"}, {"verb": "go", "target": "Ashford Square"},
                  {"verb": "go", "target": "The Landing"}])
    assert any(p["name"] == "Old Tam" for p in you.perceive()["present"])
    st = gm.inspect("Story")["state"]
    assert st["stage"] == "cross" and st["tam_came_by"] == "woken" and st["seen_landing"] is True
    # no fog yet: straight across, no lantern needed, Tam comes along
    you.act("cross", "Ferry raft")
    after = you.perceive()
    assert after["here"]["name"] == "The Far Bank"
    assert any(p["name"] == "Old Tam" for p in after["present"])
    assert gm.inspect("Story")["state"]["crossed"] is True


def test_sleeper_can_only_wake():
    eng, gm, you = ferry()
    you.act("sleep")
    with pytest.raises(Rejected) as rej:
        you.act("go", "Pell's Mill")
    assert "asleep" in rej.value.reason and "wake" in rej.value.hint
    you.act("wake", "Traveler")
    assert you.perceive()["you"]["state"]["asleep"] is False
    # dawn wakes everyone and lifts the fog; night darkens the ambient first
    gm.clock(step=160)
    amb = you.perceive()["ambient"]
    assert amb["time_of_day"] == "night" and "fog" in amb["weather"]
    you.act("sleep")
    gm.clock(step=300)
    b = you.perceive()
    assert b["you"]["state"]["asleep"] is False
    assert b["ambient"]["time_of_day"] == "dawn"
    assert gm.inspect("The Landing")["state"]["fog"] is False
    assert any(e["kind"] == "woken" and e["payload"].get("dawn") for e in you.perceive(cursor=0, events=500)["events"])


def test_followers_come_along_and_the_tinderbox_is_a_real_thing():
    eng, gm, you = ferry()
    tinder = gm.find(name="Tinderbox")[0]
    assert gm.world.need(tinder["id"])["parent_id"] == gm.find(name="Mara")[0]["id"]
    you.act("talk", "Mara", {"about": "I need fire to light it"})  # beats lantern|lamp: two aliases hit
    assert any(h["id"] == tinder["id"] for h in you.perceive()["holding"])
    # the second ask gets the gone line, not a second tinderbox
    r = you.act("talk", "Mara", {"about": "another tinderbox"})
    assert any(e["kind"] == "say" and "already" in e["payload"]["text"] for e in r["events"])
    # a fed dog follows through go, without waiting for its tick
    you.act_many([{"verb": "take", "target": "Bone"}, {"verb": "go", "target": "Pell's Mill"},
                  {"verb": "give", "target": "Biscuit", "params": {"item": "Bone"}},
                  {"verb": "touch", "target": "Biscuit"}, {"verb": "go", "target": "Ashford Square"}])
    assert any(p["name"] == "Biscuit" for p in you.perceive()["present"])


def test_dialog_prefers_the_best_matching_entry():
    eng, gm, you = ferry()
    r = you.act("talk", "Mara", {"about": "how do I get across the river in this fog"})
    lines = [e["payload"]["text"] for e in r["events"] if e["kind"] == "say"]
    assert lines and "Tam" in lines[0]  # ferry|across|crossing scores above fog|weather|dark|night
    r = you.act("talk", "Mara", {"about": "tell me a tale"})
    lines = [e["payload"]["text"] for e in r["events"] if e["kind"] == "say"]
    assert lines and "Ask me something" in lines[0]  # "tale" is not "ale"


def test_check_rolls_a_visible_d20():
    eng, gm, you = ferry()
    r = you.act("check", "Traveler", {"skill": "balance"})
    ev = next(e for e in r["events"] if e["kind"] == "checked")
    assert 1 <= ev["payload"]["roll"] <= 20 and ev["payload"]["skill"] == "balance"


def test_upgrade_brings_an_older_world_up_to_date():
    """A world built without the Reeds, the tinderbox, ambient facts, briefs or the night timers takes them on."""
    eng = Engine()
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world_file(gm, WORLDS / "ferry_at_dusk.py")
    root = gm.summary()["root"]
    # make it look like a round-two world
    gm.destroy("The Reeds")
    gm.destroy("Tinderbox")
    gm.patch(root, {"ambient": None, "policy": None}, replace=True)
    gm.patch("Mara", {"brief": None, "dialog": {"reeds": None}}, replace=False)
    gm.patch("Story", {"reeds": None, "seen_landing": None, "mara_told": None, "crossed": None, "stage": "bell"})
    gm.clear_rule(root, "weather")
    gm.clear_rule(root, "asleep_guard")
    for t in gm.timers():
        if t["kind"] in ("nightfall", "dawn"):
            gm.unschedule(t["id"])
    assert not gm.find(name="The Reeds")
    r = load_world_file(gm, WORLDS / "ferry_at_dusk.py", upgrade=True)
    assert r["upgraded"] is True
    assert gm.find(name="The Reeds") and gm.find(name="Tinderbox")
    assert gm.inspect(root)["state"]["ambient"]["time_of_day"] == "dusk"
    assert gm.inspect("Mara")["state"]["brief"].startswith("You are Mara")
    assert "reeds" in gm.inspect("Mara")["state"]["dialog"]
    st = gm.inspect("Story")["state"]
    assert st["seen_landing"] is True and st["mara_told"] is True and st["crossed"] is False
    assert {t["kind"] for t in gm.timers()} >= {"fog", "nightfall", "dawn"}
    h = gm.world.state_hash()
    load_world_file(gm, WORLDS / "ferry_at_dusk.py", upgrade=True)
    assert gm.world.state_hash() == h


def test_the_raft_crosses_back():
    eng, gm, you = ferry()
    you.act_many([{"verb": "go", "target": "Pell's Mill"}, {"verb": "go", "target": "The Reeds"}, {"verb": "wake", "target": "Old Tam"},
                  {"verb": "go", "target": "Pell's Mill"}, {"verb": "go", "target": "Ashford Square"},
                  {"verb": "go", "target": "The Landing"}, {"verb": "cross", "target": "Ferry raft"}])
    far = you.perceive()
    assert far["here"]["name"] == "The Far Bank"
    assert any(p["name"] == "Ferry raft" for p in far["present"])
    assert not gm.inspect("The Landing")["contents"] or not any(c["name"] == "Ferry raft" for c in gm.inspect("The Landing")["contents"])
    you.act("cross", "Ferry raft")
    back = you.perceive()
    assert back["here"]["name"] == "The Landing"
    assert any(p["name"] == "Old Tam" for p in back["present"]) and any(p["name"] == "Ferry raft" for p in back["present"])
    assert gm.inspect("Story")["state"]["crossed"] is True  # the story completed once, on the way over
