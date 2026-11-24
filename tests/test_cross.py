"""Crossing between worlds (Nate, 2026-11-23): two worlds on two servers link with a shared secret; a seat steps
through a gate and becomes the same person in the other world, made by that world's rules, and plays in one world at a
time. Here the two servers are two engines, and the call between them is a function instead of HTTP."""

import pytest

from embody import links
from embody.ops import AUTHOR, Engine, Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def two_worlds(tmp_path):
    ea, wa, ia = engine_with_two_rooms()
    ga = owner(ea)
    eb = Engine(tmp_path / "b.db", workspace=tmp_path)
    gb = eb.session("gm", capabilities=[AUTHOR])
    gb.create_world("The Pit", id="the-pit")
    gb.spawn("place", gb.world.root_id, "Landing")
    gb.patch(gb.world.root_id, {"templates": {"stranger": {"type": "creature", "state": {"hp": 7, "max_hp": 7}}}})
    servers = {"https://a.example": (ea, ga), "https://b.example": (eb, gb)}

    def transport(url, headers, body):
        eng, gm = servers[url]
        with eng.lock:
            return gm.link_arrive(dict(headers), body)
    ea.link_transport = eb.link_transport = transport
    made = gb.link_world("two-rooms", url="https://a.example", template="stranger", arrive="Landing", accept=["level"])
    ga.link_world("the-pit", url="https://b.example", secret=made["secret"])
    ga.patch("Prisoner", {"playable": True, "level": 3, "description": "Thin, with a river stone."})
    ga.spawn("thing", "Cell", "Shimmer", state={"gate": {"world": "the-pit", "carry": ["level"]}})
    inv = ga.invite("player", entity="Prisoner", label="Sam")
    sam = ea.session_for_token(inv["token"])
    sam.join()
    return ea, ga, eb, gb, sam, inv


def test_a_seat_crosses_as_the_same_person_and_plays_in_one_world_at_a_time(tmp_path):
    ea, ga, eb, gb, sam, inv = two_worlds(tmp_path)
    assert "secret" not in str(gb.link_world())  # a listing never shows the secret
    out = sam.cross("Shimmer")
    assert out["crossed"] and out["to"] == "The Pit"
    there = gb.inspect("Prisoner")
    assert there["state"]["level"] == 3 and there["state"]["hp"] == 7 and there["state"]["came_from"] == "two-rooms"
    assert gb.world.get(there["parent"])["name"] == "Landing"
    left = ga.inspect("Prisoner")
    assert ga.world.get(left["parent"])["name"] == "Elsewhere" and left["state"]["crossed"]["to"] == "the-pit"
    with pytest.raises(Rejected) as away:
        sam.join()
    assert "The Pit" in away.value.reason or "The Pit" in str(away.value.hint) or "in" in away.value.reason
    g = eb.store.query("grants", "world_id=? AND traveller=?", ("the-pit", f"two-rooms:{inv['id']}"))
    assert len(g) == 1 and g[0]["entity_id"] == there["id"]
    bob = eb.session_for_token(gb.relink(g[0]["id"])["token"])
    bob.join()
    gb.spawn("thing", "Landing", "Rift", state={"gate": {"world": "two-rooms"}})
    back = bob.cross("Rift")
    assert back["crossed"] and back.get("home")
    assert ga.world.get(ga.inspect("Prisoner")["parent"])["name"] == "Cell"  # by the gate it left through
    assert sam.join()["you"]["name"] == "Prisoner"  # the old token works again
    with pytest.raises(Rejected):
        bob.join()  # and the seat there waits, held
    again = sam.cross("Shimmer")  # a second trip finds the body it left
    assert again.get("returning") and len(gb.world.find(name="Prisoner", limit=5)) == 1


def test_a_crossing_is_signed_once_and_only_by_a_linked_world(tmp_path):
    ea, ga, eb, gb, sam, inv = two_worlds(tmp_path)
    secret = eb.store.get("links", "the-pit", "two-rooms")["secret"]
    card = {"traveller": "two-rooms:gX", "from": "two-rooms", "name": "Mallory", "description": "", "state": {}}
    raw = links.body_bytes(card)
    h = links.signed_headers(secret, "two-rooms", raw)
    assert gb.link_arrive(h, raw)[0] == 200
    assert gb.link_arrive(h, raw)[0] == 403  # the same call again
    bad = links.signed_headers("not-the-secret", "two-rooms", raw)
    assert gb.link_arrive(bad, raw)[0] == 403
    stale = links.signed_headers(secret, "two-rooms", raw, now=0.0)
    assert gb.link_arrive(stale, raw)[0] == 403
    other = links.signed_headers(secret, "elsewhere-world", raw)
    assert gb.link_arrive(other, raw)[0] == 403
    gb.link_world("two-rooms", revoke=True)
    with pytest.raises(Rejected):
        sam.cross("Shimmer")
    assert ga.world.get(ga.inspect("Prisoner")["parent"])["name"] == "Cell"  # a refused crossing moves nothing


def test_a_gate_is_the_worlds_to_open(tmp_path):
    ea, ga, eb, gb, sam, inv = two_worlds(tmp_path)
    ga.patch("Shimmer", {"gate": {"for": ["angel"]}})
    with pytest.raises(Rejected) as shut:
        sam.cross("Shimmer")
    assert "angel" in shut.value.hint
    with pytest.raises(Rejected):
        sam.cross("Iron door")  # no gate
    with pytest.raises(Rejected):
        ga.link_world("the-pit", url="http://evil.example")  # https only


def test_the_door_takes_a_signed_card_over_http_and_refuses_an_unsigned_one():
    import threading
    import time
    uvicorn = pytest.importorskip("uvicorn")
    from embody.mcp_server import build_server, http_app
    from tests.test_grants import _free_port
    eng, w, i = engine_with_two_rooms()
    port = _free_port()
    eng.public_url = f"http://127.0.0.1:{port}/mcp"
    gm = owner(eng)
    secret = gm.link_world("the-pit", url="https://b.example")["secret"]
    srv = build_server(gm, None, eng, http_only=True)
    server = uvicorn.Server(uvicorn.Config(http_app(srv), host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started
    try:
        base = f"http://127.0.0.1:{port}"
        raw = links.body_bytes({"traveller": "the-pit:g1", "from": "the-pit", "name": "Ash", "description": "", "state": {}})
        status, out = links.post(base, links.signed_headers(secret, "the-pit", raw), raw)
        assert status == 200 and out["ok"] and out["world_name"] == "Two Rooms"
        assert gm.inspect("Ash")["state"]["came_from"] == "the-pit"
        status, out = links.post(base, {"content-type": "application/json"}, raw)
        assert status == 403 and not out["ok"]
    finally:
        server.should_exit = True
