"""Two rooms, a locked door, a key. The first world embody ever runs."""

import pytest

from embody.store import Store
from embody.world import Rejected, World

GO = """
def check(ctx):
    here = ctx.actor.parent
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == ctx.target.id:
            door = e["data"].get("via")
            if door and not ctx.get(door).state.open:
                return "the way is shut"
            return True
    return "there is no way there from here"

def apply(ctx):
    ctx.move(ctx.actor, ctx.target)
    ctx.emit("arrived", target=ctx.target, reach=0, who=ctx.actor.id)
"""

OPEN = """
def check(ctx):
    if ctx.target.state.locked:
        return "it is locked"
    if ctx.target.state.open:
        return "it is already open"
    return True

def apply(ctx):
    ctx.target.state.open = True
    ctx.emit("opened", target=ctx.target, reach=1)
"""

UNLOCK = """
def check(ctx):
    if not ctx.target.state.locked:
        return "it is not locked"
    keys = [k for k in ctx.actor.children() if k.state.opens == ctx.target.id]
    if not keys:
        return "you hold no key that fits"
    return True

def apply(ctx):
    ctx.target.state.locked = False
    ctx.emit("unlocked", target=ctx.target, reach=1)
"""

TAKE = """
def check(ctx):
    if ctx.target.parent.id == ctx.actor.id:
        return "you already hold it"
    if not ctx.target.state.portable:
        return "it will not budge"
    return True

def apply(ctx):
    ctx.move(ctx.target, ctx.actor)
"""

ATTACK = """
def apply(ctx):
    dmg = ctx.rand.roll("1d6")
    ctx.target.state.hp = ctx.target.state.hp - dmg
    ctx.emit("hit", target=ctx.target, reach=1, dmg=dmg)
    return dmg
"""

PEACE = """
def on(ctx, event):
    if event.payload["verb"] == "attack":
        ctx.reject("violence is forbidden in this place", "talk instead, or leave")
"""

WANDER = """
def tick(ctx):
    here = ctx.self.parent
    exits = [e for e in ctx.edges(here, "connects_to", "out")]
    if exits:
        ctx.move(ctx.self, exits[0]["target"])
        ctx.say("skitter skitter")
"""


def build(store: Store, seed: int = 7) -> World:
    w = World.create(store, "Two Rooms", seed=seed)
    w.define_script("go", GO)
    w.define_script("open", OPEN)
    w.define_script("unlock", UNLOCK)
    w.define_script("take", TAKE)
    w.define_script("attack", ATTACK)
    w.define_script("peace", PEACE)
    w.define_script("wander", WANDER)
    w.define_schema("room", extends="place")
    w.define_schema("door", extends="thing", state={"open": False, "locked": False},
                    actions={"open": {"script": "open", "doc": "Open it"},
                             "unlock": {"script": "unlock", "doc": "Unlock it with a key you hold"}})
    w.define_schema("key", extends="thing", state={"portable": True, "opens": None})
    w.define_schema("person", extends="creature",
                    actions={"go": {"script": "go", "doc": "Walk to a connected place", "targets": "place"},
                             "take": {"script": "take", "doc": "Pick something up", "targets": "thing"},
                             "attack": {"script": "attack", "doc": "Strike", "targets": "creature"}})
    w.define_schema("rat", extends="creature", behaviors=[{"script": "wander", "every": 5}])
    root = w.root_id
    cell = w.spawn("room", root, "Cell")
    hall = w.spawn("room", root, "Hall")
    door = w.spawn("door", cell, "Iron door", state={"locked": True})
    w.link(cell, hall, "connects_to", {"via": door})
    w.link(hall, cell, "connects_to", {"via": door})
    w.spawn("key", cell, "Rusty key", state={"opens": door})
    w.spawn("person", cell, "Prisoner")
    w.spawn("person", hall, "Guard")
    return w


def ids(w: World) -> dict[str, str]:
    return {e["name"]: e["id"] for e in w.find()}


def test_schema_chain_and_defaults():
    w = build(Store())
    assert [s["id"] for s in w.schema_chain("rat")] == ["rat", "creature", "entity"]
    rat = w.spawn("rat", w.root_id, "Rat")
    assert w.get(rat)["state"]["hp"] == 10
    assert w.is_a("door", "thing") and not w.is_a("door", "creature")


def test_actions_resolve_and_fail_forward():
    w = build(Store())
    i = ids(w)
    with pytest.raises(Rejected) as r:
        w.act(i["Prisoner"], "go", i["Hall"])
    assert "shut" in r.value.reason
    assert r.value.alternatives  # what would work instead
    with pytest.raises(Rejected) as r:
        w.act(i["Prisoner"], "open", i["Iron door"])
    assert "locked" in r.value.reason
    with pytest.raises(Rejected) as r:
        w.act(i["Prisoner"], "unlock", i["Iron door"])
    assert "no key" in r.value.reason
    with pytest.raises(Rejected) as r:
        w.act(i["Prisoner"], "dance")
    assert "go" in r.value.alternatives


def test_escape_rewires_the_graph():
    w = build(Store())
    i = ids(w)
    p, d, k, hall = i["Prisoner"], i["Iron door"], i["Rusty key"], i["Hall"]
    w.act(p, "take", k)
    assert w.get(k)["parent_id"] == p
    w.act(p, "unlock", d)
    res = w.act(p, "open", d)
    assert w.get(d)["state"] == {"description": "", "hidden": False, "open": True, "locked": False}
    assert any(e["kind"] == "opened" for e in res["events"])
    w.act(p, "go", hall)
    assert w.get(p)["parent_id"] == hall
    # from the hall the door is still reachable through the passage it sits in
    assert w.reachable(p, d)[0]
    # the key came along
    assert w.get(k)["parent_id"] == p
    aff = {(a["verb"], a["target"]): a for a in w.affordances(p)}
    assert aff[("go", i["Cell"])]["ok"]
    assert ("take", i["Guard"]) not in aff  # take targets things; the guard is a creature
    assert not aff[("go", i["Hall"])]["ok"]  # listed, with the reason: you are already there
    assert aff[("attack", i["Guard"])]["ok"]


def test_rules_cascade_and_are_scoped():
    w = build(Store())
    i = ids(w)
    g, p = i["Guard"], i["Prisoner"]
    w.act(p, "take", i["Rusty key"])
    w.act(p, "unlock", i["Iron door"])
    w.act(p, "open", i["Iron door"])
    w.act(p, "go", i["Hall"])
    w.set_rule(i["Hall"], "peace", ["before_act"])
    with pytest.raises(Rejected) as r:
        w.act(p, "attack", g)
    assert "forbidden" in r.value.reason and r.value.hint
    assert w.get(g)["state"]["hp"] == 10  # nothing leaked out of the rejected transaction
    w.clear_rule(i["Hall"], "peace")
    res = w.act(p, "attack", g)
    assert w.get(g)["state"]["hp"] == 10 - res["result"]
    assert 1 <= res["result"] <= 6


def test_a_rule_that_walks_the_world_asks_for_its_fuel():
    # the beasts' dawn pass ran out of its 20,000 at a dozen beasts in the Reach and failed the dawn
    w = build(Store())
    root = w.root_id
    w.define_script("counter", "def on(ctx, event):\n    n = 0\n    for i in range(30000):\n        n = n + 1\n"
                               "    ctx.patch(ctx.root(), {'counted': n})\n")
    w.set_rule(root, "counter", ["tally"])
    with pytest.raises(Rejected, match="ran out of fuel"):
        w.emit("tally", target=root)
    w.set_rule(root, "counter", ["tally"], fuel=200_000)
    assert w.get(root)["state"]["rules"][-1]["fuel"] == 200_000
    w.emit("tally", target=root)
    assert w.get(root)["state"]["counted"] == 30000
    with pytest.raises(Rejected, match="fuel is 1 to 1,000,000"):
        w.set_rule(root, "counter", ["tally"], fuel=5_000_000)


def test_behaviors_tick_on_the_clock_and_stop_when_embodied():
    w = build(Store())
    i = ids(w)
    rat = w.spawn("rat", i["Cell"], "Rat")
    assert w.clock()["pending"] == 1
    evs = w.step(5)
    assert w.get(rat)["parent_id"] == i["Hall"]
    assert any(e["kind"] == "say" and e["actor"] == rat for e in evs)
    w.step(5)
    assert w.get(rat)["parent_id"] == i["Cell"]
    assert w.t == 10
    # an embodied rat is driven by its principal, not its script
    w.join("nate", rat)
    w.step(5)
    assert w.get(rat)["parent_id"] == i["Cell"]
    w.leave("nate")
    w.step(5)
    assert w.get(rat)["parent_id"] == i["Hall"]


def test_an_idle_seat_runs_the_bodys_idle_behaviors():
    """Glass Reach night one: minds on watchers held every seat, so no body drank and the bodies dried. A behavior
    marked `idle` runs on a seat that has done nothing for the world's idle_after, as on a body nobody holds."""
    w = build(Store())
    i = ids(w)
    w.define_schema("pet", extends="creature", behaviors=[{"script": "wander", "every": 5, "idle": True}])
    w.set_meta({"idle_after": 20})
    pet = w.spawn("pet", i["Cell"], "Pet")
    w.join("nate", pet)

    def says(n):
        return sum(1 for _ in range(n) for e in w.step(5) if e["kind"] == "say" and e["actor"] == pet)

    assert says(4) == 0  # the seat is fresh
    assert says(4) == 4  # past idle_after: the body sees to itself
    w.touch("nate", 0.0, acted=True)
    assert says(4) == 0  # a deed: the seat is in use again
    w.leave("nate")
    assert says(1) == 1


def test_events_touching_an_entity():
    w = build(Store())
    i = ids(w)
    p, g = i["Prisoner"], i["Guard"]
    cursor = w.store.next_seq(w.id) - 1
    w.act(p, "take", i["Rusty key"])
    w.act(p, "unlock", i["Iron door"])
    w.act(p, "open", i["Iron door"])
    mine = w.events(since=cursor, touching=p)
    theirs = w.events(since=cursor, touching=g)
    assert any(e["kind"] == "unlocked" for e in mine)
    # the guard is in the hall; the door's events reached the cell only
    assert not any(e["kind"] == "unlocked" for e in theirs)


def script_the_escape(w: World) -> None:
    i = ids(w)
    p = i["Prisoner"]
    w.spawn("rat", i["Cell"], "Rat")
    w.act(p, "take", i["Rusty key"])
    w.step(3)
    w.act(p, "unlock", i["Iron door"])
    w.act(p, "open", i["Iron door"])
    w.step(4)
    w.act(p, "go", i["Hall"])
    for _ in range(3):
        w.act(p, "attack", i["Guard"])
    w.step(10)


def test_replay_is_deterministic():
    a, b = build(Store(), seed=42), build(Store(), seed=42)
    script_the_escape(a)
    script_the_escape(b)
    assert a.state_hash() == b.state_hash()
    ka = [(e["kind"], e["actor_id"], e["target_id"]) for e in a.events(limit=10_000)]
    kb = [(e["kind"], e["actor_id"], e["target_id"]) for e in b.events(limit=10_000)]
    assert ka == kb
    c = build(Store(), seed=43)
    script_the_escape(c)
    assert c.state_hash() != a.state_hash()  # the dice differ with the seed


def test_persists_to_a_file_and_reopens(tmp_path):
    path = tmp_path / "w.db"
    w = build(Store(path))
    i = ids(w)
    w.act(i["Prisoner"], "take", i["Rusty key"])
    h = w.state_hash()
    w.store.close()
    w2 = World.open(Store(path), "two-rooms")
    assert w2.state_hash() == h
    assert w2.get(i["Rusty key"])["parent_id"] == i["Prisoner"]


def test_ticks_leave_no_rows_and_a_world_sets_its_own_pace():
    w = build(Store())
    i = ids(w)
    rat = w.spawn("rat", i["Cell"], "Rat")
    evs = w.step(5)
    assert w.get(rat)["parent_id"] == i["Hall"]  # the behavior ran
    assert not w.events(0, kinds=["tick"], limit=5000) and all(e["kind"] != "tick" for e in evs)
    # the world's pace over the schema's every: the standing ticks are re-timed, new spawns take it, a second call is quiet
    assert w.set_pace({"wander": 50}) == 1
    tick = [p for p in w.pending() if p["kind"] == "tick"][0]
    assert tick["every"] == 50 and tick["t"] == w.t + 50
    w.spawn("rat", i["Cell"], "Rat two")
    assert {p["every"] for p in w.pending() if p["kind"] == "tick"} == {50}
    assert w.set_pace({"wander": 50}) == 0 and w.meta()["pace"] == {"wander": 50}
    w.step(49)
    assert w.get(rat)["parent_id"] == i["Hall"]
    w.step(1)
    assert w.get(rat)["parent_id"] == i["Cell"]
