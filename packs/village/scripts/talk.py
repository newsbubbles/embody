def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "talking to yourself helps nobody"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.target.state.asleep:
        return "they are asleep; wake them first"
    return True

def apply(ctx):
    about = ""
    if ctx.params:
        about = str(ctx.params.get("about", ""))
    ctx.emit("talked", target=ctx.target, reach=-1, by=ctx.actor.id, about=about)
