def check(ctx):
    if ctx.target.parent.id == ctx.actor.id:
        return "you already hold it"
    if not ctx.target.state.portable:
        return "it will not budge"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "it is not here"
    return True

def apply(ctx):
    # a thing that hid this one (state.hides names it) changes its face once it is gone
    for p in ctx.peers(ctx.target.id, "thing"):
        if p.state.hides and p.state.hides == ctx.target.name:
            ctx.patch(p, {"hides": None, "description": p.state.description_after or p.state.description})
    ctx.move(ctx.target, ctx.actor)
    ctx.emit("taken", target=ctx.target, reach=1, by=ctx.actor.id)
