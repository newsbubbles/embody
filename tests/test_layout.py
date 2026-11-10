"""Layout: one frame over the tree. Where things are, read and measured, without moving anything in the tree."""

import pytest

from embody.ops import AUTHOR, Rejected
from tests.test_ops import engine_with_two_rooms


def laid_out():
    eng, w, i = engine_with_two_rooms()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    r = gm.layout(frame={"units": "m", "bounds": [[-500, -500], [500, 500]]},
                  placements=[{"entity": "Cell", "at": [0, 0], "size": [4, 6, 3]},
                              {"entity": "Hall", "at": [0, 20, 0], "radius": 8, "note": "north of the cell"},
                              {"entity": "Rusty key", "at": [1, 1, 0]}],
                  paths=[{"a": "Cell", "b": "Hall", "route": [[0, 3], [0, 12]]}])
    return eng, w, i, gm, r


def test_a_layout_is_written_in_one_call_and_read_back_level_by_level():
    eng, w, i, gm, r = laid_out()
    assert r["ok"] and r["laid_out"] == 3 and r["paths"] == 1 and r["warnings"] == []
    assert r["frame"]["units"] == "m" and r["frame"]["up"] == "z"
    m = gm.map()
    rows = {e["name"]: e for e in m["entities"]}
    assert rows["Cell"]["at"] == [0, 0, 0] and rows["Cell"]["area"] == 24.0 and rows["Hall"]["own"]
    assert m["paths"][0]["length"] == 9.0 and m["paths"][0]["drawn"] and m["paths"][0]["bearing"][1] in ("N", "S")
    assert "A Cell" in m["sketch"] and "north is up" in m["sketch"]
    inside = gm.map(under="Cell")
    key = next(e for e in inside["entities"] if e["name"] == "Rusty key")
    assert key["own"] and key["at"] == [1, 1, 0]
    door = next(e for e in inside["entities"] if e["name"] == "Iron door")
    assert not door["own"] and door["at"] == [0, 0, 0]  # nothing of its own: it is where the cell is
    # the tree did not move
    assert w.get(i["Rusty key"])["parent_id"] == i["Cell"]


def test_shapes_are_checked_and_what_only_looks_wrong_is_a_warning():
    eng, w, i, gm, r = laid_out()
    with pytest.raises(Rejected):
        gm.layout(placements=[{"entity": "Hall", "radius": 3, "size": [2, 2]}])  # one extent at a time
    with pytest.raises(Rejected):
        gm.layout(placements=[{"entity": "Hall", "footprint": [[0, 0], [1, 1], [2, 2]]}])  # no area
    with pytest.raises(Rejected):
        gm.layout(placements=[{"entity": "Hall", "colour": "red"}])
    with pytest.raises(Rejected):
        gm.layout(paths=[{"a": "Cell", "b": "Cell", "route": [[0, 0], [1, 1]]}])  # not connected
    r = gm.layout(placements=[{"entity": "Rusty key", "at": [40, 40, 0]}])
    assert r["ok"] and any("Rusty key stands outside Cell" in x for x in r["warnings"])
    # a new extent replaces the old one; None deletes a key
    gm.layout(placements=[{"entity": "Hall", "size": [10, 10]}, {"entity": "Cell", "note": None}])
    assert "radius" not in gm.measure("Hall")["a"] and gm.measure("Hall")["a"]["size"] == [10.0, 10.0]


def test_the_ruler_measures_distance_bearing_height_and_containment():
    eng, w, i, gm, r = laid_out()
    m = gm.measure("Cell", "Hall")
    assert m["ground"] == 20.0 and m["bearing"] == "N" and m["degrees"] == 0.0 and m["dz"] == 0.0
    assert m["a_contains"] is False and m["gap_from_a_edge"] == 17.0 and m["overlap"] is False
    assert gm.measure("Cell", "Rusty key")["a_contains"] is True
    east = gm.measure("Hall", point=[8, 20, 0])
    assert east["bearing"] == "E" and east["a_contains"] is True
    up = gm.measure("Cell", point=[0, 0, 5])
    assert up["a_contains"] is False and up["dz"] == 5.0  # above the ceiling
    assert gm.measure("Cell")["a"]["z_range"] == [0.0, 3.0]


def test_a_body_that_changes_place_drops_its_own_spot_and_carries_what_it_holds():
    eng, w, i, gm, r = laid_out()
    gm.layout(placements=[{"entity": "Prisoner", "at": [-1, 2, 0], "size": [0.5, 0.3, 1.8]}])
    s = eng.session("nate")
    s.join("two-rooms", "Prisoner")
    s.act("take", "Rusty key")
    assert gm.measure("Rusty key")["a"]["at"] == [-1, 2, 0] and not gm.measure("Rusty key")["a"]["own"]
    gm.move("Prisoner", "Hall")
    me = gm.measure("Prisoner")["a"]
    assert me["at"] == [0, 20, 0] and not me["own"]  # somewhere in the hall until placed
    assert w.get(i["Prisoner"])["state"]["layout"]["size"] == [0.5, 0.3, 1.8]  # the body keeps its own size


def test_perceive_with_layout_gives_bearings_to_what_is_here_and_to_each_exit():
    eng, w, i, gm, r = laid_out()
    s = eng.session("nate")
    b = s.join("two-rooms", "Prisoner")
    assert "layout" not in b and all("layout" not in c["state"] for c in b["present"])  # out of every card
    b = s.perceive(layout=True)
    lay = b["layout"]
    assert lay["you"] == [0, 0, 0] and lay["here"]["size"] == [4.0, 6.0, 3.0]
    key = next(x for x in lay["present"] if x["name"] == "Rusty key")
    assert key["distance"] == 1.4 and key["bearing"] == "NE"
    hall = next(x for x in lay["exits"] if x["name"] == "Hall")
    assert hall["bearing"] == "N" and hall["straight"] == 20.0 and hall["length"] == 9.0
    with pytest.raises(Rejected):
        s.layout(placements=[{"entity": "Cell", "at": [5, 5]}])  # a player reads the layout, it does not write it


def test_a_grid_inside_a_room_maps_into_the_frame():
    eng, w, i, gm, r = laid_out()
    gm.patch("Hall", {"space": {"dims": 2, "bounds": [10, 10], "grid": True, "frame_origin": [-5, 15, 0], "cell": 1.5}})
    gm.move("Guard", "Hall", pos=[2, 4])
    assert gm.measure("Guard")["a"]["at"] == [-2.0, 21.0, 0.0]
