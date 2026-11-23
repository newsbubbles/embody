"""A vehicle keeps a spot on the map (asked by a host, 2026-11-23): on a drawn road it rides the route through each
leg, so the map, apart and nearness see it move, and it ends the leg at the route's end; on a road with no drawing it
pulls up at its `stop_at` for the place; halted, it stands where it was on the road; those aboard ride along."""

import pytest

from embody import positions as posn
from test_vehicles import cart, roll, seat, where, world


def laid(tmp_path):
    eng, gm = world(tmp_path)
    gm.layout(frame={"units": "m"}, placements=[
        {"entity": "Yard", "at": [0, 0, 0], "radius": 20},
        {"entity": "Road", "at": [100, 0, 0], "radius": 30},
        {"entity": "Gate", "at": [200, 0, 0], "radius": 20, "landmarks": {"the arch": {"at": [205, 5, 0], "radius": 2}}}],
        paths=[{"a": "Yard", "b": "Road", "route": [[15, 0, 0], [85, 0, 0]]}])  # Road to Gate is not drawn
    gm.patch("Cart", {"stop_at": {"Gate": "the arch"}})
    ada = seat(eng, "Ada")
    ada.act("board", "Cart")
    return eng, gm, ada


def spot(gm, name):
    return posn.resolve(gm.world, gm.inspect(name)["id"])


def test_on_a_drawn_road_it_rides_the_route_and_ends_at_its_end(tmp_path):
    eng, gm, ada = laid(tmp_path)
    w = gm.world
    ada.act("drive", "Reins", params={"to": "Gate"})
    t0 = cart(gm)["trip"]["t0"]
    roll(w, 30)
    assert where(gm, "Cart") == "Yard"
    s = spot(gm, "Cart")
    assert s["how"] == "own" and s["at"][0] == pytest.approx(15 + 70 * (w.t - t0) / 100, abs=0.01)
    assert spot(gm, "Ada")["at"] == s["at"] and spot(gm, "Ada")["how"] == "inherited"  # she rides along
    roll(w, 40)
    assert where(gm, "Cart") == "Road" and 15 < spot(gm, "Cart")["at"][0] < 85  # in the road, still on the route
    roll(w, 40)  # the leg is done: the next one has no drawing, so it stands at the way's end until it rolls on
    s = spot(gm, "Cart")
    assert s["how"] == "own" and s["at"][0] == pytest.approx(85, abs=4.5)


def test_with_no_drawn_road_it_pulls_up_at_its_stop(tmp_path):
    eng, gm, ada = laid(tmp_path)
    ada.act("drive", "Reins", params={"to": "Gate"})
    roll(gm.world, 260)
    assert where(gm, "Cart") == "Gate" and not cart(gm)["moving"]
    s = spot(gm, "Cart")
    assert s["how"] == "own" and abs(s["at"][0] - 205) <= 2 and abs(s["at"][1] - 5) <= 2
    assert "along" not in cart(gm)["layout"]


def test_halted_on_the_road_it_stands_where_it_was(tmp_path):
    eng, gm, ada = laid(tmp_path)
    w = gm.world
    ada.act("drive", "Reins", params={"to": "Gate"})
    roll(w, 60)
    bel = seat(eng, "Bel")
    bel.act("halt", "Cart")
    held = spot(gm, "Cart")["at"]
    roll(w, 200)
    assert spot(gm, "Cart")["at"] == held and 15 < held[0] < 85
