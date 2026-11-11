def load(who):
    # the same count take uses: a skin or anything with a capacity is 2, the rest 1 unless it says
    n = 0
    for c in who.children():
        n = n + bulk(c)
    return n

def bulk(it):
    return int(it.state.bulk or (2 if it.state.capacity else 1))

def room(who):
    # what more this body can carry, or None when it has no limit
    if not who.state.carry:
        return None
    return int(who.state.carry) - load(who)

def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if not (ctx.target.state.down or ctx.target.state.dead):
        return "they would not let you"
    free = room(ctx.actor)
    held = ctx.target.children()
    if free is not None and held and not any([bulk(it) <= free for it in held]):
        return "your hands are full (" + str(load(ctx.actor)) + " of " + str(ctx.actor.state.carry) + "): drop, put or give something first"
    return True

def apply(ctx):
    # what fits in your hands, by the bulk take counts; the rest stays on the body
    found = []
    left = []
    free = room(ctx.actor)
    for it in ctx.target.children():
        if free is not None and bulk(it) > free:
            left.append(it)
            continue
        ctx.move(it, ctx.actor)
        found.append(it.id)
        if free is not None:
            free = free - bulk(it)
    ctx.emit("searched", target=ctx.target, reach=1, by=ctx.actor.id, found=found, left=[it.id for it in left])
    msg = str(len(found)) + " things taken"
    if left:
        msg = msg + "; your hands are full, so " + ", ".join([it.name for it in left]) + " stay on " + ctx.target.name
    ctx.log(msg)
    return found
