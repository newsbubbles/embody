# A carrier with a mind in her seat sells on purpose (the owner, 2026-11-12: the crew handed Ossa three shards as load
# and the pan turned them into skins). Glass handed to her stays in her hand; `sell` is the trade: shards she holds
# go into the Guild's tally and the buyer gets a full Guild skin for each.

def shards(ctx, me):
    for it in me.children():
        if it.state.kind == "ember":
            return it
    return None

def want(ctx):
    n = (ctx.params or {}).get("count")
    if n is None:
        return 1
    if isinstance(n, int):
        return n
    if isinstance(n, str) and n.strip().isdigit():
        return int(n.strip())
    return 0

def check(ctx):
    me = ctx.actor
    buyer = ctx.target
    if buyer.id == me.id:
        return "sell to someone else"
    if buyer.parent is None or me.parent is None or buyer.parent.id != me.parent.id:
        return "they are not here"
    n = want(ctx)
    if n < 1:
        return "count is how many skins: a whole number"
    glass = shards(ctx, me)
    have = ctx.count(glass) if glass is not None else 0
    if have < n:
        return "you hold " + str(have) + " shard" + ("" if have == 1 else "s") + ": a skin is a shard, paid first"
    return True

def apply(ctx):
    me = ctx.actor
    buyer = ctx.target
    n = want(ctx)
    glass = shards(ctx, me)
    have = ctx.count(glass)
    if have > n:
        ctx.patch(glass, {"count": have - n})
    else:
        ctx.destroy(glass)
    for _ in range(n):
        ctx.spawn("waterskin", buyer, name="Guild waterskin", state={"left": 3, "given_by": me.id,
                  "description": "A Guild skin, tallied and stamped, heavy and cool.",
                  "description_full": "A Guild skin, tallied and stamped, heavy and cool.",
                  "description_empty": "A Guild skin, tallied and stamped, slack and dry."})
    ctx.patch(me, {"ember_bought": int(me.state.ember_bought or 0) + n})
    ctx.emit("traded", target=buyer, reach=1, by=me.id, got="Guild waterskin", gave="Emberglass", count=n)
    return {"sold": n, "to": buyer.name}
