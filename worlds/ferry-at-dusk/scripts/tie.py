def check(ctx):
    if ctx.target.state.rope:
        return "the rope is already on it"
    ropes = [k for k in ctx.actor.children() if k.state.kind == "rope"]
    if not ropes:
        return "you need a rope to tie on"
    return True

def apply(ctx):
    rope = [k for k in ctx.actor.children() if k.state.kind == "rope"][0]
    ctx.destroy(rope)
    ctx.patch(ctx.target, {"rope": True,
                           "description": "Iron bell on a post. A new rope hangs from the clapper, the knot still stiff."})
    ctx.emit("tied", target=ctx.target, reach=1)
