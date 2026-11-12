"""The public face of a hosted world, for anyone, with no grant: a landing page served from a folder at `/`, and three
answers built on the server from the world as it is.

  GET /chronicle.json    the world's own prose (scene events by default), oldest first, and the days the owner published
                         with publish_chronicle: no player's words unless the owner put them there
  GET /reach.json        the clock, the day's phases, and counts (bodies held, people, open seats): no names, no places
  POST /seat-request     someone asking for a seat; kept in a file beside the database for the owner's `requests()`

The two feeds answer only for a world whose meta says `public_feed: true`, so a site folder alone never makes a world's
log public. The page is plain files; a path that names a hidden file or climbs out of the folder is nobody's."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote

# Bookkeeping that is not something happening: "last_event_ago" skips it.
QUIET_KINDS = {"patched", "spawned", "destroyed", "linked", "unlinked", "related", "unrelated", "embodied", "released",
               "left", "joined", "intended", "remembered", "clock", "scheduled", "unscheduled", "tick", "opinion", "act_refused"}
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".json": "application/json", ".svg": "image/svg+xml", ".mp4": "video/mp4", ".vtt": "text/vtt; charset=utf-8",
         ".woff2": "font/woff2", ".woff": "font/woff", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
         ".webp": "image/webp", ".txt": "text/plain; charset=utf-8", ".ico": "image/x-icon"}
CHUNK = 256 * 1024
LIMITS = {"name": 60, "contact": 120, "why": 400}
PER_ADDRESS = (3, 3600.0)       # requests one address may send in this many seconds
PER_DAY = 200                   # requests the door takes in a day, from everyone


def _headers(scope: dict[str, Any]) -> dict[bytes, bytes]:
    return dict(scope.get("headers") or [])


async def _send(send: Any, status: int, body: bytes, ctype: str, extra: tuple = (), head: bool = False) -> None:
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", ctype.encode()), (b"content-length", str(len(body)).encode()), *extra]})
    await send({"type": "http.response.body", "body": b"" if head else body})


class Site:
    """One hosted world's public face. `root` is the page's folder (or None: no page, only the feeds); `requests` the
    file seat requests are appended to (or None: the door says it keeps none)."""

    def __init__(self, engine: Any, world_id: str | None, root: str | Path | None = None,
                 requests: str | Path | None = None):
        self.engine = engine
        self.world_id = world_id
        self.root = Path(root).resolve() if root else None
        self.requests = Path(requests) if requests else None
        self._cache: dict[str, tuple[float, bytes]] = {}
        self._asks: dict[str, list[float]] = {}
        self._day: list[float] = []

    # ---- routing ----------------------------------------------------------------------------------------------

    async def handle(self, scope: dict[str, Any], receive: Any, send: Any, path: str) -> bool:
        """Answer if this path is the site's; False hands it on to the door."""
        method = scope.get("method") or "GET"
        if path == "/seat-request":
            if method != "POST":
                await _send(send, 405, b'{"ok": false, "reason": "a seat request is a POST"}', "application/json")
            else:
                await self._seat_request(scope, receive, send)
            return True
        if method not in ("GET", "HEAD"):
            return False
        head = method == "HEAD"
        if path in ("/chronicle.json", "/reach.json"):
            body = await self._feed(path)
            if body is None:
                return False
            await _send(send, 200, body, "application/json", extra=((b"cache-control", b"no-store"),), head=head)
            return True
        f = self._file(path)
        if f is None:
            if path == "/robots.txt" and self.root is not None:
                # a link preview's crawler (X, Slack) reads this first; a refusal here reads as "keep out" and no card
                await _send(send, 200, b"User-agent: *\nAllow: /\n", "text/plain; charset=utf-8", head=head)
                return True
            return False
        await self._serve_file(scope, send, f, head)
        return True

    # ---- the page --------------------------------------------------------------------------------------------

    def _file(self, path: str) -> Path | None:
        if self.root is None:
            return None
        rel = unquote(path).lstrip("/")
        if rel == "" or rel.endswith("/"):
            rel += "index.html"
        parts = rel.split("/")
        if any(p in ("", "..") or p.startswith(".") for p in parts):
            return None
        f = (self.root / rel).resolve()
        if self.root not in f.parents or not f.is_file():
            return None
        return f

    async def _serve_file(self, scope: dict[str, Any], send: Any, f: Path, head: bool) -> None:
        """A file, whole or by one byte range (a phone's video player asks for ranges and plays nothing without them)."""
        size = f.stat().st_size
        ctype = TYPES.get(f.suffix.lower()) or mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        cache = b"no-cache" if f.suffix.lower() in (".html", ".json") else b"public, max-age=3600"
        start, end, status = 0, size - 1, 200
        rng = _headers(scope).get(b"range", b"").decode("latin-1").strip()
        if rng.startswith("bytes=") and "," not in rng and size:
            a, _, b = rng[6:].partition("-")
            try:
                if a:
                    start, end = int(a), (min(int(b), size - 1) if b else size - 1)
                else:
                    start, end = max(0, size - int(b)), size - 1
            except ValueError:
                start, end = 0, -1
            if start > end or start >= size:
                await _send(send, 416, b"", "text/plain", extra=((b"content-range", f"bytes */{size}".encode()),))
                return
            status = 206
        length = end - start + 1 if size else 0
        hdrs = [(b"content-type", ctype.encode()), (b"content-length", str(length).encode()),
                (b"accept-ranges", b"bytes"), (b"cache-control", cache)]
        if status == 206:
            hdrs.append((b"content-range", f"bytes {start}-{end}/{size}".encode()))
        await send({"type": "http.response.start", "status": status, "headers": hdrs})
        if head or length == 0:
            await send({"type": "http.response.body", "body": b""})
            return
        left = length
        with f.open("rb") as fh:
            fh.seek(start)
            while left > 0:
                chunk = fh.read(min(CHUNK, left))
                if not chunk:
                    break
                left -= len(chunk)
                await send({"type": "http.response.body", "body": chunk, "more_body": left > 0})
        if left > 0:
            await send({"type": "http.response.body", "body": b""})

    # ---- the feeds -------------------------------------------------------------------------------------------

    async def _feed(self, path: str) -> bytes | None:
        """Built under the engine's lock, kept a few seconds, so a crowd on the page costs what one visitor does."""
        ttl = 5.0 if path == "/reach.json" else 30.0
        hit = self._cache.get(path)
        now = time.monotonic()
        if hit and now - hit[0] < ttl:
            return hit[1]

        def build() -> Any:
            with self.engine.lock:
                return self.reach() if path == "/reach.json" else self.chronicle()

        out = await asyncio.to_thread(build)
        if out is None:
            return None
        body = json.dumps(out, ensure_ascii=False).encode("utf-8")
        self._cache[path] = (now, body)
        return body

    def _world(self) -> Any:
        if not self.world_id or not self.engine.store.get("world", None, self.world_id):
            return None
        w = self.engine.world(self.world_id)
        return w if w.meta().get("public_feed") else None

    @staticmethod
    def _phases(w: Any, day: float) -> list[dict[str, Any]]:
        """When in the day each of the world's public timers comes round, from the next one pending of each kind."""
        public = set(w.meta().get("public_timers") or [])
        at: dict[str, float] = {}
        for s in w.pending():
            if s["kind"] in public and s["kind"] not in at:
                at[s["kind"]] = round(float(s["t"]) % day)
        return [{"name": k, "at": v} for k, v in sorted(at.items(), key=lambda kv: kv[1])]

    @staticmethod
    def _phase_now(phases: list[dict[str, Any]], t: float, day: float) -> str | None:
        if not phases:
            return None
        tod = t % day
        before = [p for p in phases if p["at"] <= tod]
        return (before[-1] if before else phases[-1])["name"]

    def chronicle(self) -> dict[str, Any] | None:
        """The world's own prose, oldest first: the kinds its meta lists as `public_chronicle` (default: scene), each
        text once."""
        w = self._world()
        if w is None:
            return None
        meta = w.meta()
        day = float(meta.get("day_seconds") or 86400)
        kinds = [str(k) for k in (meta.get("public_chronicle") or ["scene"])]
        marks = ",".join("?" * len(kinds))
        rows = w.store.query("event", f"world_id=? AND kind IN ({marks})", [w.id, *kinds], order="seq DESC", limit=400)
        entries, told = [], set()
        for r in reversed(rows):
            text = str((r.get("payload") or {}).get("text") or "").strip()
            if text and text not in told:  # a line the world says every day is told once
                told.add(text)
                entries.append({"day": int(float(r["t"]) // day) + 1, "kind": r["kind"], "text": text, "t": round(float(r["t"]))})
        phases = self._phases(w, day)
        days: dict[int, dict[str, Any]] = {}
        for r in w.store.query("event", "world_id=? AND kind='chronicled'", (w.id,), order="seq"):
            p = r.get("payload") or {}
            d = int(p.get("day") or 0)
            if p.get("text"):
                days[d] = {"day": d, "title": p.get("title"), "text": str(p["text"]), "t": round(float(r["t"]))}
            else:
                days.pop(d, None)  # withdrawn
        return {"now": {"day": int(w.t // day) + 1, "phase": self._phase_now(phases, w.t, day)}, "entries": entries,
                "days": [days[d] for d in sorted(days)]}

    def reach(self) -> dict[str, Any] | None:
        """The world right now, for anyone: the clock and counts, nothing anyone could be found by."""
        w = self._world()
        if w is None:
            return None
        meta = w.meta()
        day = float(meta.get("day_seconds") or 86400)
        ck = w.clock()
        out: dict[str, Any] = {"clock": {"t": round(w.t), "rate": ck["rate"], "running": ck["running"], "day_seconds": day,
                                         "phases": self._phases(w, day)}}
        # awake: bodies someone holds now, a player or a mind (a mind that waits on a watcher is still there)
        out["awake"] = sum(1 for p in w.principals() if p.get("entity_id") and w.get(p["entity_id"]))
        people = str(meta.get("people_type") or "person")
        is_person: dict[str, bool] = {}
        everyone = w.find(limit=None)
        n = 0
        for e in everyone:
            if e["type"] not in is_person:
                is_person[e["type"]] = any(s["id"] == people for s in w.schema_chain(e["type"]))
            if is_person[e["type"]] and not e["state"].get("dead"):
                n += 1
        out["people"] = n
        kept = {g["entity_id"] for g in w.store.query("grants", "world_id=? AND revoked=0", (w.id,)) if g.get("entity_id")}
        out["seats_open"] = sum(1 for e in everyone
                                if e["state"].get("playable") and not w.embodied(e["id"]) and e["id"] not in kept)
        for r in w.store.query("event", "world_id=?", (w.id,), order="seq DESC", limit=200):
            if r["kind"] not in QUIET_KINDS:
                if ck["rate"]:
                    out["last_event_ago"] = round(max(0.0, w.t - float(r["t"])) / ck["rate"])
                break
        board = meta.get("public_board")
        if isinstance(board, list):
            out["board"] = board[:3]
        return out

    # ---- seat requests ---------------------------------------------------------------------------------------

    def _address(self, scope: dict[str, Any]) -> str:
        fwd = _headers(scope).get(b"x-forwarded-for", b"").decode("latin-1").split(",")[0].strip()
        return fwd or str((scope.get("client") or ("?",))[0])

    async def _seat_request(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """Someone asks for a seat. Checked again here (the page's checks are the browser's), limited by address, and
        appended to the requests file; the address itself is never written down."""
        raw = b""
        while True:
            msg = await receive()
            raw += msg.get("body", b"")
            if len(raw) > 8192:
                await _send(send, 413, b'{"ok": false, "reason": "too long"}', "application/json")
                return
            if not msg.get("more_body"):
                break
        form = "application/x-www-form-urlencoded" in _headers(scope).get(b"content-type", b"").decode("latin-1")

        async def answer(status: int, reason: str = "") -> None:
            if form:  # a browser without JavaScript posted the form: send it back to the page
                where = b"/#seat" if status < 300 else b"/?seat=" + str(status).encode() + b"#seat"
                await send({"type": "http.response.start", "status": 303,
                            "headers": [(b"location", where), (b"content-length", b"0")]})
                await send({"type": "http.response.body", "body": b""})
            else:
                await _send(send, status, json.dumps({"ok": status < 300, **({"reason": reason} if reason else {})}).encode(),
                            "application/json")

        try:
            if form:
                d: Any = {k: v[0] for k, v in parse_qs(raw.decode("utf-8"), keep_blank_values=True).items()}
            else:
                d = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(d, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeDecodeError):
            await answer(400, "the body is not a JSON object")
            return
        if str(d.get("website") or "").strip():
            await answer(202)  # the field people cannot see: something filled it in; it looks taken and is kept nowhere
            return
        ask = {k: " ".join(str(d.get(k) or "").split()) for k in ("name", "contact", "side", "why")}
        sides = None
        if self.world_id and self.engine.store.get("world", None, self.world_id):
            sides = self.engine.world(self.world_id).meta().get("seat_sides")
        bad = [k for k in ("name", "contact") if not ask[k]] + [k for k, n in LIMITS.items() if len(ask[k]) > n]
        if (sides and ask["side"] not in sides) or len(ask["side"]) > 40:
            bad.append("side")
        if bad:
            await answer(422, "check " + ", ".join(sorted(set(bad))))
            return
        if self.requests is None:
            await answer(503, "this server keeps no seat requests")
            return
        now = time.time()
        who = self._address(scope)
        mine = [t for t in self._asks.get(who, []) if now - t < PER_ADDRESS[1]]
        self._day = [t for t in self._day if now - t < 86400]
        if len(mine) >= PER_ADDRESS[0] or len(self._day) >= PER_DAY:
            await answer(429, "too many requests; try again later")
            return
        self._asks[who] = mine + [now]
        self._day.append(now)
        row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "world": self.world_id, **ask}
        try:
            self.requests.parent.mkdir(parents=True, exist_ok=True)
            with self.requests.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            await answer(500, "the request could not be kept")
            return
        await answer(201)


def read_requests(path: str | Path | None, world_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """The seat requests kept for one world, newest first."""
    if not path or not Path(path).is_file():
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("world") == world_id:
            out.append(r)
    return list(reversed(out))[:limit]
