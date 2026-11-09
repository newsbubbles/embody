def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "follow someone else"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.actor.state.down:
        return "you are down: crawl"
    return True

def apply(ctx):
    # from now on, when they go, you go: the go script moves whoever has follows set to the walker
    ctx.patch(ctx.actor, {"follows": ctx.target.id})
    ctx.emit("following", target=ctx.target, reach=1, by=ctx.actor.id)
