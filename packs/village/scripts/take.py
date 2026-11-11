def load(who):
    # what a body carries, in bulk: a skin or anything with a capacity is 2, the rest 1 unless it says
    n = 0
    for c in who.children():
        n = n + int(c.state.bulk or (2 if c.state.capacity else 1))
    return n

def bulk(it):
    return int(it.state.bulk or (2 if it.state.capacity else 1))

def check(ctx):
    if ctx.target.parent.id == ctx.actor.id:
        return "you already hold it"
    if not ctx.target.state.portable:
        return "it will not budge"
    holder = ctx.target.parent
    if holder.id != ctx.actor.parent.id and not (holder.state.holds is not None and holder.parent is not None
                                                 and holder.parent.id == ctx.actor.parent.id):
        return "it is not here"
    if ctx.actor.state.carry and load(ctx.actor) + bulk(ctx.target) > int(ctx.actor.state.carry):
        return "your hands are full (" + str(load(ctx.actor)) + " of " + str(ctx.actor.state.carry) + "): drop, put or give something first"
    return True

def apply(ctx):
    # a thing that hid this one (state.hides names it) changes its face once it is gone
    for p in ctx.peers(ctx.target.id, "thing"):
        if p.state.hides and p.state.hides == ctx.target.name:
            ctx.patch(p, {"hides": None, "description": p.state.description_after or p.state.description})
    ctx.move(ctx.target, ctx.actor)
    ctx.emit("taken", target=ctx.target, reach=1, by=ctx.actor.id)
