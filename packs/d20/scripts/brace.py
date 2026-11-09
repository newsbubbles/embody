def check(ctx):
    if ctx.actor.state.down:
        return "you are down"
    return True

def apply(ctx):
    # +3 to your defence until you do anything else
    ctx.patch(ctx.actor, {"braced": True})
    ctx.emit("braced", target=ctx.actor, reach=1)
