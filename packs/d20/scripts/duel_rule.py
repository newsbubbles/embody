use("common")
def end(ctx, d, loser, how, place=None):
    winner = None
    for p in d["participants"]:
        if p != loser.id:
            winner = p
    ctx.unrelate(d["id"])
    place = place or ctx.get(d["data"].get("place")) or loser.parent
    ctx.emit("duel_over", target=place, reach=1, winner=winner, loser=loser.id, how=how)

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
    if k == "arrived":
        # a duelist who walks out of the ring has stepped back: the duel is over and their own side remembers it
        who = ctx.get(event.payload.get("who"))
        if who is None:
            return
        for d in ctx.relations(who, "duel"):
            ring = d["data"].get("place")
            if ring and event.payload.get("place") != ring:
                end(ctx, d, who, "left", ctx.get(ring))
                f = faction_of(ctx, who)
                if f is not None:
                    shift_standing(ctx, who, f, -2, "stepped out of the ring")
        return
    if k == "agreed":
        # terms struck between the two in a ring: the one who agreed yields, and the duel ends by the usual rule
        who = ctx.get(event.target)
        by = ctx.get(event.payload.get("by"))
        if who is None or by is None:
            return
        for d in ctx.relations(who, "duel"):
            if by.id in d["participants"]:
                ctx.patch(who, {"yielded": by.id, "braced": False})
                ctx.emit("yielded", target=who, reach=1, to=by.id, on_terms=str(event.payload.get("offer")))
                ctx.emit("yielded_to", target=by, reach=0, by=who.id)
        return
    who = ctx.get(event.target)
    if who is None:
        return
    for d in ctx.relations(who, "duel"):
        end(ctx, d, who, k)
