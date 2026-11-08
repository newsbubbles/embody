"""embody command line: the same ops, from a shell.

    embody worlds
    embody create "Harbor Town" --seed 3
    embody load worlds/harbor_town.py
    embody join harbor-town smuggler --as nate
    embody perceive
    embody act go tavern
    embody act say --param text="who is asking?"
    embody wait --timeout 20
    embody op define_schema --json '{"id": "door", "extends": "thing"}'
    embody serve --as gm --author        # MCP server on stdio

State that must survive between commands (which principal, which world) lives in
`.embody.json` beside the database. Agents should prefer the MCP server.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

from .ops import AUTHOR, OBSERVER, OPS, Engine, Rejected, Session, call

DEFAULT_DB = Path("worlds") / "embody.db"


def db_path(args: argparse.Namespace) -> Path:
    p = Path(args.db or os.environ.get("EMBODY_DB") or DEFAULT_DB)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def state_file(db: Path) -> Path:
    return db.parent / ".embody.json"


def load_state(db: Path) -> dict[str, Any]:
    f = state_file(db)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(db: Path, st: dict[str, Any]) -> None:
    state_file(db).write_text(json.dumps(st, indent=2), encoding="utf-8")


def open_session(args: argparse.Namespace) -> tuple[Engine, Session, dict[str, Any]]:
    db = db_path(args)
    eng = Engine(db)
    st = load_state(db)
    principal = getattr(args, "as_", None) or os.environ.get("EMBODY_AS") or st.get("principal") or "cli"
    caps = list(st.get("capabilities", {}).get(principal, []))
    if getattr(args, "author", False) and AUTHOR not in caps:
        caps.append(AUTHOR)
    if getattr(args, "observer", False) and OBSERVER not in caps:
        caps.append(OBSERVER)
    world = getattr(args, "world", None) or st.get("worlds", {}).get(principal)
    s = eng.session(principal, world_id=world if world and eng.store.get("world", None, world) else None,
                    capabilities=caps)
    st["principal"] = principal
    st.setdefault("capabilities", {})[principal] = caps
    return eng, s, st


def remember(db: Path, st: dict[str, Any], s: Session) -> None:
    if s.world_id:
        st.setdefault("worlds", {})[s.pid] = s.world_id
    st.setdefault("capabilities", {})[s.pid] = s.capabilities
    save_state(db, st)


# ---- rendering ---------------------------------------------------------------------------


def render_perceive(b: dict[str, Any]) -> str:
    out = []
    you = b["you"]
    here = b["here"]
    if here:
        crumb = " / ".join(x["name"] for x in reversed(here["breadcrumb"]))
        out.append(f"== {here['name']} ({here['id']})  [{crumb}]  t={b['t']:g}")
        if here["state"].get("description"):
            out.append(here["state"]["description"])
    out.append(f"You are {you['name']} ({you['id']}, {you['type']})" +
               (f" at {you['pos']}" if you.get("pos") is not None else ""))
    st = {k: v for k, v in you["state"].items() if k not in ("description", "hidden")}
    if st:
        out.append("  " + ", ".join(f"{k}={json.dumps(v)}" for k, v in st.items()))
    if b["holding"]:
        out.append("Holding: " + ", ".join(f"{c['name']} ({c['id']})" for c in b["holding"]))
    if b["present"]:
        out.append("Here:")
        for c in b["present"]:
            tags = []
            if c.get("embodied_by"):
                tags.append(f"played by {c['embodied_by']}")
            if c.get("pos") is not None:
                tags.append(f"at {c['pos']}")
            desc = c["state"].get("description", "")
            out.append(f"  {c['name']} ({c['id']}, {c['type']})" + (f" [{'; '.join(tags)}]" if tags else "")
                       + (f": {desc}" if desc else ""))
    if b["exits"]:
        out.append("Exits:")
        for x in b["exits"]:
            via = ""
            if x.get("via"):
                st_ = "open" if x.get("open") else "closed"
                if x.get("locked"):
                    st_ += ", locked"
                via = f" via {x['via_name']} ({x['via']}, {st_})"
            out.append(f"  {x['name']} ({x['to']}){via}")
    if b["relations"]:
        out.append("Relations: " + "; ".join(
            f"{r['relation']} {r.get('direction', '')} {r.get('name') or r.get('participants')}" for r in b["relations"]))
    ok = [a for a in b["affordances"] if a["ok"]]
    no = [a for a in b["affordances"] if not a["ok"]]
    if ok:
        out.append("You can: " + ", ".join(f"{a['verb']} {a['target_name'] or ''}".strip() + f" ({a['target']})"
                                            if a["target"] else a["verb"] for a in ok))
    if no:
        out.append("Not now: " + "; ".join(f"{a['verb']} {a['target_name'] or ''}".strip() + f": {a['reason']}" for a in no[:8]))
    if b["events"]:
        out.append("Since you last looked:")
        for e in b["events"]:
            out.append("  " + render_event(e))
    if b.get("timed_out"):
        out.append("(nothing happened)")
    return "\n".join(out)


def render_event(e: dict[str, Any]) -> str:
    p = e["payload"]
    k = e["kind"]
    if k == "say":
        return f"{e['actor']} says: {p.get('text', '')}"
    if k == "act":
        return f"{e['actor']} {p.get('verb')} {p.get('target') or ''}".strip()
    if k == "moved":
        return f"{e['target']} moved {p.get('from')} -> {p.get('to')}" + (f" {p.get('to_pos')}" if p.get("to_pos") else "")
    if k == "spawned":
        return f"{p.get('name') or p.get('type')} ({e['target']}) appeared in {p.get('parent')}"
    if k == "patched":
        return f"{e['target']} changed: " + ", ".join(f"{a}={json.dumps(v)}" for a, v in p.get("changes", {}).items())
    return f"{k} {e['actor'] or ''}->{e['target'] or ''} {json.dumps(p, ensure_ascii=False)}"


def render_act(r: dict[str, Any]) -> str:
    out = [f"ok: {r['verb']} {r.get('target') or ''}".strip()]
    if r.get("result") is not None:
        out.append(f"result: {json.dumps(r['result'])}")
    for e in r.get("events", []):
        if e["kind"] != "act":
            out.append("  " + render_event(e))
    for line in r.get("logs", []):
        out.append("  log: " + line)
    return "\n".join(out)


def emit(args: argparse.Namespace, data: Any, text: str | None = None) -> None:
    if getattr(args, "json", False) or text is None:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        print(text)


def fail(args: argparse.Namespace, r: dict[str, Any]) -> int:
    if getattr(args, "json", False):
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        msg = f"rejected: {r['reason']}"
        if r.get("hint"):
            msg += f"\n  hint: {r['hint']}"
        if r.get("alternatives"):
            msg += "\n  you could: " + ", ".join(r["alternatives"][:10])
        print(msg, file=sys.stderr)
    return 2


def parse_params(items: list[str] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"--param wants key=value, got {it!r}")
        k, v = it.split("=", 1)
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


# ---- world files -------------------------------------------------------------------


def load_world_file(session: Session, path: Path, upgrade: bool = False) -> dict[str, Any]:
    """A world file is a Python module with `build(session)`. It runs with the author's session.

    A file may split build into `define(session)` (scripts and schemas) and `populate(session)` (entities).
    With upgrade=True `define` runs against the world the session points at, then `upgrade(session)` if the
    file has one (idempotent additions: a new place, a prop, a timer, ambient facts). The code is renewed, the
    state and history stay. That is how a forked world picks up engine and world-file changes."""
    spec = importlib.util.spec_from_file_location(f"embody_world_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise Rejected(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if upgrade:
        if not hasattr(mod, "define"):
            raise Rejected(f"{path} has no define(session) function to upgrade with",
                           hint="split build into define(s) for scripts and schemas and populate(s) for entities")
        if not session.world_id:
            raise Rejected("point the session at the world to upgrade first", hint="use(world_id)")
        mod.define(session)
        if hasattr(mod, "upgrade"):
            mod.upgrade(session)
        r = session.summary()
        r["upgraded"] = True
        return r
    if not hasattr(mod, "build"):
        raise Rejected(f"{path} has no build(session) function",
                       hint="def build(s): s.create_world(...); s.define_schema(...); s.spawn(...)")
    return mod.build(session) or session.summary()


# ---- commands --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="embody", description="A deterministic world engine for agents.")
    ap.add_argument("--db", help=f"database file (default {DEFAULT_DB} or $EMBODY_DB)")
    ap.add_argument("--as", dest="as_", help="principal id (default $EMBODY_AS, then the last used)")
    ap.add_argument("--world", help="world id (default: the last one this principal used)")
    ap.add_argument("--author", action="store_true", help="grant this principal the author capability")
    ap.add_argument("--observer", action="store_true", help="grant the observer capability")
    ap.add_argument("--json", action="store_true", help="machine output")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("worlds", help="list worlds")
    c = sub.add_parser("create", help="create an empty world (author)")
    c.add_argument("name")
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--id")
    c.add_argument("--description", default="")
    c = sub.add_parser("load", help="run a world file's build(session) (author)")
    c.add_argument("file")
    c.add_argument("--upgrade", action="store_true",
                   help="run only define(session) against the current world: new code, same state")
    c = sub.add_parser("use", help="point at a world without embodying")
    c.add_argument("world_id")
    c = sub.add_parser("join", help="embody an entity")
    c.add_argument("world_id")
    c.add_argument("entity", help="id or unique name")
    sub.add_parser("leave", help="release the entity you embody")
    c = sub.add_parser("perceive", help="what you sense from where you are")
    c.add_argument("--from", dest="from_entity", help="(author/observer) perceive from another entity")
    c.add_argument("--cursor", type=int)
    c = sub.add_parser("inspect", help="one entity in full")
    c.add_argument("entity")
    c = sub.add_parser("find", help="search entities")
    c.add_argument("--type")
    c.add_argument("--name")
    c.add_argument("--under")
    c.add_argument("--limit", type=int, default=30)
    c = sub.add_parser("history", help="events")
    c.add_argument("--since", type=int, default=0)
    c.add_argument("--kinds", nargs="*")
    c.add_argument("--touching")
    c.add_argument("--limit", type=int, default=50)
    c = sub.add_parser("act", help="do a verb, optionally on a target")
    c.add_argument("verb")
    c.add_argument("target", nargs="?")
    c.add_argument("--param", action="append", help="key=value (value parsed as JSON when possible)")
    c = sub.add_parser("say", help="speak; everyone in your place hears")
    c.add_argument("text")
    c.add_argument("--reach", type=int, default=1)
    c = sub.add_parser("wait", help="block until something happens near you")
    c.add_argument("--timeout", type=float, default=30)
    c.add_argument("--kinds", nargs="*")
    c = sub.add_parser("clock", help="show or set the world clock (author to set)")
    c.add_argument("--run", action="store_true")
    c.add_argument("--pause", action="store_true")
    c.add_argument("--rate", type=float)
    c.add_argument("--step", type=float, help="advance world time by this many seconds")
    c = sub.add_parser("mirror", help="write the markdown projection (author)")
    c.add_argument("--path")
    sub.add_parser("summary", help="world summary")
    c = sub.add_parser("op", help="call any op by name with JSON arguments")
    c.add_argument("name", help="one of: " + ", ".join(OPS))
    c.add_argument("--json-args", dest="json_args", default="{}", help="JSON object of keyword arguments")
    c = sub.add_parser("serve", help="run the MCP server on stdio: embody serve --as gm --author")
    c.add_argument("--name", default="")
    # the global flags again, so they may follow the subcommand (how .mcp.json files are written)
    c.add_argument("--db", default=argparse.SUPPRESS)
    c.add_argument("--as", dest="as_", default=argparse.SUPPRESS)
    c.add_argument("--world", default=argparse.SUPPRESS)
    c.add_argument("--author", action="store_true", default=argparse.SUPPRESS)
    c.add_argument("--observer", action="store_true", default=argparse.SUPPRESS)

    args = ap.parse_args(argv)
    if args.cmd == "serve":
        from .mcp_server import serve
        return serve(args)

    eng, s, st = open_session(args)
    db = db_path(args)
    try:
        if args.cmd == "worlds":
            ws = s.worlds()
            emit(args, ws, "\n".join(f"{w['id']:20} {w['name']:24} entities={w['entities']} t={w['t']:g}"
                                     + (" running" if w["running"] else "") for w in ws) or "no worlds yet")
        elif args.cmd == "create":
            r = s.create_world(args.name, seed=args.seed, id=args.id, description=args.description)
            emit(args, r, f"created {r['id']} ({r['name']}), root {r['root']}")
        elif args.cmd == "load":
            r = load_world_file(s, Path(args.file), upgrade=args.upgrade)
            emit(args, r, f"{'upgraded' if args.upgrade else 'loaded'} {s.world_id}: {json.dumps(r, default=str)[:400]}")
        elif args.cmd == "use":
            emit(args, s.use(args.world_id))
        elif args.cmd == "join":
            b = s.join(args.world_id, args.entity)
            emit(args, b, render_perceive(b))
        elif args.cmd == "leave":
            emit(args, s.leave())
        elif args.cmd == "perceive":
            b = s.perceive(cursor=args.cursor, from_entity=args.from_entity)
            emit(args, b, render_perceive(b))
        elif args.cmd == "inspect":
            emit(args, s.inspect(args.entity))
        elif args.cmd == "find":
            r = s.find(type=args.type, name=args.name, under=args.under, limit=args.limit)
            emit(args, r, "\n".join(f"{c['id']:6} {c['type']:12} {c['name']}" for c in r) or "nothing")
        elif args.cmd == "history":
            r = s.history(since=args.since, kinds=args.kinds, touching=args.touching, limit=args.limit)
            emit(args, r, "\n".join(f"{e['seq']:5} t={e['t']:g} " + render_event(e) for e in r) or "nothing yet")
        elif args.cmd == "act":
            r = s.act(args.verb, args.target, parse_params(args.param))
            emit(args, r, render_act(r))
        elif args.cmd == "say":
            emit(args, s.say(args.text, reach=args.reach), "said.")
        elif args.cmd == "wait":
            b = s.wait(timeout=args.timeout, kinds=args.kinds)
            emit(args, b, render_perceive(b))
        elif args.cmd == "clock":
            run = True if args.run else (False if args.pause else None)
            r = s.clock(run=run, rate=args.rate, step=args.step)
            emit(args, r, f"t={r['t']:g} running={r['running']} rate={r['rate']:g} pending={r['pending']}"
                 + (f"\n" + "\n".join("  " + render_event(e) for e in r["events"]) if r.get("events") else ""))
        elif args.cmd == "mirror":
            r = s.mirror(args.path)
            emit(args, r, f"mirror at {r['root']}: {r['files']} files, {r['removed']} removed")
        elif args.cmd == "summary":
            emit(args, s.summary())
        elif args.cmd == "op":
            kw = json.loads(args.json_args)
            r = call(s, args.name, **kw)
            if isinstance(r, dict) and r.get("ok") is False and "reason" in r:
                remember(db, st, s)
                return fail(args, r)
            emit(args, r)
        remember(db, st, s)
        return 0
    except Rejected as r:
        remember(db, st, s)
        return fail(args, r.to_dict())


if __name__ == "__main__":
    sys.exit(main())
