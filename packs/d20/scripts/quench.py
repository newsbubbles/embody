use("common")
def tick(ctx):
    # Thirsty and water within reach: drink. A skin in hand first, then a source here (and fill the skin while
    # at it). Not an always behavior: while someone embodies this body they choose when to drink.
    me = ctx.self
    st = me.state
    if st.dead or st.down:
        return
    water = int(st.water if st.water is not None else 10)
    if water > 3:
        return
    mx = int(st.max_water or 10)
    skin = None
    for it in me.children():
        if it.state.capacity is not None and int(it.state.left or 0) > 0:
            skin = it
            break
    src = water_here(ctx, me.parent)
    if skin is None and src is None:
        return
    new = min(mx, water + 4)
    changes = {"water": new}
    if new > 3 and st.thirsty:
        changes["thirsty"] = False
    ctx.patch(me, changes)
    if src is not None:
        if src.state.left is not None:
            ctx.patch(src, {"left": max(0, int(src.state.left) - 1)})
        ctx.emit("drank", target=src, reach=1, by=me.id, water=new, source=src.id)
        for it in me.children():
            if it.state.capacity is not None and int(it.state.left or 0) < int(it.state.capacity):
                ctx.patch(it, {"left": int(it.state.capacity), "description": it.state.description_full or it.state.description})
                ctx.emit("filled", target=it, reach=1, by=me.id, source=src.id)
                break
        return
    left = int(skin.state.left or 0) - 1
    ctx.patch(skin, {"left": left, "description": (skin.state.description_empty or "Empty.") if left <= 0 else skin.state.description})
    ctx.emit("drank", target=skin, reach=1, by=me.id, left=left, water=new)
