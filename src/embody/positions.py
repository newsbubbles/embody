"""Positions: where each entity is in the world frame, and whether that is its own.

One rule, the same in map, measure, verify and the viewer:

1. own: its layout has `at`.
2. grid: its `pos` mapped through its container's space (`frame_origin`, `cell`, `heading`).
3. inherited: wherever its container is. A thing carried rides on its carrier; a thing in a chest is where the chest is.

Every place (but the root), and anything directly in a place, needs 1 or 2: a place's centre is not a spot in it. What
lies in no place at all (a story's hidden facts, a species) is off the map and needs none.

Tiers: a place whose state names a `tier` (universe, galaxy, system, planet, continent, region) is a container that
needs no spot of its own. One that also carries a `frame` ({units, bounds}) starts a frame: everything under it is
placed in that frame, not the root's (a region in metres, a planet in km, a system in AU). A spot is never inherited
across a frame's edge, and nothing is measured across one. A tier with no frame of its own shares its parent's.

Landmarks are named spots on a place's layout (`landmarks: {"the well": {"at": [x, y, z], "radius": 3}}`), so an
author or a script places by name (`at="the well"`) and perceive says where someone stands ("by the well").
A thing that changes hands or walks in keeps a true spot: dropped, it lies where the dropper stands; walked in, it
stands where the way comes in. Nothing here changes play: no reach, range, speed or cover.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from . import layout as geo

if TYPE_CHECKING:
    from .world import World

_MAX_DEPTH = 64


def _layout(w: "World", eid: str | None) -> dict[str, Any]:
    e = w.get(eid) if eid else None
    lay = e["state"].get("layout") if e else None
    return lay if isinstance(lay, dict) else {}


def is_place(w: "World", e: dict[str, Any]) -> bool:
    return bool(e) and w.is_a(e["type"], "place")


def is_tier(w: "World", e: dict[str, Any] | None) -> bool:
    """A tier of the world (a galaxy, a planet, a region): a place that holds places and needs no spot of its own."""
    return bool(e) and bool(e["state"].get("tier")) and is_place(w, e)


def starts_frame(w: "World", e: dict[str, Any] | None) -> bool:
    """The root, or a tier with a `frame` of its own: what is under it is placed in that frame."""
    return bool(e) and (e["id"] == w.root_id or (is_tier(w, e) and isinstance(e["state"].get("frame"), dict)))


def frame_of(w: "World", eid: str) -> str:
    """The id whose frame an entity's own spot is in: the nearest frame-starting place above it, else the root. A tier's
    own spot (a planet in its system) is in its parent's frame, like anything else's."""
    e, hops = w.get(eid), 0
    cur = w.get(e["parent_id"]) if e and e["parent_id"] else None
    while cur is not None and hops < _MAX_DEPTH:
        if starts_frame(w, cur):
            return cur["id"]
        cur, hops = (w.get(cur["parent_id"]) if cur["parent_id"] else None), hops + 1
    return w.root_id


def inner_frame(w: "World", eid: str) -> str:
    """The frame what is inside an entity is placed in: its own when it starts one, else the one it is in."""
    e = w.get(eid)
    return eid if starts_frame(w, e) else frame_of(w, eid)


def frame_def(w: "World", fid: str) -> dict[str, Any]:
    """A frame's definition ({units, bounds, geo}): the frame-starting place's `frame`, {} when it has none yet."""
    e = w.get(fid)
    f = e["state"].get("frame") if e else None
    return f if isinstance(f, dict) else {}


def same_frame(w: "World", a: str, b: str) -> bool:
    return frame_of(w, a) == frame_of(w, b)


BESIDE_M = 1.5  # within reach of a hand
HERE_M = 5.0  # a few steps: the same table, the same corner


def apart(w: "World", a: str, b: str) -> float | None:
    """Metres between two bodies by their own spots (or grid cells), or None when either has none, or they are in
    different frames."""
    if not same_frame(w, a, b):
        return None
    ra, rb = resolve(w, a), resolve(w, b)
    if ra["how"] not in ("own", "grid") or rb["how"] not in ("own", "grid") or not ra["at"] or not rb["at"]:
        return None
    return geo.dist3(ra["at"], rb["at"])


def nearness(w: "World", a: str, b: str) -> str | None:
    """How near b is to a inside one place, for perceive: beside (within BESIDE_M), here (within HERE_M) or across
    (the rest of the place). None when either has no spot of its own, or they are in different frames."""
    d = apart(w, a, b)
    if d is None:
        return None
    return "beside" if d <= BESIDE_M else "here" if d <= HERE_M else "across"


def along_at(w: "World", lay: Any) -> list[float] | None:
    """Where a thing on its way stands now: layout `along` {route: [[x, y(, z)], ...], t0, t1, stop?} puts it on the
    route at the share of [t0, t1] the world's time has run (a vehicle on a leg), held at `stop` when it was stopped
    short. None once t1 has passed with no stop (its `at` holds again), or when `along` is missing or malformed."""
    al = lay.get("along") if isinstance(lay, dict) else None
    if not isinstance(al, dict):
        return None
    try:
        pts = [[float(c) for c in p] + [0.0] * (3 - len(p)) for p in al.get("route") or []]
        t0, t1 = float(al["t0"]), float(al["t1"])
        stop = float(al["stop"]) if al.get("stop") is not None else None
    except (TypeError, ValueError, KeyError):
        return None
    if len(pts) < 2 or any(len(p) != 3 for p in pts):
        return None
    if stop is None and w.t >= t1:
        return None
    now = min(w.t, stop) if stop is not None else w.t
    f = 1.0 if t1 <= t0 else min(1.0, max(0.0, (now - t0) / (t1 - t0)))
    segs = [math.dist(a[:2], b[:2]) for a, b in zip(pts, pts[1:])]
    goal, run = f * sum(segs), 0.0
    for (a, b), d in zip(zip(pts, pts[1:]), segs):
        if d > 0 and run + d >= goal:
            k = (goal - run) / d
            return [round(a[i] + (b[i] - a[i]) * k, 2) for i in range(3)]
        run += d
    return [round(c, 2) for c in pts[-1]]


def _room(w: "World", parent: str | None) -> dict[str, Any]:
    """A container's extent as its contents see it: its layout, unless it starts a frame (its own spot and shape are
    in the frame above, not the one its contents are in)."""
    return {} if starts_frame(w, w.get(parent) if parent else None) else _layout(w, parent)


def resolve(w: "World", eid: str) -> dict[str, Any]:
    """Where an entity is: {at, how: own | grid | inherited | none, from: the id it rides on (inherited) or whose space
    it is in (grid)}."""
    e, hops = w.get(eid), 0
    first = eid
    carrier = e["parent_id"] if e else None  # what it rides on: the name an inherited spot is "from"
    while e is not None and hops < _MAX_DEPTH:
        lay = e["state"].get("layout") if isinstance(e["state"].get("layout"), dict) else None
        own = (along_at(w, lay) or lay.get("at")) if lay else None  # on its way (along), else where it stands
        if own:
            return {"at": list(own), "how": "own" if e["id"] == first else "inherited",
                    "from": None if e["id"] == first else carrier}
        parent = e["parent_id"]
        if not parent:
            break
        if starts_frame(w, w.get(parent)):
            break  # a spot is never inherited across a frame's edge (a planet's spot is not a spot on the planet)
        sp = w.space_of(parent) or {}
        if e["pos"] is not None and sp.get("frame_origin") is not None:
            o = list(sp["frame_origin"]) + [0.0] * (3 - len(sp["frame_origin"]))
            cell = float(sp.get("cell") or 1.0)
            h = math.radians(float(sp.get("heading") or 0.0))
            p = [float(x) * cell for x in e["pos"]] + [0.0] * (3 - len(e["pos"]))
            at = [o[0] + p[0] * math.cos(h) + p[1] * math.sin(h), o[1] - p[0] * math.sin(h) + p[1] * math.cos(h),
                  o[2] + p[2]]
            return {"at": at, "how": "grid" if e["id"] == first else "inherited",
                    "from": parent if e["id"] == first else carrier}
        e, hops = w.get(parent), hops + 1
    return {"at": None, "how": "none", "from": None}


def on_map(w: "World", e: dict[str, Any]) -> bool:
    """Whether an entity lies in some place below the root (a place itself counts): only those need a position."""
    cur, hops = e, 0
    while cur is not None and cur["id"] != w.root_id and hops < _MAX_DEPTH:
        if is_place(w, cur):
            return True
        cur, hops = (w.get(cur["parent_id"]) if cur["parent_id"] else None), hops + 1
    return False


def needs_own(w: "World", e: dict[str, Any]) -> bool:
    """Every place but the root and the tiers, and whatever stands directly in a place, needs a spot of its own."""
    if e["id"] == w.root_id or is_tier(w, e) or not on_map(w, e):
        return False
    parent = w.get(e["parent_id"]) if e["parent_id"] else None
    return is_place(w, e) or (parent is not None and is_place(w, parent))


def landmarks(w: "World", place: str | None) -> dict[str, dict[str, Any]]:
    return dict(_layout(w, place).get("landmarks") or {})


def _places_up(w: "World", eid: str | None) -> list[str]:
    """The entity itself if it is a place, then every place it is in, nearest first."""
    out, cur, hops = [], (w.get(eid) if eid else None), 0
    while cur is not None and hops < _MAX_DEPTH:
        if is_place(w, cur):
            out.append(cur["id"])
        cur, hops = (w.get(cur["parent_id"]) if cur["parent_id"] else None), hops + 1
    return out


def _norm(name: str) -> str:
    n = " ".join(str(name).lower().split())
    return n[4:] if n.startswith("the ") else n


def find_landmark(w: "World", where: str, name: str) -> tuple[str, dict[str, Any]] | None:
    """A landmark by name (any case, "the" optional) on `where` or any place it is in, nearest first."""
    want = _norm(name)
    for pid in _places_up(w, where):
        for k, v in landmarks(w, pid).items():
            if _norm(k) == want:
                return k, v
    return None


def landmark_names(w: "World", where: str) -> list[str]:
    seen: list[str] = []
    for pid in _places_up(w, where):
        seen.extend(k for k in landmarks(w, pid) if k not in seen)
    return seen


def ground(w: "World", place: str | None, p: list[float]) -> float | None:
    """The ground's height at p in a place with `terrain` on its own layout, for what stands directly in that place
    (not in a place inside it: a cellar under the ridge keeps its own floor); None where it has no terrain there."""
    return geo.height(_layout(w, place).get("terrain"), p[0], p[1]) if place else None


def solid(lay: dict[str, Any]) -> bool:
    """A thing with an extent is solid (you stand beside the well, not in it) unless its layout says solid: false."""
    return bool(lay.get("at")) and any(lay.get(k) for k in ("radius", "size", "footprint")) and lay.get("solid") is not False


def _inside(lay: dict[str, Any], p: list[float]) -> bool:
    if geo.contains(lay, p) is not True:
        return False
    zr = geo.z_range(lay)
    return zr is None or len(p) < 3 or zr[0] - 0.01 <= p[2] <= zr[1] + 0.01


def solid_at(w: "World", parent: str, p: list[float], skip: str | None = None) -> dict[str, Any] | None:
    """The solid thing in `parent` whose extent holds point p, if any."""
    for c in w.children(parent):
        if c["id"] == skip or is_place(w, c):
            continue
        lay = c["state"].get("layout") if isinstance(c["state"].get("layout"), dict) else {}
        if solid(lay) and _inside(lay, p):
            return c
    return None


def find_spot(w: "World", parent: str, near: list[float], within: float | None = None,
              skip: str | None = None, reserved: dict[str, list[list[float]]] | None = None) -> list[float]:
    """A free spot near a point: inside the container's extent, out of every solid thing there, half a metre or more
    from anyone else's own spot. A deterministic spiral out from `near`, `within` metres at most."""
    pl = _room(w, parent)
    taken = list((reserved or {}).get(parent, []))  # spots already handed out in this pass (verify's suggestions)
    for c in w.children(parent):
        if c["id"] != skip:
            at = (c["state"].get("layout") or {}).get("at") if isinstance(c["state"].get("layout"), dict) else None
            if at:
                taken.append(at)
    z = near[2] if len(near) > 2 else 0.0
    if within is None:
        within = max(3.0, float(pl.get("radius") or 0) * 0.8 or 3.0)
    for k in range(200):
        r = 0.75 * math.sqrt(k)
        if r > within:
            break
        a = k * 2.399963  # the golden angle: the spiral fills the disc evenly
        p = [round(near[0] + r * math.cos(a), 2), round(near[1] + r * math.sin(a), 2), z]
        g = ground(w, parent, p)
        if g is not None:
            p[2] = round(g, 2)  # on a place's terrain a spot stands on its ground
        if pl.get("at") and geo.contains(pl, p) is False:
            continue
        if solid_at(w, parent, p, skip) is not None:
            continue
        if any(geo.ground(p, t) < 0.5 for t in taken):
            continue
        if reserved is not None:
            reserved.setdefault(parent, []).append(p)
        return p
    g = ground(w, parent, near)
    return [round(near[0], 2), round(near[1], 2), round(g, 2) if g is not None else z]


def resolve_at(w: "World", parent: str, spec: Any, skip: str | None = None) -> tuple[list[float], str]:
    """`at` as written by an author: [x, y] or [x, y, z]; a landmark's name on the place or any place it is in (a free
    spot within its radius); or the name of something in the same container (a free spot beside it). Returns the
    point and how it was found."""
    from .world import Rejected
    if isinstance(spec, (list, tuple)):
        v = geo._vec(spec, "at", 2, 3)
        if len(v) == 2:  # no height: the ground's, where the place has terrain
            g = ground(w, parent, v)
            return v + [round(g, 2) if g is not None else 0.0], "coordinates"
        return v, "coordinates"
    if not isinstance(spec, str) or not spec.strip():
        raise Rejected("at is [x, y, z] or a landmark's name", hint='at=[12, -4, 0] or at="the well"')
    lm = find_landmark(w, parent, spec)
    if lm is not None:
        name, v = lm
        return find_spot(w, parent, list(v["at"]), within=float(v.get("radius") or 2.0), skip=skip), f"by {name}"
    want = _norm(spec)
    for c in w.children(parent):
        if c["id"] != skip and _norm(c["name"] or "") == want:
            cat = resolve(w, c["id"])["at"]
            if cat:
                lay = _layout(w, c["id"])
                reach = (float(lay.get("radius") or 0) or max((lay.get("size") or [0, 0])[:2]) / 2 or 0.0) + 1.0
                return find_spot(w, parent, cat, within=reach + 3.0, skip=skip), f"beside {c['name']}"
    names = landmark_names(w, parent)
    pname = (w.get(parent) or {}).get("name", parent)
    sname = (w.get(skip) or {}).get("name", skip) if skip else None
    raise Rejected((f"placing {sname} ({skip}): " if skip else "")
                   + f"no landmark or thing called {spec!r} in {pname} ({parent}), "
                   + (f"where {sname} is, " if skip else "") + f"or in any place {pname} is in",
                   hint=("landmarks here: " + ", ".join(names)) if names else
                   f"{pname} has no landmarks yet: layout(placements=[{{\"entity\": \"{pname}\", \"landmarks\": "
                   "{\"the gate\": {\"at\": [x, y, z], \"radius\": 3}}}]) names its spots, or give at=[x, y, z]")


def walk(w: "World", eid: str, to: Any, budget: float | None,
         spread: bool = False) -> tuple[list[float], bool, str | None]:
    """A body's short move inside the place it stands in, toward `to` ([x, y] in the place's frame, or a landmark's or
    a thing's name there): at most `budget` metres (None: as far as it goes), stopping short of the place's edge and of
    anything solid. A body with no spot of its own here takes one at `to` (with spread, the nearest free one: half a
    metre from anyone, out of anything solid).
    Returns (at, clipped, blocked): where it ends, whether it stopped short, and what stopped it, or None. Writes
    nothing; `stepped` does."""
    from .world import Rejected
    here = w.need(w.need(eid)["parent_id"])
    room = _room(w, here["id"])
    cur = resolve(w, eid)
    z = float(cur["at"][2]) if cur["at"] and len(cur["at"]) > 2 else \
        (geo.z_range(room) or (0.0, 0.0))[0] if room.get("at") else 0.0
    if isinstance(to, (list, tuple)):
        v = geo._vec(to, "to", 2, 3)
        want = [v[0], v[1], z]
    else:
        want, _ = resolve_at(w, here["id"], to, skip=eid)
        want = [want[0], want[1], z]
    start = cur["at"] if cur["at"] and cur["how"] in ("own", "grid") else None
    clipped, blocked = False, None
    if start is None:
        at = find_spot(w, here["id"], want, skip=eid) if spread else want
    else:
        start = [float(start[0]), float(start[1]), z]
        dist = geo.ground(start, want)
        if budget is not None and dist > budget:
            f = budget / dist
            want = [start[0] + (want[0] - start[0]) * f, start[1] + (want[1] - start[1]) * f, z]
            dist, clipped = budget, True
        at, n = start, max(1, math.ceil(dist / 0.25))
        for k in range(1, n + 1):
            p = [start[0] + (want[0] - start[0]) * k / n, start[1] + (want[1] - start[1]) * k / n, z]
            if (g := ground(w, here["id"], p)) is not None:
                p[2] = g
            if room.get("at") and geo.contains(room, p[:2]) is False:
                clipped, blocked = True, "the edge of " + (here["name"] or "this place")
                break
            hit = solid_at(w, here["id"], p, skip=eid)
            if hit is not None:
                clipped, blocked = True, hit["name"] or hit["id"]
                break
            at = p
    if (g := ground(w, here["id"], at)) is not None:
        at = [at[0], at[1], g]  # on terrain a body stands on the ground; z elsewhere is advisory
    at = [round(x, 2) for x in at]
    if room.get("at") and geo.contains(room, at[:2]) is False:
        raise Rejected(f"{at[:2]} is outside {here['name']}", hint="perceive(layout=true) shows the place's extent")
    if solid_at(w, here["id"], at, skip=eid) is not None:
        raise Rejected(f"{at[:2]} is inside something solid", hint="step to a clear spot beside it")
    return at, clipped, blocked


def stepped(w: "World", eid: str, change: dict[str, Any], caused_by: int | None = None) -> tuple[dict[str, Any], str]:
    """Write a step or a turn ({at?, heading?}) to a body's own layout and tell its place: a quiet `stepped {at, frame,
    heading?, from}` to everyone there, `from` the layout it had ({at, heading}, for the viewer's rewind). The step is
    its own record: no `patched` beside it (a herd on a 30-second tick wrote two events a step). Returns the event and
    the frame. No transaction of its own."""
    was = dict(_layout(w, eid))
    w.patch(eid, {"layout": geo.merge(dict(was), change)}, actor=eid, replace=True, caused_by=caused_by, log=False)
    frame = frame_of(w, eid)
    lay = _layout(w, eid)
    pay = {"at": lay.get("at"), "frame": frame, **({"heading": lay["heading"]} if lay.get("heading") is not None else {}),
           "from": {"at": was.get("at"), "heading": was.get("heading")}}
    return w.emit("stepped", actor=eid, target=eid, reach=1, payload=pay, caused_by=caused_by), frame


def heading_of(a: list[float], b: list[float]) -> float | None:
    """The compass heading from a to b (0 north, 90 east), or None when they are the same spot."""
    dx, dy = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None
    return round(math.degrees(math.atan2(dx, dy)) % 360.0, 1)


def spot_words(w: "World", place: str | None, at: list[float] | None) -> str | None:
    """Where in a place a point is, by its landmarks: "at the well" inside one's radius, "by the well" within
    three times it, else nothing."""
    if not place or not at:
        return None
    best = None
    for k, v in landmarks(w, place).items():
        d = geo.ground(at, v["at"])
        r = float(v.get("radius") or 2.0)
        if d <= 3 * r and (best is None or d / r < best[0]):
            best = (d / r, k)
    if best is None:
        return None
    return ("at " if best[0] <= 1 else "by ") + best[1]


def arrival(w: "World", e: dict[str, Any], old: str | None, new: str) -> list[float] | None:
    """Where a thing that changes container lands, when it lands directly in a place: where the one who put it down
    stands (the old container's own spot, if that lies in the new place), else where the way from the old place comes
    in (the end of the drawn route), else, come by a way, by the landmark named for the way's door or the place it
    came from, else near the new place's centre (a world builder, 2026-11-24: every body that walked in unplaced was a verify problem
    the owner fixed by hand). A place that moves (a vehicle rolling on) takes only the way's end. None when none of
    these is known, or the new place is not laid out itself."""
    np_ = w.get(new)
    if np_ is None or not is_place(w, np_) or not old:
        return None
    nl = _room(w, new)
    src = resolve(w, old)
    if not is_place(w, e) and src["how"] in ("own", "grid") and src["at"] and not is_place(w, w.get(old) or {}) and \
            (not nl.get("at") or geo.contains(nl, src["at"]) is not False):
        return find_spot(w, new, src["at"], within=2.0, skip=e["id"])
    ways = [ed for ed in w.edges(old, "connects_to", "out") if ed["target"] == new]
    for ed in ways:
        if ed["data"].get("route"):
            end = list(ed["data"]["route"][-1])
            return find_spot(w, new, end if len(end) == 3 else end + [0.0], within=4.0, skip=e["id"])
    if not ways or is_place(w, e) or not on_map(w, np_):
        return None  # boarding a cart or put in by a hand is no walk through a way: it rides along, as before
    marks = landmarks(w, new)
    names = [(w.get(ed["data"]["via"]) or {}).get("name") for ed in ways if ed["data"].get("via")]
    names.append((w.get(old) or {}).get("name"))
    for name in filter(None, names):
        lm = next((v for k, v in marks.items() if _norm(k) == _norm(name)), None)
        if isinstance(lm, dict) and lm.get("at"):
            at = [float(x) for x in lm["at"]][:3]
            return find_spot(w, new, at + [0.0] * (3 - len(at)), within=max(2.0, float(lm.get("radius") or 0)),
                             skip=e["id"])
    framed = starts_frame(w, np_)
    centre = None if framed else resolve(w, new)["at"]
    if centre is None and not (framed or is_tier(w, np_)):
        return None  # the place has no spot of its own: verify asks to lay it out first
    return find_spot(w, new, list(centre or [0.0, 0.0, 0.0]), skip=e["id"])


def problems(w: "World", e: dict[str, Any], reserved: dict[str, list[list[float]]] | None = None) -> list[dict[str, Any]]:
    """What is wrong with one entity's position, each with the fix: no spot of its own where it needs one, a spot
    outside its container, a spot inside something solid. `reserved` carries the spots suggested so far in one pass,
    so no two suggestions are the same spot."""
    out: list[dict[str, Any]] = []
    if not on_map(w, e):
        return out
    r = resolve(w, e["id"])
    parent = w.get(e["parent_id"]) if e["parent_id"] else None
    pname = parent["name"] if parent else "?"
    lms = landmark_names(w, parent["id"]) if parent else []
    pl = _room(w, parent["id"]) if parent else {}
    framed = parent is not None and starts_frame(w, parent)  # directly in the root or a framed tier: its own frame
    if needs_own(w, e) and r["how"] not in ("own", "grid"):
        if parent and not framed and not is_tier(w, parent) and not resolve(w, parent["id"])["at"]:
            out.append({"problem": "no position", "why": f"{pname}, the place it is in, is not laid out either",
                        "fix": f"lay out {pname} first (layout placements at, radius or size)"})
        else:
            centre = (None if framed else resolve(w, parent["id"])["at"] if parent else None) or [0.0, 0.0, 0.0]
            spot = find_spot(w, parent["id"], centre, skip=e["id"], reserved=reserved) if parent else centre
            out.append({"problem": "no position",
                        "why": (f"it is directly in {pname} and only inherits its centre" if parent and
                                not framed and not is_tier(w, parent) else "a place needs its own spot in the frame"),
                        "fix": {"at": spot, "or": lms[:8]} if lms else {"at": spot}})
        return out
    if r["how"] == "own" and parent and not framed:
        at = r["at"]
        if pl.get("at") and geo.contains(pl, at) is False:
            spot = find_spot(w, parent["id"], resolve(w, parent["id"])["at"] or at, skip=e["id"], reserved=reserved)
            out.append({"problem": "outside its container",
                        "why": f"{geo.edge_distance(pl, at):.1f} beyond the edge of {pname}",
                        "fix": {"at": spot, "or": lms[:8]} if lms else {"at": spot}})
        elif parent and not is_place(w, e):
            s = solid_at(w, parent["id"], at, skip=e["id"])
            if s is not None:
                spot = find_spot(w, parent["id"], at, skip=e["id"], reserved=reserved)
                out.append({"problem": "inside something solid",
                            "why": f"it stands inside {s['name']}'s extent",
                            "fix": {"at": spot, "or_move_into": s["name"]}})
    return out
