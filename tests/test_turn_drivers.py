"""A turn-based world with minds (asked by a world builder, 2026-11-22): only the named seats move the paused clock, a
mind's act lands at the time it is, and a long step in a world that catches up replays every beat it passes."""

import pytest

from embody.ops import AUTHOR, Rejected
from tests.test_grants import owner
from tests.test_limits import builder
from tests.test_minds import ferry
from tests.test_ops import engine_with_two_rooms


def test_only_the_drivers_acts_move_the_paused_clock():
    eng, gm = ferry()
    w = gm.world
    gm.clock(turn=10)
    for name in ("Traveler", "Mara"):
        gm.patch(name, {"playable": True})
    p = eng.session_for_token(gm.invite("player", label="Sam")["token"])
    m = eng.session_for_token(gm.invite("mind", entity="Mara", label="mara-mind")["token"])
    p.join("ferry-at-dusk", "Traveler")
    m.join("ferry-at-dusk", "Mara")
    t0 = w.t
    assert m.act("check", "Mara")["elapsed"] == 10 and w.t == t0 + 10  # no drivers named: every seat moves it
    assert gm.clock(drivers=["players"])["drivers"] == ["players"]
    t1 = w.t
    r = m.act("check", "Mara")
    assert r["elapsed"] == 0 and w.t == t1  # the mind's act lands at the time it is
    assert p.act("check", "Traveler")["elapsed"] == 10 and w.t == t1 + 10
    assert gm.clock(drivers=[m.pid])["drivers"] == [m.pid]  # or named principals
    assert p.act("check", "Traveler")["elapsed"] == 0 and m.act("check", "Mara")["elapsed"] == 10
    assert gm.clock(drivers=[])["drivers"] == []  # back to everyone
    assert p.act("check", "Traveler")["elapsed"] == 10


def test_a_long_step_replays_its_beats_only_when_the_world_catches_up():
    eng, w, i = engine_with_two_rooms()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    gm.clock(run=False)
    gm.schedule(60, "bell", entity=w.root_id, every=60)
    before = len(w.events(kinds=["bell"], limit=5000))
    gm.clock(step=600)
    assert len(w.events(kinds=["bell"], limit=5000)) - before == 1  # the default: fires once, skips ahead
    assert gm.clock(catch_up=True)["catch_up"] is True
    before = len(w.events(kinds=["bell"], limit=5000))
    gm.clock(step=600)
    bells = w.events(kinds=["bell"], limit=5000)[before:]
    assert len(bells) == 10 and [b["t"] for b in bells] == sorted(b["t"] for b in bells)
    gm.clock(run=True)
    before = len(w.events(kinds=["bell"], limit=5000))
    w.step(600)
    assert len(w.events(kinds=["bell"], limit=5000)) - before == 1  # a running world still skips a gap


def test_a_limited_grant_cannot_set_who_moves_the_clock():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    b, _ = builder(eng, gm)
    b.use("two-rooms")
    for kw in ({"drivers": ["players"]}, {"catch_up": True}):
        with pytest.raises(Rejected, match="whole world"):
            b.clock(**kw)
    assert b.clock()["drivers"] == [] and b.clock()["catch_up"] is False
