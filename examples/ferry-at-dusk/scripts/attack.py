def apply(ctx):
    dmg = ctx.rand.roll("1d6")
    ctx.target.state.hp = ctx.target.state.hp - dmg
    ctx.emit("hit", target=ctx.target, reach=1, dmg=dmg)
    return dmg
