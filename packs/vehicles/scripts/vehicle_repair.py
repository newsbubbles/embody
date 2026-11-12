use("vehicles")
# Mend a vehicle that broke down or was beaten to a standstill, aboard or alongside: done when the verb's time is
# out, and only if you are still there.

def check(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    if v is None:
        return "that is not something you can mend"
    if not v.state.broken:
        return v.name + " runs as it is: nothing to mend"
    if not (aboard(ctx, v, me) or alongside(ctx, v, me)):
        return v.name + " is not here"
    if me.state.down or me.state.asleep:
        return "you are in no state to mend anything"
    return True

def apply(ctx):
    v = vehicle_of(ctx, ctx.target)
    ctx.emit("repairing", target=v, reach=1, by=ctx.actor.id)

def finish(ctx):
    v = vehicle_of(ctx, ctx.target)
    me = ctx.actor
    if v is None or me is None or not (aboard(ctx, v, me) or alongside(ctx, v, me)):
        return
    ch = {"broken": False}
    if v.state.hull is not None:
        ch["hull"] = v.state.hull_max if v.state.hull_max is not None else max(1, int(v.state.hull))
    ctx.patch(v, ch)
    ctx.emit("repaired", target=v, reach=1, by=me.id)
