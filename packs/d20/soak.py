"""Soak a world: run it for days with nobody playing and say who went dry and which water ran out.

Part of the d20 pack's water rules, for any world that uses them. The world is built fresh in memory (your
database is not touched), every playable seat is held by someone who never acts (a mind on a watcher, a player
asleep; `--seats none` leaves them empty), and the clock runs in steps. What comes back is per body (lowest
water, hours thirsty, whether thirst put it down and when) and per source (lowest, when it ran dry, how often
something filled it again). A world whose routines keep it alive shows nobody down and no source dry for good.

    uv run python packs/d20/soak.py glass-reach --days 7
    uv run python packs/d20/soak.py glass-reach --days 7 --set "Story.truce=true" --json

`--set "Name.key=value"` patches an entity's state before the soak (a value is read as JSON when it parses, so
true, 3 and "x" all work), to soak the world as a story left it. Exit code 1 when thirst put anyone down.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
DAY = 86400.0


def _value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def soak(world: str, days: float = 7, seats: str = "held", sets: tuple[str, ...] = (), step: float = 600,
         hosted: bool = True) -> dict[str, Any]:
    sys.path.insert(0, str(REPO / "src"))
    from embody.cli import load_world
    from embody.ops import AUTHOR, Engine

    eng = Engine(workspace=REPO)
    gm = eng.session("soak", capabilities=[AUTHOR])
    load_world(gm, world, hosted=hosted)
    for item in sets:
        target, _, value = item.partition("=")
        name, _, key = target.rpartition(".")
        gm.patch(gm.inspect(name)["id"], {key: _value(value)})
    held = []
    if seats == "held":
        for i, seat in enumerate(gm.seats()["seats"]):
            if not seat.get("taken"):
                eng.session(f"idle-{i}").join(gm.world_id, seat["name"])
                held.append(seat["name"])
    rows = gm.find(limit=1000)
    bodies = {r["id"]: r["name"] for r in rows if "water" in r["state"] and "max_water" in r["state"]}
    sources = {r["id"]: r["name"] for r in rows if r["state"].get("water_source") and r["state"].get("left") is not None}
    t0 = gm.world.t
    body = {i: {"name": n, "low": None, "thirsty_h": 0.0, "down_at": None, "end": None, "place": None} for i, n in bodies.items()}
    src = {i: {"name": n, "low": None, "dry_at": None, "refills": 0, "end": None, "last": None} for i, n in sources.items()}

    def sample(dt: float) -> None:
        day = round((gm.world.t - t0) / DAY, 2)
        for i, b in body.items():
            st = gm.world.get(i)["state"]
            w = int(st.get("water") if st.get("water") is not None else 10)
            b["low"] = w if b["low"] is None else min(b["low"], w)
            b["end"] = w
            if st.get("thirsty"):
                b["thirsty_h"] += dt / 3600
            if st.get("down") and st.get("downed_by") == "thirst" and b["down_at"] is None:
                b["down_at"] = day
            p = gm.world.get(gm.world.get(i)["parent_id"]) if gm.world.get(i)["parent_id"] else None
            b["place"] = p["name"] if p else None
        for i, s in src.items():
            e = gm.world.get(i)
            if e is None:
                continue
            left = int(e["state"].get("left") or 0)
            if s["last"] is not None and left > s["last"]:
                s["refills"] += 1
            s["last"] = s["end"] = left
            s["low"] = left if s["low"] is None else min(s["low"], left)
            if left == 0 and s["dry_at"] is None:
                s["dry_at"] = day
            if left > 0:
                s["dry_at"] = None if s["refills"] and s["dry_at"] is not None else s["dry_at"]

    sample(0)
    end = t0 + days * DAY
    while gm.world.t < end:
        dt = min(step, end - gm.world.t)
        gm.clock(step=dt)
        sample(dt)
    for s in src.values():
        s.pop("last")
    down = [b["name"] for b in body.values() if b["down_at"] is not None]
    return {"world": world, "days": days, "seats": seats, "held": held, "set": list(sets),
            "bodies": sorted(body.values(), key=lambda b: (b["low"], b["name"])),
            "sources": sorted(src.values(), key=lambda s: s["name"]), "down": down, "ok": not down}


def render(r: dict[str, Any]) -> str:
    out = [f"{r['world']}: {r['days']} days, seats {r['seats']}" + (f" ({len(r['held'])} held, never acting)" if r["held"] else "")
           + (f", set {', '.join(r['set'])}" if r["set"] else "")]
    out.append("bodies (lowest water first):")
    for b in r["bodies"]:
        out.append(f"  {b['name']:<28} low {b['low']:>2}  end {b['end']:>2}  thirsty {b['thirsty_h']:>5.1f} h"
                   + (f"  DOWN day {b['down_at']}" if b["down_at"] is not None else "") + f"  at {b['place']}")
    out.append("sources:")
    for s in r["sources"]:
        out.append(f"  {s['name']:<28} low {s['low']:>2}  end {s['end']:>2}  refills {s['refills']:>2}"
                   + (f"  dry since day {s['dry_at']}" if s["dry_at"] is not None and s["end"] == 0 else ""))
    out.append("OK: nobody went down of thirst" if r["ok"] else f"DRY: thirst put down {', '.join(r['down'])}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="soak", description=__doc__.split("\n\n")[0])
    ap.add_argument("world", help="a world folder under worlds/")
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--seats", choices=["held", "none"], default="held", help="held: every seat taken by someone who never acts")
    ap.add_argument("--set", action="append", default=[], metavar="NAME.KEY=VALUE")
    ap.add_argument("--step", type=float, default=600, help="world seconds per step")
    ap.add_argument("--story", action="store_true", help="the world as built, not hosted")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = soak(a.world, a.days, a.seats, tuple(a.set), a.step, hosted=not a.story)
    print(json.dumps(r, indent=1) if a.json else render(r))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
