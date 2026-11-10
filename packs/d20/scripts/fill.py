use("common")
def source_here(ctx):
    return water_here(ctx, ctx.actor.parent)

def check(ctx):
    if ctx.target.parent.id != ctx.actor.id:
        return "you are not holding it"
    if ctx.target.state.capacity is None:
        return "it holds no water"
    if ctx.target.state.left is not None and int(ctx.target.state.left) >= int(ctx.target.state.capacity):
        return "it is already full: drink from it first"
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
