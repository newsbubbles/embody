use("locks")

def check(ctx):
    lk = ctx.target
    if not lk.state.locked:
        return "it is not locked"
    if not lk.state.break_dc:
        return "it will not break" + ("; pick it, or find its key or its code" if lk.state.pick_dc else ": find its key or its code")
    return True

def apply(ctx):
    # loud from the first blow
    lk = ctx.target
    held = shut_what(lk)
    ctx.patch(lk, {"picking": {"who": ctx.actor.id, "at": where_of(ctx)}})
    ctx.emit("scene", target=held, reach=2, text="Someone is battering at " + held.name.lower() + ".")
    ctx.log("you set your weight against " + lk.name + "; stay here until it gives")

def finish(ctx):
    lk = ctx.get(ctx.target.id)
    if lk is None:
        return
    me = ctx.actor
    at = (lk.state.picking or {}).get("at") if (lk.state.picking or {}).get("who") == me.id else None
    if not lk.state.locked:
        ctx.log(lk.name + " was opened before you were done")
        return
    if at is None or me.parent is None or me.parent.id != at:
        ctx.log("you left " + lk.name + " before it gave")
        return
    held = shut_what(lk)
    roll = ctx.rand.roll("1d20")
    mod = int(me.state.body or 0)
    total = roll + mod
    dc = int(lk.state.break_dc)
    if total >= dc:
        ctx.patch(lk, {"locked": False, "broken": True, "picking": None})
        ctx.emit("lock_broken", target=held, reach=2, by=me.id, lock=lk.id, holder=held.id, roll=roll, mod=mod, total=total, dc=dc)
        ctx.emit("scene", target=held, reach=2, text=lk.name + " gives with a crack: " + held.name.lower() + " stands open.")
        ctx.log("break: d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + ": it gives, and it will never lock again")
        return
    ctx.patch(lk, {"picking": None})
    ctx.emit("break_failed", target=held, reach=2, by=me.id, lock=lk.id, holder=held.id, roll=roll, mod=mod, total=total, dc=dc)
    ctx.log("break: d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + ": it holds, and everyone near heard it")
