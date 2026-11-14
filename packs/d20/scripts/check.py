use("common")
def apply(ctx):
    # d20 + stat + skill against a difficulty; everyone near sees the numbers
    p = ctx.params or {}
    skill = str(p.get("skill") or "")
    dc = int(p.get("dc") or 12)
    roll = ctx.rand.roll("1d20")
    mod = bonus(ctx.actor, skill, ctx)  # a dc the caller chose teaches nothing: no learn here
    here = ctx.actor.parent
    aid = take_aid(ctx, ctx.actor, skill, here)
    if aid is not None:
        mod = mod + int(aid.get("bonus") or 0)
    total = roll + mod
    ok = total >= dc
    # a skill nobody here has heard of is still a roll, an untrained one on wits, and the result says so plainly
    untrained = bool(skill) and not known_skill(ctx, ctx.actor, skill)
    note = None
    if untrained:
        note = "no skill '" + skill + "' here: an untrained roll on wits (skills: " + ", ".join(sorted(SKILLS)) + ")"
        if ctx.actor.state.sheet:
            note = "no skill '" + skill + "' in this world's skillbook: an untrained roll on " + sheet_rules(ctx)["untrained"] + " (guide('skills') lists them)"
    ctx.emit("checked", target=ctx.actor, reach=1, by=ctx.actor.id, place=here.id if here is not None else None,
             skill=skill, roll=roll, mod=mod, total=total, dc=dc, success=ok, margin=total - dc, untrained=untrained, aid=aid)
    helped = " (+" + str(aid.get("bonus") or 0) + ": " + str(aid.get("why") or "a hand from someone") + ")" if aid is not None else ""
    ctx.log(skill + ": d20 " + str(roll) + " + " + str(mod) + helped + " = " + str(total) + " vs " + str(dc) + (" pass" if ok else " fail") + (" (" + note + ")" if note else ""))
    out = {"roll": roll, "mod": mod, "total": total, "dc": dc, "success": ok}
    if aid is not None:
        out["aid"] = aid
    if note:
        out["untrained"] = True
        out["note"] = note
    return out
