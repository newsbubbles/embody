"""The chronicle: one world day of the log sorted for whoever writes it up, and the days the owner publishes."""

import pytest

from embody.ops import AUTHOR, Rejected
from tests.test_ops import engine_with_two_rooms


def played():
    eng, w, i = engine_with_two_rooms()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    s = eng.session("nate")
    s.join("two-rooms", "Prisoner")
    w.emit("scene", target=i["Cell"], reach=1, payload={"text": "Water drips somewhere you cannot see."})
    s.say("Is anyone there?")
    s.act("take", "Rusty key")
    s.act("unlock", "Iron door")
    s.act_many([{"verb": "open", "target": "Iron door"}, {"verb": "go", "target": "Hall"}])
    s.remember("the guard looked away")  # a note is its owner's, never the chronicle's
    return eng, w, i, gm, s


def test_history_counts_only_what_it_shows_and_reads_from_the_end():
    eng, w, i, gm, s = played()
    for n in range(80):
        gm.schedule(1, "drip", entity=i["Cell"])  # bookkeeping the log keeps to itself (scheduled)
    first = gm.history(limit=5)
    assert len(first) == 5 and all(e["kind"] not in ("scheduled", "tick", "script_defined") for e in first)
    said = gm.history(kinds=["say"])
    assert [e["payload"]["text"] for e in said] == ["Is anyone there?"]
    last = gm.history(limit=2, newest=True)
    assert len(last) == 2 and last[-1]["seq"] > first[-1]["seq"] and last[0]["seq"] < last[1]["seq"]


def test_the_digest_sorts_the_day_and_leaves_out_what_is_private():
    eng, w, i, gm, s = played()
    d = gm.chronicle()
    assert d["day"] == 1 and d["today"] == 1 and d["published"] is None
    assert [x["text"] for x in d["scenes"]] == ["Water drips somewhere you cannot see."] and d["scenes"][0]["place"] == "Cell"
    assert d["said"][0]["who"] == "Prisoner" and d["said"][0]["text"] == "Is anyone there?"
    assert d["travel"]["Prisoner"] == ["Cell", "Hall"]
    kinds = {b["kind"] for b in d["beats"]}
    assert "remembered" not in d["counts"] and "the guard looked away" not in str(d)
    assert not kinds & {"spawned", "patched", "scheduled", "tick"}
    assert any(p["name"] == "Prisoner" for p in d["people"])
    with pytest.raises(Rejected):
        gm.chronicle(day=2)  # not yet
    with pytest.raises(Rejected):
        s.chronicle()  # a player reads its own story, not the world's


def test_a_day_is_published_replaced_and_withdrawn():
    eng, w, i, gm, s = played()
    r = gm.publish_chronicle(1, "The first day. Someone in the cell found the key.", title="The key")
    assert r["ok"] and r["public"] is False and "public_feed" in r["hint"]
    gm.publish_chronicle(1, "The first day, told again.")
    assert gm.chronicle(day=1)["published"]["text"] == "The first day, told again."
    gm.publish_chronicle(1, "")
    assert gm.chronicle(day=1)["published"] is None
    with pytest.raises(Rejected):
        gm.publish_chronicle(1, "")  # nothing left to withdraw
    with pytest.raises(Rejected):
        gm.publish_chronicle(5, "Days that have not come.")
    with pytest.raises(Rejected):
        s.publish_chronicle(1, "I was here.")


def test_the_chronicle_tools_answer_through_the_mcp_server():
    import anyio
    import json
    from embody.mcp_server import build_server
    eng, w, i, gm, s = played()
    srv = build_server(gm, None, eng)

    async def call(name, args):
        r = await srv.call_tool(name, args)
        assert not r.is_error, r.content
        return json.loads("".join(getattr(b, "text", "") for b in r.content))
    assert anyio.run(call, "chronicle", {})["day"] == 1
    assert anyio.run(call, "publish_chronicle", {"day": 1, "text": "Day one."})["ok"]


def test_the_digest_leads_with_what_changed_and_counts_the_routine():
    eng, w, i, gm, s = played()
    for rat in w.find(type="rat"):
        w.destroy(rat["id"])  # its wandering is no one's news
    w.set_meta({"day_seconds": 100})
    w.emit("scene", target=i["Cell"], reach=1, payload={"text": "Dawn greys the bars."})
    w.step(100)
    w.emit("scene", target=i["Cell"], reach=1, payload={"text": "Dawn greys the bars."})  # every day: routine
    w.emit("scene", target=i["Cell"], reach=1, payload={"text": "Dawn greys the bars."})  # told twice: once
    w.emit("scene", target=i["Hall"], reach=1, payload={"text": "A bell rings in the yard."})
    w.patch(i["Prisoner"], {"faction": "Inmates"})
    w.patch(i["Guard"], {"faction": "Watch"})
    stranger = w.spawn("person", i["Hall"], "Stranger", state={"faction": "Watch"})
    w.spawn("room", w.root_id, "Yard")
    w.emit("hit", actor=i["Guard"], target=i["Prisoner"], payload={"by": i["Guard"], "dmg": 2})
    w.emit("missed", actor=i["Guard"], target=i["Prisoner"], payload={"by": i["Guard"]})
    w.emit("given", actor=i["Guard"], target=i["Prisoner"], payload={"by": i["Guard"], "item": i["Rusty key"], "count": 1})
    w.emit("given", actor=i["Guard"], target=stranger, payload={"by": i["Guard"], "item": i["Rusty key"]})  # same side
    w.emit("downed", actor=i["Prisoner"], target=i["Prisoner"], payload={"by": i["Guard"]})
    w.patch(w.root_id, {"alarm": "raised"})
    w.patch(w.root_id, {"alarm": "sounding"})
    d = gm.chronicle(day=2)
    assert [x["text"] for x in d["scenes"]] == ["A bell rings in the yard."]
    assert d["routine"]["kinds"]["scene"] == 2 and d["routine"]["count"] >= 2
    news = {x["what"]: x for x in d["news"]}
    assert news["new_person"]["who"] == "Stranger" and news["new_person"]["faction"] == "Watch"
    assert news["new_place"]["name"] == "Yard"
    assert news["fight"] == {**news["fight"], "who": "Guard", "target": "Prisoner", "blows": 2, "hits": 1, "damage": 2}
    gifts = [x for x in d["news"] if x["what"] == "gift"]
    assert len(gifts) == 1 and gifts[0]["sides"] == ["Watch", "Inmates"] and gifts[0]["thing"] == "Rusty key"
    assert news["downed"]["who"] == "Guard" and news["downed"]["target"] == "Prisoner"
    assert news["story"]["key"] == "alarm" and news["story"]["was"] is None and news["story"]["now"] == "sounding"
    assert all("t" in x and "place" in x or x["what"] == "story" for x in d["news"])
    assert "news" in d["hint"] and "routine" in d["hint"]
