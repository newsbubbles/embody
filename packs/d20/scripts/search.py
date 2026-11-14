use("common")
def room(ctx, who):
    # what more this body can carry, or None when it has no limit
    if not who.state.carry:
        return None
    return float(who.state.carry) - ctx.load(who)

def fitting(ctx, it, free):
    # how many of it fit in the hands: all of it, as many of a stack as fit, or none. What weighs nothing always fits,
    # even in hands already over their carry
    have = ctx.count(it)
    if free is None or ctx.bulk(it) <= max(free, 0):
        return have
    each = ctx.bulk(it) / have
    if it.state.count is None or each <= 0:
        return 0
    return min(have, int(max(free, 0) / each))

def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if not (ctx.target.state.down or ctx.target.state.dead or ctx.target.state.asleep):
        return "they would not let you: only someone down, dead or asleep"
    free = room(ctx, ctx.actor)
    held = ctx.target.children()
    if free is not None and held and not any([fitting(ctx, it, free) > 0 for it in held]):
        return "your hands are full (" + str(ctx.load(ctx.actor)) + " of " + str(ctx.actor.state.carry) + "): drop, put or give something first"
    return True

def apply(ctx):
    # what fits in your hands, by the bulk take counts (part of a stack when only part fits); the rest stays on the body.
    # A sleeper is searched by stealth: d20 + wits + stealth against 10 + their wits. Done quietly, the event names the
    # thief and the sleeper sleeps on; fumbled, nothing is taken and the hand on them wakes them.
    t = ctx.target
    sly = bool(t.state.asleep and not (t.state.down or t.state.dead))
    if sly:
        roll = ctx.rand.roll("1d20")
        mod = bonus(ctx.actor, "stealth", ctx)
        dc = 10 + int(t.state.wits or 0)
        learn(ctx, ctx.actor, "stealth", dc, roll + mod >= dc, t)
        if roll + mod < dc:
            ctx.emit("caught", target=t, reach=1, by=ctx.actor.id, roll=roll, mod=mod, total=roll + mod, dc=dc)
            ctx.log("stealth: d20 " + str(roll) + " + " + str(mod) + " vs " + str(dc) + ": your hand wakes " + t.name)
            return []
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
    if sly:
        # the event is on the thief: the room may see it, the sleeper does not
        ctx.emit("lifted", target=ctx.actor, reach=1, by=ctx.actor.id, sleeper=t.id, found=found, counts=counts,
                 left=[it.id for it in left], roll=roll, mod=mod, dc=dc)
    else:
        ctx.emit("searched", target=ctx.target, reach=1, by=ctx.actor.id, found=found, counts=counts, left=[it.id for it in left])
    msg = str(len(found)) + " things taken"
    if left:
        msg = msg + "; your hands are full, so " + ", ".join([it.name + (" (" + str(ctx.count(it)) + ")" if it.state.count is not None else "") for it in left]) + " stay on " + ctx.target.name
    ctx.log(msg)
    return found
