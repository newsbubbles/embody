use("clothing")

# let_dress: who may dress or undress you (params {"who": a name here, "anyone" or "nobody"}); names add up.

def who_of(ctx):
    return lower((ctx.params or {}).get("who"))

def body_named(ctx, name):
    here = ctx.actor.parent
    if here is None:
        return None
    for c in here.children():
        if c.id != ctx.actor.id and c.is_a("creature") and lower(c.name) == name:
            return c
    return None

def check(ctx):
    who = who_of(ctx)
    if not who:
        return "say who: params {\"who\": a name here, \"anyone\" or \"nobody\"}"
    if who not in ["anyone", "nobody"] and body_named(ctx, who) is None:
        return "nobody here is called " + who
    return True

def apply(ctx):
    me = ctx.actor
    who = who_of(ctx)
    if who == "nobody":
        now = []
    elif who == "anyone":
        now = ["anyone"]
    else:
        now = [x for x in (me.state.lets_dress or []) if x != "anyone"]
        b = body_named(ctx, who)
        if b.id not in now:
            now.append(b.id)
    ctx.patch(me, {"lets_dress": now if now else None})
    names = [ctx.get(i).name for i in now if ctx.get(i) is not None]
    ctx.log("you let " + ("anyone" if now == ["anyone"] else (join_and(names) if names else "nobody")) + " dress or undress you")
    return {"lets_dress": now}
