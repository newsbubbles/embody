"""A world played with its clock paused (chat play), and the door's small seams a second world's playtest found: far
views refresh on what happens, not only on the world hour; minds() counts a player's wait in real minutes; join takes
`world` as well as world_id; the HTTP door answers principals for its own grant; two waits on one principal say they
share a cursor."""

import threading
import time

import pytest

from tests.test_far import sight, skyline
from tests.test_grants import _free_port, _post, owner
from tests.test_ops import engine_with_two_rooms


def test_a_paused_world_refreshes_far_views_on_any_event():
    eng, w, gm, nate = skyline()
    gm.clock(run=False)
    assert sight(nate)["Signal Tower"]["line"] == "a stone tower, a fire basket on top"
    gm.patch("Signal Tower", {"far": {"far": "a black stump on the skyline", "mid": "a burnt stump of a tower"}})
    assert sight(nate)["Signal Tower"]["line"] == "a burnt stump of a tower"  # the hour never turned, the view did


def test_minds_counts_a_wait_in_real_minutes_while_the_clock_is_paused():
    eng, w, i = engine_with_two_rooms()
    wall = [1000.0]
    eng.wall = lambda: wall[0]
    gm = owner(eng)
    gm.clock(run=False)
    gm.patch("Guard", {"brief": "You keep the hall."})
    gm.move("Prisoner", "Hall")
    sam = eng.session("sam")
    sam.join("two-rooms", "Prisoner")
    sam.say("Guard, open the gate", to="Guard")
    said = w.events(kinds=["say"], limit=5, newest=True)
    assert said[-1]["payload"]["wall"] == 1000.0  # the store keeps the real time; a player's view does not
    assert "wall" not in sam._events_for(i["Prisoner"], said)[-1]["payload"]
    wall[0] += 15 * 60
    r = gm.minds()
    guard = next(m for m in r["minds"] if m["name"] == "Guard")
    assert guard["owed"]["min"] == 15.0 and any("Prisoner has waited 15.0 min" in a for a in r["alerts"])


def test_join_takes_world_as_well_as_world_id():
    eng, w, i = engine_with_two_rooms()
    sam = eng.session("sam")
    assert sam.join(world="two-rooms", entity="Prisoner")


def test_two_waits_on_one_principal_say_they_share_a_cursor():
    eng, w, i = engine_with_two_rooms()
    sam = eng.session("sam")
    sam.join("two-rooms", "Prisoner")
    assert "shared_cursor" not in sam.wait(timeout=0)
    eng.__dict__.setdefault("_waits", {})[sam.pid] = 1  # another wait of this principal's is running
    assert "since=" in sam.wait(timeout=0)["shared_cursor"]


def test_the_wait_cap_follows_embody_wait_max(monkeypatch):
    """A proxy that cuts a silent request at 100 s (Cloudflare) needs every wait to answer sooner: the host sets
    EMBODY_WAIT_MAX, read at each call, and a wait asking for more answers at the cap."""
    from embody.mcp_server import wait_max
    monkeypatch.delenv("EMBODY_WAIT_MAX", raising=False)
    assert wait_max() == 120.0
    monkeypatch.setenv("EMBODY_WAIT_MAX", "90")
    assert wait_max() == 90.0
    monkeypatch.setenv("EMBODY_WAIT_MAX", "soon")
    assert wait_max() == 120.0
    uvicorn = pytest.importorskip("uvicorn")
    from embody.mcp_server import build_server, http_app
    eng, w, i = engine_with_two_rooms()
    port = _free_port()
    eng.public_url = f"http://127.0.0.1:{port}/mcp"
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    inv = gm.invite("player", entity="Prisoner", label="Sam")
    srv = build_server(gm, None, eng, http_only=True)
    server = uvicorn.Server(uvicorn.Config(http_app(srv), host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        base = f"http://127.0.0.1:{port}"
        assert _post(base + "/op/join", {"world": "two-rooms"}, token=inv["token"])[0] == 200
        monkeypatch.setenv("EMBODY_WAIT_MAX", "1")
        t0 = time.monotonic()
        status, body = _post(base + "/op/wait", {"timeout": 60}, token=inv["token"])
        assert status == 200 and time.monotonic() - t0 < 15
    finally:
        server.should_exit = True


def test_the_http_door_answers_principals_for_its_own_grant_only():
    uvicorn = pytest.importorskip("uvicorn")
    from embody.mcp_server import build_server, http_app
    eng, w, i = engine_with_two_rooms()
    port = _free_port()
    eng.public_url = f"http://127.0.0.1:{port}/mcp"
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    inv = gm.invite("player", entity="Prisoner", label="Sam")
    srv = build_server(gm, None, eng, http_only=True)
    server = uvicorn.Server(uvicorn.Config(http_app(srv), host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        base = f"http://127.0.0.1:{port}"
        status, body = _post(base + "/op/principals", {}, token=inv["token"])
        assert status == 200 and len(body) == 1 and body[0]["main"] and body[0]["principal"] != gm.pid
        status, body = _post(base + "/op/join", {"world": "two-rooms"}, token=inv["token"])
        assert status == 200 and body.get("ok") is not False
    finally:
        server.should_exit = True
