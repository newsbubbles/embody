def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "it is not here"
    if int(ctx.target.state.stone or 0) <= 0:
        return "nothing left in the pile worth the chisel"
    if ctx.actor.state.down:
        return "you are down"
    # the engine's own count, as take and give use it: stacks by the piece, paper at nothing (a wright went to 9 of
    # 8 on a count of his own that missed his three shards, 2026-11-12)
    if ctx.actor.state.carry and ctx.load(ctx.actor) + 2 > float(ctx.actor.state.carry):
        return "your hands are full: a dressed stone is a two-hand load; drop or put something first"
    return True

def apply(ctx):
    ctx.emit("dressing", target=ctx.target, reach=1, by=ctx.actor.id)

def finish(ctx):
    left = int(ctx.target.state.stone or 0) - 1
    ctx.patch(ctx.target, {"stone": left})
    ctx.spawn("thing", ctx.actor, name="Dressed stone", state={"kind": "dressed stone", "portable": True, "bulk": 2,
              "description": "A block of Scar stone squared on four faces, heavy as a child."})
    ctx.emit("dressed", target=ctx.target, reach=1, by=ctx.actor.id, left=left)
    ctx.log("a dressed stone, " + str(left) + " more in the pile")
