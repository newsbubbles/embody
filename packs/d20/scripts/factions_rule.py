use("common")
def on(ctx, event):
    # standing moves on deeds: strike a member and the faction remembers; at -4 they come for you
    k = event.kind
    t = ctx.get(event.target) if event.target else None
    by = ctx.get(event.payload.get("by")) if event.payload.get("by") else None
    if k == "dishonor":
        who = ctx.get(event.target)
        if who is None:
            return
        for f in ctx.find(type="faction", limit=20):
            shift_standing(ctx, who, f, -2, "dishonor")
        return
    if t is None or by is None or by.id == t.id:
        return
    f = faction_of(ctx, t)
    if f is None or by.state.faction == f.name:
        return
    if k == "hit":
        shift_standing(ctx, by, f, -2, "struck " + t.name)
    elif k == "killed":
        shift_standing(ctx, by, f, -5, "killed " + t.name)
    elif k == "cowed":
        shift_standing(ctx, by, f, -1, "threatened " + t.name)
    elif k == "agreed":
        shift_standing(ctx, by, f, 2, "terms with " + t.name)
    elif k == "given":
        # a gift is something they keep: a trade (the thing is gone by now) or a return (they gave it first) is not one
        item = ctx.get(event.payload.get("item"))
        if item is None or item.parent is None or item.parent.id != t.id or item.state.given_before_by == t.id:
            return
        shift_standing(ctx, by, f, 1, "a gift to " + t.name)
