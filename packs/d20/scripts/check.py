use("common")
def apply(ctx):
    # d20 + stat + skill against a difficulty; everyone near sees the numbers
    p = ctx.params or {}
    skill = str(p.get("skill") or "")
    dc = int(p.get("dc") or 12)
    roll = ctx.rand.roll("1d20")
    mod = bonus(ctx.actor, skill)
    total = roll + mod
    ok = total >= dc
    here = ctx.actor.parent
    ctx.emit("checked", target=ctx.actor, reach=1, by=ctx.actor.id, place=here.id if here is not None else None,
             skill=skill, roll=roll, mod=mod, total=total, dc=dc, success=ok, margin=total - dc)
    ctx.log(skill + ": d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + (" pass" if ok else " fail"))
    return {"roll": roll, "mod": mod, "total": total, "dc": dc, "success": ok}
