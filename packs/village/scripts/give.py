def find_item(ctx):
    want = str(ctx.params.get("item", "")).lower()
    for it in ctx.actor.children():
        if it.id == want or (it.name or "").lower() == want:
            return it
    return None

def load(who):
    # what a body carries, in bulk: a skin or anything with a capacity is 2, the rest 1 unless it says
    n = 0
    for c in who.children():
        n = n + int(c.state.bulk or (2 if c.state.capacity else 1))
    return n

def bulk(it):
    return int(it.state.bulk or (2 if it.state.capacity else 1))

def check(ctx):
    if not ctx.params or "item" not in ctx.params:
        return "say what to give: params {\"item\": <id or name of something you hold>}"
    if find_item(ctx) is None:
        return "you hold no such thing"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.target.state.carry and load(ctx.target) + bulk(find_item(ctx)) > int(ctx.target.state.carry):
        return "their hands are full: they cannot take it until they put something down"
    return True

def apply(ctx):
    it = find_item(ctx)
    ctx.patch(it, {"given_by": ctx.actor.id, "given_before_by": it.state.given_by})
    ctx.move(it, ctx.target)
    ctx.emit("given", target=ctx.target, reach=1, item=it.id, by=ctx.actor.id)
