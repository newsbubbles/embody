use("common")
def check(ctx):
    me = ctx.actor
    t = ctx.target
    if t.parent is None or (t.parent.id != me.parent.id and t.id != me.id):
        return "they are not here"
    if t.state.dead:
        return "they are past tending"
    v = int(t.state.hp or 0)
    if not t.state.down and v >= int(t.state.max_hp or 6):
        return "they are whole: nothing to tend"
    med = medicine_in_hand(me)
    if med is None and not t.state.down:
        return "they are on their feet and you have no medicine in hand: rest mends them, or bring medicine (a medic carries it)"
    if med is None and wash_water(ctx, me) is None:
        return "a wound bound dry festers: hold a skin with water in it, or tend them beside a cask or a source"
    return True

def medicine_in_hand(me):
    for it in me.children():
        if it.state.medicine and int(it.state.doses or 0) > 0:
            return it
    return None

def wash_water(ctx, me):
    # a skin in hand with water in it, else the water here (a cask, the jars, a well)
    for it in me.children():
        if it.state.capacity is not None and int(it.state.left or 0) > 0:
            return it
    return water_here(ctx, me.parent)

def apply(ctx):
    # medicine in hand: a dose, no roll. Bare hands: a draw of water to wash the wound, and survival against 12
    # binds a downed body so it can stand at 1. The water is spent whether the binding holds or not.
    me = ctx.actor
    t = ctx.target
    st = t.state
    v = int(st.hp or 0)
    mx = int(st.max_hp or 6)
    med = medicine_in_hand(me)
    roll = None
    washed = None
    if med is not None:
        doses = int(med.state.doses or 0) - 1
        heal = int(med.state.heals or 3)
        ctx.patch(med, {"doses": doses, "description": (med.state.description_empty or "Used up.") if doses <= 0 else med.state.description})
    else:
        src = wash_water(ctx, me)
        washed = src.id
        if src.state.left is not None:
            left = int(src.state.left) - 1
            changes = {"left": left}
            if left <= 0 and src.state.description_empty:
                changes["description"] = src.state.description_empty
            ctx.patch(src, changes)
        roll = ctx.rand.roll("1d20")
        total = roll + bonus(me, "survival")
        heal = 1 if total >= 12 else 0
    v = min(mx, v + heal)
    changes = {"hp": v}
    if v > mx // 2 and st.wounded:
        changes["wounded"] = False
    rose = bool(st.down and v >= 1)
    if rose:
        changes["down"] = False
        changes["downed_by"] = None
        changes["dry_since"] = None
        changes["fading"] = None
    ctx.patch(t, changes)
    ctx.emit("tended", target=t, reach=1, by=me.id, medicine=med.name if med is not None else None,
             washed_with=washed, roll=roll, success=heal > 0, hp=v)
    if rose:
        ctx.emit("rose", target=t, reach=1, by=me.id)
    if heal <= 0:
        ctx.log("survival " + str(roll) + ": the binding slips and the water is gone; try again")
    else:
        ctx.log("hp " + str(v) + (", on their feet" if rose else "") + (" (" + med.name + ")" if med is not None else ""))
    return {"hp": v, "rose": rose, "success": heal > 0}
