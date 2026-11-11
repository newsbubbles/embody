def key_in_hand(who, lk):
    # the thing that fits: the one the lock names, by id or by name
    want = str(lk.state.key or "").lower()
    if not want:
        return None
    for it in who.children():
        if it.id == lk.state.key or (it.name or "").lower() == want:
            return it
    return None

def turns(ctx, lk):
    # how this hand may turn the lock: "key", "code" or "bolt" (no key and no code), else why not and what would
    p = ctx.params or {}
    if p.get("code") is not None:
        if not lk.state.code:
            return "this lock takes no code" + (": it takes its key" if lk.state.key else "")
        if str(p.get("code")) != str(lk.state.code):
            return "the code is wrong"
        return "code"
    if key_in_hand(ctx.actor, lk) is not None:
        return "key"
    if not lk.state.key and not lk.state.code:
        return "bolt"
    ways = []
    if lk.state.key:
        ways.append("its key in your hand")
    if lk.state.code:
        ways.append("its code (params {\"code\": ...})")
    return "it takes " + " or ".join(ways) + ("; or pick it" if lk.state.pick_dc and lk.state.locked else "")

def shut_what(lk):
    # the box, the door or the place this lock keeps shut
    return lk.parent

def where_of(ctx):
    here = ctx.actor.parent
    return here.id if here is not None else None
