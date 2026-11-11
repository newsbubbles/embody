# Things hidden in the Reach until someone looks: a hidden thing with `find_dc` turns up for whoever passes a check
# here with one of its `find_skills` and a total that reaches its dc. The place says something is off (a hint in a
# description); the check is the looking. Found, it is in plain sight for everyone there.

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
        ctx.emit("scene", target=place, reach=1, text=st.find_text)
        ctx.emit("found", target=c, reach=1, by=me.id, place=place.id, thing=c.name)
