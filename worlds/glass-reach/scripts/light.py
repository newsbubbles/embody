# A light (2026-11-12, Aaron knelt at a shrine whose candle the words named and nothing could light): a candle, lamp or
# torch you light from a fire, from another light, or with a tinderbox in your hand, and snuff again. It burns down
# while lit: `fuel` is the seconds it has left, and when they run out it goes dark for good. A lit light is a fire to
# whatever reads `lit` (burning a paper at it, a shrine that sees by it). Its words change with it when the world sets
# `desc_lit`, `desc_dark` and `desc_spent` on its state.

def here_or_held(ctx):
    me = ctx.self
    a = ctx.actor
    if me.parent is None or a.parent is None:
        return False
    return me.parent.id == a.id or me.parent.id == a.parent.id

def kindling(ctx):
    # what it catches from: a tinderbox or a light in your hands, the place's own fire, or a fire or light here
    me = ctx.self
    a = ctx.actor
    for it in a.children():
        if it.id != me.id and (it.state.kindles or it.state.lit):
            return it
    here = a.parent
    if here is not None and (here.state.fire or here.state.lit):
        return here
    if here is not None:
        for it in ctx.children(here):
            if it.id != me.id and (it.state.fire or it.state.lit):
                return it
    return None

def check(ctx):
    me = ctx.self
    if not here_or_held(ctx):
        return "it is not in your hands or here"
    if ctx.verb == "snuff":
        return True if me.state.lit else "it is not lit"
    if me.state.lit:
        return "it is already lit"
    if float(me.state.fuel or 0) <= 0:
        return "it is burned down to nothing: there is nothing left to light"
    if kindling(ctx) is None:
        return ("there is nothing to light it from: carry it to a fire or another light, or hold a tinderbox "
                "(a flint and steel) in your hands")
    return True

def apply(ctx):
    me = ctx.self
    a = ctx.actor
    if ctx.verb == "snuff":
        at = me.state.lit_at
        left = max(0.0, float(me.state.fuel or 0) - (ctx.t - (ctx.t if at is None else float(at))))
        changes = {"lit": False, "fuel": left, "lit_at": None}
        if me.state.desc_dark:
            changes["description"] = me.state.desc_dark
        ctx.patch(me, changes)
        ctx.emit("scene", target=a.parent, reach=1, text=a.name + " pinches out " + me.name.lower() + ".")
        return "snuffed: it has about " + str(max(1, int(left // 60))) + " minutes of burning left"
    src = kindling(ctx)
    fuel = float(me.state.fuel or 0)
    changes = {"lit": True, "lit_at": ctx.t}
    if me.state.desc_lit:
        changes["description"] = me.state.desc_lit
    ctx.patch(me, changes)
    ctx.schedule(fuel, "light_out", target=me, payload={"at": ctx.t})
    how = "strikes a spark into the tinder and lights " if src.state.kindles else "lights "
    ctx.emit("scene", target=a.parent, reach=1, text=a.name + " " + how + me.name.lower() + ". The flame stands up, "
             "small and steady.")
    return "lit: it will burn about " + str(max(1, int(fuel // 60))) + " minutes"

def on(ctx, event):
    me = ctx.self
    if event.kind != "light_out" or not me.state.lit:
        return
    at = (event.payload or {}).get("at")
    if at is None or me.state.lit_at is None or float(at) != float(me.state.lit_at):
        return  # snuffed and lit again since: a later light_out is the one that counts
    changes = {"lit": False, "fuel": 0, "lit_at": None}
    if me.state.desc_spent:
        changes["description"] = me.state.desc_spent
    ctx.patch(me, changes)
    if me.parent is not None:
        ctx.emit("scene", target=me.parent, reach=1, text=me.name + " gutters and goes out.")
