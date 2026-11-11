def room(ctx, who):
    # what more this body can carry, or None when it has no limit
    if not who.state.carry:
        return None
    return float(who.state.carry) - ctx.load(who)

def fitting(ctx, it, free):
    # how many of it fit in the hands: all of it, as many of a stack as fit, or none
    have = ctx.count(it)
    if free is None or ctx.bulk(it) <= free:
        return have
    each = ctx.bulk(it) / have
    if it.state.count is None or each <= 0:
        return 0
    return min(have, int(free / each))

def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if not (ctx.target.state.down or ctx.target.state.dead):
        return "they would not let you"
    free = room(ctx, ctx.actor)
    held = ctx.target.children()
    if free is not None and held and not any([fitting(ctx, it, free) > 0 for it in held]):
        return "your hands are full (" + str(ctx.load(ctx.actor)) + " of " + str(ctx.actor.state.carry) + "): drop, put or give something first"
    return True

def apply(ctx):
    # what fits in your hands, by the bulk take counts (part of a stack when only part fits); the rest stays on the body
    found = []
    counts = {}
    left = []
    for it in ctx.target.children():
        free = room(ctx, ctx.actor)
        n = fitting(ctx, it, free)
        if n <= 0:
            left.append(it)
            continue
        whole = n == ctx.count(it)
        got = ctx.transfer(it, ctx.actor, n)
        found.append(got.id)
        counts[got.id] = n
        if not whole:
            left.append(it)
    ctx.emit("searched", target=ctx.target, reach=1, by=ctx.actor.id, found=found, counts=counts, left=[it.id for it in left])
    msg = str(len(found)) + " things taken"
    if left:
        msg = msg + "; your hands are full, so " + ", ".join([it.name + (" (" + str(ctx.count(it)) + ")" if it.state.count is not None else "") for it in left]) + " stay on " + ctx.target.name
    ctx.log(msg)
    return found
