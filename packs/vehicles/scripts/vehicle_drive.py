use("vehicles")
# Drive the vehicle you are aboard to a place on its road (params to). It sets out now and takes the road's time:
# halfway through each leg it is in the next place, and it pulls in when the last leg is done.

def check(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    if v is None:
        return "that is not something you drive: stand aboard a vehicle and drive it, or its wheel"
    if not aboard(ctx, v, me):
        return "climb aboard " + v.name + " first (board it): it is driven from inside"
    if me.state.down or me.state.asleep:
        return "you are in no state to drive"
    if v.state.moving:
        tr = v.state.trip or {}
        return v.name + " is already on the road to " + name_of(ctx, tr.get("to")) + ": halt it, or wait until it pulls in"
    if v.state.broken:
        return v.name + " is broken down: repair it first"
    if v.state.hold:
        return v.name + " is held: " + (v.state.hold if isinstance(v.state.hold, str) else "it is not to go anywhere now")
    where = names(ctx, destinations(ctx, v))
    if not ctx.params or not ctx.params.get("to"):
        return "say where: params {\"to\": one of " + ", ".join(where) + "}"
    dest = match_place(ctx, destinations(ctx, v), ctx.params.get("to"))
    if dest is None:
        return v.name + " keeps to its road: drive it to one of " + ", ".join(where)
    why = off_road_why(ctx, v, dest.id)
    if why:
        return why
    if v.state.cargo is not None and cargo_load(ctx, v) > float(v.state.cargo):
        return v.name + " is overloaded (" + str(cargo_load(ctx, v)) + " of " + str(v.state.cargo) + "): unload something first"
    if v.state.fuel_per_leg and float(v.state.fuel or 0) < float(v.state.fuel_per_leg):
        return v.name + " has no fuel: refuel it first"
    return True

def apply(ctx):
    v = vehicle_of(ctx, ctx.target)
    dest = match_place(ctx, destinations(ctx, v), ctx.params.get("to"))
    why = start_trip(ctx, v, dest.id, ctx.actor.id, False)
    if why:
        ctx.reject(v.name + " will not go: " + why)
    ctx.log(v.name + " sets out for " + dest.name + ", due at t=" + str(round(float(v.state.trip["eta"]))))
