def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "it is not here"
    if int(ctx.target.state.ember or 0) <= 0:
        return "this vein is picked clean"
    if ctx.actor.state.down:
        return "you are down"
    if ctx.actor.state.carry and ctx.load(ctx.actor) + 1 > float(ctx.actor.state.carry):
        return "your hands are full: drop or give something before you dig"
    return True

def apply(ctx):
    ctx.emit("harvesting", target=ctx.target, reach=1, by=ctx.actor.id)

def finish(ctx):
    left = int(ctx.target.state.ember or 0) - 1
    ctx.patch(ctx.target, {"ember": left})
    # one shard, onto the shards already in hand: Emberglass is a stack
    shard = ctx.spawn("thing", ctx.actor, name="Emberglass", state={"kind": "ember", "portable": True, "count": 1,
                      "description": "A shard the length of a hand, dull red, warm through the cloth you wrap it in."})
    ctx.merge(shard)
    ctx.emit("harvested", target=ctx.target, reach=1, by=ctx.actor.id, left=left)
    ctx.log("a shard of emberglass, " + str(left) + " more in the vein")
