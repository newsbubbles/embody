use("clothing")

# the garment's own timer: when the time to put it on or take it off is out, it is done (or it says why not)

def on(ctx, event):
    it = ctx.self
    d = it.state.donning
    p = event.payload or {}
    if not d or d.get("by") != p.get("by") or d.get("doing") != p.get("doing"):
        return
    if float(d.get("until") or 0) > ctx.t + 0.5:
        return  # a later start replaced this one: its own timer finishes it
    finish_dressing(ctx, it)
