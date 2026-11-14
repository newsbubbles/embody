"""Positions: where each entity is in the world frame, and whether that is its own.

One rule, the same in map, measure, verify and the viewer:

1. own: its layout has `at`.
2. grid: its `pos` mapped through its container's space (`frame_origin`, `cell`, `heading`).
3. inherited: wherever its container is. A thing carried rides on its carrier; a thing in a chest is where the chest is.

Every place (but the root), and anything directly in a place, needs 1 or 2: a place's centre is not a spot in it. What
lies in no place at all (a story's hidden facts, a species) is off the map and needs none.

Landmarks are named spots on a place's layout (`landmarks: {"the cistern": {"at": [x, y, z], "radius": 3}}`), so an
author or a script places by name (`at="the cistern"`) and perceive says where someone stands ("by the cistern").
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


def resolve(w: "World", eid: str) -> dict[str, Any]:
    """Where an entity is: {at, how: own | grid | inherited | none, from: the id it rides on (inherited) or whose space
    it is in (grid)}."""
    e, hops = w.get(eid), 0
    first = eid
    carrier = e["parent_id"] if e else None  # what it rides on: the name an inherited spot is "from"
    while e is not None and hops < _MAX_DEPTH:
        own = (e["state"].get("layout") or {}).get("at") if isinstance(e["state"].get("layout"), dict) else None
        if own:
            return {"at": list(own), "how": "own" if e["id"] == first else "inherited",
                    "from": None if e["id"] == first else carrier}
        parent = e["parent_id"]
        if not parent:
            break
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
    """Every place but the root, and whatever stands directly in a place, needs a spot of its own."""
    if e["id"] == w.root_id or not on_map(w, e):
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


def solid(lay: dict[str, Any]) -> bool:
    """A thing with an extent is solid (you stand beside the cistern, not in it) unless its layout says solid: false."""
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
    pl = _layout(w, parent)
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
        if pl.get("at") and geo.contains(pl, p) is False:
            continue
        if solid_at(w, parent, p, skip) is not None:
            continue
        if any(geo.ground(p, t) < 0.5 for t in taken):
            continue
        if reserved is not None:
            reserved.setdefault(parent, []).append(p)
        return p
    return [round(near[0], 2), round(near[1], 2), z]


def resolve_at(w: "World", parent: str, spec: Any, skip: str | None = None) -> tuple[list[float], str]:
    """`at` as written by an author: [x, y] or [x, y, z]; a landmark's name on the place or any place it is in (a free
    spot within its radius); or the name of something in the same container (a free spot beside it). Returns the
    point and how it was found."""
    from .world import Rejected
    if isinstance(spec, (list, tuple)):
        v = geo._vec(spec, "at", 2, 3)
        return (v if len(v) == 3 else v + [0.0]), "coordinates"
    if not isinstance(spec, str) or not spec.strip():
        raise Rejected("at is [x, y, z] or a landmark's name", hint='at=[12, -4, 0] or at="the cistern"')
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
    raise Rejected(f"no landmark or thing called {spec!r} in {pname}",
                   hint=("landmarks here: " + ", ".join(names)) if names else
                   f"{pname} has no landmarks yet: layout(placements=[{{\"entity\": \"{pname}\", \"landmarks\": "
                   "{\"the gate\": {\"at\": [x, y, z], \"radius\": 3}}}]) names its spots, or give at=[x, y, z]")


def spot_words(w: "World", place: str | None, at: list[float] | None) -> str | None:
    """Where in a place a point is, by its landmarks: "at the cistern" inside one's radius, "by the cistern" within
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
    in (the end of the drawn route). None when neither is known."""
    np_ = w.get(new)
    if np_ is None or not is_place(w, np_) or is_place(w, e) or not old:
        return None
    nl = _layout(w, new)
    src = resolve(w, old)
    if src["how"] in ("own", "grid") and src["at"] and not is_place(w, w.get(old) or {}) and \
            (not nl.get("at") or geo.contains(nl, src["at"]) is not False):
        return find_spot(w, new, src["at"], within=2.0, skip=e["id"])
    for ed in w.edges(old, "connects_to", "out"):
        if ed["target"] == new and ed["data"].get("route"):
            end = list(ed["data"]["route"][-1])
            return find_spot(w, new, end if len(end) == 3 else end + [0.0], within=4.0, skip=e["id"])
    return None


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
    pl = _layout(w, parent["id"]) if parent else {}
    if needs_own(w, e) and r["how"] not in ("own", "grid"):
        if parent and not resolve(w, parent["id"])["at"] and parent["id"] != w.root_id:
            out.append({"problem": "no position", "why": f"{pname}, the place it is in, is not laid out either",
                        "fix": f"lay out {pname} first (layout placements at, radius or size)"})
        else:
            centre = (resolve(w, parent["id"])["at"] if parent else None) or [0.0, 0.0, 0.0]
            spot = find_spot(w, parent["id"], centre, skip=e["id"], reserved=reserved) if parent else centre
            out.append({"problem": "no position",
                        "why": (f"it is directly in {pname} and only inherits its centre" if parent and
                                parent["id"] != w.root_id else "a place needs its own spot in the frame"),
                        "fix": {"at": spot, "or": lms[:8]} if lms else {"at": spot}})
        return out
    if r["how"] == "own" and parent and parent["id"] != w.root_id:
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
