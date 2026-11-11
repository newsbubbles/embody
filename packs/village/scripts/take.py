def how_many(ctx):
    # a stack gives up part of itself (params count); no count takes it whole
    c = (ctx.params or {}).get("count")
    return None if c is None else int(c)

def check(ctx):
    if ctx.target.parent.id == ctx.actor.id:
        return "you already hold it"
    if not ctx.target.state.portable:
        return "it will not budge"
    holder = ctx.target.parent
    if holder.id != ctx.actor.parent.id and not (holder.state.holds is not None and holder.parent is not None
                                                 and holder.parent.id == ctx.actor.parent.id):
        return "it is not here"
    n = how_many(ctx)
    have = ctx.count(ctx.target)
    if n is not None and (n < 1 or n > have):
        return "there are " + str(have) + " of " + ctx.target.name + ": take 1 to " + str(have) + ", or leave count out for all of it"
    weight = ctx.bulk(ctx.target) * (n if n is not None else have) / have
    if ctx.actor.state.carry and ctx.load(ctx.actor) + weight > float(ctx.actor.state.carry):
        return "your hands are full (" + str(ctx.load(ctx.actor)) + " of " + str(ctx.actor.state.carry) + "): drop, put or give something first, or take fewer"
    return True

def apply(ctx):
    # a thing that hid this one (state.hides names it) changes its face once it is gone
    for p in ctx.peers(ctx.target.id, "thing"):
        if p.state.hides and p.state.hides == ctx.target.name:
            ctx.patch(p, {"hides": None, "description": p.state.description_after or p.state.description})
    n = how_many(ctx)
    n = ctx.count(ctx.target) if n is None else n
    got = ctx.transfer(ctx.target, ctx.actor, n)
    ctx.emit("taken", target=got, reach=1, by=ctx.actor.id, item=got.id, count=n, source=ctx.target.id)
