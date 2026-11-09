use("common")
def in_duel(ctx, who):
    return len(ctx.relations(who, "duel")) > 0

def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "challenge someone else"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.actor.state.down or ctx.target.state.down or ctx.target.state.dead:
        return "a duel needs two on their feet"
    if in_duel(ctx, ctx.actor) or in_duel(ctx, ctx.target):
        return "there is already a duel standing"
    return True

def apply(ctx):
    here = ctx.actor.parent
    ctx.relate("duel", [ctx.actor.id, ctx.target.id], {"place": here.id, "since": ctx.t, "public": True})
    ctx.emit("challenged", target=ctx.target, reach=1, by=ctx.actor.id, place=here.id, ring=bool(here.state.ring))
