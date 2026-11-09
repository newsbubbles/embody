def check(ctx):
    if ctx.target.parent.id != ctx.actor.id:
        return "you are not holding it"
    if (ctx.target.state.left or 0) <= 0:
        return "it is empty"
    return True

def apply(ctx):
    left = (ctx.target.state.left or 0) - 1
    ctx.target.state.left = left
    drinks = (ctx.actor.state.drinks or 0) + 1
    ctx.actor.state.drinks = drinks
    ctx.emit("drank", target=ctx.target, reach=1, by=ctx.actor.id, left=left)
    if left <= 0:
        ctx.patch(ctx.target, {"description": "An empty mug. It was " + (ctx.target.name or "a drink").lower() + "."})
        ctx.log("Empty. Mara will want the mug back.")
    else:
        ctx.log("A long pull. Some left.")
    if drinks >= 3 and not ctx.actor.state.tipsy:
        ctx.actor.state.tipsy = True
        ctx.emit("tipsy", target=ctx.actor, reach=1)
        ctx.log("The room has taken on a lean.")
