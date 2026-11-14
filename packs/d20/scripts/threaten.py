use("common")
def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "threaten someone else"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.actor.state.down:
        return "nobody fears a man on the ground"
    if ctx.target.state.down or ctx.target.state.dead:
        return "they are past threatening"
    return True

def apply(ctx):
    me = ctx.actor
    t = ctx.target
    a = ctx.rand.roll("1d20") + bonus(me, "resolve", ctx) + (2 if held(me, "weapon") else 0)
    friends = 0
    for p in ctx.children(t.parent, "creature"):
        if p.id != t.id and p.id != me.id and p.state.faction and p.state.faction == t.state.faction and not p.state.down:
            friends = friends + 1
    d = ctx.rand.roll("1d20") + bonus(t, "resolve", ctx) + (2 if friends else 0)
    learn(ctx, me, "resolve", d + 1, a > d, t)
    learn(ctx, t, "resolve", a, a <= d, me)
    if a > d:
        ctx.patch(t, {"cowed_by": me.id})
        ctx.emit("cowed", target=t, reach=1, by=me.id, mine=a, theirs=d)
        ctx.log("cowed (" + str(a) + " vs " + str(d) + ")")
        return {"cowed": True, "mine": a, "theirs": d}
    ctx.emit("defied", target=t, reach=1, by=me.id, mine=a, theirs=d)
    ctx.log("defied (" + str(a) + " vs " + str(d) + ")")
    return {"cowed": False, "mine": a, "theirs": d}
