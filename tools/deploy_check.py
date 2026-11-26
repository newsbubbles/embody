"""The checklist for a deploy to a host: before it goes up, the new stage against the last one that went live and
against what the host says is live now; after, each world up on the new container, each domain's page, each remote,
and each world's door for a token you hold. Every item prints the moment it passes or fails, and a failure exits 1.

    uv run python tools/deploy_check.py pre <stage> --url https://<the host> --service <name>
    (upload the stage)
    uv run python tools/deploy_check.py post <stage> --url https://<the host> --service <name> \\
        [--door <world>=<file holding its token>]

`--service` names the host's service: `post` marks the stage as the last good one for it when every item passes
(`.last-good-<service>` beside the stage), and `pre` compares with that stage unless `--last` names another. A token
file is read for its token (a paste's `Bearer <token>`, else the whole file) and the token is never printed.

What fails `pre`: a world, domain or remote the last stage or the live host has that this stage drops (the world
would go down, or its domain would go elsewhere); a site that the last stage shipped and this one does not (the
world's page would die); a world whose build.py is missing. What `post` waits for: /health naming this stage (the
new container, not the old one still answering), then every world `up` and every remote `remote`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

Get = Callable[..., "tuple[int, str]"]


def http(url: str, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None,
         timeout: float = 20) -> tuple[int, str]:
    """(status, text); a host that does not answer is (0, why)."""
    req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": "embody-deploy-check",
                                                                        **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - any failure to reach the host is one answer
        return 0, type(e).__name__


class Checklist:
    """Items printed as they land: ok, FAIL or note."""

    def __init__(self, out: Any = None) -> None:
        self.out = out or sys.stdout
        self.failed = 0

    def item(self, ok: bool | None, text: str) -> None:
        self.failed += ok is False
        mark = "note" if ok is None else ("ok" if ok else "FAIL")
        print(f"[{mark:>4}] {text}", file=self.out, flush=True)

    def done(self, what: str) -> int:
        print(f"{what}: {'all clear' if not self.failed else f'{self.failed} failed'}", file=self.out, flush=True)
        return 1 if self.failed else 0


def _pairs(p: Path) -> dict[str, str]:
    if not p.is_file():
        return {}
    return dict(x.strip().partition("=")[::2] for x in p.read_text(encoding="utf-8").strip().split(",") if x.strip())


def read_stage(stage: Path) -> dict[str, Any]:
    """What a stage holds: its manifest (tools/stage_deploy.py), else what its deploy/ files and folders show."""
    d = stage / "deploy"
    if not d.is_dir():
        raise SystemExit(f"{stage} is not a stage: no deploy/ folder (tools/stage_deploy.py makes one)")
    m = d / "manifest.json"
    if m.is_file():
        out = json.loads(m.read_text(encoding="utf-8"))
        out["id"] = hashlib.sha256(m.read_bytes()).hexdigest()[:12]
        return out
    ids = [w for w in (d / "worlds").read_text(encoding="utf-8").strip().split(",") if w] if (d / "worlds").is_file() \
        else [(d / "world").read_text(encoding="utf-8").strip()] if (d / "world").is_file() else []
    worlds = {}
    for wid in ids:
        site = stage / wid / "site" if "/" in wid else stage / "worlds" / wid / "site"
        files = [p for p in site.rglob("*") if p.is_file()] if site.is_dir() else []
        worlds[wid] = {"commit": None, "site_files": len(files), "site_bytes": sum(p.stat().st_size for p in files)}
    return {"id": None, "engine": None, "worlds": worlds, "domains": _pairs(d / "domains"), "remotes": _pairs(d / "remotes")}


def compare(stage: Path, new: dict[str, Any], last: dict[str, Any] | None, live: dict[str, Any] | None,
            c: Checklist) -> None:
    """The `pre` items: this stage against the last good one and against the host's /health."""
    for wid in new["worlds"]:
        where = stage / wid if "/" in wid else stage / "worlds" / wid
        c.item((where / "build.py").is_file(), f"world {wid}: build.py in the stage")
    if last is None:
        c.item(None, "no last good stage to compare with (--last, or a `post` that passed with --service)")
    else:
        for wid, was in last["worlds"].items():
            now = new["worlds"].get(wid)
            if now is None:
                c.item(wid in new.get("remotes", {}), f"world {wid}: in the last stage, "
                       + ("now a remote" if wid in new.get("remotes", {}) else "MISSING here (it would go down)"))
                continue
            if was.get("site_files") and not now.get("site_files"):
                c.item(False, f"world {wid}: the last stage shipped its site ({was['site_files']} files) and this one "
                              f"has none (pass its site: --world {wid}=<site folder>)")
            elif was.get("site_files") and now["site_files"] < was["site_files"]:
                c.item(None, f"world {wid}: site files {was['site_files']} -> {now['site_files']}")
            if (was.get("commit"), now.get("commit")) != (None, None) and was.get("commit") != now.get("commit"):
                c.item(None, f"world {wid}: {was.get('commit')} -> {now.get('commit')}")
        for wid in new["worlds"]:
            if wid not in last["worlds"]:
                c.item(None, f"world {wid}: new on this host")
        for kind in ("domains", "remotes"):
            for k, v in last.get(kind, {}).items():
                got = new.get(kind, {}).get(k)
                c.item(got == v, f"{kind[:-1]} {k}: " + (f"-> {v}" if got == v else
                                                       f"was -> {v}, now {'-> ' + got if got else 'GONE'}"))
            for k, v in new.get(kind, {}).items():
                if k not in last.get(kind, {}):
                    c.item(None, f"{kind[:-1]} {k}: new, -> {v}")
        if last.get("engine") != new.get("engine"):
            c.item(None, f"engine {last.get('engine')} -> {new.get('engine')}")
    if live is None:
        c.item(None, "the host's /health was not read (--url)")
        return
    for wid, state in (live.get("worlds") or {}).items():
        kept = wid in new["worlds"] or wid in new.get("remotes", {})
        c.item(kept, f"live world {wid} ({state}): " + ("in this stage" if kept else "NOT in this stage (it would go down)"))


def token_of(path: Path) -> str:
    s = path.read_text(encoding="utf-8")
    m = re.search(r"Bearer ([A-Za-z0-9_-]{20,})", s)
    return m.group(1) if m else s.strip()


def watch_health(url: str, new: dict[str, Any], c: Checklist, get: Get, wait: float, every: float = 5) -> dict | None:
    """Poll /health until it names this stage and every world is up; one item per world as it comes up."""
    start, said, health = time.monotonic(), set(), None
    want = {**{w: "up" for w in new["worlds"]}, **{r: "remote" for r in new.get("remotes", {})}}
    while True:
        code, text = get(url.rstrip("/") + "/health")
        try:
            health = json.loads(text) if code == 200 else None
        except ValueError:
            health = None
        fresh = health is not None and (new.get("id") is None or health.get("stage") == new["id"])
        if fresh:
            if "stage" not in said:
                said.add("stage")
                c.item(True if new.get("id") else None, f"/health answers from this stage ({new.get('id')})" if new.get("id")
                       else "this stage has no manifest: /health cannot say it is the new container")
            # a single world's own server (no hub) says only that embody is up: that is its one world's state
            worlds = health.get("worlds") or ({w: "up" for w in want} if len(want) == 1 and health.get("embody") == "up"
                                              else {})
            for w, state in want.items():
                if w not in said and worlds.get(w) == state:
                    said.add(w)
                    c.item(True, f"world {w}: {state} after {time.monotonic() - start:.0f} s")
            if all(w in said for w in want):
                return health
        if time.monotonic() - start > wait:
            if not fresh:
                c.item(False, f"/health never named this stage in {wait:.0f} s (last: {code} "
                              f"{(health or {}).get('stage')}); the old container may still be serving")
            for w, state in want.items():
                if w not in said:
                    c.item(False, f"world {w}: {((health or {}).get('worlds') or {}).get(w)!r} after {wait:.0f} s, "
                                  f"not {state}")
            return health
        time.sleep(every)


def check_after(url: str, new: dict[str, Any], doors: dict[str, Path], c: Checklist, get: Get, wait: float,
                every: float = 5) -> None:
    """The `post` items."""
    watch_health(url, new, c, get, wait, every)
    for host, wid in new.get("domains", {}).items():
        remote = wid in new.get("remotes", {})
        site = (new["worlds"].get(wid) or {}).get("site_files")
        for path in ("/", "/now.json"):
            code, _ = get(f"https://{host}{path}")
            if remote:  # its own server answers, with whatever its own door says without a token
                c.item(0 < code < 500, f"https://{host}{path}: {code or 'no answer'} (forwarded to {wid}'s own server)")
            elif path == "/" and site:
                c.item(code == 200, f"https://{host}/: {code or 'no answer'} ({wid}'s site)")
            else:
                c.item(0 < code < 500, f"https://{host}{path}: {code or 'no answer'} ({wid})")
    for wid, base in new.get("remotes", {}).items():
        code, _ = get(base.rstrip("/") + "/health")
        c.item(code == 200, f"remote {wid}: its own server's /health {code or 'no answer'}")
    for wid, f in doors.items():
        code, text = get(url.rstrip("/") + "/op/worlds", method="POST", body=b"{}",
                         headers={"Authorization": f"Bearer {token_of(f)}", "content-type": "application/json"})
        try:
            ids = [w.get("id") for w in json.loads(text)] if code == 200 else []
        except (ValueError, AttributeError):
            ids = []
        c.item(wid in ids, f"door {wid}: a token's worlds() " + (f"names {wid}" if wid in ids else f"answered {code}"))


def _last(stage: Path, service: str | None, last: str | None) -> Path | None:
    if last:
        return Path(last)
    mark = stage.parent / f".last-good-{service}" if service else None
    return Path(mark.read_text(encoding="utf-8").strip()) if mark and mark.is_file() else None


def main(argv: list[str] | None = None, get: Get = http, out: Any = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("when", choices=("pre", "post"))
    ap.add_argument("stage")
    ap.add_argument("--url", help="the host's base URL (https://...), for /health and the doors")
    ap.add_argument("--service", help="the host's service name: pre reads, post marks its last good stage")
    ap.add_argument("--last", help="the stage to compare with (default: the service's last good one)")
    ap.add_argument("--door", action="append", default=[], help="WORLD=TOKEN_FILE: check that world's door; repeat")
    ap.add_argument("--wait", type=float, default=600, help="seconds post waits for the new container (default 600)")
    ap.add_argument("--every", type=float, default=5, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    stage = Path(a.stage).resolve()
    new = read_stage(stage)
    c = Checklist(out)
    if a.when == "pre":
        last_path = _last(stage, a.service, a.last)
        last = read_stage(last_path) if last_path else None
        if last_path:
            c.item(None, f"comparing with {last_path}")
        live = None
        if a.url:
            code, text = get(a.url.rstrip("/") + "/health")
            try:
                live = json.loads(text) if code == 200 else None
            except ValueError:
                live = None
            c.item(live is not None, f"the host's /health: {code or 'no answer'}")
        compare(stage, new, last, live, c)
        return c.done("pre")
    if not a.url:
        print("post needs --url, the host's base URL", file=sys.stderr)
        return 2
    doors = {}
    for d in a.door:
        wid, _, f = d.partition("=")
        if not Path(f).is_file():
            print(f"--door {wid}: no file {f}", file=sys.stderr)
            return 2
        doors[wid] = Path(f)
    check_after(a.url, new, doors, c, get, a.wait, a.every)
    code = c.done("post")
    if code == 0 and a.service:
        (stage.parent / f".last-good-{a.service}").write_text(str(stage) + "\n", encoding="utf-8")
        print(f"marked {stage} as the last good stage for {a.service}", file=c.out, flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
