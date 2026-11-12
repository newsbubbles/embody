use("vehicles")
# The vehicle's own clock. On a trip: halfway through each leg it rolls into the next place (people there see it
# come through), at the end of the leg it is at that place, and at the last one it pulls in. A hold, a driver who is
# gone or down, a blocker in the road, a breakdown or no fuel stops it where it is. Standing: a world's dispatch, a
# run that was stopped and may go on, or the timetable sends it out from a stop. Times are read from the trip's own
# clock, so a late tick (or a server that slept) catches up leg by leg.

def advance(ctx, v):
    n = 0
    while v.state.moving and v.state.trip and n < 40:
        n = n + 1
        tr = dict(v.state.trip)
        if v.state.hold:
            stop_here(ctx, v, v.state.hold if isinstance(v.state.hold, str) else "held", None)
            return
        if v.state.broken:
            stop_here(ctx, v, "broken down", None)
            return
        if tr.get("by") and not able(ctx, v, tr["by"]):
            stop_here(ctx, v, "nobody at the wheel", None)
            return
        path = tr["path"]
        nxt = path[tr["i"] + 1]
        last = tr["i"] + 1 == len(path) - 1
        if not tr.get("half"):
            if ctx.t < (float(tr["t0"]) + float(tr["t1"])) / 2:
                return
            if ctx.get(nxt) is None:
                stop_here(ctx, v, "the road ends", None)
                return
            ctx.move(v, nxt)
            tr["half"] = True
            ctx.patch(v, {"trip": tr})
            if v.state.fault:
                ctx.patch(v, {"broken": True})
                ctx.emit("broke_down", target=v, reach=1, place=nxt, why="breakdown", loud=bool(v.state.loud))
                tell(ctx, v, "break", nxt, tr["to"], None)
                stop_here(ctx, v, "broken down", None)
                return
            b = blocker_in(ctx, nxt) if not last else None
            if b is not None:
                stop_here(ctx, v, "blocked by " + b.name, b.id)
                return
            if last:
                ctx.emit("approaching", target=v, reach=1, place=nxt, loud=bool(v.state.loud))
                tell(ctx, v, "approach", nxt, tr["to"], None)
            else:
                ctx.emit("passing", target=v, reach=1, place=nxt, to=tr["to"], loud=bool(v.state.loud))
                tell(ctx, v, "pass", nxt, tr["to"], None)
            continue
        if ctx.t < float(tr["t1"]):
            return
        if last:
            ctx.patch(v, {"moving": False, "trip": None, "driving": None, "arrived_t": ctx.t, "fault": None})
            ctx.emit("pulled_in", target=v, reach=1, place=nxt, origin=tr.get("origin"), by=tr.get("by"),
                     run=bool(tr.get("run")), loud=bool(v.state.loud))
            tell(ctx, v, "arrive", nxt, nxt, None)
            return
        tr["i"] = tr["i"] + 1
        why = begin_leg(ctx, v, tr, float(tr["t1"]))
        if why:
            ctx.patch(v, {"trip": tr})
            stop_here(ctx, v, why, None)
            return
        ctx.patch(v, {"trip": tr})

def next_slot(ctx, tt, t):
    # the first departure on the timetable at or after t
    if tt.get("every"):
        e = float(tt["every"])
        o = float(tt.get("offset") or 0)
        k = int((t - o) / e)
        if o + k * e < t:
            k = k + 1
        return o + k * e
    day = float(tt.get("day") or ctx.root().state.day_seconds or 86400)
    base = t - (t % day)
    best = None
    for d in (0, 1):
        for s in tt.get("at") or []:
            c = base + d * day + float(s)
            if c >= t and (best is None or c < best):
                best = c
    return best

def next_stop(ctx, v, stops, here):
    # shuttle (the default) turns back at either end; a loop goes on from the last stop to the first
    i = stops.index(here)
    if len(stops) < 2:
        return None
    if v.state.loop:
        return stops[(i + 1) % len(stops)]
    h = int(v.state.heading or 1)
    if i + h < 0 or i + h >= len(stops):
        h = -h
        ctx.patch(v, {"heading": h})
    return stops[i + h]

def run(ctx, v):
    if v.state.hold or v.state.broken:
        return
    by = None
    if v.state.driver:
        d = run_driver(ctx, v)
        if d is None or not able(ctx, v, d.id) or ctx.embodied(d):
            return  # no driver aboard and able, or a seat that drives by hand
        by = d.id
    here = v.parent.id
    order = v.state.dispatch
    if order:
        ctx.patch(v, {"dispatch": None})
        dest = match_place(ctx, destinations(ctx, v), order.get("to") if isinstance(order, dict) else order)
        if dest is not None and not off_road_why(ctx, v, dest.id):
            why = start_trip(ctx, v, dest.id, by, True)
            if why:
                ctx.emit("stopped", target=v, reach=1, place=here, why=why, to=dest.id)
        return
    if v.state.resume_to and ctx.t >= float(v.state.resume_after or 0):
        if blocker_in(ctx, here) is None and v.state.resume_to != here and ctx.get(v.state.resume_to) is not None:
            start_trip(ctx, v, v.state.resume_to, by, True)
        return
    tt = v.state.timetable
    if not tt:
        return
    stops = ids_of(ctx, v.state.stops)
    if here not in stops:
        return
    nd = v.state.next_departure
    if nd is None:
        ctx.patch(v, {"next_departure": next_slot(ctx, tt, ctx.t)})
        return
    if ctx.t < float(nd) or ctx.t < float(v.state.arrived_t or 0) + float(v.state.dwell or 60):
        return  # not yet, or it pulled in late and stands its dwell before it sets out again
    ctx.patch(v, {"next_departure": next_slot(ctx, tt, ctx.t + 1)})
    dest = next_stop(ctx, v, stops, here)
    if dest is not None:
        start_trip(ctx, v, dest, by, True)

def tick(ctx):
    v = ctx.self
    if v.state.moving and v.state.trip:
        advance(ctx, v)
    else:
        run(ctx, v)
