use("ledgers")
# A device writes down by itself the deeds its `records` names, done by its holder or to them (a `holder` listener:
# the engine hands it what its holder's events are, wherever they happen).

def spec_for(rec, kind):
    if isinstance(rec, list):
        return dict(DEEDS.get(kind) or {"doer": "note", "other": "note"}) if kind in rec else None
    if isinstance(rec, dict) and kind in rec and rec[kind]:
        s = dict(DEEDS.get(kind) or {"doer": "note", "other": "note"})
        if isinstance(rec[kind], dict):
            s.update(rec[kind])
        return s
    return None

def on(ctx, ev):
    dev = ctx.self
    holder = dev.parent
    if holder is None or holder.is_a("place") or not dev.state.records:
        return
    spec = spec_for(dev.state.records, ev.kind)
    if spec is None:
        return
    p = ev.payload
    if p.get("item") == dev.id:
        return  # the device itself changing hands is not an entry in it
    doer = p.get("by") or p.get("who") or ev.actor
    if holder.id == doer:
        side = "doer"
        other = None
        for x in [ev.target, p.get("to"), p.get("source")]:
            if other is None and x and x != doer and x != p.get("item"):
                other = x
    elif holder.id in [ev.target, p.get("to"), p.get("source")]:
        side = "other"
        other = doer
    else:
        return
    kind = spec.get(side)
    if not kind:
        return
    it = ctx.get(p.get("item")) if isinstance(p.get("item"), str) else None
    item = it.name if it is not None else (p.get("name") or p.get("what"))
    qty = num(p.get("count"))
    if qty is None and item:
        qty = 1
    who = party_of(ctx, other)
    here = place_of(ctx, holder)
    f = {"ledger": spec.get("ledger"), "kind": kind, "item": item, "item_id": it.id if it is not None else None,
         "qty": qty, "unit": spec.get("unit"), "party": who.name if who is not None else None, "party_id": who.id if who is not None else None,
         "place": here.name if here is not None else None, "text": spec.get("text") or ev.kind, "tags": [ev.kind],
         "author": dev.name, "source": {"event": ev.seq, "kind": ev.kind}}
    got = write_entry(ctx, dev, f)
    if isinstance(got, str):
        ctx.patch(dev, {"missed": int(dev.state.missed or 0) + 1})
