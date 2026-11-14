"""Shooting: a bow that fires at someone in sight, ammo that runs down and lands where they stand, cover, the ward,
fighters who cover a road, and a fighter's blows waiting out the engine's strike cooldown."""

import pytest

from embody.ops import Rejected
from packs.d20.tests.test_rules_d20 import reach, state


def kinds(r):
    return [e["kind"] for e in r["events"]]


def range_of(gm):
    """Two open places side by side and a third behind a hidden way, the Reeve in the first with a bow."""
    root = gm.world.root_id
    for name in ("Range A", "Range B", "Range C"):
        gm.spawn("place", root, name)
    gm.connect("Range A", "Range B")
    gm.patch("Range C", {"hidden": True, "known_to": []})
    gm.connect("Range A", "Range C")
    gm.move("Reeve Ansel Varrick", "Range A")
    me = gm.inspect("Reeve Ansel Varrick")["id"]
    gm.spawn("thing", me, "Short bow", state={"weapon": True, "ranged": True, "ammo": "arrow", "damage": 2, "portable": True})
    gm.spawn("thing", me, "Arrows", state={"ammo": "arrow", "count": 3, "portable": True})
    return me


def shootable(you):
    return {a["target_name"]: a for a in you.perceive()["affordances"] if a["verb"] == "shoot"}


def test_a_shot_one_way_over_spends_an_arrow_that_lands_where_they_stand():
    eng, gm, you = reach()
    me = range_of(gm)
    gm.spawn("person", "Range B", "Bandit", state={"hp": 30, "max_hp": 30})
    gm.spawn("person", "Range C", "Lurker", state={"hp": 30, "max_hp": 30})
    can = shootable(you)
    assert can["Bandit"]["ok"] and "Lurker" not in can  # the hidden way is not one he knows
    with pytest.raises(Rejected, match="cannot see"):
        you.act("shoot", "Lurker")

    gm.patch(me, {"wits": 40})  # d20 + 40 - 2 beats any d20 + wits
    r = you.act("shoot", "Bandit")
    assert {"shot", "hit"} <= set(kinds(r)) and r["result"]["far"] is True
    hit = [e for e in r["events"] if e["kind"] == "hit"][0]["payload"]
    assert hit["ranged"] is True and hit["dmg"] == 2 and state(gm, "Bandit")["hp"] == 28
    held = {c["name"]: c for c in gm.world.children(me)}
    assert held["Arrows"]["state"]["count"] == 2
    landed = [c for c in gm.world.children(gm.inspect("Range B")["id"]) if c["name"] == "Arrows"]
    assert len(landed) == 1 and landed[0]["state"].get("count", 1) == 1

    # a ward that is on stops the shot; the arrow still lands, on the same pile
    bandit = gm.inspect("Bandit")["id"]
    gm.spawn("thing", bandit, "Ward", state={"ward": True, "on": True})
    r = you.act("shoot", "Bandit")
    assert r["result"]["warded"] is True and "warded" in kinds(r)
    landed = [c for c in gm.world.children(gm.inspect("Range B")["id"]) if c["name"] == "Arrows"]
    assert len(landed) == 1 and landed[0]["state"]["count"] == 2

    # cover adds to the defence of whoever stands there
    gm.destroy("Ward")
    gm.patch("Range B", {"cover": 100})
    r = you.act("shoot", "Bandit")
    miss = [e for e in r["events"] if e["kind"] == "missed"][0]["payload"]
    assert miss["ranged"] is True and miss["defence"] >= 101

    # out of arrows: refused, with the reason
    assert not shootable(you)["Bandit"]["ok"]
    with pytest.raises(Rejected, match="no arrow left"):
        you.act("shoot", "Bandit")


def test_a_weapon_that_must_be_loaded_and_a_blade_still_strikes():
    eng, gm, you = reach()
    me = range_of(gm)
    gm.patch("Short bow", {"loaded": False})
    gm.spawn("person", "Range A", "Bandit", state={"hp": 30, "max_hp": 30})
    with pytest.raises(Rejected, match="not loaded"):
        you.act("shoot", "Bandit")
    gm.patch("Short bow", {"loaded": True})
    you.act("shoot", "Bandit")
    assert state(gm, "Short bow")["loaded"] is False  # fired: load it again
    # a blow is struck with the blade, never the bow
    gm.spawn("thing", me, "Knife", state={"weapon": True, "damage": 1, "portable": True})
    gm.patch(me, {"body": 40})
    r = you.act("attack", "Bandit")
    assert [e for e in r["events"] if e["kind"] == "hit"][0]["payload"]["weapon"] != "Short bow"


def test_a_warden_with_a_bow_covers_the_road():
    eng, gm, you = reach()
    me = range_of(gm)
    gm.patch(me, {"hp": 50, "max_hp": 50})
    gm.spawn("fighter", "Range B", "Warden", state={"faction": "House Varrick", "wits": 40})
    warden = gm.inspect("Warden")["id"]
    gm.spawn("thing", warden, "Long bow", state={"weapon": True, "ranged": True, "ammo": "arrow", "damage": 1})
    gm.spawn("thing", warden, "Quiver", state={"ammo": "arrow", "count": 5})
    varrick = [f for f in gm.find(type="faction") if f["name"] == "House Varrick"][0]["id"]
    gm.patch(varrick, {"hostile": {me: True}})
    shots = lambda: [e for e in gm.world.events(0, kinds=["hit", "missed", "warded"], limit=5000) if e["payload"].get("by") == warden]
    gm.clock(step=6)
    assert not shots()  # his belt ward is on: a shot would only be stopped, so the warden holds it
    gm.patch("Belt ward", {"on": False})
    gm.clock(step=6)
    assert shots() and shots()[0]["payload"]["ranged"] is True and shots()[0]["target_id"] == me
    assert [c for c in gm.world.children(gm.inspect("Range A")["id"]) if c["name"] == "Quiver"]


def test_a_fighter_waits_out_its_cooldown_longer_on_a_seated_player():
    eng, gm, you = reach()
    me = range_of(gm)
    gm.patch(me, {"hp": 80, "max_hp": 80})
    gm.spawn("fighter", "Range A", "Brute", state={"body": 40, "attacked_by": me})
    brute = gm.inspect("Brute")["id"]
    blows = lambda: [e["t"] for e in gm.world.events(0, kinds=["hit", "missed"], limit=5000) if e["payload"].get("by") == brute]
    gm.clock(run=True, rate=4)
    gm.clock(step=6)
    assert len(blows()) == 1
    for _ in range(30):  # in small steps, as hosted: a big step runs a repeating tick once
        gm.clock(step=6)
    assert len(blows()) == 1  # the Reeve is held: a minute of real time, 240 world seconds at 4x
    you.act("brace")  # acting does not hurry the brute
    for _ in range(12):
        gm.clock(step=6)
    t = blows()
    assert len(t) == 2 and t[1] - t[0] >= 240
    you.act("attack", "Brute")  # his own blows keep the same time: the first goes, the next waits a minute
    with pytest.raises(Rejected, match="strike Brute again in about"):
        you.act("attack", "Brute")


def test_a_heavy_weapon_holds_a_players_next_blow_longer_and_a_light_one_shorter():
    eng, gm, you = reach()
    me = range_of(gm)
    gm.spawn("person", "Range B", "Bandit", state={"hp": 30, "max_hp": 30})
    gm.spawn("person", "Range A", "Thug", state={"hp": 30, "max_hp": 30})
    bandit, thug = gm.inspect("Bandit")["id"], gm.inspect("Thug")["id"]
    gm.clock(run=True, rate=4)
    base = gm.world.strike_cooldown(me, bandit)
    assert base > 0
    gm.patch("Short bow", {"cooldown_x": 2})  # a windlass crossbow: the player waits as long as a fighter would
    you.act("shoot", "Bandit")
    assert gm.world.strike_wait(me, bandit) == pytest.approx(2 * base, abs=1)
    for _ in range(40):
        gm.clock(step=6)
    gm.spawn("thing", me, "Glass needle", state={"weapon": True, "damage": 1, "portable": True, "cooldown_x": 0.5})
    for c in gm.world.children(me):
        if c["state"].get("weapon") and not c["state"].get("ranged") and c["name"] != "Glass needle":
            gm.patch(c["id"], {"weapon": False})  # the needle is the only blade he holds
    you.act("attack", "Thug")
    assert gm.world.strike_wait(me, thug) == pytest.approx(0.5 * base, abs=1)
