def apply(ctx):
    # stop following whoever you followed
    who = ctx.actor.state.follows
    ctx.patch(ctx.actor, {"follows": None})
    ctx.emit("stayed", target=ctx.actor, reach=1, was_following=who)
