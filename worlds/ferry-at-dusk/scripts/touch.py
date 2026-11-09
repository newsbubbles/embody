def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id and ctx.target.parent.id != ctx.actor.id:
        return "it is not within reach"
    return True

def apply(ctx):
    ctx.emit("touched", target=ctx.target, reach=1, by=ctx.actor.id)
