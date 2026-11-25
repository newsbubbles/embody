"""One server, many worlds: `embody hub` runs one `embody serve` per world, each on its own database file, and routes
the public port to them. Each world keeps its own process, file, lock, ticker and restarts, so one busy or broken
world never stalls or downs another.

    EMBODY_WORLDS=my-world,other-world embody hub --port 8900 --data /data

Routing, in order:
- GET /health is the hub's own (the platform's probe): up while the hub is, whatever its worlds are doing.
- GET /status is a world's state with no world data: {world, state: up | maintenance | down, since, message},
  for a site to show "offline" and to poll for the world coming back. The world is the request's host.
- A request with a bearer token goes to the world that minted the token, on any domain.
- GET /i/<code> goes to the world that minted the invite.
- Everything else goes by host: the domain map (hub.json, $EMBODY_DOMAINS), else the first world.
- A world in the domain map may run elsewhere ($EMBODY_REMOTES, world=https://its-server): its requests stream there
  unchanged, so a world that moved to its own server keeps every address its guests already use. The hub holds none
  of its tokens, so a remote world is reached by its domain, never by a token on another world's domain.

Files under --data: worlds/<id>.db, one database per world; hub.json, the domain map ({"domains": {"host": id}});
maintenance/<id>, a flag whose text is the message while a world is down for upkeep on purpose. A first boot finds
the old single database (embody.db) and copies it to the first world's file, keeping the old file as the backup;
the files kept beside it (seat requests, flaw reports, asks) are copied beside the new file, where that world reads them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .grants import token_hash

_HOP = {b"connection", b"keep-alive", b"proxy-authenticate", b"proxy-authorization", b"te", b"trailers",
        b"transfer-encoding", b"upgrade", b"host"}
_STATES = ("up", "maintenance", "down")
_BESIDE = ("seat-requests.jsonl", "flaw-reports.jsonl", "asks.jsonl")  # what a world keeps beside its database file
# the hub's calls to a world's server. The longest call a world answers is a wait (120 s), so a reply silent for 180 s
# is a stuck call and is cut off; a call that finds every connection busy for 10 s gets a 503 instead of a queue
_UPSTREAM = {"connect": 5.0, "read": 180.0, "write": 30.0, "pool": 10.0}
_CONNECTIONS = 1000


class World:
    """One world the hub runs: its id, file, port, process and state."""

    def __init__(self, wid: str, db: Path, port: int):
        self.id, self.db, self.port = wid, db, port
        self.proc: subprocess.Popen | None = None
        self.state, self.since, self.message = "down", time.time(), "starting"
        self.fails = 0

    def set(self, state: str, message: str = "") -> None:
        if state != self.state or message != self.message:
            self.since = time.time() if state != self.state else self.since
            self.state, self.message = state, message

    def status(self, maint: str | None) -> dict[str, Any]:
        if maint is not None:
            return {"world": self.id, "state": "maintenance", "since": self.since, "message": maint or "resting for upkeep"}
        return {"world": self.id, "state": self.state, "since": self.since, "message": self.message}


class Hub:
    """The worlds, the token index and the domain map. No world's data passes through here but its tokens' hashes."""

    def __init__(self, worlds: list[str], data: Path, base_port: int = 9100, domains: dict[str, str] | None = None,
                 remotes: dict[str, str] | None = None):
        if not worlds:
            raise SystemExit("no worlds: set EMBODY_WORLDS or pass --worlds")
        self.data = data
        (data / "worlds").mkdir(parents=True, exist_ok=True)
        self.worlds = {w: World(w, data / "worlds" / f"{w}.db", base_port + i) for i, w in enumerate(worlds)}
        self.first = worlds[0]
        self.remotes = {k: v.rstrip("/") for k, v in (remotes or {}).items() if k not in self.worlds}
        self.domains = {**self._domain_file(), **(domains or {})}
        self.tokens: dict[str, str] = {}
        self._missed: dict[str, float] = {}
        self._lock = threading.Lock()

    # ---- config ----------------------------------------------------------------------------------------------

    def _domain_file(self) -> dict[str, str]:
        p = self.data / "hub.json"
        try:
            raw = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
        except (OSError, ValueError):
            return {}
        return {str(k).lower(): str(v) for k, v in (raw.get("domains") or {}).items()}

    def maintenance(self, wid: str) -> str | None:
        p = self.data / "maintenance" / wid
        try:
            return p.read_text(encoding="utf-8").strip() if p.is_file() else None
        except OSError:
            return ""

    def world_for_host(self, host: str) -> str:
        h = host.split(",")[0].strip().lower().rsplit(":", 1)[0] if host else ""
        known = set(self.worlds) | set(self.remotes)
        if h in self.domains and self.domains[h] in known:
            return self.domains[h]
        if h.startswith("www.") and self.domains.get(h[4:]) in known:
            return self.domains[h[4:]]
        return self.first

    # ---- tokens ----------------------------------------------------------------------------------------------

    def reindex(self) -> None:
        """Token, invite code and spent code hashes to worlds, read from each world's file (read-only)."""
        out: dict[str, str] = {}
        for w in self.worlds.values():
            if not w.db.is_file():
                continue
            try:
                con = sqlite3.connect(f"file:{w.db.as_posix()}?mode=ro", uri=True, timeout=2)
                try:
                    cols = {r[1] for r in con.execute("PRAGMA table_info(grants)")}
                    keys = [c for c in ("token_hash", "code_hash", "spent_hash") if c in cols]
                    if keys:
                        for row in con.execute(f"SELECT {', '.join(keys)} FROM grants WHERE world_id=?", (w.id,)):
                            out.update({h: w.id for h in row if h})
                finally:
                    con.close()
            except sqlite3.Error:
                continue
        with self._lock:
            self.tokens = out

    def world_for_secret(self, secret: str) -> str | None:
        """The world that minted a token or an invite code. A miss re-reads the files, so one minted a moment ago is
        found; the same unknown secret re-reads at most once a minute, so a stream of bad tokens costs nothing."""
        h = token_hash(secret)
        if h not in self.tokens and time.time() - self._missed.get(h, 0.0) > 60.0:
            self.reindex()
            if h not in self.tokens:
                if len(self._missed) > 4096:
                    self._missed.clear()
                self._missed[h] = time.time()
        return self.tokens.get(h)

    def route(self, path: str, headers: dict[bytes, bytes]) -> str:
        auth = headers.get(b"authorization", b"").decode("latin-1")
        if auth.lower().startswith("bearer ") and auth[7:].strip():
            w = self.world_for_secret(auth[7:].strip())
            if w:
                return w
        if path.startswith("/i/"):
            w = self.world_for_secret(path[3:].strip("/"))
            if w:
                return w
        host = (headers.get(b"x-forwarded-host") or headers.get(b"host") or b"").decode("latin-1")
        return self.world_for_host(host)

    # ---- the worlds' processes -------------------------------------------------------------------------------

    def migrate(self, legacy: Path | None) -> str | None:
        """The old single database becomes the file of the world it holds, once: the first of this hub's worlds with
        rows in it (not simply the first world listed), copied with SQLite's backup, its rows for that world counted on
        both sides, the old file kept. A file that holds none of the hub's worlds is left alone. Returns what it did,
        or None."""
        if legacy is None or not legacy.is_file():
            return None
        src = sqlite3.connect(f"file:{legacy.as_posix()}?mode=ro", uri=True)
        try:
            held = {r[0] for r in src.execute("SELECT DISTINCT world_id FROM entity")}
        except sqlite3.Error:
            held = set()
        finally:
            src.close()
        w = next((self.worlds[i] for i in self.worlds if i in held), None)
        if w is None or w.db.exists():
            return None
        src = sqlite3.connect(f"file:{legacy.as_posix()}?mode=ro", uri=True)
        tmp = w.db.with_suffix(".db.part")
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
            counts = [tuple(c.execute(f"SELECT count(*) FROM {t} WHERE world_id=?", (w.id,)).fetchone()[0]
                            for t in ("entity", "grants", "event")) for c in (src, dst)]
        finally:
            src.close()
            dst.close()
        if counts[0] != counts[1]:
            tmp.unlink()
            raise SystemExit(f"copying {legacy} to {w.db}: counts differ {counts}; nothing moved")
        tmp.rename(w.db)
        for name in _BESIDE:  # the world reads these beside its database: they follow it, the old ones stay
            if legacy.with_name(name).is_file() and not w.db.with_name(name).exists():
                shutil.copy2(legacy.with_name(name), w.db.with_name(name))
        return f"moved {legacy} to {w.db} (entities, grants, events: {counts[0]}); the old file stays as the backup"

    def _env(self, w: World) -> dict[str, str]:
        env = {**os.environ, "EMBODY_DB": str(w.db), "EMBODY_WORLD": w.id}
        env.pop("EMBODY_URL", None)  # invite links take the domain each request came in on
        site = os.environ.get("EMBODY_SITES")
        if site and (Path(site) / w.id).is_dir():
            env["EMBODY_SITE"] = str(Path(site) / w.id)
        else:
            env.pop("EMBODY_SITE", None)
        return env

    def load(self, w: World) -> bool:
        """Build a world into its file the first time, renew it every later boot (deploy/start.sh's rule)."""
        cmd = [sys.executable, "-m", "embody.cli", "--author", "--world", w.id, "load", w.id, "--upgrade", "--hosted"] \
            if _has_world(w.db, w.id) else [sys.executable, "-m", "embody.cli", "--author", "load", w.id, "--hosted"]
        print(f"[hub] {'renewing' if '--upgrade' in cmd else 'building'} {w.id} in {w.db}", flush=True)
        r = subprocess.run(cmd, env=self._env(w), capture_output=True, text=True)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
            print(f"[hub] {w.id} failed to load:\n  " + "\n  ".join(tail), flush=True)
            w.set("down", "failed to load")
            return False
        return True

    def start(self, w: World) -> None:
        cmd = [sys.executable, "-m", "embody.cli", "--author", "--world", w.id, "serve", "--http", "--host", "127.0.0.1",
               "--port", str(w.port), "--log-level", os.environ.get("EMBODY_LOG_LEVEL", "warning")]
        w.proc = subprocess.Popen(cmd, env=self._env(w))
        w.set("down", "starting")
        print(f"[hub] {w.id} serving on 127.0.0.1:{w.port} (pid {w.proc.pid})", flush=True)

    def boot(self, legacy: Path | None = None) -> None:
        moved = self.migrate(legacy)
        if moved:
            print(f"[hub] {moved}", flush=True)
        for w in self.worlds.values():
            if self.load(w):
                self.start(w)
        self.reindex()

    def watch(self, stop: threading.Event, period: float = 2.0) -> None:
        """Every couple of seconds: is each world's process alive and answering /health? A dead one restarts after a
        wait that grows (2 s, 4 s, ... 5 min); one that failed to load stays down until the next deploy."""
        import urllib.request
        waits: dict[str, float] = {}
        while not stop.is_set():
            for w in self.worlds.values():
                if w.proc is None:
                    continue
                if w.proc.poll() is not None:
                    if w.state == "up" or w.message == "starting":
                        w.fails += 1
                        waits[w.id] = time.time() + min(300.0, 2.0 ** w.fails)
                        w.set("down", f"stopped (exit {w.proc.returncode}); restarting")
                        print(f"[hub] {w.id} stopped with exit {w.proc.returncode}", flush=True)
                    if time.time() >= waits.get(w.id, 0):
                        self.start(w)
                    continue
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{w.port}/health", timeout=2) as r:
                        ok = r.status == 200
                except OSError:
                    ok = False
                if ok:
                    if w.state != "up":
                        print(f"[hub] {w.id} is up", flush=True)
                        w.fails = 0
                    w.set("up")
            stop.wait(period)

    def stop(self) -> None:
        for w in self.worlds.values():
            if w.proc is not None and w.proc.poll() is None:
                w.proc.terminate()
        for w in self.worlds.values():
            if w.proc is not None:
                try:
                    w.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    w.proc.kill()


def _has_world(db: Path, wid: str) -> bool:
    if not db.is_file():
        return False
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            return con.execute("SELECT 1 FROM world WHERE id=?", (wid,)).fetchone() is not None
        finally:
            con.close()
    except sqlite3.Error:
        return False


async def _reply(send: Any, status: int, body: Any, ctype: str = "application/json",
                 extra: tuple[tuple[bytes, bytes], ...] = ()) -> None:
    data = body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", ctype.encode()), (b"content-length", str(len(data)).encode()),
                            (b"cache-control", b"no-store"), *extra]})
    await send({"type": "http.response.body", "body": bytes(data)})


_OFFLINE = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<title>{name}</title><body style='font:16px/1.5 system-ui;max-width:32em;margin:4em auto;padding:0 16px'>"
            "<p><b>{name}</b> is currently offline{why}.</p><p>This page checks again on its own.</p>"
            "<script>setTimeout(()=>location.reload(),30000)</script>")


class Router:
    """The hub's ASGI app: its own /health and /status, everything else streamed to the world's server unchanged
    (headers, body and the server-sent events of the MCP door), with the client's host passed on so each world's
    invite links carry the domain the guest came in on."""

    def __init__(self, hub: Hub):
        self.hub = hub
        self._client: Any = None

    def client(self) -> Any:
        if self._client is None:
            import httpx2
            self._client = httpx2.AsyncClient(timeout=httpx2.Timeout(**_UPSTREAM), follow_redirects=False,
                                              limits=httpx2.Limits(max_connections=_CONNECTIONS,
                                                                   max_keepalive_connections=100))
        return self._client

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            while True:
                msg = await receive()
                if msg["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif msg["type"] == "lifespan.shutdown":
                    if self._client is not None:
                        await self._client.aclose()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            return
        path, method = scope.get("path") or "", scope.get("method") or "GET"
        headers = dict(scope.get("headers") or [])
        hub = self.hub
        if path == "/health" and method == "GET":
            await _reply(send, 200, {"ok": True, "embody": "up",
                                     "worlds": {**{w.id: w.status(hub.maintenance(w.id))["state"] for w in hub.worlds.values()},
                                                **{r: "remote" for r in hub.remotes}}})
            return
        wid = hub.route(path, headers)
        if wid in hub.remotes:  # its own server answers everything, /status and its offline page included
            await self._proxy(scope, receive, send, wid, headers, hub.remotes[wid])
            return
        w = hub.worlds[wid]
        maint = hub.maintenance(wid)
        if path == "/status":
            cors = ((b"access-control-allow-origin", b"*"), (b"access-control-allow-methods", b"GET, OPTIONS"))
            await _reply(send, 204 if method == "OPTIONS" else 200, b"" if method == "OPTIONS" else w.status(maint),
                         extra=cors)
            return
        if w.state != "up":
            why = f" ({maint or w.message})" if (maint is not None or w.message) else ""
            if method == "GET" and b"text/html" in headers.get(b"accept", b""):
                await _reply(send, 503, _OFFLINE.format(name=wid, why=why).encode(), ctype="text/html; charset=utf-8",
                             extra=((b"retry-after", b"30"),))
            else:
                await _reply(send, 503, {"ok": False, "reason": f"the world {wid} is offline{why}",
                                         "hint": "GET /status says when it is back; try again then"},
                             extra=((b"retry-after", b"30"),))
            return
        await self._proxy(scope, receive, send, wid, headers, f"http://127.0.0.1:{w.port}")

    async def _proxy(self, scope: dict[str, Any], receive: Any, send: Any, wid: str, headers: dict[bytes, bytes],
                     base: str) -> None:
        body = b""
        while True:
            msg = await receive()
            body += msg.get("body", b"")
            if not msg.get("more_body"):
                break
        out = [(k, v) for k, v in scope.get("headers") or [] if k.lower() not in _HOP]
        host = headers.get(b"host", b"")
        if b"x-forwarded-host" not in headers and host:
            out.append((b"x-forwarded-host", host))
        if b"x-forwarded-proto" not in headers:
            out.append((b"x-forwarded-proto", (scope.get("scheme") or "http").encode()))
        qs = scope.get("query_string") or b""
        path = scope.get("raw_path", b"").decode("latin-1") or scope["path"]
        url = base + path
        if qs and "?" not in url:
            url += "?" + qs.decode("latin-1")
        work = asyncio.ensure_future(self._forward(scope.get("method") or "GET", url, out, body, send, wid, path))
        gone = asyncio.ensure_future(_disconnected(receive))
        await asyncio.wait({work, gone}, return_when=asyncio.FIRST_COMPLETED)
        for t in (work, gone):  # a client that went away cancels its call, and the connection goes back to the pool
            t.cancel()
        if work.done() and not work.cancelled():
            work.result()

    async def _forward(self, method: str, url: str, headers: list[tuple[bytes, bytes]], body: bytes, send: Any,
                       wid: str, path: str) -> None:
        import httpx2
        client = self.client()
        try:
            req = client.build_request(method, url, headers=headers, content=body)
            resp = await client.send(req, stream=True)
        except httpx2.PoolTimeout:
            await _reply(send, 503, {"ok": False, "reason": f"the world {wid} has {_CONNECTIONS} calls open; this one "
                                                            "waited its turn and gave up",
                                     "hint": "try again in a few seconds"}, extra=((b"retry-after", b"5"),))
            return
        except Exception as e:  # the world's process died between the check and the call, or never answered
            await _reply(send, 502, {"ok": False, "reason": f"the world {wid} did not answer ({type(e).__name__})",
                                     "hint": "GET /status, then try again"})
            return
        try:
            await send({"type": "http.response.start", "status": resp.status_code,
                        "headers": [(k.lower(), v) for k, v in resp.headers.raw if k.lower() not in _HOP]})
            async for chunk in resp.aiter_raw():
                await send({"type": "http.response.body", "body": chunk, "more_body": True})
            await send({"type": "http.response.body", "body": b""})
        except Exception as e:  # cut off midway: the reply is left unfinished, so the client sees it broke
            print(f"hub: {wid} {method} {path.split('?')[0]}: reply cut off "
                  f"({type(e).__name__})", flush=True)
        finally:
            await resp.aclose()


async def _disconnected(receive: Any) -> None:
    """Returns when the client is gone (the server says so once the reply is done, too)."""
    while (await receive())["type"] != "http.disconnect":
        pass


def parse_domains(text: str | None) -> dict[str, str]:
    """`host=world,host=world` (from $EMBODY_DOMAINS) as a map; `world=url,...` ($EMBODY_REMOTES) reads the same."""
    out: dict[str, str] = {}
    for part in (text or "").split(","):
        if "=" in part:
            h, w = part.split("=", 1)
            if h.strip() and w.strip():
                out[h.strip().lower()] = w.strip()
    return out


def main(args: argparse.Namespace) -> int:
    import uvicorn
    worlds = [w.strip() for w in (args.worlds or os.environ.get("EMBODY_WORLDS") or "").split(",") if w.strip()]
    data = Path(args.data or os.environ.get("EMBODY_DATA") or Path(os.environ.get("EMBODY_DB", "/data/embody.db")).parent)
    hub = Hub(worlds, data, base_port=int(args.base_port), domains=parse_domains(args.domains or os.environ.get("EMBODY_DOMAINS")),
              remotes=parse_domains(getattr(args, "remotes", None) or os.environ.get("EMBODY_REMOTES")))
    legacy = Path(args.legacy) if args.legacy else data / "embody.db"
    hub.boot(legacy)
    stop = threading.Event()
    threading.Thread(target=hub.watch, args=(stop,), name="embody-hub-watch", daemon=True).start()
    port = int(args.port or os.environ.get("PORT") or 8900)
    print(f"[hub] {', '.join(hub.worlds)} behind 0.0.0.0:{port}; domains {hub.domains or '(none: all to ' + hub.first + ')'}"
          + (f"; remote {hub.remotes}" if hub.remotes else ""), flush=True)
    try:
        uvicorn.run(Router(hub), host=args.host, port=port, log_level=args.log_level or "warning", proxy_headers=False)
    finally:
        stop.set()
        hub.stop()
    return 0
