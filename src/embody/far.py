"""Far views: what a body sees of the world past its own place (Nate 2026-11-16).

An entity may carry `far`: lines by band, {"far": "...", "mid": "..."} (a bare string is its far line); its near look is
its description, in ordinary perceive. Only what carries `far` is ever in sight, so a world says what its skyline is.

- Range from size: an entity is seen as far as `far_k` (the root's, default 100) times its largest dimension (its
  extent, or its height from floor to ceiling; `far.size_m` when it has no extent), capped by the horizon from the
  viewer's eye and the target's top on a planet of the root's `planet_radius_m` (default the Earth's), and by the
  nearest `visibility_m` up from the viewer's place (haze, dust).
- Bands: past half its range it is far, inside it mid (the mid line when it has one, else the far line).
- Merging up the tree: a thing whose container is also in sight shows only if it is larger than the container's merge
  size (`far.merge_m`, default a quarter of the container's size), or its `far.stands_out` is true (what moves on a
  plain catches the eye); otherwise the container's line stands for it.
- Hidden stays hidden: a hidden thing never shows; a hidden place shows only to one who knows the way to it, or when
  its `far` says `seen: true`, and then without its name or id (`far.called`, if any, is what it looks like).
- Line of sight, 2.5D: a thing with `occludes: true` and a top (a ridge, a wall, the Scar) blocks what lies behind it
  when its top stands above the line from the viewer's eye to the target's top where that line crosses it. One you
  stand on blocks nothing.
- Night (the viewer's ambient `time_of_day` is one of the root's `far_night`, default ["night"]): what has a `glow`
  ({line, range_m}, or a string) shows its glow line, as far as `range_m` when that is farther; anything else is seen at
  `far_night_x` (default a tenth) of its day range.
- Sound and smell: `carries` {"sound": {text, range_m}, "smell": {text, range_m, downwind}} reaches whoever is within
  range, through any wall, as `heard` and `smelled` (bearing, distance, text; named only as sight would name it). A
  smell that goes `downwind` (the default) reaches only a viewer the wind blows toward, within 45 degrees, by the
  ambient `wind_from` at the viewer's place (degrees or a compass point); with no wind it reaches a quarter of its range.
- Nothing from inside a place that is `indoors`. Both ends are measured in one ruler: one frame, or frames that say
  they are `aligned_with` each other (the same origin and units), in metres or km.

Read on demand only (`perceive(far=true)`), cached per place and body per world hour; while the clock is paused, until
the next event (a paused world's hour never turns, and a chat-played world may sit paused all session).
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any

from . import layout as geo
from . import positions as posn

if TYPE_CHECKING:
    from .world import World

FAR_K = 100.0
EYE_M = 1.7
PLANET_R = 6_371_000.0
MAX_IN_SIGHT = 8
MAX_CARRIED = 4
NIGHT_X = 0.1
STILL_X = 0.25
UNITS = {"m": 1.0, "km": 1000.0}


def lines(e: dict[str, Any]) -> dict[str, Any] | None:
    f = e["state"].get("far")
    if isinstance(f, str) and f.strip():
        return {"far": f.strip()}
    return f if isinstance(f, dict) and (f.get("far") or f.get("mid") or f.get("glow")) else None


def glow(f: dict[str, Any]) -> dict[str, Any] | None:
    g = f.get("glow")
    if isinstance(g, str) and g.strip():
        return {"line": g.strip()}
    return g if isinstance(g, dict) and g.get("line") else None


def ambient(w: "World", place: str) -> dict[str, Any]:
    """The air at a place as perceive reads it: the root's ambient, each place's above, then its own."""
    root = w.get(w.root_id)
    out = dict((root["state"].get("ambient") or {}) if root else {})
    for a in [x for x in reversed(w.ancestors(place)) if x != w.root_id] + [place]:
        out.update((w.get(a) or {}).get("state", {}).get("ambient") or {})
    return out


def wind_from(amb: dict[str, Any]) -> float | None:
    v = amb.get("wind_from")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v) % 360
    if isinstance(v, str) and v.strip().upper() in geo.COMPASS:
        return geo.COMPASS.index(v.strip().upper()) * 22.5
    return None


def size(lay: dict[str, Any], f: dict[str, Any], unit: float) -> float:
    """The largest dimension in metres: the extent on the ground or its height."""
    dims = []
    if lay.get("radius"):
        dims.append(2 * float(lay["radius"]))
    if lay.get("size"):
        dims.extend(float(x) for x in lay["size"])
    if lay.get("footprint"):
        xs, ys = [p[0] for p in lay["footprint"]], [p[1] for p in lay["footprint"]]
        dims.extend([max(xs) - min(xs), max(ys) - min(ys)])
    zr = geo.z_range(lay)
    if zr is not None and math.isfinite(zr[1]):
        dims.append(zr[1] - zr[0])
    out = max(dims) * unit if dims else 0.0
    return max(out, float(f.get("size_m") or 0))


def top(lay: dict[str, Any], at: list[float], unit: float) -> float:
    zr = geo.z_range(lay)
    hi = zr[1] if zr is not None and math.isfinite(zr[1]) else (at[2] if len(at) > 2 else 0.0)
    return float(hi) * unit


def horizon(eye_m: float, top_m: float, r: float) -> float:
    """How far two heights see each other over a planet's curve."""
    return math.sqrt(2 * r * max(eye_m, 0.0)) + math.sqrt(2 * r * max(top_m, 0.0))


def words(d: float) -> str:
    if d < 1000:
        return f"about {max(10, round(d, -1)):.0f} m"
    km = d / 1000
    dist = f"about {km:.1f} km" if km < 10 else f"about {round(km):.0f} km"
    h = km / 5  # a walker's pace
    walk = ("under an hour's walk" if h < 0.75 else "about an hour's walk" if h < 1.5 else
            f"about {round(h)} hours' walk" if h < 8 else "a day's walk" if h <= 12 else f"about {round(h / 8)} days' walk")
    return f"{dist}, {walk}"


def ruler(w: "World", frame: str) -> set[str]:
    """The frames measured with one ruler: this one and every frame `aligned_with` it, either way, in the same units."""
    units = posn.frame_def(w, frame).get("units") or "m"
    named = []
    for e in w.store.query("entity", "world_id=? AND state LIKE ?", (w.id, '%"aligned_with"%')):
        f = e["state"].get("frame")
        if isinstance(f, dict) and f.get("aligned_with") and posn.starts_frame(w, e):
            other = w.get(f["aligned_with"]) or next(iter(w.find(name=f["aligned_with"], limit=1)), None)
            if other is not None and (f.get("units") or "m") == (posn.frame_def(w, other["id"]).get("units") or "m"):
                named.append((e["id"], other["id"]))
    out, grew = {frame}, True
    while grew:
        grew = False
        for a, b in named:
            if (a in out) != (b in out) and (posn.frame_def(w, a).get("units") or "m") == units:
                out |= {a, b}
                grew = True
    return out


def blocked(eye_at: list[float], eye_m: float, at: list[float], top_m: float, lay: dict[str, Any], occ_top: float) -> bool:
    """Whether an occluder's extent, `occ_top` metres high, stands above the sight line where the line crosses it."""
    poly = geo.outline(lay)
    if poly is None or geo.in_polygon(eye_at, poly):
        return False
    ts = [1.0] if geo.in_polygon(at, poly) else []
    dx, dy = at[0] - eye_at[0], at[1] - eye_at[1]
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        ex, ey = x2 - x1, y2 - y1
        den = dx * ey - dy * ex
        if abs(den) < 1e-12:
            continue
        t = ((x1 - eye_at[0]) * ey - (y1 - eye_at[1]) * ex) / den
        u = ((x1 - eye_at[0]) * dy - (y1 - eye_at[1]) * dx) / den
        if 0 < t < 1 and 0 <= u <= 1:
            ts.append(t)
    return any(occ_top > eye_m + (top_m - eye_m) * t for t in ts)


def under_ground(t: dict[str, Any], eye_at: list[float], eye_m: float, at: list[float], top_m: float,
                 unit: float) -> bool:
    """Whether a terrain grid's ground rises above the sight line anywhere between the eye and the target's top,
    sampled about a cell apart where the line runs over the grid."""
    d = geo.ground(eye_at, at)
    n = max(2, math.ceil(d / float(t["cell_m"])))
    for k in range(1, n):
        s = k / n
        g = geo.height(t, eye_at[0] + (at[0] - eye_at[0]) * s, eye_at[1] + (at[1] - eye_at[1]) * s)
        if g is not None and g * unit > eye_m + (top_m - eye_m) * s + 0.01:
            return True
    return False


def _viewpoint(w: "World", place: str, body: str | None) -> list[float] | None:
    """Where a body stands to look, when it stands directly on its place's terrain: its own spot, else None (the
    place's spot is the viewpoint, as before)."""
    e = w.get(body) if body else None
    if e is None or e["parent_id"] != place or not (posn._layout(w, place).get("terrain")):
        return None
    p = posn.resolve(w, body)
    return list(p["at"]) + [0.0] * (3 - len(p["at"])) if p["at"] and p["how"] in ("own", "grid") else None


def _up(w: "World", eid: str, key: str) -> Any:
    cur, hops = w.get(eid), 0
    while cur is not None and hops < 64:
        if cur["state"].get(key) is not None:
            return cur["state"][key]
        cur, hops = (w.get(cur["parent_id"]) if cur["parent_id"] else None), hops + 1
    return None


def _shown(w: "World", e: dict[str, Any], body: str | None, frame: str) -> str | None:
    """'named', 'unnamed' or None (not in sight), by what is hidden from e up to its frame."""
    f = lines(e) or {}
    cur, hops, named = e, 0, "named"
    while cur is not None and cur["id"] != frame and hops < 64:
        if cur["state"].get("hidden"):
            if not posn.is_place(w, cur):
                return None  # a hidden thing is out of sight, however big
            if not w.knows_way(body, cur["id"]):
                if not f.get("seen"):
                    return None
                named = "unnamed"
        cur, hops = (w.get(cur["parent_id"]) if cur["parent_id"] else None), hops + 1
    return named


def in_sight(w: "World", place: str, body: str | None) -> dict[str, Any]:
    """What a body in `place` sees far off: {in_sight: [{id, name, bearing, compass, distance_m, distance, band,
    line}], note?}, up to MAX_IN_SIGHT, the most prominent (size over distance) first."""
    here = w.get(place)
    if here is None:
        return {"in_sight": [], "note": "nowhere to look from"}
    indoors = {"in_sight": [], "note": "you are indoors: no far view from here"}
    frame = posn.frame_of(w, place)
    unit = UNITS.get(str(posn.frame_def(w, frame).get("units") or "m"))
    spot = posn.resolve(w, place)
    if unit is None or spot["at"] is None:
        return indoors if here["state"].get("indoors") else \
            {"in_sight": [], "note": "this place has no spot in a frame of metres or km to look from"}
    lay_here = here["state"].get("layout") if isinstance(here["state"].get("layout"), dict) else {}
    at = list(spot["at"]) + [0.0] * (3 - len(spot["at"]))
    if here["state"].get("indoors"):  # no far view, but what carries from the places within this one is heard
        return {**indoors, **carried(w, place, body, at, unit, ruler(w, frame), {place, *w.ancestors(place)},
                                     ambient(w, place), inner_only=True)}
    zr = geo.z_range(lay_here)
    eye = (zr[0] if zr is not None else at[2]) * unit + EYE_M
    stand = _viewpoint(w, place, body)
    if stand is not None:  # on the ground of a place with terrain: from where the body stands, its eye over that ground
        at = stand
        g = geo.height(lay_here.get("terrain"), at[0], at[1])
        eye = (g if g is not None else at[2]) * unit + EYE_M
    root = w.get(w.root_id)
    rs = root["state"] if root else {}
    k = float(rs.get("far_k") or FAR_K)
    r = float(rs.get("planet_radius_m") or PLANET_R)
    vis = _up(w, place, "visibility_m")
    vis = float(vis) if vis is not None else math.inf
    amb = ambient(w, place)
    night = str(amb.get("time_of_day") or "").lower() in [str(x).lower() for x in rs.get("far_night") or ["night"]]
    dark = float(rs.get("far_night_x") or NIGHT_X)

    skip = {place, *w.ancestors(place)}
    frames = ruler(w, frame)
    walls = []
    for o in w.store.query("entity", "world_id=? AND state LIKE ?", (w.id, '%"occludes"%')):
        lay = o["state"].get("layout")
        if o["state"].get("occludes") is True and isinstance(lay, dict) and lay.get("at") and \
                posn.frame_of(w, o["id"]) in frames and geo.z_range(lay) is not None:
            walls.append((o["id"], lay, top(lay, lay["at"], unit)))
    grounds = []  # every place's terrain in this ruler: a ridge's own ground hides what lies behind it
    for o in w.store.query("entity", "world_id=? AND state LIKE ?", (w.id, '%"terrain"%')):
        t = (o["state"].get("layout") or {}).get("terrain") if isinstance(o["state"].get("layout"), dict) else None
        if isinstance(t, dict) and posn.frame_of(w, o["id"]) in frames:
            grounds.append((o["id"], t))
    rows = w.store.query("entity", "world_id=? AND state LIKE ?", (w.id, '%"far"%'))
    seen: dict[str, dict[str, Any]] = {}
    for e in rows:
        f = lines(e)
        own_frame = posn.frame_of(w, e["id"])
        if f is None or e["id"] in skip or place in w.ancestors(e["id"]) or own_frame not in frames:
            continue
        how = _shown(w, e, body, own_frame)
        if how is None:
            continue
        p = posn.resolve(w, e["id"])
        if p["at"] is None or p["how"] not in ("own", "grid"):
            continue
        lay = e["state"].get("layout") if isinstance(e["state"].get("layout"), dict) and p["how"] == "own" else {}
        big = size(lay, f, unit)
        if big <= 0:
            continue
        gap = geo.edge_distance(lay, at) if lay and (lay.get("radius") or lay.get("footprint") or lay.get("size")) else None
        d = (gap if gap is not None else geo.ground(at, p["at"])) * unit
        lit = glow(f) if night else None
        hz = horizon(eye, top(lay, p["at"], unit), r)
        if lit:
            reach = min(max(k * big, float(lit.get("range_m") or 0)), vis, hz)
        else:
            reach = min(k * big, vis, hz) * (dark if night else 1.0)  # a dark shape is lost long before the horizon
        if d > reach or d <= 0:
            continue
        up = w.ancestors(e["id"])
        tip = top(lay, p["at"], unit)
        if any(blocked(at, eye, p["at"], tip, wl, wt) for oid, wl, wt in walls
               if oid != e["id"] and oid not in up and e["id"] not in w.ancestors(oid)):
            continue
        if any(under_ground(t, at, eye, p["at"], tip, unit) for gid, t in grounds if gid != e["id"] and gid not in up):
            continue
        band = "far" if d > reach / 2 else "mid"
        line = lit["line"] if lit else (f.get("mid") or f.get("far")) if band == "mid" else (f.get("far") or f.get("mid"))
        if not line:
            continue
        deg, compass = geo.bearing(at, p["at"])
        seen[e["id"]] = {"id": e["id"] if how == "named" else None,
                         "name": e["name"] if how == "named" else (f.get("called") or None),
                         "bearing": deg, "compass": compass, "distance_m": round(d), "distance": words(d),
                         "band": band, "line": line, "_size": big, "_merge": float(f.get("merge_m") or big / 4),
                         "_out": bool(f.get("stands_out"))}
    out = []
    for eid, row in seen.items():
        holder = next((a for a in w.ancestors(eid) if a in seen), None)
        if holder is not None and row["_size"] <= seen[holder]["_merge"] and not row["_out"]:
            continue  # the container's line stands for it (unless it stands out: a pack moving on the plain)
        out.append(row)
    out.sort(key=lambda x: -x["_size"] / max(x["distance_m"], 1))
    for row in out:
        del row["_size"], row["_merge"], row["_out"]
    res: dict[str, Any] = {"in_sight": out[:MAX_IN_SIGHT]}
    res.update(carried(w, place, body, at, unit, frames, skip, amb))
    return res


def _within(w: "World", place: str, eid: str) -> bool:
    """Whether an entity lies in a place nested inside `place` (a balcony laid out beyond a room's window), not in
    `place` itself: what is in `place` is ordinary perceive, what is in a place within it is heard from afar."""
    near = posn._places_up(w, eid)
    return bool(near) and near[0] != place and place in w.ancestors(near[0])


def carried(w: "World", place: str, body: str | None, at: list[float], unit: float, frames: set[str],
            skip: set[str], amb: dict[str, Any], inner_only: bool = False) -> dict[str, Any]:
    """What a body hears and smells from afar (`carries` on a thing or a place): {heard, smelled}, nearest first.
    From places nested inside its own too, by the same distance (a world owner, 2026-11-24: a sound on a balcony beyond
    the room's window never carried into the room). `inner_only`: only those (an indoors listener)."""
    wind = wind_from(amb)
    heard, smelled = [], []
    for e in w.store.query("entity", "world_id=? AND state LIKE ?", (w.id, '%"carries"%')):
        c = e["state"].get("carries")
        if not isinstance(c, dict) or e["id"] in skip:
            continue
        inner = _within(w, place, e["id"])
        if (place in w.ancestors(e["id"]) and not inner) or (inner_only and not inner):
            continue
        own_frame = posn.frame_of(w, e["id"])
        if own_frame not in frames:
            continue
        p = posn.resolve(w, e["id"])
        if p["at"] is None or p["how"] not in ("own", "grid"):
            continue
        lay = e["state"].get("layout") if isinstance(e["state"].get("layout"), dict) and p["how"] == "own" else {}
        gap = geo.edge_distance(lay, at) if lay and (lay.get("radius") or lay.get("footprint") or lay.get("size")) else None
        d = (gap if gap is not None else geo.ground(at, p["at"])) * unit
        if d <= 0:
            continue  # here already: ordinary perceive
        deg, compass = geo.bearing(at, p["at"])
        named = _shown(w, e, body, own_frame) == "named"
        for sense, bucket in (("sound", heard), ("smell", smelled)):
            s = c.get(sense)
            if not isinstance(s, dict) or not s.get("text"):
                continue
            span = float(s.get("range_m") or 0)
            if sense == "smell" and s.get("downwind", True):
                if wind is None:
                    span *= STILL_X
                elif abs((deg - wind + 180) % 360 - 180) > 45:
                    continue  # the wind carries it away from here
            if d > span:
                continue
            bucket.append({"id": e["id"] if named else None, "name": e["name"] if named else None, "bearing": deg,
                           "compass": compass, "distance_m": round(d), "distance": words(d), "text": s["text"]})
    out: dict[str, Any] = {}
    for key, rows in (("heard", heard), ("smelled", smelled)):
        if rows:
            out[key] = sorted(rows, key=lambda x: x["distance_m"])[:MAX_CARRIED]
    return out


def _key(w: "World", place: str, body: str | None) -> str:
    stand = _viewpoint(w, place, body)  # on terrain, where it stands counts too, to ten metres
    when = int(w.t // 3600) if w.clock()["running"] else ["seq", w.store.next_seq(w.id)]
    return json.dumps([w.id, place, body, when, [round(x / 10) for x in stand[:2]] if stand else None])
