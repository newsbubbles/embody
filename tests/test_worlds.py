"""The sample worlds load and their rails run."""

from pathlib import Path

from embody.cli import load_world_file
from embody.ops import AUTHOR, Engine, Rejected

WORLDS = Path(__file__).resolve().parent.parent / "worlds"


def test_ferry_at_dusk_rails_complete():
    eng = Engine()
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world_file(gm, WORLDS / "ferry_at_dusk.py")
    you = eng.session("you")
    first = you.join("ferry-at-dusk", "Traveler")
    assert first["here"]["name"] == "Ashford Square"
    verbs = {(a["verb"], a["target_name"]) for a in first["affordances"] if a["ok"]}
    assert ("talk", "Mara") in verbs and ("read", "Notice board") in verbs

    r = you.act("talk", "Mara", {"about": "the ferry"})
    assert any(e["kind"] == "say" and "Tam" in e["payload"]["text"] for e in r["events"])
    you.act("talk", "Mara", {"about": "a light"})
    assert any(h["name"] == "Tinderbox" for h in you.perceive()["holding"])

    # peace rule in the square, with a hint
    try:
        you.act("attack", "Mara")
        assert False, "should be rejected"
    except Rejected as rej:
        assert "square" in rej.reason and rej.hint == "talk instead"

    you.act_many([{"verb": "take", "target": "Bone"}, {"verb": "go", "target": "Pell's Mill"},
                  {"verb": "give", "target": "Biscuit", "params": {"item": "Bone"}},
                  {"verb": "take", "target": "Coil of rope"}, {"verb": "go", "target": "Ashford Square"},
                  {"verb": "go", "target": "The Landing"}])
    story = gm.find(type="story")[0]
    assert story["state"]["stage"] == "ask"
    try:
        you.act("ring", "Landing bell")
        assert False
    except Rejected as rej:
        assert "cut" in rej.reason
    you.act("tie", "Landing bell")
    r = you.act("ring", "Landing bell")
    assert any(e["kind"] == "scene" for e in r["events"])
    assert any(p["name"] == "Old Tam" for p in you.perceive()["present"])

    gm.clock(step=100)  # fog at 90, dog ticks, Hob walks
    here = you.perceive()
    assert here["here"]["state"]["fog"] is True
    assert any(p["name"] == "Biscuit" for p in here["present"])
    try:
        you.act("cross", "Ferry raft")
        assert False
    except Rejected as rej:
        assert "fog" in rej.reason
    you.act_many([{"verb": "take", "target": "Post lantern"}, {"verb": "light", "target": "Post lantern"},
                  {"verb": "cross", "target": "Ferry raft"}])
    assert you.perceive()["here"]["name"] == "The Landing"  # the crossing takes 12 s
    gm.clock(step=13)
    after = you.perceive()
    assert after["here"]["name"] == "The Far Bank"
    assert any(p["name"] == "Old Tam" for p in after["present"])
    assert gm.inspect("Story")["state"]["stage"] == "done"
    assert gm.world.need(gm.world.root_id)["state"]["story"] == "complete"


def test_ferry_at_dusk_is_deterministic():
    hashes = []
    for _ in range(2):
        eng = Engine()
        gm = eng.session("gm", capabilities=[AUTHOR])
        load_world_file(gm, WORLDS / "ferry_at_dusk.py")
        gm.clock(step=200)
        hashes.append(gm.world.state_hash())
    assert hashes[0] == hashes[1]
