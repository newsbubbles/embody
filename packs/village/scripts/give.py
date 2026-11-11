def find_item(ctx):
    want = str(ctx.params.get("item", "")).lower()
    for it in ctx.actor.children():
        if it.id == want or (it.name or "").lower() == want:
            return it
    return None

def how_many(ctx, it):
    c = ctx.params.get("count")
    return ctx.count(it) if c is None else int(c)

def check(ctx):
    if not ctx.params or "item" not in ctx.params:
        return "say what to give: params {\"item\": <id or name of something you hold>, \"count\": how many of a stack}"
    it = find_item(ctx)
    if it is None:
        return "you hold no such thing"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    n = how_many(ctx, it)
    have = ctx.count(it)
    if n < 1 or n > have:
        return "you hold " + str(have) + " of " + it.name + ": give 1 to " + str(have) + ", or leave count out for all of it"
    if ctx.target.state.carry and ctx.load(ctx.target) + ctx.bulk(it) * n / have > float(ctx.target.state.carry):
        return "their hands are full: they cannot take it until they put something down"
    return True

def apply(ctx):
    it = find_item(ctx)
    n = how_many(ctx, it)
    piece = ctx.split(it, n)
    ctx.patch(piece, {"given_by": ctx.actor.id, "given_before_by": piece.state.given_by})
    got = ctx.transfer(piece, ctx.target)
    ctx.emit("given", target=ctx.target, reach=1, item=got.id, count=n, by=ctx.actor.id)
