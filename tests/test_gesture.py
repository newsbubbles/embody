"""A player's gesture (asked from a player session, 2026-11-23): NPCs made signs (`gestured`) and players had no way
to. gesture() and say(text, gesture=...) make one: seen by the place, marked as a guest's, never a change to the
world, and a watcher wakes on it."""

import pytest

from embody.ops import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def two_in_a_cell():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    gm.spawn("person", "Cell", "Mara", state={"playable": True})
    sam = eng.session_for_token(gm.invite("player", entity="Prisoner", label="Sam")["token"])
    sam.join()
    ann = eng.session_for_token(gm.invite("player", entity="Mara", label="Ann")["token"])
    ann.join()
    return eng, gm, sam, ann


def signs(s):
    return [e for e in s.perceive()["events"] if e["kind"] == "gestured"]


def test_a_gesture_is_seen_marked_and_changes_nothing():
    eng, gm, sam, ann = two_in_a_cell()
    before = gm.inspect("Prisoner")["state"]
    r = sam.gesture("thumbs his river stone", to="Mara")
    assert r["ok"] and r["event"]["kind"] == "gestured"
    seen = signs(ann)
    assert seen and seen[-1]["payload"]["text"] == "thumbs his river stone" and seen[-1]["untrusted"]
    assert gm.inspect("Prisoner")["state"] == before
    for bad in ("", "x" * 400, "calls act('take')"):
        if not bad:
            assert sam.gesture(bad)["event"] is None
            continue
        with pytest.raises(Rejected):
            sam.gesture(bad)


def test_say_with_a_gesture_makes_the_sign_and_the_line():
    eng, gm, sam, ann = two_in_a_cell()
    r = sam.say("Lucky.", gesture="thumbs his river stone")
    assert r["gesture"]["kind"] == "gestured" and r["event"]["kind"] == "say"
    kinds = [e["kind"] for e in ann.perceive()["events"] if e["kind"] in ("say", "gestured")]
    assert kinds[-2:] == ["gestured", "say"]
    assert sam.say("", gesture="nods")["event"]["kind"] == "gestured"  # a sign alone


def test_a_small_sign_shows_its_text_only_near():
    eng, gm, sam, ann = two_in_a_cell()
    r = sam.gesture("taps the bars twice", low=True)  # a place with no spots: only the one it is to sees it in full
    assert r["seen_by"] == [] and "nobody" in r["note"]
    got = signs(ann)[-1]["payload"]
    assert got.get("seen") is False and "text" not in got


def test_a_watcher_wakes_on_a_sign_and_the_dead_make_none():
    eng, gm, sam, ann = two_in_a_cell()
    sam.gesture("raises a hand")
    got = ann.wait(until="did('gestured', by='Prisoner')", timeout=0.2)
    assert not got.get("timed_out") and any(e["kind"] == "gestured" for e in got["events"])
    gm.patch("Prisoner", {"dead": True})
    with pytest.raises(Rejected):
        sam.gesture("waves")
