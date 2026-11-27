use("vehicles")
# Feed a vehicle what it runs on (state fuel_kind, a thing's name or kind): params item, and count for part of a
# stack. Each unit gives fuel_per_unit (default 1), up to fuel_max.

def fuel_item(ctx, v):
    want = str((ctx.params or {}).get("item") or v.state.fuel_kind or "").lower()
    for it in ctx.actor.children():
        if it.id == want or it.name.lower() == want or str(it.state.kind or "").lower() == want:
            if it.name == v.state.fuel_kind or it.state.kind == v.state.fuel_kind:
                return it
    return None

def check(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    if v is None:
        return no("that is not a vehicle", "not_a_vehicle")
    if not v.state.fuel_per_leg or not v.state.fuel_kind:
        return no(v.name + " runs on nothing you can pour in", "no_fuel_kind")
    if not (aboard(ctx, v, me) or alongside(ctx, v, me)):
        return no(v.name + " is not here", "not_here")
    if fuel_item(ctx, v) is None:
        return no("you hold no " + str(v.state.fuel_kind) + ": " + v.name + " runs on that", "no_fuel_held")
    if v.state.fuel_max is not None and float(v.state.fuel or 0) >= float(v.state.fuel_max):
        return no(v.name + " is full", "full")
    return True

def apply(ctx):
    v = vehicle_of(ctx, ctx.target)
    it = fuel_item(ctx, v)
    have = ctx.count(it)
    n = int(ctx.params.get("count") or have)
    n = max(1, min(n, have))
    each = float(v.state.fuel_per_unit or 1)
    if v.state.fuel_max is not None:
        room = float(v.state.fuel_max) - float(v.state.fuel or 0)
        n = max(1, min(n, int((room + each - 0.001) / each)))
    piece = ctx.split(it, n) if n < have else it
    ctx.destroy(piece)
    fuel = float(v.state.fuel or 0) + n * each
    if v.state.fuel_max is not None:
        fuel = min(fuel, float(v.state.fuel_max))
    ctx.patch(v, {"fuel": round(fuel, 3)})
    ctx.emit("refuelled", target=v, reach=1, by=ctx.actor.id, count=n, fuel=round(fuel, 3))
