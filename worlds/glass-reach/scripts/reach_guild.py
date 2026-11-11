# The Guild Yard beside the Landing. The dawn crawler fills the yard tank. The counting house is the yard's to keep:
# anyone not of the Guild who walks into it while one of the yard's four stands in the yard or at the door is turned
# back into the yard, unless they crept in unseen (stealth against the yard's watch). With all four down or gone, the
# door is only a door. The strongbox's own lock, when it has one, is the locks pack's to keep.
WATCH_DC = 15  # a creep past the yard's eyes: d20 + wits + stealth

def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def keepers(ctx, places):
    out = []
    for p in places:
        if p is None:
            continue
        for c in ctx.children(p, "creature"):
            if c.state.yard and not c.state.down and not c.state.dead:
                out.append(c)
    return out

def on(ctx, event):
    st = story_of(ctx).state
    if not st.guild_yard:
        return
    yard = ctx.get(st.guild_yard)
    if yard is None:
        return
    p = event.payload or {}
    if event.kind == "crawler":
        for it in ctx.children(yard, "thing"):
            if it.state.max_left and it.state.guild:
                ctx.patch(it, {"left": int(it.state.max_left)})
        return
    if event.kind != "arrived":
        return
    room = ctx.get(p.get("place"))
    who = ctx.get(p.get("who"))
    if room is None or who is None or not room.state.strongroom or who.state.faction == "the Carriers":
        return
    if who.parent is None or who.parent.id != room.id:
        return
    eyes = keepers(ctx, [yard, room])
    if len(eyes) == 0:
        return
    if p.get("quiet"):
        roll = ctx.rand.roll("1d20") + int(who.state.wits or 0) + int((who.state.skills or {}).get("stealth") or 0)
        if roll >= WATCH_DC:
            ctx.emit("scene", target=who, reach=0, text="You slip through the counting house door on the broken step. "
                     "Nobody in the yard turns.")
            ctx.emit("slipped_in", target=room, reach=0, by=who.id)
            return
    ctx.move(who, yard)
    ctx.emit("scene", target=yard, reach=1, text=eyes[0].name + " is in the counting house door before " + who.name +
             " is through it. 'Guild's. Not yours.' A hand on the chest, and " + who.name + " is back in the yard.")
    ctx.emit("turned_away", target=yard, reach=1, by=eyes[0].id, who=who.id)
