use("common")
def tick(ctx):
    me = ctx.self
    st = me.state
    if st.dead:
        return
    here = me.parent
    if here is None or water_here(ctx, here) is not None:
        return
    loss = 2 if here.state.open else 1
    changes = {}
    if st.asleep:
        # asleep a body is not working: it dries at half the pace, a half carried to the next beat
        half = float(st.thirst_owed or 0) + loss / 2
        loss = int(half)
        changes["thirst_owed"] = half - loss
        if loss == 0:
            ctx.patch(me, changes)
            return
    water = max(0, int(st.water if st.water is not None else 10) - loss)
    changes["water"] = water
    if water <= 3 and not st.thirsty:
        changes["thirsty"] = True
        ctx.emit("thirsty", target=me, reach=0, water=water)
    roused = water <= 3 and bool(st.asleep)
    if roused:
        changes["asleep"] = False  # thirst wakes a sleeper, so it can drink
    ctx.patch(me, changes)
    if roused:
        ctx.emit("woke", target=me, reach=1, by=me.id, why="thirst")
    if water == 0:
        # dry: hp goes down to the floor. Thirst puts a body down, and one left down and dry fades and dies in a few
        # world days (fade). Water brings it up while it still breathes.
        v = int(st.hp or 0)
        if v > 0:
            ctx.patch(me, {"hp": v - 1})
            ctx.emit("parched", target=me, reach=0, hp=v - 1)
            if v - 1 <= 0 and not st.down:
                ctx.patch(me, {"downed_by": "thirst", "dry_since": ctx.t})
            settle(ctx, me, "thirst")
        elif st.down and st.downed_by == "thirst":
            fade(ctx, me)
