def check(ctx):
    if ctx.actor.state.asleep:
        return "you are already asleep"
    return True

def apply(ctx):
    ctx.actor.state.asleep = True
    ctx.emit("slept", target=ctx.actor, reach=1, who=ctx.actor.id)
    ctx.log("You settle down and sleep. Dawn, or a hand on your shoulder, will wake you.")
