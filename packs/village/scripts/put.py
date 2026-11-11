def find_item(ctx):
    want = str(ctx.params.get("item", "")).lower()
    for it in ctx.actor.children():
        if it.id == want or (it.name or "").lower() == want:
            return it
    return None

def fits(holder, it):
    # a holder says what it takes: ["any"], or state flags the thing must carry (["weapon"] for a rack of blades)
    for k in holder.state.holds or []:
        if k == "any" or it.state.get(k):
            return True
    return False

def joins(holder, it):
    # a stack that lands on a like stack takes no new place on the holder
    if it.state.count is None:
        return False
    for c in holder.children():
        if c.name == it.name and c.type == it.type and c.state.count is not None:
            return True
    return False

def check(ctx):
    if not ctx.params or "item" not in ctx.params:
        return "say what to put there: params {\"item\": <id or name of something you hold>, \"count\": how many of a stack}"
    it = find_item(ctx)
    if it is None:
        return "you hold no such thing"
    if ctx.target.state.holds is None:
        return "it holds nothing; drop the thing here instead, or find a rack, a shelf or a chest"
    if ctx.target.parent is None or ctx.target.parent.id != ctx.actor.parent.id:
        return "it is not here"
    lk = ctx.locked(ctx.target)
    if lk is not None:
        return ctx.target.name + " is locked: unlock " + ("it" if lk.id == ctx.target.id else lk.name) + " first, with its key or its code, or pick it"
    if not fits(ctx.target, it):
        return "it does not take that: it holds " + ", ".join(ctx.target.state.holds)
    n = ctx.params.get("count")
    have = ctx.count(it)
    if n is not None and (int(n) < 1 or int(n) > have):
        return "you hold " + str(have) + " of " + it.name + ": put 1 to " + str(have) + ", or leave count out for all of it"
    room = ctx.target.state.room
    if room is not None and not joins(ctx.target, it) and len([c for c in ctx.target.children() if not c.state.attached]) >= int(room):
        return "it is full"
    return True

def apply(ctx):
    it = find_item(ctx)
    n = ctx.params.get("count")
    n = ctx.count(it) if n is None else int(n)
    got = ctx.transfer(it, ctx.target, n)
    ctx.emit("put", target=ctx.target, reach=1, item=got.id, count=n, by=ctx.actor.id)
