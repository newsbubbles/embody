def tick(ctx):
    # rest: a body with water in it mends a point of hp a beat (the world's pace for mend), down or up. A body
    # a wound put down gets up at 2; thirst's down is water's to undo, and a dry body does not mend. Mending is
    # thirsty work: every second beat of mending costs a point of water. Asleep it mends twice as fast, and no thirstier.
    me = ctx.self
    st = me.state
    if st.dead:
        return
    water = int(st.water if st.water is not None else 10)
    if water <= 3:
        return
    v = int(st.hp or 0)
    mx = int(st.max_hp or 6)
    if v >= mx:
        return
    # asleep, a body mends two points a beat for the water of one
    v = min(mx, v + (2 if st.asleep else 1))
    owed = int(st.mend_owed or 0) + 1
    changes = {"hp": v, "mend_owed": owed % 2}
    if owed >= 2:
        changes["water"] = water - 1
    if v > mx // 2 and st.wounded:
        changes["wounded"] = False
    rose = bool(st.down and st.downed_by != "thirst" and v >= 2)
    if rose:
        changes["down"] = False
    ctx.patch(me, changes)
    ctx.emit("mended", target=me, reach=0, hp=v, wounded=changes.get("wounded", st.wounded),
             water=changes.get("water", water))
    if rose:
        ctx.emit("rose", target=me, reach=1, by="rest")
