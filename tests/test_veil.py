"""A hidden body shown to some (`shown_to`): a familiar at one person's side. Everyone it is not shown to perceives
nothing of it, in perceive, wait, watch and history; `hands: false` keeps it from things; ctx.ways measures a tether."""

import pytest

from embody.ops import AUTHOR, Rejected
from tests.test_ops import engine_with_two_rooms


def familiar_world():
    eng, w, i = engine_with_two_rooms()
    w.define_schema("familiar", extends="creature", state={"hidden": True, "shown_to": [], "hands": False},
                    actions={"go": {"script": "go", "doc": "Drift to a connected place", "targets": "place"}})
    i["Wisp"] = w.spawn("familiar", i["Cell"], "Wisp")
    i["Witness"] = w.spawn("person", i["Cell"], "Witness")
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    aaron, other, wisp = eng.session("aaron"), eng.session("other"), eng.session("wisp")
    aaron.join("two-rooms", "Prisoner")
    other.join("two-rooms", "Witness")
    wisp.join("two-rooms", "Wisp")
    return eng, w, i, gm, aaron, other, wisp


def heard(s, text):
    """Whether this session can find the line anywhere a player looks: perceive, wait and its own history."""
    seen = [e for e in s.history(limit=500) if text in str((e.get("payload") or {}).get("text"))]
    return bool(seen)


def names(rows):
    return {c["name"] for c in rows}


def test_a_hidden_body_shown_to_no_one_leaves_no_trace():
    eng, w, i, gm, aaron, other, wisp = familiar_world()
    wisp.say("the stone is watching")
    for s in (aaron, other):
        assert "Wisp" not in names(s.perceive()["present"])
        assert not heard(s, "the stone is watching")
        assert "Wisp" not in names(s.wait(timeout=0)["present"])
    assert heard(gm, "the stone is watching")  # the owner sees everything
    assert heard(wisp, "the stone is watching")


def test_shown_to_one_person_and_still_hidden_from_the_rest():
    eng, w, i, gm, aaron, other, wisp = familiar_world()
    gm.patch("Wisp", {"shown_to": [i["Prisoner"]]})
    assert "Wisp" in names(aaron.perceive()["present"])
    assert "Wisp" not in names(other.perceive()["present"])
    wisp.say("look under the bench")
    assert heard(aaron, "look under the bench") and not heard(other, "look under the bench")
    # the one it shows itself to may answer it; the room does not hear him speak to the air
    aaron.say("which bench?", to="Wisp")
    assert heard(wisp, "which bench?") and not heard(other, "which bench?")
    # it can't be heard by someone it has not shown itself to, and is told so
    with pytest.raises(Rejected) as r:
        wisp.say("boo", to="Witness")
    assert "can't hear you" in r.value.reason and "shown_to" in (r.value.hint or "")
    # unseen by the rest, it is not a target: no one strikes or hands things to what they can't see
    with pytest.raises(Rejected):
        other.act("attack", i["Wisp"])


def test_a_veiled_deed_stays_veiled_after_a_later_reveal():
    eng, w, i, gm, aaron, other, wisp = familiar_world()
    wisp.say("before you knew me")
    gm.patch("Wisp", {"shown_to": [i["Witness"]]})
    assert not heard(other, "before you knew me")  # who could witness it was fixed when it was said
    wisp.say("now you know me")
    assert heard(other, "now you know me")


def test_its_comings_and_goings_are_unseen():
    eng, w, i, gm, aaron, other, wisp = familiar_world()
    gm.patch("Iron door", {"open": True, "locked": False})
    guard = eng.session("guard")
    guard.join("two-rooms", "Guard")
    wisp.act("go", "Hall")
    for s in (aaron, other, guard):
        evs = s.history(limit=500)
        assert not any(i["Wisp"] in (e.get("actor"), e.get("target"), (e.get("payload") or {}).get("entity"))
                       for e in evs), s.pid
    assert "Wisp" not in names(guard.perceive()["present"])


def test_no_hands_refuses_a_things_verbs_and_keeps_its_own():
    eng, w, i, gm, aaron, other, wisp = familiar_world()
    with pytest.raises(Rejected) as r:
        wisp.act("open", "Iron door")
    assert "no hands" in r.value.reason
    assert ("open", i["Iron door"]) not in {(a["verb"], a["target"]) for a in wisp.perceive()["affordances"] if a["ok"]}
    gm.patch("Iron door", {"open": True, "locked": False})
    wisp.act("go", "Hall")
    assert w.get(i["Wisp"])["parent_id"] == i["Hall"]


def test_ways_counts_the_ways_between_two_bodies():
    eng, w, i, gm, aaron, other, wisp = familiar_world()
    assert w.ways(i["Prisoner"], i["Witness"]) == 0
    assert w.ways(i["Prisoner"], i["Guard"]) == 1
    assert w.ways(i["Rusty key"], i["Hall"]) == 1  # a thing is where it lies
    assert w.ways(i["Prisoner"], i["Guard"], most=0) is None
    lone = w.spawn("room", w.root_id, "Far room")
    assert w.ways(i["Prisoner"], lone) is None


def test_a_body_it_is_not_shown_to_does_not_hear_its_deeds():
    eng, w, i, gm, aaron, other, wisp = familiar_world()
    w.define_script("notice", "def on(ctx, ev):\n    ctx.patch(ctx.self, {'noticed': ev.kind})\n")
    w.define_script("point", "def apply(ctx):\n    ctx.log('points')\n")
    w.define_schema("watcher", extends="person", listeners=[{"script": "notice", "kinds": ["act"]}])
    w.define_schema("familiar", extends="creature", state={"hidden": True, "shown_to": [], "hands": False},
                    actions={"point": {"script": "point", "doc": "Show someone where to look", "targets": "creature"}})
    eye = w.spawn("watcher", i["Cell"], "Eye")
    wisp.act("point", eye)
    assert w.get(eye)["state"].get("noticed") is None  # it was not shown the wisp
    gm.patch("Wisp", {"shown_to": [eye]})
    wisp.act("point", eye)
    assert w.get(eye)["state"].get("noticed") == "act"
