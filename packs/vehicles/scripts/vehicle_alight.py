use("vehicles")
# Climb down from a vehicle into the place it is in. While it rolls that is the road it is on: you are left there.

def check(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    if v is None:
        return "that is not something you ride"
    if not aboard(ctx, v, me):
        return "you are not aboard " + v.name
    if me.state.dead:
        return "you are dead"
    return True

def apply(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    place = v.parent
    ctx.move(me, place)
    ctx.emit("alighted", target=v, reach=1, who=me.id, place=place.id, moving=bool(v.state.moving))
    ctx.emit("arrived", target=place, reach=-1, who=me.id, place=place.id)
    for p in ctx.children(v):
        if (p.state.friend == me.id or p.state.follows == me.id) and not p.state.asleep:
            ctx.move(p, place)
            ctx.emit("alighted", target=v, reach=1, who=p.id, place=place.id, following=me.id)
