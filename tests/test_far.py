"""Far views (src/embody/far.py): what carries `far` lines is seen as far as its size allows, capped by the horizon and
the haze; past half its range it shows its far line, inside it its mid line; a container's line stands for what in it is
small; nothing hidden shows unless the viewer knows the way or the world says it is seen, and then without its name."""

from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def skyline():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    root = w.root_id
    tower = gm.spawn("place", root, name="Signal Tower", state={"far": {"far": "a thin grey stalk on the skyline",
                                                                         "mid": "a stone tower, a fire basket on top"}})["id"]
    city = gm.spawn("place", root, name="Varn", state={"far": "a smudge of smoke over a city to the west"})["id"]
    spire = gm.spawn("place", city, name="Varn Spire", state={"far": "a needle of glass"})["id"]
    keep = gm.spawn("place", root, name="Keep of Teeth", state={"hidden": True, "far": {
        "far": "a dark shape on a crag", "seen": True, "called": "a keep on a crag"}})["id"]
    cairn = gm.spawn("place", root, name="Cairn", state={"far": "a heap of stones"})["id"]
    fire = gm.spawn("thing", tower, name="Beacon", state={"hidden": True, "far": "a fire"})["id"]
    gm.layout(frame={"units": "m"}, placements=[
        {"entity": "Cell", "at": [0, 0, 0], "radius": 4}, {"entity": "Hall", "at": [20, 0, 0], "size": [12, 8]},
        {"entity": tower, "at": [0, 5000, 0], "radius": 20, "ceiling": 300},
        {"entity": city, "at": [-40000, 0, 0], "radius": 3000, "ceiling": 100},
        {"entity": spire, "at": [-40000, 0, 0], "radius": 200, "ceiling": 900},
        {"entity": keep, "at": [0, -3000, 0], "radius": 50, "ceiling": 40},
        {"entity": cairn, "at": [0, 20000, 0], "radius": 1},
        {"entity": fire, "at": [0, 5000, 300], "radius": 50}])
    nate = eng.session("nate")
    nate.join("two-rooms", "Prisoner")
    return eng, w, gm, nate


def sight(seat):
    return {(r["name"] or "?"): r for r in seat.perceive(far=True)["in_sight"]}


def test_size_sets_the_range_and_the_band_picks_the_line():
    eng, w, gm, nate = skyline()
    assert "in_sight" not in nate.perceive()  # ordinary perceive stays as it is
    s = sight(nate)
    tower = s["Signal Tower"]
    assert (tower["band"], tower["line"], tower["compass"]) == ("mid", "a stone tower, a fire basket on top", "N")
    assert tower["distance_m"] == 4980 and "hour" in tower["distance"]
    city = s["Varn"]
    assert (city["band"], city["compass"], city["line"]) == ("far", "W", "a smudge of smoke over a city to the west")
    assert "Varn Spire" not in s  # the city's line stands for its spire
    assert "Cairn" not in s and "Beacon" not in s  # too small to see from 20 km; a hidden thing never shows
    keep = s["a keep on a crag"]
    assert keep["id"] is None and keep["line"] == "a dark shape on a crag"  # seen, but nothing revealed
    assert list(s)[0] == "Varn"  # the most prominent first: 6 km of city at 37 km over 300 m of tower at 5 km


def test_merge_size_haze_knowing_the_way_and_indoors():
    eng, w, gm, nate = skyline()
    gm.patch("Varn", {"far": {"far": "a smudge of smoke", "merge_m": 500}})
    gm.patch("Keep of Teeth", {"known_to": [gm.inspect("Prisoner")["id"]]})
    gm.clock(step=3601)  # a new world hour: the cache is fresh
    s = sight(nate)
    assert s["Varn Spire"]["line"] == "a needle of glass"
    assert s["Keep of Teeth"]["id"] is not None
    gm.patch("Cell", {"visibility_m": 1000})  # dust: nothing past a kilometre
    gm.clock(step=3601)
    assert sight(nate) == {}
    gm.patch("Cell", {"visibility_m": None, "indoors": True})
    gm.clock(step=3601)
    b = nate.perceive(far=True)
    assert b["in_sight"] == [] and "indoors" in b["note"]


def test_a_ridge_blocks_what_lies_behind_it_and_aligned_frames_share_a_ruler():
    eng, w, gm, nate = skyline()
    ridge = gm.spawn("place", w.root_id, name="Saw Ridge", state={"occludes": True})["id"]
    gm.layout(placements=[{"entity": ridge, "at": [-10000, 0, 0], "size": [200, 4000], "floor": 0, "ceiling": 400}])
    gm.clock(step=3601)
    s = sight(nate)
    assert "Varn" not in s and "Signal Tower" in s  # behind the ridge to the west; the tower stands north, clear
    gm.layout(placements=[{"entity": ridge, "ceiling": 20}])  # a low bank: the city's smoke shows over it
    gm.clock(step=3601)
    assert "Varn" in sight(nate)

    # a basin laid out in its own frame of metres from the same origin: unseen until its frame says so
    basin = gm.spawn("place", w.root_id, name="The Basin", state={"tier": "region"})["id"]
    kiln = gm.spawn("place", basin, name="Kiln Town", state={"far": "a row of chimneys, smoking"})["id"]
    gm.layout(placements=[{"entity": basin, "frame": {"units": "m"}},
                          {"entity": kiln, "at": [6000, 0, 0], "radius": 400, "ceiling": 40}])
    gm.clock(step=3601)
    assert "Kiln Town" not in sight(nate)
    gm.layout(placements=[{"entity": basin, "frame": {"units": "m", "aligned_with": "Two Rooms"}}])
    gm.clock(step=3601)
    assert sight(nate)["Kiln Town"]["compass"] == "E"


def test_at_night_a_glow_carries_and_the_dark_shapes_close_in_and_smoke_goes_downwind():
    eng, w, gm, nate = skyline()
    gm.patch("Signal Tower", {"far": {"far": "a thin grey stalk", "glow": {"line": "a fire burning on the skyline",
                                                                          "range_m": 60000}}})
    gm.patch("Varn", {"carries": {"smell": {"text": "coal smoke, sour and thick", "range_m": 60000},
                                  "sound": {"text": "a bell, very faint", "range_m": 30000}}})
    gm.patch(w.root_id, {"ambient": {"time_of_day": "night", "wind_from": "W"}})
    s = sight(nate)
    assert s["Signal Tower"]["line"] == "a fire burning on the skyline"
    assert "Varn" not in s  # 37 km of dark city is gone at night
    b = nate.perceive(far=True)
    assert b["smelled"][0]["text"] == "coal smoke, sour and thick" and b["smelled"][0]["compass"] == "W"
    assert "heard" not in b  # the bell carries 30 km; the city's edge is 37 km off
    gm.patch(w.root_id, {"ambient": {"time_of_day": "day", "wind_from": "E"}})
    gm.clock(step=3601)
    b = nate.perceive(far=True)
    assert "smelled" not in b and "Varn" in sight(nate)  # the wind takes the smoke away; by day the city is back
    gm.patch(w.root_id, {"ambient": {"wind_from": None}})
    gm.patch("Varn", {"carries": {"smell": {"range_m": 160000}}})
    gm.clock(step=3601)
    assert nate.perceive(far=True)["smelled"][0]["distance_m"] == 37000  # still air: a quarter of its range


def test_what_stands_out_shows_though_its_container_is_in_sight():
    eng, w, gm, nate = skyline()
    gm.patch("Varn Spire", {"far": {"far": "a needle of glass", "stands_out": True}})  # what moves on a plain, say
    gm.clock(step=3601)
    s = sight(nate)
    assert s["Varn Spire"]["line"] == "a needle of glass" and "Varn" in s and "_out" not in s["Varn Spire"]


def test_a_sound_carries_from_a_place_within_the_listeners_own_even_indoors():
    # a world owner, 2026-11-24: a sound on a balcony laid out beyond a room's window never carried into the room
    eng, w, gm, nate = skyline()
    balcony = gm.spawn("place", "Cell", name="Balcony")["id"]
    gm.spawn("thing", balcony, name="Grinder", state={"carries": {"sound": {"text": "a grindstone's slow rasp", "range_m": 40}}})
    gm.spawn("thing", "Cell", name="Clock", state={"carries": {"sound": {"text": "a tock", "range_m": 40}}})
    gm.layout(placements=[{"entity": balcony, "at": [8, 0, 0], "radius": 2}, {"entity": "Grinder", "at": [8, 0, 0]},
                          {"entity": "Clock", "at": [2, 0, 0]}])
    gm.clock(step=3601)
    heard = [h["text"] for h in nate.perceive(far=True).get("heard", [])]
    assert heard == ["a grindstone's slow rasp"]  # the clock in the cell itself is ordinary perceive, not far
    gm.patch("Cell", {"indoors": True})
    gm.clock(step=3601)
    b = nate.perceive(far=True)
    assert b["in_sight"] == [] and "indoors" in b["note"] and [h["text"] for h in b["heard"]] == ["a grindstone's slow rasp"]
