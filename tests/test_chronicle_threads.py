"""chronicle(day, threads=N): the day as story threads ranked by stakes, not the clock (asked by a world host,
2026-11-23). A downing with a player in it leads over births; a world sets its own weights; news joins by place, body
or one cause; what was hidden when it happened stays out, a faction never hides a line; an open arc lifts its thread;
the reply keeps its size however busy the day."""

import pytest

from embody.ops import Rejected
from tests.test_chronicle import played
from tests.test_grants import owner

HOUR = 3600


def with_player():
    """The played day, then a guest's agent in the Prisoner through a real player invite."""
    eng, w, i, gm, s = played()
    s.leave()
    own = owner(eng)
    own.patch("Prisoner", {"playable": True})
    sam = eng.session_for_token(own.invite("player", entity="Prisoner", label="Sam")["token"])
    sam.join()
    sam.say("Who goes there?")
    return eng, w, i, own, sam


def births(w, place, n):
    for k in range(n):
        w.spawn("person", place, f"Kid {k}")


def test_the_lead_is_the_stakes_not_the_clock():
    eng, w, i, gm, s = with_player()
    births(w, i["Hall"], 3)  # the morning: births
    w.step(8 * HOUR)
    w.emit("hit", actor=i["Guard"], target=i["Prisoner"], payload={"by": i["Guard"], "dmg": 4})
    w.emit("downed", actor=i["Prisoner"], target=i["Prisoner"], payload={"by": i["Guard"]})
    d = gm.chronicle(day=1)
    lead = d["threads"][0]
    assert any(" downed " in x for x in lead["news"]) and lead["players"] == ["Prisoner"]
    kids = [th for th in d["threads"] if any("Kid 0" in x for x in th["news"])]
    assert kids and kids[0]["score"] < lead["score"]
    assert all(not k.startswith("_") for x in d["news"] for k in x)  # where it happened stays the engine's
    said = [x for th in d["threads"] for x in th.get("said", [])] + d["around"]
    assert any("Who goes there?" in x and "never quote" in x for x in said)  # a player's words: retold


def test_a_world_sets_its_own_weights():
    eng, w, i, gm, s = played()
    births(w, i["Hall"], 3)
    w.step(8 * HOUR)
    w.emit("downed", actor=i["Prisoner"], target=i["Prisoner"], payload={"by": i["Guard"]})
    w.set_meta({"chronicle_weights": {"new_person": 60}})  # a herding world: the births are the story
    assert any("Kid 0" in x for x in gm.chronicle(day=1)["threads"][0]["news"])


def test_one_cause_joins_one_thread_across_places():
    eng, w, i, gm, s = played()
    w.step(10 * HOUR)
    a = w.spawn("person", i["Cell"], "Runner")
    b = w.spawn("person", i["Hall"], "Keeper")
    first = w.emit("found", actor=a, target=a, payload={"what": "a map"})
    w.step(5 * HOUR)  # past the place and the body windows: only the cause joins them
    w.emit("struck", actor=b, target=b, caused_by=first["seq"])
    lines = [th["news"] for th in gm.chronicle(day=1, threads=12)["threads"]]
    assert any(any("found" in x for x in ns) and any("struck" in x for x in ns) for ns in lines)


def test_what_was_hidden_then_stays_out_and_a_faction_hides_nothing():
    eng, w, i, gm, s = played()
    w.define_schema("faction", extends="entity")
    keth = w.spawn("faction", w.root_id, "the Keth", state={"hidden": True})
    vault = w.spawn("room", w.root_id, "Vault", state={"hidden": True})
    thief = w.spawn("person", vault, "Thief")
    w.step(HOUR)
    w.emit("found", actor=thief, target=thief, payload={"what": "the ledger"})  # in a place nobody knew then
    w.emit("caught", actor=keth, target=i["Guard"])  # a side, not a place: it hides nothing
    w.step(HOUR)
    w.patch(vault, {"hidden": False})  # revealed later: what happened before stays out
    w.patch(i["Hall"], {"hidden": True})  # hidden later: what happened before still shows
    d = gm.chronicle(day=1, threads=12)
    text = str(d["threads"]) + str(d["around"])
    assert "the ledger" not in text and "Thief" not in text
    assert "caught" in text and "Hall" in text


def test_an_open_arc_lifts_its_thread_and_the_arcs_are_kept():
    eng, w, i, gm, s = played()
    births(w, i["Hall"], 1)
    w.step(8 * HOUR)
    w.emit("struck", actor=i["Guard"], target=i["Guard"])
    base = {th["news"][0]: th["score"] for th in gm.chronicle(day=1, threads=12)["threads"]}
    r = gm.chronicle_arc("guard-falls", title="The guard's fall", people=["Guard"])
    assert r["ok"] and r["open"] == ["guard-falls"] and r["arc"]["opened"] == 1
    d = gm.chronicle(day=1, threads=12)
    th = next(t for t in d["threads"] if t.get("arc") == "guard-falls")
    assert th["score"] == pytest.approx(base[th["news"][0]] * 1.5, abs=0.11)
    assert d["arcs"][0]["id"] == "guard-falls"
    gm.chronicle_arc("guard-falls", status="closed", note="he rose at dawn")
    assert "arc" not in str(gm.chronicle(day=1, threads=12)["threads"])
    assert gm.chronicle_arc()["arcs"][0]["status"] == "closed"
    with pytest.raises(Rejected):
        gm.chronicle_arc("nothing-yet")  # an arc opens with a title
    with pytest.raises(Rejected):
        gm.chronicle_arc("guard-falls", status="paused")
    with pytest.raises(Rejected):
        s.chronicle_arc()  # a player's story is not theirs to keep


def test_the_reply_keeps_its_size_on_a_busy_day():
    eng, w, i, gm, s = played()
    for k in range(70):  # seventy small stories in seventy places
        room = w.spawn("room", w.root_id, f"Room {k}")
        w.spawn("person", room, f"Kid {k}")
    d = gm.chronicle(day=1, threads=4, limit=10)
    assert len(d["threads"]) == 4 and d["threads_more"] >= 60
    assert len(d["around"]) == 40 and d["around_more"] > 0
    assert "threads" not in gm.chronicle(day=1, threads=0)
