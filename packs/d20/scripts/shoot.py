use("common")
def check(ctx):
    me = ctx.actor
    t = ctx.target
    if t.id == me.id:
        return "you would not"
    if me.state.dead:
        return "the dead do not fight"
    if me.state.down:
        return "you are down: yield, drink or crawl"
    w = ranged(me)
    if w is None:
        return "you hold nothing that shoots"
    why = can_fire(me, w)
    if why:
        return why
    if not in_sight(ctx, me, t):
        return "you cannot see them from here"
    if t.state.dead:
        return "they are dead"
    if t.state.down:
        return "they are down: kill them, or spare them"
    if me.state.yielded == t.id:
        return "you yielded to them"
    why = ring_blocks(ctx, me, t)
    if why:
        return why
    return True

def apply(ctx):
    return shot(ctx, ctx.actor, ctx.target, ranged(ctx.actor))
