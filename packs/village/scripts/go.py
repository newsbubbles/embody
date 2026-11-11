def shut(ctx, x):
    # a door or a place a lock keeps shut, with the way to open it
    lk = ctx.locked(x)
    if lk is None:
        return None
    return x.name + " is locked: unlock " + ("it" if lk.id == x.id else lk.name) + " first, with its key or its code, or pick it"

def check(ctx):
    here = ctx.actor.parent
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == ctx.target.id:
            via = e["data"].get("via")
            if via and shut(ctx, ctx.get(via)):
                return shut(ctx, ctx.get(via))
            if via and not ctx.get(via).state.open:
                return "the way is shut"
            if shut(ctx, ctx.target):
                return shut(ctx, ctx.target)
            return True
    return "there is no way there from here"

def apply(ctx):
    here = ctx.actor.parent
    ctx.move(ctx.actor, ctx.target)
    ctx.emit("arrived", target=ctx.target, reach=-1, who=ctx.actor.id, place=ctx.target.id)
    # whoever follows you comes along: the dog you fed, anyone told to follow
    for p in ctx.children(here):
        if p.state.friend == ctx.actor.id or p.state.follows == ctx.actor.id:
            if not p.state.asleep:
                ctx.move(p, ctx.target)
                ctx.emit("arrived", target=ctx.target, reach=1, who=p.id, place=ctx.target.id, following=ctx.actor.id)
