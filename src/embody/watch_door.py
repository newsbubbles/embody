"""`embody watch --door <.mcp.json>`: a watcher over a hosted world's door.

It is the long wait a mind (or a narrator, or the host) runs from a shell instead of looping wait() turn after
turn: it connects with the grant in the door file, calls wait(until=...) in short pieces for as long as --for
says, reconnects when the line drops, takes the seat again with --rejoin if it lapsed, and exits printing what
happened when the condition comes true (FIRED) or the time is up (TIME UP). Every wait keeps the seat warm.
Exit code 0 for both; 2 when the door refuses (the reason is printed); 3 when the door has been unreachable for
LOST_LIMIT, so whoever runs it wakes and looks instead of sitting blind until --for runs out. The token never
leaves the door file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

PIECE = 50.0  # seconds per wait call: under what proxies and clients hold a request open
LOST_LIMIT = 600.0  # seconds without the door before the watch gives up: past a redeploy, short of a blind night


def cause(e: BaseException) -> str:
    """The error under the transport's exception groups, as one short line."""
    while isinstance(e, BaseExceptionGroup) and e.exceptions:
        e = e.exceptions[0]
    return f"{type(e).__name__}: {str(e)[:160]}".rstrip(": ")


def read_door(path: str, server: str | None = None) -> tuple[str, str]:
    """The URL and the Authorization header from a .mcp.json (an http server entry), or from any text file with
    an https URL ending in /mcp and 'Bearer <token>' in it (an invite paste)."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        servers = json.loads(text).get("mcpServers") or {}
    except (json.JSONDecodeError, AttributeError):
        servers = {}
    for name, conf in servers.items():
        if server and name != server:
            continue
        if isinstance(conf, dict) and conf.get("url"):
            auth = (conf.get("headers") or {}).get("Authorization") or ""
            if auth:
                return conf["url"], auth
    if servers and server:
        raise SystemExit(f"{path}: no server named {server!r} with a URL and a bearer token")
    m_url = re.search(r"(https?://\S+?/mcp)\b", text)
    m_tok = re.search(r"Bearer ([A-Za-z0-9_-]+)", text)
    if m_url and m_tok:
        return m_url.group(1), f"Bearer {m_tok.group(1)}"
    raise SystemExit(f"{path}: no server URL with a bearer token in it"
                     + (f" under the name {server!r}" if server else ""))


def _one(res: Any) -> Any:
    raw = "".join(c.text for c in res.content if hasattr(c, "text"))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def watch_door(args: argparse.Namespace) -> int:
    import anyio
    return anyio.run(_watch, args)


async def _watch(args: argparse.Namespace) -> int:
    import anyio
    import httpx2
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    from .cli import parse_span, render_watch

    url, auth = read_door(args.door, args.server)
    end = time.monotonic() + parse_span(args.for_)
    since: int | None = None
    who = {"principal": args.principal} if args.principal else {}
    lost: float | None = None  # when the door was last lost, while it stays lost

    def out(r: dict[str, Any]) -> int:
        print(json.dumps(r, default=str) if args.json else render_watch(r))
        return 0

    while True:
        try:
            async with httpx2.AsyncClient(headers={"Authorization": auth}, timeout=PIECE + 60) as hc, \
                    streamable_http_client(url, http_client=hc) as streams:
                async with ClientSession(streams[0], streams[1]) as s:
                    await s.initialize()
                    lost = None
                    world = args.world
                    if not world:
                        ws = _one(await s.call_tool("worlds", {}))
                        ws = ws if isinstance(ws, list) else [ws]
                        world = next((w.get("id") for w in ws if isinstance(w, dict) and w.get("id")), None)
                    if world:
                        await s.call_tool("use", {"world_id": world})
                    while True:
                        left = end - time.monotonic()
                        a: dict[str, Any] = {"timeout": max(0.0, min(left, PIECE)), **who}
                        if args.until:
                            a["until"] = args.until
                            if since is not None:
                                a["since"] = since
                        if args.full:
                            a["full"] = True
                        r = _one(await s.call_tool("wait", a))
                        if isinstance(r, dict) and r.get("ok") is False:
                            reason = str(r.get("reason", ""))
                            if args.rejoin and ("not embodied" in reason or "not in this world" in reason):
                                j = _one(await s.call_tool("join", {"world_id": world, **who}))
                                if not (isinstance(j, dict) and j.get("ok") is False):
                                    print(f"(the seat had lapsed; took it again at t={j.get('t', '?')})", file=sys.stderr)
                                    continue
                                reason = str(j.get("reason", reason))
                            print(f"REFUSED: {reason}" + (f"\nhint: {r.get('hint')}" if r.get("hint") else ""))
                            return 2
                        if not isinstance(r, dict) or "raw" in r:
                            raw = r.get("raw") if isinstance(r, dict) else r
                            print(f"REFUSED: the door answered {str(raw)[:400]}"
                                  + ("\nhint: this server is older than wait(until=...); drop --until, or ask the host"
                                     " to update it" if args.until and "until" in str(raw) else ""))
                            return 2
                        if not r.get("timed_out") or left <= PIECE:
                            return out(r)
                        since = r.get("since", since)
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:  # the line dropped, a redeploy, a proxy timeout: wait a little and go again
            if time.monotonic() >= end:
                print(f"TIME UP (the door was unreachable at the end: {cause(e)})")
                return 0
            lost = lost or time.monotonic()
            if time.monotonic() - lost >= LOST_LIMIT:
                print(f"LOST THE DOOR for {round((time.monotonic() - lost) / 60)} min ({cause(e)}): nothing was watched "
                      f"since. Check the server with one wait() call, then start the watch again.")
                return 3
            print(f"(lost the door: {cause(e)}; trying again in 15 s)", file=sys.stderr)
            await anyio.sleep(15)
