def check(ctx):
    if not ctx.target.state.asleep:
        return "they are awake"
    if ctx.target.id != ctx.actor.id and ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    return True

def apply(ctx):
    ctx.target.state.asleep = False
    ctx.emit("woken", target=ctx.target, reach=-1, by=ctx.actor.id)  # to the root: the story listens for Tam
