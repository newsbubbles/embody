use("vehicles")
# Strike a vehicle from alongside or aboard: 1d6 + body, less its armour, off its hull. At no hull it breaks down
# and stops. A vehicle with no hull in its state is too much for hands.

def check(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    if v is None:
        return "that is not a vehicle"
    if v.state.hull is None:
        return v.name + " is too much for your hands to hurt"
    if not (aboard(ctx, v, me) or alongside(ctx, v, me)):
        return v.name + " is not here"
    if me.state.down or me.state.dead or me.state.asleep:
        return "you are in no state to strike anything"
    return True

def apply(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    dmg = max(0, ctx.rand.roll("1d6") + int(me.state.body or 0) - int(v.state.armour or 0))
    hull = max(0, int(v.state.hull) - dmg)
    ctx.patch(v, {"hull": hull})
    ctx.emit("struck", target=v, reach=1, by=me.id, damage=dmg, hull=hull, loud=True)
    if hull <= 0 and not v.state.broken:
        ctx.patch(v, {"broken": True})
        ctx.emit("broke_down", target=v, reach=1, place=v.parent.id, why="struck", by=me.id, loud=True)
        tell(ctx, v, "break", v.parent.id, None, None)
        if v.state.moving:
            stop_here(ctx, v, "broken down", me.id)
    return {"damage": dmg, "hull": hull}
