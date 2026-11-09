use("common")
def check(ctx):
    me = ctx.actor.state
    t = ctx.target
    if t.id == ctx.actor.id:
        return "you would not"
    if t.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if me.dead:
        return "the dead do not fight"
    if me.down:
        return "you are down: yield, drink or crawl"
    if t.state.dead:
        return "they are dead"
    if t.state.down:
        return "they are down: kill them, or spare them"
    if me.yielded == t.id:
        return "you yielded to them"
    return True

def apply(ctx):
    p = ctx.params or {}
    return strike(ctx, ctx.actor, ctx.target, bool(p.get("slow")))
