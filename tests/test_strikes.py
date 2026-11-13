"""Strikes take their time: a verb with `strikes: true` holds the striker off that target for a cooldown (longer when
a player or a mind holds either side, none on a paused clock), half of it off anyone, and spends its `cost`."""

import pytest

from embody.world import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def ring(eng):
    gm = owner(eng)
    gm.define_script("jab", "def apply(ctx):\n    ctx.emit('jabbed', target=ctx.target, reach=1)\n")
    gm.define_schema("boxer", extends="creature", state={"breath": 3},
                     actions={"jab": {"script": "jab", "targets": "creature", "scope": "here", "strikes": True,
                                      "cost": {"breath": 1}},
                              "haymaker": {"script": "jab", "targets": "creature", "scope": "here", "strikes": True,
                                           "cooldown_x": 2}})
    for name in ("Ann", "Bo", "Cy"):
        gm.spawn("boxer", "Hall", name, state={"playable": True})
    gm.clock(run=True, rate=4)
    return gm


def test_a_strike_waits_its_cooldown_per_target_and_costs_what_it_says():
    eng, w, i = engine_with_two_rooms()
    gm = ring(eng)
    ann, bo, cy = (gm.inspect(n)["id"] for n in ("Ann", "Bo", "Cy"))
    gm.act_as("Ann", "jab", "Bo")
    assert w.get(ann)["state"]["breath"] == 2
    # nobody holds either side: 15 real seconds, 60 world seconds at 4x; half of it before anyone else
    assert w.strike_wait(ann, bo) == pytest.approx(60, abs=1) and w.strike_wait(ann, cy) == pytest.approx(30, abs=1)
    with pytest.raises(Rejected, match="strike Bo again in about 15 s"):
        gm.act_as("Ann", "jab", "Bo")
    ok, why = w.check_action(ann, "jab", cy)
    assert not ok and "again in about 8 s" in why  # what perceive lists, so an agent never retries blind
    gm.clock(step=31)
    gm.act_as("Ann", "jab", "Cy")  # the floor has passed
    with pytest.raises(Rejected, match="again"):
        gm.act_as("Ann", "jab", "Bo")  # Bo's own cooldown has not, and the floor is back
    gm.clock(step=61)
    gm.act_as("Ann", "jab", "Bo")
    gm.clock(step=61)
    with pytest.raises(Rejected, match="jab costs 1 breath and you have 0"):
        gm.act_as("Ann", "jab", "Cy")
    # a heavy verb holds twice as long
    gm.act_as("Ann", "haymaker", "Cy")
    assert w.strike_wait(ann, cy) == pytest.approx(120, abs=1)


def test_a_held_side_waits_a_readers_time_and_a_paused_clock_none():
    eng, w, i = engine_with_two_rooms()
    gm = ring(eng)
    ann, bo = gm.inspect("Ann")["id"], gm.inspect("Bo")["id"]
    sam = eng.session("sam")
    sam.join("two-rooms", "Bo")
    assert w.strike_cooldown(ann, bo) == pytest.approx(240)  # a minute of real time for the agent to read and decide
    gm.act_as("Ann", "jab", "Bo")
    assert "cooldowns" not in sam.inspect("Ann")["state"]  # the timer is the striker's own
    gm.clock(run=False)
    assert w.strike_cooldown(ann, bo) == 0  # turn-based: the turns are the pace
    w.set_meta({"strike_cooldown": {"held": 30}})
    gm.clock(run=True, rate=2)
    assert w.strike_cooldown(ann, bo) == pytest.approx(60)
