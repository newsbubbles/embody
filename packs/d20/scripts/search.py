def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if not (ctx.target.state.down or ctx.target.state.dead):
        return "they would not let you"
    return True

def apply(ctx):
    found = []
    for it in ctx.target.children():
        ctx.move(it, ctx.actor)
        found.append(it.id)
    ctx.emit("searched", target=ctx.target, reach=1, by=ctx.actor.id, found=found)
    ctx.log(str(len(found)) + " things taken")
    return found
