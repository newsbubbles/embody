use("locks")

def check(ctx):
    lk = ctx.target
    if not lk.state.locked:
        return "it is not locked"
    how = turns(ctx, lk)
    if how not in ("key", "code", "bolt"):
        return how
    return True

def apply(ctx):
    lk = ctx.target
    held = shut_what(lk)
    how = turns(ctx, lk)
    ctx.patch(lk, {"locked": False, "picking": None})
    ctx.emit("unlocked", target=held, reach=1, by=ctx.actor.id, lock=lk.id, holder=held.id, how=how)
    ctx.log(lk.name + " is unlocked: " + held.name + " is open to anyone here")
