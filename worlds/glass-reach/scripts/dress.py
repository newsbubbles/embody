def load(who):
    # the same count take uses: a skin or anything with a capacity is 2, the rest 1 unless it says
    n = 0
    for c in who.children():
        n = n + int(c.state.bulk or (2 if c.state.capacity else 1))
    return n

def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "it is not here"
    if int(ctx.target.state.stone or 0) <= 0:
        return "nothing left in the pile worth the chisel"
    if ctx.actor.state.down:
        return "you are down"
    if ctx.actor.state.carry and load(ctx.actor) + 2 > int(ctx.actor.state.carry):
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
