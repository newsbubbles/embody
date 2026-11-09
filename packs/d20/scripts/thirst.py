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
    water = max(0, int(st.water if st.water is not None else 10) - loss)
    changes = {"water": water}
    if water <= 3 and not st.thirsty:
        changes["thirsty"] = True
        ctx.emit("thirsty", target=me, reach=0, water=water)
    ctx.patch(me, changes)
    if water == 0:
        # dry: vigor goes down to the floor and no further. Thirst puts a body down; it does not kill. Water brings it up.
        v = int(st.vigor or 0)
        if v > 0:
            ctx.patch(me, {"vigor": v - 1})
            ctx.emit("parched", target=me, reach=0, vigor=v - 1)
            if v - 1 <= 0 and not st.down:
                ctx.patch(me, {"downed_by": "thirst"})
            settle(ctx, me, "thirst")
