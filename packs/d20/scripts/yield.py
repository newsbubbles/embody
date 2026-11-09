use("common")
def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "yield to someone"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    return True

def apply(ctx):
    ctx.patch(ctx.actor, {"yielded": ctx.target.id, "braced": False})
    ctx.emit("yielded", target=ctx.actor, reach=1, to=ctx.target.id)
    ctx.emit("yielded_to", target=ctx.target, reach=0, by=ctx.actor.id)
