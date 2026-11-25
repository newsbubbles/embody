"""One server, many worlds (src/embody/hub.py): each world on its own database file and its own process, a token or
an invite goes to the world that minted it on any domain, the rest goes by host, /status says each world's state with
no world data, a world that is down answers 503 while the others serve, and the old single database moves into the
first world's file once."""

import json
import shutil
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.hub import Hub, Router, parse_domains
from embody.ops import AUTHOR, Engine

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def workspace(tmp: Path) -> Path:
    ws = tmp / "ws"
    for w in ("two-rooms", "ferry-at-dusk"):
        shutil.copytree(REPO / "examples" / w, ws / "worlds" / w)
    shutil.copytree(REPO / "packs" / "village", ws / "packs" / "village", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    return ws


def built(tmp: Path, wid: str) -> tuple[Path, str]:
    """A world in its own file, and an owner's token for it."""
    db = tmp / "data" / "worlds" / f"{wid}.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    eng = Engine(db, workspace=workspace(tmp) if not (tmp / "ws").exists() else tmp / "ws", record=False)
    gm = eng.session("host", capabilities=[AUTHOR])
    load_world(gm, wid)
    tok = gm.invite("owner", label="o")["token"]
    eng.store.close()
    return db, tok


def test_tokens_and_invites_route_to_their_world_and_the_rest_goes_by_host(tmp_path):
    _, rooms = built(tmp_path, "two-rooms")
    _, ferry = built(tmp_path, "ferry-at-dusk")
    hub = Hub(["two-rooms", "ferry-at-dusk"], tmp_path / "data", domains=parse_domains("ferry.example=ferry-at-dusk"))
    hub.reindex()
    bearer = lambda t, host=b"rooms.example": {b"authorization": b"Bearer " + t.encode(), b"host": host}
    assert hub.route("/mcp", bearer(ferry)) == "ferry-at-dusk"  # the token decides, whatever the domain
    assert hub.route("/mcp", bearer(rooms, b"ferry.example")) == "two-rooms"
    assert hub.route("/", {b"host": b"ferry.example"}) == "ferry-at-dusk"
    assert hub.route("/", {b"host": b"www.ferry.example:443"}) == "ferry-at-dusk"
    assert hub.route("/", {b"x-forwarded-host": b"ferry.example", b"host": b"internal"}) == "ferry-at-dusk"
    assert hub.route("/", {b"host": b"unknown.example"}) == "two-rooms"  # the first world is the default
    assert hub.route("/mcp", bearer("not-a-token", b"ferry.example")) == "ferry-at-dusk"  # its world refuses it

    eng = Engine(tmp_path / "data" / "worlds" / "ferry-at-dusk.db", workspace=tmp_path / "ws", record=False)
    gm = eng.session("host", capabilities=[AUTHOR], world_id="ferry-at-dusk")
    eng.public_url = "https://ferry.example/mcp"
    link = gm.invite("player", entity="Traveler", label="new")["link"]
    code = link.rsplit("/i/", 1)[1]
    assert hub.route(f"/i/{code}", {b"host": b"rooms.example"}) == "ferry-at-dusk"  # minted a moment ago: a miss re-reads


def test_the_old_single_database_moves_into_the_first_worlds_file_once(tmp_path):
    db, _ = built(tmp_path, "two-rooms")
    legacy = tmp_path / "data" / "embody.db"
    db.rename(legacy)
    (tmp_path / "data" / "seat-requests.jsonl").write_text('{"world": "two-rooms", "name": "Ada"}\n', encoding="utf-8")
    hub = Hub(["two-rooms"], tmp_path / "data")
    assert "entities, grants, events" in hub.migrate(legacy)
    assert legacy.is_file() and db.is_file()  # the old file stays as the backup
    assert "Ada" in db.with_name("seat-requests.jsonl").read_text(encoding="utf-8")  # the queue follows the world
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM grants WHERE world_id='two-rooms'").fetchone()[0] == 1
    con.close()
    assert hub.migrate(legacy) is None  # once


def test_the_old_database_moves_into_the_world_it_holds_not_the_first_listed(tmp_path):
    db, _ = built(tmp_path, "two-rooms")
    legacy = tmp_path / "data" / "embody.db"
    db.rename(legacy)
    hub = Hub(["ferry-at-dusk", "two-rooms"], tmp_path / "data")
    assert str(db) in hub.migrate(legacy)
    assert db.is_file() and not (tmp_path / "data" / "worlds" / "ferry-at-dusk.db").exists()
    assert Hub(["ferry-at-dusk"], tmp_path / "other").migrate(legacy) is None  # holds none of this hub's worlds


def _port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str, host: str, token: str | None = None, body: dict | None = None, accept: str = "application/json"):
    req = urllib.request.Request(url, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"host": host, "accept": accept, "content-type": "application/json",
                                          **({"authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_the_hub_serves_each_world_from_its_own_process_and_a_down_world_does_not_down_the_others(tmp_path, monkeypatch):
    uvicorn = pytest.importorskip("uvicorn")
    _, rooms = built(tmp_path, "two-rooms")
    _, ferry = built(tmp_path, "ferry-at-dusk")
    monkeypatch.setenv("EMBODY_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.delenv("EMBODY_URL", raising=False)
    hub = Hub(["two-rooms", "ferry-at-dusk"], tmp_path / "data", base_port=_port(),
              domains=parse_domains("ferry.example=ferry-at-dusk"))
    hub.worlds["ferry-at-dusk"].port = _port()
    hub.boot()
    stop = threading.Event()
    threading.Thread(target=hub.watch, args=(stop, 0.2), daemon=True).start()
    port = _port()
    server = uvicorn.Server(uvicorn.Config(Router(hub), host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(200):
            if server.started and all(w.state == "up" for w in hub.worlds.values()):
                break
            time.sleep(0.1)
        assert all(w.state == "up" for w in hub.worlds.values()), {w.id: (w.state, w.message) for w in hub.worlds.values()}

        s, h, b = _get(base + "/status", "ferry.example")
        assert s == 200 and json.loads(b)["world"] == "ferry-at-dusk" and json.loads(b)["state"] == "up"
        assert h.get("access-control-allow-origin") == "*" and h.get("cache-control") == "no-store"
        s, _, b = _get(base + "/op/worlds", "rooms.example", token=ferry, body={})
        assert s == 200 and [w["id"] for w in json.loads(b)] == ["ferry-at-dusk"]  # the token's world, on any domain
        s, _, b = _get(base + "/op/invite", "ferry.example", token=ferry, body={"role": "player", "entity": "Traveler"})
        link = json.loads(b)["link"]
        assert link.startswith("http://ferry.example/i/")  # the domain the request came in on
        s, _, page = _get(base + link[len("http://ferry.example"):], "rooms.example", accept="text/plain")
        assert s == 200 and b"ferry" in page.lower()

        (tmp_path / "data" / "maintenance").mkdir()
        (tmp_path / "data" / "maintenance" / "ferry-at-dusk").write_text("upkeep until noon")
        assert json.loads(_get(base + "/status", "ferry.example")[2])["state"] == "maintenance"
        (tmp_path / "data" / "maintenance" / "ferry-at-dusk").unlink()

        hub.worlds["ferry-at-dusk"].proc.kill()
        for _ in range(100):
            if hub.worlds["ferry-at-dusk"].state == "down":
                break
            time.sleep(0.05)
        s, h, b = _get(base + "/op/worlds", "ferry.example", token=ferry, body={})
        why = json.loads(b)["reason"]
        assert s in (502, 503) and ("offline" in why or "did not answer" in why)
        assert _get(base + "/op/worlds", "rooms.example", token=rooms, body={})[0] == 200  # the other still serves
        s, _, b = _get(base + "/health", "x")
        assert s == 200 and json.loads(b)["ok"] is True
        for _ in range(200):  # and it comes back on its own
            if hub.worlds["ferry-at-dusk"].state == "up":
                break
            time.sleep(0.1)
        assert hub.worlds["ferry-at-dusk"].state == "up"
    finally:
        server.should_exit = True
        stop.set()
        hub.stop()


def test_the_cli_writes_into_a_hub_worlds_own_file(tmp_path, monkeypatch):
    import argparse
    from embody.cli import db_path
    (tmp_path / "worlds").mkdir()
    (tmp_path / "worlds" / "two-rooms.db").write_bytes(b"")
    monkeypatch.setenv("EMBODY_DB", str(tmp_path / "embody.db"))
    ns = lambda **kw: argparse.Namespace(**{"db": None, "world": None, **kw})
    assert db_path(ns(world="two-rooms")) == tmp_path / "worlds" / "two-rooms.db"  # railway ssh -- embody --world ...
    assert db_path(ns(world="other")) == tmp_path / "embody.db"  # no file of its own: as before
    assert db_path(ns(world="two-rooms", db=str(tmp_path / "x.db"))) == tmp_path / "x.db"  # --db always wins


def test_a_world_on_its_own_server_is_forwarded_by_its_domain_and_the_others_stay_local(tmp_path, monkeypatch):
    """A world that moved to its own server (its own service, its own engine version) keeps every address its guests
    already use: the hub streams its domain's requests there unchanged (2026-11-24, a world left a shared hub for its own server)."""
    uvicorn = pytest.importorskip("uvicorn")
    _, rooms = built(tmp_path, "two-rooms")
    _, ferry = built(tmp_path, "ferry-at-dusk")
    monkeypatch.setenv("EMBODY_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.delenv("EMBODY_URL", raising=False)
    servers, hubs, stop = [], [], threading.Event()

    def run(hub: Hub) -> str:
        hub.boot()
        threading.Thread(target=hub.watch, args=(stop, 0.2), daemon=True).start()
        port = _port()
        server = uvicorn.Server(uvicorn.Config(Router(hub), host="127.0.0.1", port=port, log_level="error"))
        threading.Thread(target=server.run, daemon=True).start()
        servers.append(server)
        hubs.append(hub)
        for _ in range(200):
            if server.started and all(w.state == "up" for w in hub.worlds.values()):
                break
            time.sleep(0.1)
        assert all(w.state == "up" for w in hub.worlds.values()), {w.id: (w.state, w.message) for w in hub.worlds.values()}
        return f"http://127.0.0.1:{port}"

    try:
        away = run(Hub(["ferry-at-dusk"], tmp_path / "data", base_port=_port()))  # the world's own server
        base = run(Hub(["two-rooms"], tmp_path / "data", base_port=_port(),
                       domains=parse_domains("ferry.example=ferry-at-dusk"),
                       remotes=parse_domains(f"ferry-at-dusk={away}/")))
        s, _, b = _get(base + "/status", "ferry.example")
        assert s == 200 and json.loads(b)["world"] == "ferry-at-dusk" and json.loads(b)["state"] == "up"
        s, _, b = _get(base + "/op/worlds", "ferry.example", token=ferry, body={})
        assert s == 200 and [w["id"] for w in json.loads(b)] == ["ferry-at-dusk"]
        s, _, b = _get(base + "/op/worlds", "ferry.example", token=rooms, body={})
        assert s == 200 and [w["id"] for w in json.loads(b)] == ["two-rooms"]  # a local world's token stays local
        s, _, b = _get(base + "/op/worlds", "rooms.example", token=ferry, body={})
        assert s == 401  # the hub holds none of a remote world's tokens: it is reached by its domain
        assert json.loads(_get(base + "/health", "x")[2])["worlds"] == {"two-rooms": "up", "ferry-at-dusk": "remote"}
    finally:
        for server in servers:
            server.should_exit = True
        stop.set()
        for hub in hubs:
            hub.stop()
