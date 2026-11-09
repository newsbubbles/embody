use("common")
def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.target.state.dead:
        return "they are already dead"
    if not ctx.target.state.down:
        return "they are on their feet: that is an attack"
    if ctx.actor.state.down:
        return "you are down"
    return True

def apply(ctx):
    ctx.patch(ctx.target, {"dead": True, "vigor": 0})
    ctx.emit("killed", target=ctx.target, reach=-1, by=ctx.actor.id)
    if ctx.target.state.yielded == ctx.actor.id:
        ctx.emit("dishonor", target=ctx.actor, reach=-1, against=ctx.target.id)
