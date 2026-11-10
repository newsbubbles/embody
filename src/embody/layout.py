"""Layout: where things are, in one frame for the whole world (DESIGN.md, section 8, "Layout").

The tree says how the story moves; a layout says where an entity is. Pure geometry here, no world access: checking
a frame and a layout, the outline of an extent, containment, distance and bearing, and a text sketch for agents.
Extents are 2.5D: a footprint on the ground (a circle, a turned box or a polygon) and an optional floor and ceiling.
"""

from __future__ import annotations

import math
from typing import Any

from .world import Rejected

FRAME_KEYS = {"units", "up", "north", "bounds", "geo", "note"}
LAYOUT_KEYS = {"at", "heading", "radius", "size", "footprint", "floor", "ceiling", "mesh", "note"}
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
DEFAULT_FRAME = {"units": "m", "up": "z", "north": "y"}


def _num(x: Any, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
        raise Rejected(f"{what} must be a number, got {x!r}")
    return float(x)


def _vec(x: Any, what: str, lo: int, hi: int) -> list[float]:
    if not isinstance(x, (list, tuple)) or not lo <= len(x) <= hi:
        raise Rejected(f"{what} is a list of {lo} to {hi} numbers, got {x!r}")
    return [_num(v, what) for v in x]


def check_frame(frame: dict[str, Any]) -> dict[str, Any]:
    """The root's frame, checked: units, which axis is up and which is north, optional bounds and a geo anchor."""
    if not isinstance(frame, dict):
        raise Rejected("frame is a dict", hint='{"units": "m", "up": "z", "north": "y"}')
    bad = set(frame) - FRAME_KEYS
    if bad:
        raise Rejected(f"frame does not know {sorted(bad)}", hint=f"frame keys: {sorted(FRAME_KEYS)}")
    out = {**DEFAULT_FRAME, **frame}
    if out["up"] != "z" or out["north"] != "y":
        raise Rejected("this engine's frame is z up and y north", hint='leave "up" and "north" out, or say "z" and "y"')
    if "bounds" in out and out["bounds"] is not None:
        b = out["bounds"]
        if not isinstance(b, (list, tuple)) or len(b) != 2:
            raise Rejected("bounds is [min corner, max corner]", hint="[[-10000, -10000], [10000, 10000]]")
        out["bounds"] = [_vec(b[0], "bounds", 2, 3), _vec(b[1], "bounds", 2, 3)]
    if "geo" in out and out["geo"] is not None:
        g = out["geo"]
        if not isinstance(g, dict) or set(g) - {"lat", "lon"} or not {"lat", "lon"} <= set(g):
            raise Rejected("geo is {lat, lon}: where x = y = 0 lies on a real map")
        out["geo"] = {"lat": _num(g["lat"], "geo.lat"), "lon": _num(g["lon"], "geo.lon")}
    return out


def check_layout(lay: dict[str, Any]) -> dict[str, Any]:
    """One entity's layout, checked. Every key is optional but a layout with no `at` places nothing."""
    if not isinstance(lay, dict):
        raise Rejected("a layout is a dict", hint='{"at": [x, y, z], "radius": 40}')
    bad = set(lay) - LAYOUT_KEYS
    if bad:
        raise Rejected(f"a layout does not know {sorted(bad)}", hint=f"layout keys: {sorted(LAYOUT_KEYS)}")
    out: dict[str, Any] = {}
    if lay.get("at") is not None:
        at = _vec(lay["at"], "at", 2, 3)
        out["at"] = at if len(at) == 3 else at + [0.0]
    if lay.get("heading") is not None:
        out["heading"] = _num(lay["heading"], "heading") % 360.0
    shapes = [k for k in ("radius", "size", "footprint") if lay.get(k) is not None]
    if len(shapes) > 1:
        raise Rejected(f"one extent per layout, got {shapes}", hint="radius (a circle), size (a box) or footprint (a polygon)")
    if lay.get("radius") is not None:
        r = _num(lay["radius"], "radius")
        if r <= 0:
            raise Rejected("radius must be above zero")
        out["radius"] = r
    if lay.get("size") is not None:
        sz = _vec(lay["size"], "size", 2, 3)
        if any(v <= 0 for v in sz):
            raise Rejected("every side of size must be above zero")
        out["size"] = sz
    if lay.get("footprint") is not None:
        fp = lay["footprint"]
        if not isinstance(fp, (list, tuple)) or len(fp) < 3:
            raise Rejected("a footprint is at least three [x, y] points, in the world frame")
        out["footprint"] = [_vec(p, "footprint point", 2, 2) for p in fp]
        if abs(polygon_area(out["footprint"])) < 1e-9:
            raise Rejected("that footprint has no area", hint="three or more points that are not on one line")
    for k in ("floor", "ceiling"):
        if lay.get(k) is not None:
            out[k] = _num(lay[k], k)
    if "floor" in out and "ceiling" in out and out["ceiling"] <= out["floor"]:
        raise Rejected("ceiling must be above floor")
    for k in ("mesh", "note"):
        if lay.get(k) is not None:
            if not isinstance(lay[k], str):
                raise Rejected(f"{k} is text")
            out[k] = lay[k]
    if out.get("footprint") and "at" not in out:
        c = centroid(out["footprint"])
        out["at"] = [c[0], c[1], out.get("floor", 0.0)]
    return out


def merge(old: dict[str, Any] | None, new: dict[str, Any], replace: bool = False) -> dict[str, Any]:
    """A layout write: keys merge over the old layout (None deletes one), or replace it whole. One extent at a time:
    a new radius, size or footprint drops the other two."""
    base = {} if replace else dict(old or {})
    if any(new.get(k) is not None for k in ("radius", "size", "footprint")):
        for k in ("radius", "size", "footprint"):
            base.pop(k, None)
    for k, v in new.items():
        if v is None:
            base.pop(k, None)
        else:
            base[k] = v
    return check_layout(base)


# ---- plane geometry ------------------------------------------------------------------------------------------------

def polygon_area(pts: list[list[float]]) -> float:
    """Signed area (shoelace): positive when the points run counter-clockwise."""
    a = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        a += x1 * y2 - x2 * y1
    return a / 2.0


def centroid(pts: list[list[float]]) -> list[float]:
    a = polygon_area(pts)
    if abs(a) < 1e-12:
        return [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]
    cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        f = x1 * y2 - x2 * y1
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    return [cx / (6 * a), cy / (6 * a)]


def in_polygon(p: list[float], pts: list[list[float]]) -> bool:
    x, y = p[0], p[1]
    inside = False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:
            inside = not inside
    return inside


def outline(lay: dict[str, Any], sides: int = 24) -> list[list[float]] | None:
    """The extent as a polygon on the ground (a circle as `sides` points), or None for a layout with no extent."""
    at = lay.get("at") or [0.0, 0.0, 0.0]
    if lay.get("footprint"):
        return [list(p) for p in lay["footprint"]]
    if lay.get("radius"):
        r = lay["radius"]
        return [[at[0] + r * math.sin(2 * math.pi * i / sides), at[1] + r * math.cos(2 * math.pi * i / sides)]
                for i in range(sides)]
    if lay.get("size"):
        w, d = lay["size"][0] / 2.0, lay["size"][1] / 2.0
        h = math.radians(lay.get("heading", 0.0))
        out = []
        for dx, dy in ((-w, -d), (w, -d), (w, d), (-w, d)):
            # heading turns clockwise from north: a local +y (depth) axis points along the heading
            out.append([at[0] + dx * math.cos(h) + dy * math.sin(h), at[1] - dx * math.sin(h) + dy * math.cos(h)])
        return out
    return None


def z_range(lay: dict[str, Any]) -> tuple[float, float] | None:
    """The extent's floor and ceiling, when it has any height."""
    at = lay.get("at") or [0.0, 0.0, 0.0]
    lo = lay.get("floor", at[2])
    hi = lay.get("ceiling")
    if hi is None and lay.get("size") and len(lay["size"]) == 3:
        hi = lo + lay["size"][2]
    if hi is None and "floor" not in lay:
        return None
    return (lo, hi if hi is not None else math.inf)


def contains(lay: dict[str, Any], p: list[float]) -> bool | None:
    """Is point p inside this extent (on the ground, and between floor and ceiling when it has them)? None: no extent."""
    if lay.get("radius"):
        at = lay["at"]
        inside = math.hypot(p[0] - at[0], p[1] - at[1]) <= lay["radius"]
    else:
        poly = outline(lay)
        if poly is None:
            return None
        inside = in_polygon(p, poly)
    zr = z_range(lay)
    if inside and zr is not None and len(p) > 2:
        inside = zr[0] <= p[2] <= zr[1]
    return inside


def area(lay: dict[str, Any]) -> float | None:
    if lay.get("radius"):
        return math.pi * lay["radius"] ** 2
    poly = outline(lay)
    return abs(polygon_area(poly)) if poly else None


def _segments_cross(a: list[float], b: list[float], c: list[float], d: list[float]) -> bool:
    def side(p: list[float], q: list[float], r: list[float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2, d3, d4 = side(c, d, a), side(c, d, b), side(a, b, c), side(a, b, d)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def overlap(a: dict[str, Any], b: dict[str, Any]) -> bool | None:
    """Do two extents share ground (and, when both have heights, some height)? None when either has no extent."""
    pa, pb = outline(a), outline(b)
    if pa is None or pb is None:
        return None
    hit = any(in_polygon(p, pb) for p in pa) or any(in_polygon(p, pa) for p in pb) or any(
        _segments_cross(p1, p2, q1, q2) for p1, p2 in zip(pa, pa[1:] + pa[:1]) for q1, q2 in zip(pb, pb[1:] + pb[:1]))
    za, zb = z_range(a), z_range(b)
    if hit and za is not None and zb is not None:
        hit = za[0] < zb[1] and zb[0] < za[1]
    return hit


def bearing(a: list[float], b: list[float]) -> tuple[float, str]:
    """Compass bearing from a to b: degrees clockwise from north, and the 16-point name."""
    deg = math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360.0
    return round(deg, 1), COMPASS[int((deg + 11.25) // 22.5) % 16]


def ground(a: list[float], b: list[float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def dist3(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((y - x) ** 2 for x, y in zip(a[:3], b[:3])))


def route_length(pts: list[list[float]]) -> float:
    return sum(dist3(p + [0.0] * (3 - len(p)), q + [0.0] * (3 - len(q))) for p, q in zip(pts, pts[1:]))


def edge_distance(lay: dict[str, Any], p: list[float]) -> float | None:
    """How far point p is from the edge of an extent on the ground: 0 inside, else the gap."""
    if lay.get("radius"):
        return max(0.0, ground(lay["at"], p) - lay["radius"])
    poly = outline(lay)
    if poly is None:
        return None
    if in_polygon(p, poly):
        return 0.0
    best = math.inf
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((p[0] - x1) * dx + (p[1] - y1) * dy) / ((dx * dx + dy * dy) or 1e-12)))
        best = min(best, math.hypot(p[0] - (x1 + t * dx), p[1] - (y1 + t * dy)))
    return best


# ---- a sketch for agents --------------------------------------------------------------------------------------------

def sketch(items: list[dict[str, Any]], paths: list[dict[str, Any]], width: int = 64, height: int = 32) -> str:
    """A top-down text map: north up, each extent's outline in dots, each path in dashes, each entity's place a
    letter keyed below. items: {name, at, layout?}. paths: {route}. Enough to see a layout is the shape meant."""
    pts: list[list[float]] = []
    for it in items:
        pts.append(it["at"])
        poly = outline(it.get("layout") or {}) if it.get("layout") else None
        pts.extend(poly or [])
    for p in paths:
        pts.extend(p["route"])
    if not pts:
        return "(nothing laid out)"
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    span = max(x1 - x0, (y1 - y0) * 2.0 * width / max(1, 2 * height), 1e-9)
    sx = (width - 1) / span
    sy = sx / 2.0  # a text cell is about twice as tall as it is wide
    height = max(3, min(height, int((y1 - y0) * sy) + 1))
    grid = [[" "] * width for _ in range(height)]

    def cell(p: list[float]) -> tuple[int, int]:
        return (min(width - 1, max(0, int(round((p[0] - x0) * sx)))),
                min(height - 1, max(0, height - 1 - int(round((p[1] - y0) * sy)))))

    def line(a: list[float], b: list[float], ch: str) -> None:
        (c0, r0), (c1, r1) = cell(a), cell(b)
        n = max(abs(c1 - c0), abs(r1 - r0), 1)
        for i in range(n + 1):
            c, r = round(c0 + (c1 - c0) * i / n), round(r0 + (r1 - r0) * i / n)
            if grid[r][c] == " ":
                grid[r][c] = ch

    for it in items:
        poly = outline(it.get("layout") or {}) if it.get("layout") else None
        if poly:
            for a, b in zip(poly, poly[1:] + poly[:1]):
                line(a, b, ".")
    for p in paths:
        for a, b in zip(p["route"], p["route"][1:]):
            line(a, b, "-")
    keys = []
    for i, it in enumerate(items):
        k = chr(ord("A") + i) if i < 26 else chr(ord("a") + i - 26) if i < 52 else "*"
        c, r = cell(it["at"])
        if grid[r][c].isalnum():  # the first listed (the outer place) keeps the cell; the rest are keyed to it
            keys.append(f"{k} {it['name']} (at {grid[r][c]} at this scale)")
            continue
        grid[r][c] = k
        keys.append(f"{k} {it['name']}")
    scale = f"one column is {1 / sx:.0f} {'m'}; north is up"
    return "\n".join("".join(row).rstrip() for row in grid) + "\n" + scale + "\n" + "\n".join(keys)
