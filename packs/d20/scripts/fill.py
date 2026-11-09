def source_here(ctx):
    here = ctx.actor.parent
    if here.state.water_source:
        return here
    for p in ctx.children(here, "thing"):
        if p.state.water_source and (p.state.left is None or int(p.state.left) > 0):
            return p
    return None

def check(ctx):
    if ctx.target.parent.id != ctx.actor.id:
        return "you are not holding it"
    if ctx.target.state.capacity is None:
        return "it holds no water"
    if source_here(ctx) is None:
        return "there is no water here to fill it from"
    return True

def apply(ctx):
    src = source_here(ctx)
    cap = int(ctx.target.state.capacity)
    if src.state.left is not None:
        ctx.patch(src, {"left": max(0, int(src.state.left) - 1)})
    ctx.patch(ctx.target, {"left": cap, "description": ctx.target.state.description_full or ctx.target.state.description})
    ctx.emit("filled", target=ctx.target, reach=1, by=ctx.actor.id, source=src.id)
