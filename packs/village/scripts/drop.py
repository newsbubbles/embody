def check(ctx):
    if ctx.target.parent.id != ctx.actor.id:
        return "you are not holding it"
    n = (ctx.params or {}).get("count")
    have = ctx.count(ctx.target)
    if n is not None and (int(n) < 1 or int(n) > have):
        return "you hold " + str(have) + " of " + ctx.target.name + ": drop 1 to " + str(have) + ", or leave count out for all of it"
    return True

def apply(ctx):
    n = (ctx.params or {}).get("count")
    n = ctx.count(ctx.target) if n is None else int(n)
    got = ctx.transfer(ctx.target, ctx.actor.parent, n)
    ctx.emit("dropped", target=got, reach=1, by=ctx.actor.id, item=got.id, count=n)
