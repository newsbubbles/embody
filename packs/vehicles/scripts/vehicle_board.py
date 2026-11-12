use("vehicles")
# Climb aboard a vehicle standing (or rolling) in your place. Whoever follows you climbs in with you.

def check(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    if v is None:
        return "that is not something you ride"
    if aboard(ctx, v, me):
        return "you are already aboard " + v.name
    if not alongside(ctx, v, me):
        return v.name + " is not here"
    if me.state.down or me.state.dead or me.state.asleep:
        return "you cannot climb aboard like this"
    lk = ctx.locked(v)
    if lk is not None:
        return v.name + " is locked: unlock " + ("it" if lk.id == v.id else lk.name) + " first, with its key or its code, or pick it"
    if v.state.moving and v.state.boardable_moving is False:
        return v.name + " is moving too fast to climb aboard: halt it, or wait until it stands"
    if v.state.seats is not None and len(riders(ctx, v)) >= int(v.state.seats):
        return v.name + " is full: " + str(v.state.seats) + " aboard already"
    return True

def apply(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    here = me.parent
    ctx.move(me, v)
    ctx.emit("boarded", target=v, reach=1, who=me.id, moving=bool(v.state.moving))
    ctx.emit("arrived", target=v, reach=-1, who=me.id, place=v.id)
    for p in ctx.children(here):
        if (p.state.friend == me.id or p.state.follows == me.id) and not p.state.asleep:
            if v.state.seats is None or len(riders(ctx, v)) < int(v.state.seats):
                ctx.move(p, v)
                ctx.emit("boarded", target=v, reach=1, who=p.id, following=me.id)
