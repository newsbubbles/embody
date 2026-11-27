use("vehicles")
# Climb down from a vehicle into the place it is in. While it rolls that is the road it is on: you are left there.

def check(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    if v is None:
        return no("that is not something you ride", "not_a_vehicle")
    if not aboard(ctx, v, me):
        return no("you are not aboard " + v.name, "not_aboard")
    if me.state.dead:
        return no("you are dead", "unfit")
    return True

def apply(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    place = v.parent
    ctx.move(me, place)
    ctx.emit("alighted", target=v, reach=1, who=me.id, place=place.id, moving=bool(v.state.moving))
    ctx.emit("arrived", target=place, reach=-1, who=me.id, place=place.id)
    for pl in followers(ctx, v, me):
        ctx.move(pl[0], place)
        ctx.emit("alighted", target=v, reach=1, who=pl[0].id, place=place.id, following=pl[1])
