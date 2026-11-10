use("common")
def check(ctx):
    me = ctx.actor
    t = ctx.target
    if t.parent is None or (t.parent.id != me.parent.id and t.id != me.id):
        return "they are not here"
    if t.state.dead:
        return "they are past tending"
    v = int(t.state.vigor or 0)
    if not t.state.down and v >= int(t.state.max_vigor or 6):
        return "they are whole: nothing to tend"
    med = medicine_in_hand(me)
    if med is None and not t.state.down:
        return "they are on their feet and you have no medicine in hand: rest mends them, or bring medicine (a medic carries it)"
    return True

def medicine_in_hand(me):
    for it in me.children():
        if it.state.medicine and int(it.state.doses or 0) > 0:
            return it
    return None

def apply(ctx):
    # medicine in hand: a dose, no roll. Bare hands: survival against 12 binds a downed body so it can stand at 1.
    me = ctx.actor
    t = ctx.target
    st = t.state
    v = int(st.vigor or 0)
    mx = int(st.max_vigor or 6)
    med = medicine_in_hand(me)
    roll = None
    if med is not None:
        doses = int(med.state.doses or 0) - 1
        heal = int(med.state.heals or 3)
        ctx.patch(med, {"doses": doses, "description": (med.state.description_empty or "Used up.") if doses <= 0 else med.state.description})
    else:
        roll = ctx.rand.roll("1d20")
        total = roll + bonus(me, "survival")
        heal = 1 if total >= 12 else 0
    v = min(mx, v + heal)
    changes = {"vigor": v}
    if v > mx // 2 and st.wounded:
        changes["wounded"] = False
    rose = bool(st.down and v >= 1)
    if rose:
        changes["down"] = False
        changes["downed_by"] = None
    ctx.patch(t, changes)
    ctx.emit("tended", target=t, reach=1, by=me.id, medicine=med.name if med is not None else None,
             roll=roll, success=heal > 0, vigor=v)
    if rose:
        ctx.emit("rose", target=t, reach=1, by=me.id)
    if heal <= 0:
        ctx.log("survival " + str(roll) + ": the binding slips; try again")
    else:
        ctx.log("vigor " + str(v) + (", on their feet" if rose else "") + (" (" + med.name + ")" if med is not None else ""))
    return {"vigor": v, "rose": rose, "success": heal > 0}
