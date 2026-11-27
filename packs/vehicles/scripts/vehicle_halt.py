use("vehicles")
# Stop a moving vehicle where it is: step into its road from alongside, or pull up from the driver's place. With a
# halt_dc on the vehicle, someone alongside must make d20 + body against it (a crawler does not stop for everyone).

def check(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    if v is None:
        return no("that is not something that moves", "not_a_vehicle")
    if not v.state.moving:
        return no(v.name + " is standing still already", "not_moving")
    if me.state.down or me.state.dead or me.state.asleep:
        return no("you are in no state to stop anything", "unfit")
    if aboard(ctx, v, me):
        tr = v.state.trip or {}
        if tr.get("by") != me.id:
            return no("you are not the one driving " + v.name, "not_driver")
        return True
    if not alongside(ctx, v, me):
        return no(v.name + " is not here", "not_here")
    return True

def apply(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    if not aboard(ctx, v, me) and v.state.halt_dc is not None:
        roll = ctx.rand.roll("1d20")
        total = roll + int(me.state.body or 0)
        if total < int(v.state.halt_dc):
            ctx.emit("halt_failed", target=v, reach=1, by=me.id, roll=roll, total=total, dc=v.state.halt_dc)
            ctx.log(v.name + " does not stop for you (" + str(total) + " against " + str(v.state.halt_dc) + ")")
            return False
    stop_here(ctx, v, "pulled up" if aboard(ctx, v, me) else "halted", me.id)
    return True
