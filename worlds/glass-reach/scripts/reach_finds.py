# Things hidden in the Reach until someone looks: a hidden thing with `find_dc` turns up for whoever passes a check
# here with one of its `find_skills` and a total that reaches its dc. The place says something is off (a hint in a
# description); the check is the looking. Found, it is in plain sight for everyone there.

def unhint(ctx, c):
    # what pointed at it (the cistern's glint, the proud stone) says nothing more once it is found
    on = ctx.get(c.state.hint_on) if c.state.hint_on else None
    hint = c.state.find_hint
    if on is None or not hint:
        return
    d = on.state.description or ""
    if hint in d:
        ctx.patch(on, {"description": " ".join(d.replace(hint, "").split())})

def on(ctx, event):
    p = event.payload
    if not p.get("success"):
        return
    place = ctx.get(p.get("place"))
    me = ctx.get(p.get("by"))
    if place is None or me is None:
        return
    skill = str(p.get("skill") or "")
    total = int(p.get("total") or 0)
    for c in ctx.children(place):
        st = c.state
        if not st.hidden or not st.find_dc:
            continue
        if skill not in (st.find_skills or []) or total < int(st.find_dc):
            continue
        ctx.patch(c, {"hidden": False, "found_by": me.id})
        unhint(ctx, c)
        ctx.emit("scene", target=place, reach=1, text=st.find_text)
        if st.portable:
            # finding is not holding: a player once told the Landing he carried a log still lying where he found it
            ctx.emit("scene", target=me, reach=0, text="The " + c.name + " lies where you found it. To carry it, take it ("
                     + c.id + "); it is anyone's to pick up until someone does.")
        ctx.emit("found", target=c, reach=1, by=me.id, place=place.id, thing=c.name)
    # a hidden place one step off (Weeping Rock off the road): found, it is on everyone's map
    for e in ctx.edges(place.id, "connects_to", "out"):
        t = ctx.get(e["target"])
        if t is None or not t.state.hidden or not t.state.find_dc:
            continue
        if skill not in (t.state.find_skills or []) or total < int(t.state.find_dc):
            continue
        ctx.patch(t, {"hidden": False, "known_to": None, "found_by": me.id})
        ctx.emit("scene", target=place, reach=1, text=t.state.find_text)
        ctx.emit("found", target=t, reach=1, by=me.id, place=place.id, thing=t.name)
