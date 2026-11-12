# Shared by the vehicles verbs and the vehicle's tick (packs/vehicles/pack.py says what a vehicle's state holds).

SCENES = {"depart": "{vehicle} pulls out of {place}, bound for {to}.",
          "pass": "{vehicle} comes through {place} on its way to {to}.",
          "approach": "{vehicle} comes up the road toward {place}.",
          "arrive": "{vehicle} pulls in at {place} and stands.",
          "stop": "{vehicle} stops short in {place}: {why}.",
          "break": "{vehicle} lurches and stops dead in {place}: something in it has given way."}

def vehicle_of(ctx, x):
    # the vehicle a verb is done to: the vehicle itself, or the one its wheel stands in
    if x is None:
        return None
    if x.is_a("vehicle"):
        return x
    p = x.parent
    if p is not None and p.is_a("vehicle"):
        return p
    return None

def place_ref(ctx, ref):
    # a place by its id or its exact name
    if ref is None:
        return None
    e = ctx.get(ref)
    if e is not None:
        return e
    for c in ctx.find(name=str(ref), limit=20):
        if c.name == str(ref):
            return c
    return None

def ids_of(ctx, refs):
    out = []
    for r in refs or []:
        p = place_ref(ctx, r)
        if p is not None and p.id not in out:
            out.append(p.id)
    return out

def road(ctx, v):
    # the places it drives through, in order: its route, else its stops
    return ids_of(ctx, v.state.route or v.state.stops)

def name_of(ctx, i):
    e = ctx.get(i) if i else None
    return e.name if e is not None else ""

def names(ctx, ids):
    return [name_of(ctx, i) for i in ids]

def connected(ctx, a, b):
    for e in ctx.edges(a, "connects_to", "out"):
        if e["target"] == b:
            return True
    return False

def destinations(ctx, v):
    # where it can be driven from here: its road, and with offroad any place connected to where it stands
    here = v.parent.id
    out = [i for i in road(ctx, v) if i != here]
    if v.state.offroad:
        for e in ctx.edges(here, "connects_to", "out"):
            if e["target"] not in out and e["target"] != v.id:
                out.append(e["target"])
    return out

def match_place(ctx, ids, want):
    want = str(want or "").lower().strip()
    if not want:
        return None
    for i in ids:
        p = ctx.get(i)
        if p is not None and (p.id == want or p.name.lower() == want):
            return p
    for i in ids:
        p = ctx.get(i)
        if p is not None and len(want) >= 4 and want in p.name.lower():
            return p
    return None

def path_to(ctx, v, dest):
    # the places it passes from where it stands to dest, both ends included
    here = v.parent.id
    r = road(ctx, v)
    if v.state.direct or here not in r or dest not in r:
        return [here, dest]
    i = r.index(here)
    j = r.index(dest)
    if j >= i:
        return r[i:j + 1]
    if v.state.loop:
        return r[i:] + r[:j + 1]
    return list(reversed(r[j:i + 1]))

def off_road_why(ctx, v, dest):
    # why it cannot be driven to dest from where it stands, or None
    here = v.parent.id
    r = road(ctx, v)
    if v.state.direct or (here in r and dest in r) or connected(ctx, here, dest):
        return None
    return v.name + " is off its road here: drive it to a place connected to " + v.parent.name + " first"

def leg_secs(ctx, v, a, b):
    legs = v.state.legs or {}
    na = name_of(ctx, a)
    nb = name_of(ctx, b)
    for k in (na + "|" + nb, nb + "|" + na):
        if legs.get(k) is not None:
            return float(legs[k])
    return float(v.state.leg_time or 300)

def able(ctx, v, who):
    # a body that can drive it: aboard, awake, on its feet and alive
    d = ctx.get(who) if who else None
    if d is None or d.parent is None or d.parent.id != v.id:
        return False
    return not (d.state.dead or d.state.down or d.state.asleep)

def run_driver(ctx, v):
    # the body named to drive its runs (state.driver, a name or an id): aboard first, else anywhere
    ref = v.state.driver
    if not ref:
        return None
    e = ctx.get(ref)
    if e is not None:
        return e
    for c in v.children():
        if c.name == str(ref):
            return c
    for c in ctx.find(name=str(ref), limit=20):
        if c.name == str(ref) and c.is_a("creature"):
            return c
    return None

def aboard(ctx, v, who):
    return who is not None and who.parent is not None and who.parent.id == v.id

def alongside(ctx, v, who):
    return who is not None and who.parent is not None and v.parent is not None and who.parent.id == v.parent.id

def riders(ctx, v):
    return [c for c in v.children() if c.is_a("creature")]

def cargo_load(ctx, v):
    # the bulk of what lies aboard that could be carried off (riders and the fittings do not count)
    n = 0
    for c in v.children():
        if c.state.portable and not c.is_a("creature"):
            n = n + ctx.bulk(c)
    return n

def blocker_in(ctx, place):
    for c in ctx.children(place):
        if c.state.blocks_road:
            return c
    return None

def tell(ctx, v, key, place, to, why):
    # the scene riders and the place both see; a world rewords one in state.scenes, or silences it with False
    sc = v.state.scenes or {}
    if key in sc and sc[key] is False:
        return
    t = str(sc.get(key) or SCENES[key])
    drv = ctx.get(v.state.driving) if v.state.driving else None
    t = t.replace("{vehicle}", v.name).replace("{place}", name_of(ctx, place)).replace("{to}", name_of(ctx, to))
    t = t.replace("{why}", str(why or "")).replace("{driver}", drv.name if drv is not None else "nobody")
    ctx.emit("scene", target=v, reach=1, text=t, loud=bool(v.state.loud))

def begin_leg(ctx, v, tr, t0):
    # the next leg of a trip: fuel spent, a breakdown rolled, the clock set. A reason when it cannot go
    per = v.state.fuel_per_leg
    if per:
        if float(v.state.fuel or 0) < float(per):
            return "out of fuel"
        ctx.patch(v, {"fuel": round(float(v.state.fuel or 0) - float(per), 3)})
    a = tr["path"][tr["i"]]
    b = tr["path"][tr["i"] + 1]
    tr["t0"] = t0
    tr["t1"] = t0 + leg_secs(ctx, v, a, b)
    tr["half"] = False
    # whether this leg breaks it is rolled now and kept secret (state.fault), so nobody aboard reads it off the card
    ctx.patch(v, {"fault": bool(v.state.breakdown) and ctx.rand.chance(float(v.state.breakdown))})
    return None

def start_trip(ctx, v, dest, by, run):
    # set out from where it stands for dest; a reason when it cannot
    path = path_to(ctx, v, dest)
    tr = {"path": path, "i": 0, "to": dest, "by": by, "origin": v.parent.id, "run": bool(run)}
    why = begin_leg(ctx, v, tr, ctx.t)
    if why:
        return why
    eta = tr["t1"]
    k = 1
    while k < len(path) - 1:
        eta = eta + leg_secs(ctx, v, path[k], path[k + 1])
        k = k + 1
    tr["eta"] = eta
    ctx.patch(v, {"moving": True, "trip": tr, "driving": by, "stopped": None, "resume_to": None, "resume_after": None})
    ctx.emit("departed", target=v, reach=1, by=by, origin=v.parent.id, to=dest, path=names(ctx, path), eta=eta,
             run=bool(run), loud=bool(v.state.loud))
    tell(ctx, v, "depart", v.parent.id, dest, None)
    return None

def stop_here(ctx, v, why, by):
    # it stops in the place it is in; a run (a timetable or a world's dispatch) takes up its trip again later
    tr = v.state.trip or {}
    ch = {"moving": False, "trip": None, "driving": None, "stopped": why, "fault": None}
    if tr.get("run"):
        ch["resume_to"] = tr.get("to")
        ch["resume_after"] = ctx.t + float(v.state.resume_wait or 120)
    ctx.patch(v, ch)
    ctx.emit("stopped", target=v, reach=1, place=v.parent.id, why=why, by=by, to=tr.get("to"), loud=bool(v.state.loud))
    tell(ctx, v, "stop", v.parent.id, tr.get("to"), why)
