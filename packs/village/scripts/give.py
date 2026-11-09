def find_item(ctx):
    want = str(ctx.params.get("item", "")).lower()
    for it in ctx.actor.children():
        if it.id == want or (it.name or "").lower() == want:
            return it
    return None

def check(ctx):
    if not ctx.params or "item" not in ctx.params:
        return "say what to give: params {\"item\": <id or name of something you hold>}"
    if find_item(ctx) is None:
        return "you hold no such thing"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    return True

def apply(ctx):
    it = find_item(ctx)
    ctx.move(it, ctx.target)
    ctx.emit("given", target=ctx.target, reach=1, item=it.id, by=ctx.actor.id)
