"""Roles, grants and invites: who may call what, who may sit where, how a token gets a friend into a hosted world,
and the HTTP door with its bearer check."""

import json
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from embody.grants import ROLES, ROLE_OPS, allowed
from embody.ops import AUTHOR, OPS, Engine, Rejected, call
from tests.test_ops import engine_with_two_rooms


def owner(eng):
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    return gm


def test_every_op_has_a_role_and_roles_nest():
    for op in OPS:
        assert any(allowed(r, op) for r in ROLES), op
    assert ROLE_OPS["player"] < ROLE_OPS["author"] < ROLE_OPS["owner"]
    assert ROLE_OPS["mind"] == ROLE_OPS["player"]
    assert "invite" not in ROLE_OPS["author"] and "define_script" not in ROLE_OPS["narrator"]


def test_roles_gate_ops_with_a_pointer_to_who_may():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    assert gm.role == "owner"
    nar = eng.session("n", role="narrator")
    nar.use("two-rooms")
    assert nar.say_as("Guard", "Quiet in there.")["ok"]
    assert nar.perceive(from_entity="Guard")["here"]["name"] == "Hall"
    with pytest.raises(Rejected) as r:
        nar.define_script("x", "def main(): pass")
    assert "narrator" in r.value.reason and "author" in r.value.reason
    player = eng.session("p", role="player")
    out = call(player, "invite", role="player")
    assert out["ok"] is False and "owner" in out["reason"]
    obs = eng.session("o", role="observer")
    obs.use("two-rooms")
    with pytest.raises(Rejected):
        obs.join("two-rooms", "Guard")
    with pytest.raises(Rejected):
        eng.session("bad", role="wizard")


def test_named_seat_invite_joins_bare_and_returns_a_briefing():
    eng, w, i = engine_with_two_rooms()
    eng.public_url = "https://reach.example/mcp"
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    inv = gm.invite("player", entity="Prisoner", label="Sam Pike")
    assert inv["principal"].startswith("sam-pike-") and inv["url"] == eng.public_url
    assert "claude mcp add" in inv["paste"] and inv["token"] in inv["paste"] and "Prisoner" in inv["paste"]
    assert eng.session_for_token("not-a-token") is None
    sam = eng.session_for_token(inv["token"])
    assert sam.role == "player" and sam.world_id == "two-rooms"
    b = sam.join()
    assert b["you"]["name"] == "Prisoner"
    assert b["briefing"]["role"] == "player" and b["briefing"]["you"] == "Prisoner" and b["briefing"]["how"]
    # the owner sees the grant without its token, and that Sam is in
    g = gm.grants()[0]
    assert "token_hash" not in g and g["embodying"] == i["Prisoner"] and g["active"]
    # revoking ends the token and the seat
    gm.revoke(g["id"])
    assert eng.session_for_token(inv["token"]) is None
    assert w.embodied(i["Prisoner"]) is None


def test_open_invite_sees_seats_and_claims_race_to_one_winner():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    gm.patch("Guard", {"playable": True})
    kept = gm.invite("player", entity="Guard", label="Ana")
    a = eng.session_for_token(gm.invite("player", label="one")["token"])
    b = eng.session_for_token(gm.invite("player", label="two")["token"])
    seats = a.seats()
    by = {s["name"]: s for s in seats["seats"]}
    assert by["Prisoner"]["open"] and by["Guard"]["reserved"] and not by["Guard"]["open"]
    with pytest.raises(Rejected) as r:
        a.join()
    assert "seats()" in r.value.hint
    with pytest.raises(Rejected) as r:
        a.join(entity="Guard")
    assert "kept" in r.value.reason and r.value.alternatives == ["Prisoner"]
    with pytest.raises(Rejected):
        a.join(entity="Rusty key")  # not playable
    assert a.join(entity="Prisoner")["you"]["name"] == "Prisoner"
    with pytest.raises(Rejected) as r:
        b.join(entity="Prisoner")
    assert "already embodied" in r.value.reason
    ana = eng.session_for_token(kept["token"])
    assert ana.join()["you"]["name"] == "Guard"
    assert a.seats()["seats"] and all(not s["open"] for s in a.seats()["seats"])
    # evicted: the body is free again
    gm.evict(ana.pid)
    assert {s["name"] for s in b.seats()["seats"] if s["open"]} == set()  # still reserved for Ana
    gm.evict(a.pid)
    assert b.join(entity="Prisoner")["you"]["name"] == "Prisoner"


def test_idle_grant_holder_lapses_and_the_seat_frees():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    w.set_meta({"claim_lapse": 60})
    gm.patch("Prisoner", {"playable": True})
    wall = [1000.0]
    eng.wall = lambda: wall[0]
    a = eng.session_for_token(gm.invite("player", label="a")["token"])
    b = eng.session_for_token(gm.invite("player", label="b")["token"])
    a.join(entity="Prisoner")
    wall[0] = 1030.0
    with pytest.raises(Rejected):
        b.join(entity="Prisoner")
    a.perceive()  # still here: touching keeps the seat
    wall[0] = 1080.0
    with pytest.raises(Rejected):
        b.join(entity="Prisoner")
    wall[0] = 1200.0
    assert b.join(entity="Prisoner")["you"]["name"] == "Prisoner"
    assert w.principal(a.pid) is None
    # the ticker does the same without a claimant
    wall[0] = 1500.0
    out = eng.tick_all()
    assert out["released"] == {"two-rooms": [b.pid]}
    # the owner at the keyboard never lapses
    gm.join("two-rooms", "Guard")
    wall[0] = 9000.0
    assert eng.tick_all()["released"] == {}


def test_template_makes_a_new_character_in_its_place():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.patch(w.root_id, {"templates": {"newcomer": {"type": "person", "place": "Hall", "doc": "a stranger off the road",
                                                    "state": {"coins": 3}}},
                         "briefing": "Two rooms and a locked door."})
    p = eng.session_for_token(gm.invite("player", label="kit")["token"])
    assert p.seats()["templates"][0]["template"] == "newcomer"
    with pytest.raises(Rejected):
        p.join(template="newcomer")  # needs a name
    b = p.join(template="newcomer", name="Kit")
    assert b["you"]["name"] == "Kit" and b["here"]["name"] == "Hall" and b["briefing"]["text"] == "Two rooms and a locked door."
    assert w.get(b["you"]["id"])["state"]["playable"] and w.get(b["you"]["id"])["state"]["coins"] == 3
    with pytest.raises(Rejected):
        eng.session_for_token(gm.invite("player", label="kit2")["token"]).join(template="newcomer", name="kit")


def test_mind_grant_holds_only_its_npcs():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    with pytest.raises(Rejected):
        gm.invite("mind", label="no npc")
    inv = gm.invite("mind", entity="Guard", label="guard-mind")
    m = eng.session_for_token(inv["token"])
    assert m.join()["you"]["name"] == "Guard"
    with pytest.raises(Rejected) as r:
        m.join(entity="Prisoner")
    assert r.value.alternatives == ["Guard"]
    with pytest.raises(Rejected):
        m.spawn("rat", i["Hall"], "Rat")
    with pytest.raises(Rejected):
        m.perceive(from_entity="Prisoner")
    with pytest.raises(Rejected):
        m.join(template="x", name="y")


def test_say_is_capped_for_players_and_carries_provenance():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    gm.patch("Guard", {"playable": True})
    gm.act_as("Prisoner", "take", "Rusty key")
    a = eng.session_for_token(gm.invite("player", entity="Prisoner", label="a")["token"])
    b = eng.session_for_token(gm.invite("player", entity="Guard", label="b")["token"])
    a.join()
    b.join()
    gm.move("Guard", i["Cell"])
    b.perceive()
    with pytest.raises(Rejected):
        a.say("x" * 1001)
    for n in range(30):
        a.say(f"line {n}")
    with pytest.raises(Rejected) as r:
        a.say("one more")
    assert "minute" in r.value.reason
    evs = [e for e in b.perceive(events=50)["events"] if e["kind"] == "say"]
    assert evs and all(e["by_player"] == a.pid and e["untrusted"] is True for e in evs)
    # the owner's own speech carries no stranger mark
    gm.say_as("Rat", "squeak") if w.find(name="Rat") else None
    assert all("by_player" not in e for e in gm.perceive(from_entity="Guard", events=50)["events"] if e["actor"] != i["Prisoner"])


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post(url: str, body: dict, token: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json",
                                          "accept": "application/json, text/event-stream",
                                          **({"authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_http_door_needs_a_bearer_and_serves_the_grants_session():
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
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started
    try:
        url = eng.public_url
        with urllib.request.urlopen(url.replace("/mcp", "/health"), timeout=10) as r:
            assert r.status == 200 and json.loads(r.read())["ok"] is True
        status, body = _post(url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert status == 401 and body["ok"] is False and "grant" in body["reason"]
        status, body = _post(url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, token="nope")
        assert status == 401
        status, body = _post(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                   "params": {"name": "join", "arguments": {}}}, token=inv["token"])
        assert status == 200, body
        out = json.loads(body["result"]["content"][0]["text"])
        assert out["you"]["name"] == "Prisoner" and out["briefing"]["role"] == "player"
        status, body = _post(url, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                   "params": {"name": "spawn", "arguments": {"type": "rat", "parent": i["Cell"]}}},
                             token=inv["token"])
        out = json.loads(body["result"]["content"][0]["text"])
        assert out["ok"] is False and "player" in out["reason"]
        status, body = _post(url, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                   "params": {"name": "say", "arguments": {"text": "hello?", "principal": "other"}}},
                             token=inv["token"])
        out = json.loads(body["result"]["content"][0]["text"])
        assert out["ok"] is False and "one principal" in out["reason"]
        assert w.embodied(i["Prisoner"])["id"] == inv["principal"]
    finally:
        server.should_exit = True
        t.join(timeout=5)


def _get(url: str, token: str | None = None) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.headers.get("content-type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type", ""), e.read()


def test_viewer_is_mounted_behind_the_door_for_watching_roles_only():
    uvicorn = pytest.importorskip("uvicorn")
    from embody.mcp_server import build_server, http_app
    eng, w, i = engine_with_two_rooms()
    port = _free_port()
    eng.public_url = f"http://127.0.0.1:{port}/mcp"
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    player = gm.invite("player", entity="Prisoner", label="Sam")
    eye = gm.invite("observer", label="Eye")
    assert "/watch" in eye["paste"] and "/watch" not in player["paste"]  # only roles the viewer admits are told about it
    told = gm.invite("player", template=None, label="Ana", brief="Find the Prisoner before the Warden does.")
    assert "Find the Prisoner" in told["paste"]
    sess = eng.session_for_token(told["token"])
    assert sess._briefing(i["Prisoner"])["from_the_host"].startswith("Find the Prisoner")
    assert "from_the_host" not in eng.session_for_token(player["token"])._briefing(i["Prisoner"])
    srv = build_server(gm, None, eng, http_only=True)
    server = uvicorn.Server(uvicorn.Config(http_app(srv), host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started
    try:
        base = f"http://127.0.0.1:{port}/watch"
        status, ctype, body = _get(base)
        assert status == 200 and ctype.startswith("text/html") and b"embody watch" in body  # the page needs no grant
        status, _, body = _get(base + "/state.json")
        assert status == 401 and json.loads(body)["ok"] is False
        status, _, body = _get(base + "/state.json", token=player["token"])
        assert status == 403 and "observer" in json.loads(body)["reason"]
        status, _, body = _get(base + "/state.json?limit=5", token=eye["token"])
        assert status == 200, body
        d = json.loads(body)
        assert d["ok"] and d["world"]["id"] == "two-rooms" and {e["id"] for e in d["entities"]} >= {i["Cell"], i["Prisoner"]}
        assert len(d["events"]) <= 5
        status, _, body = _get(base + "/state.json?world=some-other-world", token=eye["token"])
        assert json.loads(body)["world"]["id"] == "two-rooms"  # a grant sees its own world whatever it asks for
        status, _, body = _get(base + "/worlds.json", token=eye["token"])
        assert [x["id"] for x in json.loads(body)] == ["two-rooms"]
        status, _, body = _get(base + "/nothing.json", token=eye["token"])
        assert status == 404
    finally:
        server.should_exit = True
        t.join(timeout=5)


def test_door_calls_write_last_used_once_a_minute():
    from embody.mcp_server import Hub
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    clock = [1000.0]
    eng.wall = lambda: clock[0]
    inv = gm.invite("player", label="kit")
    assert eng.store.get("grants", "two-rooms", inv["id"])["last_used"] is None
    hub = Hub(eng, gm, http_only=True)
    s = hub.for_token(inv["token"])
    assert s.grant["last_used"] == 1000.0
    assert eng.store.get("grants", "two-rooms", inv["id"])["last_used"] == 1000.0
    clock[0] = 1030.0
    hub.for_token(inv["token"])
    assert eng.store.get("grants", "two-rooms", inv["id"])["last_used"] == 1000.0, "one write a minute"
    clock[0] = 1070.0
    hub.for_token(inv["token"])
    assert eng.store.get("grants", "two-rooms", inv["id"])["last_used"] == 1070.0
    assert [g["last_used"] for g in gm.grants() if g["id"] == inv["id"]] == [1070.0]


def test_use_says_who_you_are_and_principals_answers_the_caller():
    from embody.mcp_server import Hub, _current
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    assert gm.use("two-rooms")["you"]["role"] == "owner"
    inv = gm.invite("observer", label="eye")
    eye = eng.session_for_token(inv["token"])
    you = eye.use("two-rooms")["you"]
    assert you["role"] == "observer" and you["grant"] == inv["id"] and you["label"] == "eye"
    assert you["principal"] == inv["principal"]
    hub = Hub(eng, gm, http_only=True)
    tok = _current.set(eye)
    try:
        ps = hub.principals()
    finally:
        _current.reset(tok)
    assert [p["principal"] for p in ps] == [inv["principal"]] and ps[0]["role"] == "observer" and ps[0]["main"]
    assert hub.principals()[0]["principal"] == "gm"


def test_file_paths_over_the_door_stay_inside_the_workspace(tmp_path):
    from embody.workspace import Workspace
    eng, w, i = engine_with_two_rooms()
    eng.workspace = Workspace(tmp_path / "ws")
    (tmp_path / "ws").mkdir()
    gm = owner(eng)
    outside = tmp_path / "elsewhere.json"
    outside.write_text("{}", encoding="utf-8")
    au = eng.session_for_token(gm.invite("author", label="ed")["token"])
    au.use("two-rooms")
    with pytest.raises(Rejected) as r:
        au.restore(str(outside))
    assert "inside the workspace" in r.value.reason
    with pytest.raises(Rejected) as r:
        au.door_path(str(outside.parent / "x" / "build.py"), "load_world")
    assert "inside the workspace" in r.value.reason
    assert au.door_path("two-rooms", "load_world") == "two-rooms"
    assert au.door_path("night-one", "restore") == "night-one"
    inside = tmp_path / "ws" / "saves" / "two-rooms" / "saves" / "night-one.json"
    assert au.door_path(str(inside), "restore") == str(inside)
    with pytest.raises(Rejected) as r:
        gm.restore(str(outside))
    assert "not an embody save" in r.value.reason, "the host's own process reaches the file and is told what it is"
