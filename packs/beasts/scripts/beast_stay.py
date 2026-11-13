use("beasts")
# Tell your beast to stay where it is: it stops following you until you call it (come).

def check(ctx):
    b = ctx.target
    if b.state.owner != ctx.actor.id:
        return b.name + " is not yours to order"
    if b.parent is None or ctx.actor.parent is None or b.parent.id != ctx.actor.parent.id:
        return b.name + " is not here"
    return True

def apply(ctx):
    ctx.patch(ctx.target, {"follows": None, "staying": True})
    ctx.emit("beast_stays", target=ctx.target, reach=1, by=ctx.actor.id)
