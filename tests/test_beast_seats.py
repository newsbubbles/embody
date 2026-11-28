"""A seat on a beast (Ridge Kid's goat): its body's `verbs_only` are all it can do, a verb's `cooldown` holds it off
that verb a while, it hears how a line sounds and not its words unless it `understands`, and it moves about its place
with short `step`s that everyone there can follow with wait(positions=true)."""

import pytest

from embody.world import Rejected, rules_only_keys, tone
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def pasture(eng):
    gm = owner(eng)
    gm.define_script("bleat", "def apply(ctx):\n    ctx.emit('bleated', target=ctx.actor, reach=1)\n")
    gm.define_schema("goat", extends="creature", state={"beast": True, "verbs_only": ["bleat", "go", "step"]},
                     actions={"bleat": {"script": "bleat", "reach": "self", "cooldown": 20}})
    gm.spawn("goat", "Hall", "Nan", state={"playable": True})
    sam = eng.session("sam")
    sam.join("two-rooms", "Nan")
    nate = eng.session("nate")
    nate.join("two-rooms", "Guard")
    return gm, sam, nate


def test_a_goat_does_only_its_own_verbs_and_waits_out_a_bleat():
    eng, w, i = engine_with_two_rooms()
    gm, sam, nate = pasture(eng)
    gm.clock(run=True, rate=1)
    sam.act("bleat")
    with pytest.raises(Rejected, match="you can bleat again in about 20 s"):
        sam.act("bleat")
    gm.clock(step=21)
    sam.act("bleat")
    with pytest.raises(Rejected, match="a goat cannot say: it can bleat, go, step"):
        sam.say("let me out")
    with pytest.raises(Rejected, match="a goat cannot take"):
        sam.act("take")
    nan = gm.inspect("Nan")["id"]
    assert set(rules_only_keys(w, nan, ["verbs_only", "understands", "understands_until", "beast"])) == {
        "verbs_only", "understands", "understands_until", "beast"}
    gm.clock(run=False)
    gm.clock(step=21)
    sam.act("bleat")
    sam.act("bleat")  # a paused clock has no cooldowns: its turns are the pace


def test_a_beast_hears_the_tone_not_the_words_until_it_understands():
    eng, w, i = engine_with_two_rooms()
    gm, sam, nate = pasture(eng)
    # how far the line was sent, never its letters or its punctuation: a line is in any language
    assert [tone("Get out of the way, you goat"), tone("SHOO"), tone("Here, girl?"), tone("psst", 0),
            tone("Out of the barley now!"), tone("hello", 2), tone("走開!")] == [
        "calm", "calm", "calm", "whisper", "calm", "shout", "calm"]
    nate.say("Get out of the way, you goat")
    heard = [e for e in sam.perceive()["events"] if e["kind"] == "say"]
    assert heard[-1]["payload"] == {"to": None, "tone": "calm", "heard": False}
    nate.say("Here, girl?", to="Nan")
    assert sam.recall(about="Guard")["exchanges"][-1] == {
        "t": pytest.approx(w.t), "who": i["Guard"], "kind": "say", "tone": "calm", "heard": False}
    assert nate.recall(about="Nan")["exchanges"][-1]["text"] == "Here, girl?"  # the speaker keeps his own words
    gm.patch("Nan", {"understands_until": w.t + 100})  # the rare herb: a while of words
    nate.say("The pass is that way")
    assert [e for e in sam.perceive()["events"] if e["kind"] == "say"][-1]["payload"]["text"] == "The pass is that way"
    gm.clock(step=101)
    nate.say("Good girl")
    assert "text" not in [e for e in sam.perceive()["events"] if e["kind"] == "say"][-1]["payload"]
    gm.patch("Nan", {"understands": True})  # a beast that says it understands does
    nate.say("Home now")
    assert [e for e in sam.perceive()["events"] if e["kind"] == "say"][-1]["payload"]["text"] == "Home now"


def test_a_step_moves_a_little_stays_in_the_place_and_out_of_solids():
    eng, w, i = engine_with_two_rooms()
    gm, sam, nate = pasture(eng)
    trough = gm.spawn("thing", "Hall", "Trough")["id"]
    gm.layout(frame={"units": "m"}, placements=[
        {"entity": "Cell", "at": [0, 0, 0], "radius": 4},
        {"entity": "Hall", "at": [20, 0, 0], "size": [12, 8],
         "landmarks": {"the gate": {"at": [25, 3, 0], "radius": 1}}},
        {"entity": "Nan", "at": [20, 0, 0]}, {"entity": "Guard", "at": [16, -2, 0]},
        {"entity": trough, "at": [23, 0, 0], "radius": 0.5}])
    nan = gm.inspect("Nan")["id"]
    r = sam.step([20, 1])
    assert r["at"] == [20, 1, 0] and "clipped" not in r and r["frame"] == w.root_id
    r = sam.step([20, 3.9])  # a paused clock gives a second's walk: 1.4 m
    assert r["clipped"] is True and r["at"] == [20, 2.4, 0] and "blocked_by" not in r
    gm.patch("Nan", {"speed_mps": 10})
    r = sam.step([20, 9])
    assert r["clipped"] is True and r["blocked_by"] == "the edge of Hall" and r["at"][1] <= 4
    sam.step([21, 0])
    r = sam.step([25, 0])
    assert r["blocked_by"] == "Trough" and r["at"][0] < 22.5
    r = sam.step("the gate")
    assert r["where"] in ("at the gate", "by the gate")
    b = nate.wait(timeout=0, positions=True)
    assert b["positions"] == {nan: r["at"]}
    assert any(e["kind"] == "stepped" for e in b["events"])
    at = r["at"]
    r = sam.step(heading=270)  # a goat turns in place to face the trough: no walking
    assert r["turned"] and r["at"] == at and r["heading"] == 270
    assert gm.inspect("Nan")["state"]["layout"]["heading"] == 270
    seen = [e for e in nate.wait(timeout=0)["events"] if e["kind"] == "stepped"]
    assert seen and seen[-1]["payload"]["heading"] == 270
    r = sam.step([24.5, 2], heading=-45)
    assert r["heading"] == 315 and "turned" not in r
    with pytest.raises(Rejected, match="needs to= .* or heading="):
        sam.step()
    gm.patch("Nan", {"verbs_only": ["bleat"]})
    with pytest.raises(Rejected, match="a goat cannot step"):
        sam.step([24, 2])



def test_a_script_steps_a_body_about_its_place():
    from embody.world import Ctx
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.layout(frame={"units": "m"}, placements=[
        {"entity": "Hall", "at": [20, 0, 0], "size": [12, 8], "landmarks": {"the gate": {"at": [25, 3, 0], "radius": 1}}},
        {"entity": "Guard", "at": [20, 0, 0]}])
    guard = i["Guard"]
    seq = w.store.next_seq(w.id) - 1
    ctx = Ctx(w, actor=guard, target=None, owner=guard, params=None, event=None, verb=None, caused_by=None, seed=1)
    assert ctx.step(guard, to=[23, 0]) == {"at": [23, 0, 0], "heading": 90.0}  # it faces the way it walked: east
    b = ctx.step(guard, to=[40, 0], max_m=50)
    assert b["clipped"] and b["blocked_by"] == "the edge of Hall" and b["at"][0] <= 26
    assert ctx.step(guard, heading=180) == {"heading": 180.0}  # a turn where it stands
    d = ctx.step(guard, to="the gate", max_m=1)
    assert d["clipped"] and "blocked_by" not in d  # a short budget stops it on the way
    assert [e["kind"] for e in w.store.query("event", "world_id=? AND seq>?", (w.id, seq))].count("stepped") == 4
    with pytest.raises(Rejected, match="needs to= .* or heading="):
        ctx.step(guard)
    with pytest.raises(Rejected, match="not standing in one"):
        ctx.step(i["Hall"], to=[0, 0])


def test_a_step_is_one_event_that_carries_where_it_came_from(tmp_path):
    from embody.watch import Reader
    from tests.test_watch_feed import REPO
    eng, w, i = engine_with_two_rooms()
    gm, sam, nate = pasture(eng)
    gm.layout(frame={"units": "m"}, placements=[
        {"entity": "Hall", "at": [20, 0, 0], "size": [12, 8]}, {"entity": "Nan", "at": [20, 0, 0]}])
    before = w.store.next_seq(w.id)
    sam.step([20, 1])
    kinds = [e["kind"] for e in w.events(since=before - 1, limit=50) if e["target_id"] == gm.inspect("Nan")["id"]]
    assert "stepped" in kinds and "patched" not in kinds  # the step is its own record
    st = [e for e in w.events(since=before - 1, kinds=["stepped"], limit=5)][-1]["payload"]
    assert st["at"] == [20, 1, 0] and st["from"]["at"] == [20, 0, 0]
    past = Reader(tmp_path / "w.db", REPO, conn=eng.store.conn).state(w.id, 0, 50, at=before - 1)
    nan = next(e for e in past["entities"] if e["name"] == "Nan")
    assert nan["state"]["layout"]["at"] == [20, 0, 0]  # the viewer's rewind undoes a step by its `from`
