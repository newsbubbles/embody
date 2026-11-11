"""The op table as a harness sees it: sessions, perceive, wait, capabilities, spaces, a combat pocket."""

import pytest

from embody.ops import AUTHOR, OBSERVER, Engine, Rejected, call
from tests.test_world import build


def engine_with_two_rooms():
    eng = Engine()
    w = build(eng.store)
    eng._worlds[w.id] = w
    ids = {e["name"]: e["id"] for e in w.find()}
    return eng, w, ids


def test_join_and_perceive_bundle():
    eng, w, i = engine_with_two_rooms()
    s = eng.session("nate")
    b = s.join("two-rooms", "Prisoner")
    assert b["you"]["id"] == i["Prisoner"]
    assert b["here"]["name"] == "Cell" and b["here"]["breadcrumb"][0]["name"] == "Two Rooms"
    names = {c["name"] for c in b["present"]}
    assert names == {"Iron door", "Rusty key"}
    assert b["exits"] == [{"to": i["Hall"], "name": "Hall", "via": i["Iron door"], "via_name": "Iron door",
                           "open": False, "locked": True}]
    verbs = {(a["verb"], a["target"]) for a in b["affordances"]}
    assert ("take", i["Rusty key"]) in verbs and ("unlock", i["Iron door"]) in verbs
    assert ("attack", i["Guard"]) not in verbs  # the guard is in the other room
    # names work as targets; ids too
    s.act("take", "Rusty key")
    s.act("unlock", i["Iron door"])
    res = s.act_many([{"verb": "open", "target": "Iron door"}, {"verb": "go", "target": "Hall"},
                      {"verb": "go", "target": "Hall"}])
    assert res["ok"] is False and res["failed_at"] == 2 and len(res["done"]) == 2
    b = s.perceive()
    assert b["here"]["name"] == "Hall"
    assert [c["name"] for c in b["holding"]] == ["Rusty key"]
    assert any(c["name"] == "Guard" for c in b["present"])
    # the cursor moved past our own acts; nothing new
    assert b["events"] == []


def test_wait_wakes_on_events_that_touch_me():
    eng, w, i = engine_with_two_rooms()
    nate = eng.session("nate")
    nate.join("two-rooms", "Guard")
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    clock = [0.0]
    calls = []

    def fake_sleep(dt):
        clock[0] += dt
        calls.append(dt)
        if len(calls) == 3:
            gm.act_as("Prisoner", "take", "Rusty key")  # not in the hall, the guard does not hear it
        if len(calls) == 5:
            gm.spawn("rat", i["Hall"], "Rat")  # something appears in the hall

    b = nate.wait(timeout=5, clock=lambda: clock[0], sleep=fake_sleep)
    assert "timed_out" not in b
    assert any(e["kind"] == "spawned" and e["payload"]["name"] == "Rat" for e in b["events"])
    assert len(calls) == 5
    b = nate.wait(timeout=0.3, clock=lambda: clock[0], sleep=fake_sleep)
    assert b["timed_out"] is True


def test_capabilities_gate_authoring_and_observing():
    eng, w, i = engine_with_two_rooms()
    player = eng.session("p")
    player.join("two-rooms", "Prisoner")
    with pytest.raises(Rejected) as r:
        player.spawn("rat", i["Cell"], "Rat")
    assert "author" in r.value.reason
    with pytest.raises(Rejected):
        player.inspect("Guard")  # not reachable from the cell
    obs = eng.session("o", capabilities=[OBSERVER])
    obs.use("two-rooms")
    b = obs.perceive(from_entity="Guard")
    assert b["here"]["name"] == "Hall"
    with pytest.raises(Rejected):
        obs.join("two-rooms", "Guard")
    out = call(player, "fly")
    assert out["ok"] is False and "no op" in out["reason"]
    out = call(player, "act", verb="go", target="Hall")
    assert out["ok"] is False and "shut" in out["reason"] and out["alternatives"]


def test_realtime_clock_advances_with_wall_time():
    eng, w, i = engine_with_two_rooms()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    rat = gm.spawn("rat", i["Cell"], "Rat")["id"]
    wall = [100.0]
    eng.now = lambda: wall[0]
    gm.clock(run=True, rate=10)
    wall[0] = 100.6  # 6 world seconds: the rat ticked once
    assert gm.summary()["t"] == pytest.approx(6.0)
    assert w.get(rat)["parent_id"] == i["Hall"]
    wall[0] = 1000.0  # a long gap: the behavior fires once more, it does not replay 1800 ticks
    gm.summary()
    assert w.get(rat)["parent_id"] == i["Cell"]
    assert w.clock()["pending"] == 1


STEP = """
def check(ctx):
    dx = ctx.params.get("dx", 0)
    dy = ctx.params.get("dy", 0)
    if abs(dx) + abs(dy) != 1:
        return "one square at a time"
    return True

def apply(ctx):
    p = ctx.actor.pos
    ctx.set_pos(ctx.actor, [p[0] + ctx.params.get("dx", 0), p[1] + ctx.params.get("dy", 0)])
"""

STRIKE = """
def check(ctx):
    d = ctx.distance(ctx.actor, ctx.target)
    if d is None or d > 1.5:
        return "too far to strike"
    return True

def apply(ctx):
    ctx.target.state.hp = ctx.target.state.hp - 3
    ctx.emit("hit", target=ctx.target, reach=1, dmg=3)
"""

TURNS = """
def on(ctx, event):
    arena = ctx.self
    order = arena.state.order
    if event.payload["verb"] == "step" or event.payload["verb"] == "strike":
        if event.actor != order[arena.state.turn]:
            ctx.reject("not your turn", "wait for " + order[arena.state.turn])

def after(ctx, event):
    arena = ctx.self
    if event.payload["verb"] in ["step", "strike"]:
        arena.state.turn = (arena.state.turn + 1) % len(arena.state.order)
"""


def test_grid_space_and_turn_based_pocket():
    eng = Engine()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.create_world("Pit", seed=1)
    gm.define_script("step", STEP)
    gm.define_script("strike", STRIKE)
    gm.define_script("turns", TURNS)
    gm.define_schema("arena", extends="place", space={"dims": 2, "bounds": [5, 5], "grid": True},
                     listeners=[{"script": "turns", "kinds": ["before_act"]},
                                {"script": "turns", "fn": "after", "kinds": ["act"]}])
    gm.define_schema("fighter", extends="creature",
                     actions={"step": {"script": "step", "doc": "Move one square", "params": {"dx": "int", "dy": "int"}},
                              "strike": {"script": "strike", "doc": "Hit an adjacent creature", "targets": "creature"}})
    arena = gm.spawn("arena", gm.world.root_id, "Pit")["id"]
    a = gm.spawn("fighter", arena, "Ash", pos=[0, 0])["id"]
    b = gm.spawn("fighter", arena, "Bone", pos=[3, 0])["id"]
    gm.patch(arena, {"order": [a, b], "turn": 0})
    with pytest.raises(Rejected) as r:
        gm.spawn("fighter", arena, "Out", pos=[5, 0])
    assert "outside" in r.value.reason
    with pytest.raises(Rejected):
        gm.spawn("fighter", arena, "Half", pos=[1.5, 0])
    ash, bone = eng.session("ash"), eng.session("bone")
    ash.join("pit", a)
    bone.join("pit", b)
    with pytest.raises(Rejected) as r:
        bone.act("step", params={"dx": -1})
    assert "not your turn" in r.value.reason
    with pytest.raises(Rejected) as r:
        ash.act("strike", "Bone")
    assert "too far" in r.value.reason
    ash.act("step", params={"dx": 1})
    bone.act("step", params={"dx": -1})
    ash.act("step", params={"dx": 1})  # Ash at 2,0; Bone at 2,0? no: Bone at 2,0 then Ash tries 2,0 too
    bone.act("strike", "Ash")
    assert gm.inspect(a)["state"]["hp"] == 7
    assert gm.world.distance(a, b) == 0.0
    b_ = ash.perceive()
    assert b_["you"]["pos"] == [2.0, 0.0] and b_["here"]["space"]["dims"] == 2
    # perceive explains the turn rule through the affordance reasons
    aff = {x["verb"]: x for x in bone.perceive()["affordances"] if x["verb"] == "step"}
    assert aff["step"]["ok"] is False and "not your turn" in aff["step"]["reason"]


def test_find_pages_and_refuses_a_limit_it_cannot_meet():
    eng, w, i = engine_with_two_rooms()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    for n in range(120):
        gm.spawn("thing", "Hall", name=f"Pebble {n:03d}")
    with pytest.raises(Rejected) as r:
        gm.find(name="Pebble", limit=500)
    assert "offset" in r.value.hint
    first = gm.find(name="Pebble", limit=100)
    rest = gm.find(name="Pebble", limit=100, offset=100)
    assert len(first) == 100 and len(rest) == 20
    assert [e["name"] for e in first + rest] == [f"Pebble {n:03d}" for n in range(120)]


def test_introduce_brings_a_thing_in_with_a_past():
    eng, w, i = engine_with_two_rooms()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    # always there: no sound in the room, and the one who would know it remembers it
    shelf = gm.introduce("thing", "Cell", "Old shelf", how="always_there",
                         known_by={"Prisoner": "The shelf by the door has been there since before I came."})
    ev = w.store.query("event", "world_id=? AND kind='spawned' AND target_id=?", (w.id, shelf["id"]))[0]
    assert ev["path"] == [shelf["id"]]
    assert "since before I came" in w.get(i["Prisoner"])["state"]["memory"][-1]["text"]
    assert w.get(shelf["id"])["state"]["provenance"]["how"] == "always_there"
    # a stranger arrives: the room sees the scene, nobody knows him, he knows the road he came by
    gm.introduce("person", "Hall", "Rider", how="arrived", known_by={}, scene="A rider comes in off the salt.",
                 remembers=["I came up the north road. I know nobody here."])
    scene = w.store.query("event", "world_id=? AND kind='scene'", (w.id,))[-1]
    assert scene["payload"]["text"].startswith("A rider") and i["Hall"] in scene["path"]
    assert "north road" in w.get(w.find(name="Rider")[0]["id"])["state"]["memory"][0]["text"]
    # one the Guard knows: a knows link as well as the note
    kin = gm.introduce("person", "Hall", "Cousin", how="arrived", scene="The Guard's cousin walks in.",
                       known_by={"Guard": "My cousin, owes me money."})
    assert any(e["target"] == kin["id"] for e in w.edges(i["Guard"], "knows", "out"))


def test_introduce_asks_how_and_what_the_room_saw():
    eng, w, i = engine_with_two_rooms()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    with pytest.raises(Rejected) as r:
        gm.introduce("thing", "Cell", "Crate", how="spawned", known_by={})
    assert "always_there" in r.value.alternatives
    with pytest.raises(Rejected):
        gm.introduce("thing", "Cell", "Crate", how="appeared", known_by={})  # no scene
    with pytest.raises(Rejected):
        gm.introduce("thing", "Cell", "Crate", how="delivered", known_by={}, scene="A crate is set down.")  # no by
    with pytest.raises(Rejected):
        gm.introduce("thing", "Cell", "Crate", how="always_there", known_by={"Nobody at all": "x"})
    assert not w.find(name="Crate")
