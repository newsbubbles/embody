use("works")

def find_item(ctx):
    want = str(ctx.params.get("item", "")).lower()
    for it in ctx.actor.children():
        if it.id == want or (it.name or "").lower() == want:
            return it
    return None

def check(ctx):
    if not ctx.params or "item" not in ctx.params:
        return "say what to hand in: params {\"item\": <id or name of something you hold>}"
    if find_item(ctx) is None:
        return "you hold no such thing"
    if not at_site(ctx.target, ctx.actor):
        return "you are not at the works"
    return True

def apply(ctx):
    proj = ctx.target
    it = find_item(ctx)
    ctx.move(it, proj)
    ctx.emit("supplied", target=proj, reach=1, item=it.id, name=it.name, by=ctx.actor.id)
    if it.id == proj.state.plan:
        ctx.emit("scene", target=proj.parent, reach=1, works=proj.id,
                 text=ctx.actor.name + " puts the " + it.name + " back in the works.")
    describe(ctx, proj)
    b = blockers(ctx, proj, None, None)
    ctx.log("the works hold the " + it.name + (" (still: " + "; ".join(b) + ")" if b else "; nothing stops the work now"))
