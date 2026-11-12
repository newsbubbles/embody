"""A refused act is logged for the hosts only: the friction a player meets, never news, never another body's."""

import pytest

from embody.world import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def refuse(s, verb, target=None, params=None):
    with pytest.raises(Rejected):
        s.act(verb, target, params)


def test_a_refused_act_is_logged_for_the_hosts_only():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.move("Guard", "Cell")  # a witness in the same room
    nate, sam = eng.session("nate"), eng.session("sam")
    nate.join("two-rooms", "Prisoner")
    sam.join("two-rooms", "Guard")
    sam.perceive()
    for _ in range(3):
        refuse(nate, "go", "Hall")  # the door is locked; a retry of the same refusal is logged once
    refuse(nate, "open", "Rusty key", {"note": "x" * 500})
    refuse(nate, "go", "the moon")

    seen = gm.history(kinds=["act_refused"], touching="Prisoner")
    assert [(e["payload"]["verb"], e["payload"]["asked"]) for e in seen] == [
        ("go", "Hall"), ("open", "Rusty key"), ("go", "the moon")]
    go, op, moon = (e["payload"] for e in seen)
    assert go["target"] == i["Hall"] and go["reason"] and all(e["actor"] == i["Prisoner"] for e in seen)
    assert op["params"]["note"].endswith("...") and len(op["params"]["note"]) <= 160
    assert moon["target"] is None

    # nobody else hears it, and the body's own feed leaves it out (it had the refusal already)
    assert not [e for e in sam.perceive()["events"] if e["kind"] == "act_refused"]
    assert not [e for e in nate.perceive()["events"] if e["kind"] == "act_refused"]
    assert not nate.history(kinds=["act_refused"])
    assert not sam.history(kinds=["act_refused"])

    # a cap per body per world hour, the last one marked; 0 logs none
    w.set_meta({"refused_per_hour": 5})
    for n in range(6):
        refuse(nate, "go", f"nowhere {n}")
    seen = gm.history(kinds=["act_refused"], touching="Prisoner")
    assert len(seen) == 5 and seen[-1]["payload"].get("capped") is True
    w.set_meta({"refused_per_hour": 0})
    refuse(sam, "go", "nowhere")
    assert not gm.history(kinds=["act_refused"], touching="Guard")
