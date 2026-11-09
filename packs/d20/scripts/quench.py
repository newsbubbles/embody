use("common")
def walk(ctx, me, place, back):
    # one step, for water or back to the post; quiet, so the story takes no first sight from it
    here = me.parent
    if not back and not me.state.post and here is not None:
        ctx.patch(me, {"post": here.id})
    ctx.move(me, place)
    ctx.emit("arrived", target=place, reach=1, who=me.id, place=place.id, quiet=True, for_water=not back)
    if back:
        ctx.patch(me, {"post": None})

def tick(ctx):
    # Thirsty and water within reach: drink. A skin in hand first, then a source here (and fill the skin while at
    # it). Thirsty, nothing here, water one known step away and on my feet: walk there; watered, walk back to the
    # post. A body that is down drinks what is put in its hand. Not an always behavior: while someone embodies this
    # body they choose when to drink and where to go.
    me = ctx.self
    st = me.state
    if st.dead:
        return
    here = me.parent
    water = int(st.water if st.water is not None else 10)
    if water > 3:
        post = ctx.get(st.post) if st.post else None
        if post is not None and here is not None and post.id != here.id and not st.down:
            walk(ctx, me, post, True)
        return
    mx = int(st.max_water or 10)
    skin = None
    for it in me.children():
        if it.state.capacity is not None and int(it.state.left or 0) > 0:
            skin = it
            break
    src = water_here(ctx, here)
    if skin is None and src is None:
        if not st.down and here is not None:
            near = water_near(ctx, me, here)
            if near is not None:
                walk(ctx, me, near, False)
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
        revive(ctx, me, new)
        return
    left = int(skin.state.left or 0) - 1
    ctx.patch(skin, {"left": left, "description": (skin.state.description_empty or "Empty.") if left <= 0 else skin.state.description})
    ctx.emit("drank", target=skin, reach=1, by=me.id, left=left, water=new)
    revive(ctx, me, new)
