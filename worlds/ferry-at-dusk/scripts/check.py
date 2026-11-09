def apply(ctx):
    # a plain d20 with the world's seed: deterministic, replayable, and the player sees the number
    skill = ""
    if ctx.params:
        skill = str(ctx.params.get("skill", ""))
    roll = ctx.rand.roll("1d20")
    mod = -2 if ctx.actor.state.tipsy else 0
    ctx.emit("checked", target=ctx.target, reach=1, by=ctx.actor.id, skill=skill, roll=roll, mod=mod, total=roll + mod)
    ctx.log("d20: " + str(roll) + (" " + str(mod) + " (tipsy)" if mod else ""))
    return roll + mod
