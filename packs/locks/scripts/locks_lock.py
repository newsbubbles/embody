use("locks")

def check(ctx):
    lk = ctx.target
    if lk.state.broken:
        return "the lock is broken: it will never lock again"
    if lk.state.locked:
        return "it is already locked"
    how = turns(ctx, lk)
    if how not in ("key", "code", "bolt"):
        return how
    return True

def apply(ctx):
    lk = ctx.target
    held = shut_what(lk)
    how = turns(ctx, lk)
    ctx.patch(lk, {"locked": True, "picking": None})
    ctx.emit("locked", target=held, reach=1, by=ctx.actor.id, lock=lk.id, holder=held.id, how=how)
    ctx.log(lk.name + " is locked: " + held.name + " stays shut until its key, its code or a pick opens it")
