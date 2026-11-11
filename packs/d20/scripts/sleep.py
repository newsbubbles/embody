def check(ctx):
    me = ctx.actor.state
    if me.dead:
        return "the dead do not sleep"
    if me.asleep:
        return "you are asleep already"
    return True

def apply(ctx):
    # lie down: you mend faster, you hear only what is loud, and anyone here may rob or strike you
    me = ctx.actor
    ctx.patch(me, {"asleep": True, "braced": False})
    ctx.emit("slept", target=me, reach=1, by=me.id, place=me.parent.id if me.parent else None)
    ctx.log("you sleep; something loud, a hand on you or your next deed wakes you")
