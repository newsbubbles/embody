def check(ctx):
    if not ctx.target.state.rope:
        return "the bell rope has been cut; nothing to pull"
    return True

def apply(ctx):
    ctx.emit("rang", target=ctx.target, reach=-1, by=ctx.actor.id)
    ctx.say("The bell rings out over the river.")
