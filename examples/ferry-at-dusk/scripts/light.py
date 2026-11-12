def check(ctx):
    if ctx.target.state.lit:
        return "it is already lit"
    fire = [k for k in ctx.actor.children() if k.state.kind == "fire"]
    if not fire:
        return "you have nothing to light it with"
    return True

def apply(ctx):
    ctx.target.state.lit = True
    ctx.emit("lit", target=ctx.target, reach=1)
