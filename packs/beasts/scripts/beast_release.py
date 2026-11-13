use("beasts")
# Let your beast go: it is nobody's, and wild again.

def check(ctx):
    b = ctx.target
    if b.state.owner != ctx.actor.id:
        return b.name + " is not yours to let go"
    if b.parent is None or ctx.actor.parent is None or b.parent.id != ctx.actor.parent.id:
        return b.name + " is not here"
    return True

def apply(ctx):
    b = ctx.target
    ctx.patch(b, {"owner": None, "follows": None, "loyalty": 0, "trust": {}, "staying": False})
    ctx.emit("beast_released", target=b, reach=1, by=ctx.actor.id)
