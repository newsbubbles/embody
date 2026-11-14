use("common")
def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "parley with someone else"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.target.state.down or ctx.target.state.dead:
        return "they are past talking terms"
    if not ctx.params or not ctx.params.get("offer"):
        return "say what you offer: params {\"offer\": \"...\"}"
    return True

def apply(ctx):
    me = ctx.actor
    t = ctx.target
    offer = str(ctx.params.get("offer"))
    a = ctx.rand.roll("1d20") + bonus(me, "parley", ctx)
    d = ctx.rand.roll("1d20") + bonus(t, "resolve", ctx)
    if t.state.cowed_by == me.id:
        d = d - 3
    learn(ctx, me, "parley", d + 1, a > d, t)
    learn(ctx, t, "resolve", a, a <= d, me)
    if a > d:
        ctx.emit("agreed", target=t, reach=1, by=me.id, offer=offer, mine=a, theirs=d)
        ctx.log("agreed (" + str(a) + " vs " + str(d) + ")")
        return {"agreed": True, "mine": a, "theirs": d}
    ctx.emit("refused", target=t, reach=1, by=me.id, offer=offer, mine=a, theirs=d)
    ctx.log("refused (" + str(a) + " vs " + str(d) + ")")
    return {"agreed": False, "mine": a, "theirs": d}
