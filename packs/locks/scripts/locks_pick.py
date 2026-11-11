use("locks")

def check(ctx):
    lk = ctx.target
    if not lk.state.locked:
        return "it is not locked"
    if not lk.state.pick_dc:
        ways = []
        if lk.state.key:
            ways.append("its key")
        if lk.state.code:
            ways.append("its code")
        if lk.state.break_dc:
            ways.append("force (break)")
        return "this lock cannot be picked" + (": it takes " + " or ".join(ways) if ways else "")
    return True

def apply(ctx):
    # quiet while it works: the roll comes when the time is out, and only if you are still there
    lk = ctx.target
    ctx.patch(lk, {"picking": {"who": ctx.actor.id, "at": where_of(ctx)}})
    ctx.log("you set to work on " + lk.name + "; stay here until it gives")

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
    skills = me.state.skills or {}
    # a lockpick is the trade itself; a quiet hand or a craftsman's comes near it
    mod = int(me.state.wits or 0) + max(int(skills.get("lockpick") or 0), int(skills.get("stealth") or 0), int(skills.get("craft") or 0))
    roll = ctx.rand.roll("1d20")
    total = roll + mod
    dc = int(lk.state.pick_dc)
    if total >= dc:
        ctx.patch(lk, {"locked": False, "picking": None})
        ctx.emit("lock_picked", target=held, reach=1, by=me.id, lock=lk.id, holder=held.id, roll=roll, mod=mod, total=total, dc=dc)
        ctx.log("pick: d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + ": " + lk.name + " gives")
        return
    ctx.patch(lk, {"picking": None})
    ctx.emit("pick_failed", target=held, reach=1, by=me.id, lock=lk.id, holder=held.id, roll=roll, mod=mod, total=total, dc=dc)
    ctx.emit("scene", target=held, reach=1, text="Metal scrapes and clicks at " + lk.name.lower() + ": " + me.name + " is working at it.")
    ctx.log("pick: d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + ": it holds, and the room heard you")
