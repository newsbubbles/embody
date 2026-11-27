use("vehicles")
# Climb aboard a vehicle standing (or rolling) in your place. Whoever follows you climbs in with you.

def check(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    if v is None:
        return no("that is not something you ride", "not_a_vehicle")
    if aboard(ctx, v, me):
        return no("you are already aboard " + v.name, "already_aboard")
    if not alongside(ctx, v, me):
        return no(v.name + " is not here", "not_here")
    if me.state.down or me.state.dead or me.state.asleep:
        return no("you cannot climb aboard like this", "unfit")
    if ctx.shut(v):
        return no(ctx.shut(v), "locked")
    if v.state.moving and v.state.boardable_moving is False:
        return no(v.name + " is moving too fast to climb aboard: halt it, or wait until it stands", "moving")
    if v.state.seats is not None and len(riders(ctx, v)) >= int(v.state.seats):
        return no(v.name + " is full: " + str(v.state.seats) + " aboard already", "full")
    return True

def apply(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    here = me.parent
    ctx.move(me, v)
    ctx.emit("boarded", target=v, reach=1, who=me.id, moving=bool(v.state.moving))
    ctx.emit("arrived", target=v, reach=-1, who=me.id, place=v.id)
    for pl in followers(ctx, here, me):
        if v.state.seats is None or len(riders(ctx, v)) < int(v.state.seats):
            ctx.move(pl[0], v)
            ctx.emit("boarded", target=v, reach=1, who=pl[0].id, following=pl[1])
