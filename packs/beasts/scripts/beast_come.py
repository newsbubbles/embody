use("beasts")
# Call your beast: here, it follows you again; one way over, it comes to you if the way is open.

def check(ctx):
    b = ctx.target
    me = ctx.actor
    if b.state.owner != me.id:
        return b.name + " is not yours to call"
    if b.state.dead or b.state.down or b.parent is None or me.parent is None:
        return b.name + " cannot come"
    if b.parent.id == me.parent.id:
        return True
    if not open_way(ctx, b, b.parent, me.parent):
        return b.name + " is too far off to hear you, or the way is shut"
    return True

def apply(ctx):
    b = ctx.target
    me = ctx.actor
    if b.parent.id != me.parent.id:
        walk_to(ctx, b, me.parent, "called")
    ctx.patch(b, {"follows": me.id, "staying": False, "asleep": False})
    ctx.emit("beast_comes", target=b, reach=1, by=me.id)
