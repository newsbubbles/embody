def find_item(ctx):
    want = str(ctx.params.get("item", "")).lower()
    for it in ctx.actor.children():
        if it.id == want or (it.name or "").lower() == want:
            return it
    return None

def check(ctx):
    if not ctx.params or "item" not in ctx.params:
        return "say what to show: params {\"item\": <id or name of something you hold>}"
    if find_item(ctx) is None:
        return "you hold no such thing"
    if ctx.target.id == ctx.actor.id:
        return "show it to someone else"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    return True

def apply(ctx):
    # they see it and read it; it stays in your hand
    it = find_item(ctx)
    text = it.state.text or it.state.description or ""
    ctx.emit("shown", target=ctx.target, reach=1, by=ctx.actor.id, item=it.id, name=it.name, text=text)
    ctx.log(ctx.target.name + " looks at the " + str(it.name).lower())
    return {"item": it.id, "text": text}
