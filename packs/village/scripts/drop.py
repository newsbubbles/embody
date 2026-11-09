def check(ctx):
    if ctx.target.parent.id != ctx.actor.id:
        return "you are not holding it"
    return True

def apply(ctx):
    ctx.move(ctx.target, ctx.actor.parent)
    ctx.emit("dropped", target=ctx.target, reach=1, by=ctx.actor.id)
