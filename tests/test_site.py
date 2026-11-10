"""The public face of a hosted world: the page at /, the two feeds, and seat requests."""

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from embody.ops import AUTHOR
from tests.test_grants import _free_port, owner
from tests.test_ops import engine_with_two_rooms


def _serve(eng, w, tmp_path, site_root=None):
    uvicorn = pytest.importorskip("uvicorn")
    from embody.mcp_server import build_server, http_app
    from embody.site import Site
    port = _free_port()
    eng.public_url = f"http://127.0.0.1:{port}/mcp"
    gm = owner(eng)
    site = Site(eng, w.id, root=site_root, requests=tmp_path / "seat-requests.jsonl")
    srv = build_server(gm, None, eng, http_only=True)
    server = uvicorn.Server(uvicorn.Config(http_app(srv, site=site), host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started
    return gm, server, t, f"http://127.0.0.1:{port}"


def _call(url, body=None, headers=None, method=None, form=False):
    data = None
    h = dict(headers or {})
    if body is not None:
        if form:
            from urllib.parse import urlencode
            data, h["content-type"] = urlencode(body).encode(), "application/x-www-form-urlencoded"
        else:
            data, h["content-type"] = json.dumps(body).encode(), "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method or ("POST" if body is not None else "GET"))

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_the_page_is_served_at_the_root_with_byte_ranges_and_nothing_hidden(tmp_path):
    eng, w, i = engine_with_two_rooms()
    root = tmp_path / "site"
    (root / "media").mkdir(parents=True)
    (root / "index.html").write_text("<h1>The Reach</h1>", encoding="utf-8")
    (root / "media" / "film.mp4").write_bytes(bytes(range(256)) * 4)
    (root / ".secret").write_text("no", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("no", encoding="utf-8")
    gm, server, t, base = _serve(eng, w, tmp_path, site_root=root)
    try:
        status, h, body = _call(base + "/")
        assert status == 200 and body == b"<h1>The Reach</h1>" and h["content-type"].startswith("text/html")
        status, h, body = _call(base + "/media/film.mp4", headers={"range": "bytes=10-19"})
        assert status == 206 and body == bytes(range(10, 20)) and h["content-range"] == "bytes 10-19/1024"
        assert h["content-type"] == "video/mp4" and h["accept-ranges"] == "bytes"
        status, h, body = _call(base + "/media/film.mp4", headers={"range": "bytes=-4"})
        assert status == 206 and body == bytes(range(252, 256))
        status, _, _ = _call(base + "/media/film.mp4", headers={"range": "bytes=5000-"})
        assert status == 416
        for path in ("/.secret", "/../outside.txt", "/%2e%2e/outside.txt", "/nothing.html"):
            status, _, _ = _call(base + path)
            assert status == 401, path  # not the site's: the door answers, and it wants a grant
        status, _, body = _call(base + "/robots.txt")
        assert status == 200 and b"Allow: /" in body  # a link preview needs it, or there is no card
        status, _, _ = _call(base + "/mcp", body={})
        assert status == 401  # the door is still the door
    finally:
        server.should_exit = True
        t.join(timeout=5)


def test_the_feeds_answer_only_for_a_public_world_and_name_nobody(tmp_path):
    eng, w, i = engine_with_two_rooms()
    gm, server, t, base = _serve(eng, w, tmp_path)
    try:
        assert _call(base + "/reach.json")[0] == 401  # not public: the feeds are nobody's
        assert _call(base + "/chronicle.json")[0] == 401
        w.set_meta({"public_feed": True, "public_timers": ["dawn"], "people_type": "creature",
                    "public_board": [{"label": "The wall", "text": "Nine men.", "have": 9, "want": 20}]})
        gm.schedule(30, "dawn", entity=w.root_id, every=86400)
        w.emit("scene", target=i["Cell"], reach=1, payload={"text": "Water drips somewhere you cannot see."})
        gm.say_as("Prisoner", "my secret plan")
        status, _, body = _call(base + "/chronicle.json")
        d = json.loads(body)
        assert status == 200 and [e["text"] for e in d["entries"]] == ["Water drips somewhere you cannot see."]
        assert d["entries"][0]["day"] == 1 and d["now"]["day"] == 1 and "my secret plan" not in body.decode()
        status, _, body = _call(base + "/reach.json")
        r = json.loads(body)
        assert status == 200 and r["clock"]["phases"] == [{"name": "dawn", "at": round(w.t + 30)}]
        assert r["people"] >= 1 and r["board"][0]["have"] == 9 and "awake" in r and "seats_open" in r
        text = body.decode()
        assert "Prisoner" not in text and "Cell" not in text  # counts, never names or places
    finally:
        server.should_exit = True
        t.join(timeout=5)


def test_a_seat_request_is_checked_limited_and_kept_for_the_owner_alone(tmp_path):
    eng, w, i = engine_with_two_rooms()
    w.set_meta({"seat_sides": ["hold", "keth", "any"]})
    gm, server, t, base = _serve(eng, w, tmp_path)
    try:
        ok = {"name": "Wen", "contact": "wen@example.com", "side": "keth", "why": "I want to carry water."}
        assert _call(base + "/seat-request", ok)[0] == 201
        assert _call(base + "/seat-request", {**ok, "side": "dreyer"})[0] == 422  # not one of this world's sides
        assert _call(base + "/seat-request", {**ok, "name": ""})[0] == 422
        assert _call(base + "/seat-request", {**ok, "why": "x" * 401})[0] == 422
        assert _call(base + "/seat-request", {**ok, "website": "http://spam"})[0] == 202  # the hidden field: kept nowhere
        assert _call(base + "/seat-request", method="GET")[0] == 405
        status, h, _ = _call(base + "/seat-request", {**ok, "name": "Kit"}, form=True)
        assert status == 303 and h["location"] == "/#seat"  # a browser without JavaScript goes back to the page
        assert _call(base + "/seat-request", {**ok, "name": "Ana"})[0] == 201
        assert _call(base + "/seat-request", {**ok, "name": "Too many"})[0] == 429  # three an hour from one address
        eng.requests_path = tmp_path / "seat-requests.jsonl"
        got = gm.requests()
        assert [r["name"] for r in got] == ["Ana", "Kit", "Wen"] and got[-1]["contact"] == "wen@example.com"
        assert all("127.0.0.1" not in json.dumps(r) for r in got)  # the address is never written down
        gm.patch("Prisoner", {"playable": True})
        player = eng.session_for_token(gm.invite("player", entity="Prisoner", label="Sam")["token"])
        from embody.ops import Rejected
        with pytest.raises(Rejected):
            player.requests()  # the owner's alone
    finally:
        server.should_exit = True
        t.join(timeout=5)
