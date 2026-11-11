def check(ctx):
    t = ctx.target if ctx.target is not None else ctx.actor
    if t.parent is None or (t.id != ctx.actor.id and t.parent.id != ctx.actor.parent.id):
        return "they are not here"
    if not t.state.asleep:
        return ("you are awake" if t.id == ctx.actor.id else t.name + " is awake")
    return True

def apply(ctx):
    # a shake of the shoulder, or your own eyes opening
    t = ctx.target if ctx.target is not None else ctx.actor
    ctx.patch(t, {"asleep": False})
    ctx.emit("woke", target=t, reach=1, by=ctx.actor.id, why="woken" if t.id != ctx.actor.id else "rested")
