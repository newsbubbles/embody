"""What holds while a seat is idle: things remember whom they were taken from, an idle body gives back what is not
its own and what its standing orders give, and answers with its standing line. And the schedule a player may read."""

import pytest

from embody.ops import Rejected, call
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def two_in_the_cell():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    w.set_meta({"idle_after": 60})
    gm.move("Guard", "Cell")
    p, g = eng.session("p"), eng.session("g")
    p.join("two-rooms", "Prisoner")
    g.join("two-rooms", "Guard")
    return eng, w, i, gm, p, g


def test_what_was_taken_goes_home_from_an_idle_holder():
    eng, w, i, gm, p, g = two_in_the_cell()
    gm.move("Rusty key", "Prisoner")
    w.move(i["Rusty key"], i["Guard"], actor=i["Guard"])  # the guard takes it off him
    assert w.need(i["Rusty key"])["state"]["taken_from"] == i["Prisoner"]
    with pytest.raises(Rejected) as r:
        p.reclaim("Rusty key")
    assert "awake" in r.value.reason
    gm.clock(step=120)
    assert [x["name"] for x in p.perceive()["reclaim"]] == ["Rusty key"]
    out = p.reclaim("Rusty key")
    assert out["why"] == "yours" and w.need(i["Rusty key"])["parent_id"] == i["Prisoner"]
    assert "taken_from" not in w.need(i["Rusty key"])["state"]
    assert call(g, "reclaim", thing="Rusty key")["ok"] is False  # the guard has no claim on it


def test_a_gift_is_not_a_taking():
    eng, w, i, gm, p, g = two_in_the_cell()
    gm.move("Rusty key", "Prisoner")
    w.patch(i["Rusty key"], {"given_by": i["Prisoner"]})
    w.move(i["Rusty key"], i["Guard"], actor=i["Prisoner"])
    assert "taken_from" not in w.need(i["Rusty key"])["state"]


def test_standing_orders_give_and_answer_while_the_seat_is_idle():
    eng, w, i, gm, p, g = two_in_the_cell()
    gm.spawn("thing", "Guard", name="Lamp")
    g.away(give=[{"item": "Lamp", "to": "anyone"}], answer="Asleep on my feet. Take the lamp if you need it.")
    assert call(p, "reclaim", thing="Lamp")["ok"] is False  # he is awake: his orders wait
    gm.clock(step=120)
    card = [c for c in p.perceive()["present"] if c["name"] == "Guard"][0]
    assert card["idle"] and card["state"]["standing_orders"]["give"][0]["item"] == "Lamp"
    before = len(w.events(kinds=["say"], limit=500))
    p.say("Guard?", to="Guard")
    p.say("Guard!", to="Guard")
    lines = [e for e in w.events(kinds=["say"], limit=500)][before:]
    assert [e["payload"].get("away") for e in lines] == [None, True, None]  # one answer, not two
    out = p.reclaim("Lamp")
    assert out["why"] == "their orders"
    lamp = w.find(name="Lamp")[0]
    assert lamp["parent_id"] == i["Prisoner"] and "taken_from" not in lamp["state"]
    g.away()
    assert "standing_orders" not in w.need(i["Guard"])["state"]
    assert call(p, "away", answer="x", entity="Guard")["ok"] is False  # orders are for your own body


def test_a_player_reads_the_public_schedule_in_words():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.schedule(7200, "dusk")
    gm.schedule(9000, "dusk")
    gm.schedule(600, "ambush", entity="Guard")
    w.set_meta({"public_timers": ["dusk"]})
    p = eng.session("p")
    p.join("two-rooms", "Prisoner")
    assert p.timers() == [{"kind": "dusk", "in": pytest.approx(7200, abs=1), "when": "in about 2 hours", "every": None}]
    assert {t["kind"] for t in gm.timers()} >= {"dusk", "ambush"}
