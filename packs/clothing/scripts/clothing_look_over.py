use("clothing")

# look_over: what someone here wears and carries in sight, for your eyes; within two metres (or with no spots to
# measure) the close detail of each piece too. Yourself: everything, with what hides what.

def apply(ctx):
    me = ctx.actor
    t = ctx.target
    refresh(ctx, t)  # what someone's hand moved past every verb is set right before anyone reads it
    full = t.id == me.id
    d = ctx.distance(me, t)
    close = full or d is None or d <= 2
    lines = outfit(t, close, full)
    if not lines:
        lines = [t.name + " wears nothing anyone could name."]
    for l in lines:
        ctx.log(l)
    out = {"who": t.name, "attire": lines, "close": close}
    if full:
        out["warmth"] = warmth(t)
        out["lets_dress"] = [ctx.get(i).name if ctx.get(i) is not None else i for i in (t.state.lets_dress or [])]
    return out
