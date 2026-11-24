use("common")
def walk(ctx, me, place, back, key):
    # one step, toward water or back toward where it came from (`key`: the post of a body nobody holds, the place a
    # held seat left for water); quiet, so the story takes no first sight from it
    here = me.parent
    if not back and not home_of(me, key) and here is not None:
        ctx.patch(me, {key: here.id, "water_left_t": ctx.t})
    ctx.move(me, place)
    ctx.emit("arrived", target=place, reach=1, who=me.id, place=place.id, quiet=True, for_water=not back)
    if back and home_of(me, key) == place.id:
        ctx.patch(me, {key: None})

def home_key(ctx, me):
    # A body nobody holds goes back to its post. A held seat gone idle goes back only to the place it left for water,
    # and only while its player has done nothing since: a post is an NPC's, and a player who walked off chose to (a
    # player waiting on a watcher was walked back to his template post, 2026-11-23).
    if not ctx.embodied(me):
        return "post"
    acted = ctx.acted_at(me)
    if me.state.water_from and acted is not None and acted > float(me.state.water_left_t or 0):
        ctx.patch(me, {"water_from": None})  # its errand is over: the player has moved it since
    return "water_from"

def home_of(me, key):
    return me.state.post if key == "post" else me.state.water_from

def tick(ctx):
    # Thirsty and water within reach: drink. A skin in hand first, then a source here (and fill the skin while at
    # it). Thirsty, nothing here and on my feet: a step toward the nearest water I know the way to, one step a look;
    # there, a draw a look until full or near it, then a step a look back (home_key says where). A body that is down drinks what is put in its hand. Not an always
    # behavior: while someone embodies this body they choose when to drink and where to go. A held seat gone idle
    # (a mind on a watcher) looks after itself the same way: every walk goes around a side that outlawed the body.
    # A body whose state says `stays` (the world's call, per body) drinks what is at hand and never walks for it.
    me = ctx.self
    st = me.state
    if st.dead:
        return
    here = me.parent
    roams = not st.down and not st.stays
    water = int(st.water if st.water is not None else 10)
    mx = int(st.max_water or 10)
    key = home_key(ctx, me)
    post = ctx.get(home_of(me, key)) if home_of(me, key) else None
    away = post is not None and here is not None and post.id != here.id
    # away from the post for water, drink your fill at an endless source before the walk back; a store with a
    # count gives one draw, enough to end the thirst, and its keeper's people the rest
    topping = away and water <= mx - 4 and endless(water_here(ctx, here, me))
    if water > 3 and not topping:
        if away and roams:
            step = first_step(ctx, me, here, post.id, 8)
            if step is not None:
                walk(ctx, me, step, True, key)
        return
    skin = None
    for it in ([] if topping else me.children()):  # at the source the skin is for the road back
        if it.state.capacity is not None and int(it.state.left or 0) > 0:
            skin = it
            break
    src = water_here(ctx, here, me)
    if skin is None and src is None:
        if roams and here is not None:
            near = water_near(ctx, me, here)
            if near is not None:
                walk(ctx, me, near, False, key)
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
        for it in (me.children() if endless(src) else []):  # a skin is filled where it costs no one's count
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
