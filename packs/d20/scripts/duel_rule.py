def duels_in(ctx, place):
    out = []
    seen = {}
    for c in ctx.children(place, "creature"):
        for d in ctx.relations(c, "duel"):
            if not seen.get(d["id"]):
                seen[d["id"]] = True
                out.append(d)
    return out

def on(ctx, event):
    k = event.kind
    if k == "before_act":
        if event.payload.get("verb") != "attack":
            return
        a = ctx.get(event.actor)
        if a is None or a.parent is None:
            return
        for d in duels_in(ctx, a.parent):
            ps = d["participants"]
            names = [ctx.get(p).name for p in ps if ctx.get(p) is not None]
            if a.id not in ps:
                ctx.reject("the ring holds: this is between " + " and ".join(names), "wait for the duel to end, or challenge the winner")
            if event.target not in ps:
                ctx.reject("you are in a duel: your blade is for " + " and ".join([n for n in names if n != a.name]), "attack your opponent, or yield")
        return
    who = ctx.get(event.target)
    if who is None:
        return
    for d in ctx.relations(who, "duel"):
        ps = d["participants"]
        winner = None
        for p in ps:
            if p != who.id:
                winner = p
        ctx.unrelate(d["id"])
        place = ctx.get(d["data"].get("place")) or who.parent
        ctx.emit("duel_over", target=place, reach=1, winner=winner, loser=who.id, how=k)
