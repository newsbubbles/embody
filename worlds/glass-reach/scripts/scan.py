use("ledgers")
# The Reach's own verb for its slates (Nate 2026-11-12): hold a slate up to the room and it writes down, as counts in a
# ledger you choose, what a careful look would see: the loose things here, the bodies here, and (a Guild slate only)
# what each of them holds in the open. Nothing hidden, nothing inside a pack, a box or a vehicle, nobody hidden. The
# Keth cord has no scan: the Keth count by hand.

def stack(it):
    return int(it.state.count or 1)

def add(counts, order, name, n, holder):
    key = name + "|" + (holder or "")
    if key not in counts:
        counts[key] = [name, 0, holder]
        order.append(key)
    counts[key][1] = counts[key][1] + n

def check(ctx):
    dev = ctx.target
    me = ctx.actor
    if dev.parent is None or dev.parent.id != me.id:
        return "hold " + dev.name + " in your hands to scan with it"
    why = shut(ctx, dev, me)
    if why:
        return why
    if me.parent is None:
        return "there is nothing around you to count"
    return True

def apply(ctx):
    dev = ctx.target
    me = ctx.actor
    here = me.parent
    p = ctx.params or {}
    ledger = str(p.get("ledger") or "scans")
    hands = bool(dev.state.scan_hands)
    counts = {}
    order = []
    people = 0

    for c in ctx.children(here):
        cs = c.state
        if cs.hidden or c.is_a("place"):
            continue
        if c.is_a("creature"):
            if cs.dead:
                add(counts, order, "the dead", 1, None)
                continue
            people = people + 1
            if hands and c.id != me.id:
                for it in ctx.children(c):
                    if it.state.hidden or it.state.attached or it.is_a("creature"):
                        continue
                    add(counts, order, it.name, stack(it), c.name)
            continue
        if cs.attached:
            continue
        add(counts, order, c.name, stack(c), None)
    src = {"event": ctx.event.seq, "kind": "scan"}
    rows = [{"ledger": ledger, "kind": "count", "item": "people", "qty": people, "place": here.name,
             "text": "scan of " + here.name, "tags": ["scan"], "author": dev.name, "source": src}]
    for key in order:
        name, n, holder = counts[key]
        rows.append({"ledger": ledger, "kind": "count", "item": name, "qty": n, "party": holder, "place": here.name,
                     "text": "scan of " + here.name + (", in " + holder + "'s hands" if holder else ""),
                     "tags": ["scan"], "author": dev.name, "source": src})
    got = write_entries(ctx, dev, rows)
    if not got[0]:
        ctx.reject(got[1] or (dev.name + " wrote nothing"))
    line = dev.state.scan_line or "{who} holds {device} up to the room."
    ctx.emit("scene", target=here, reach=1, text=line.replace("{who}", me.name).replace("{device}", dev.name))
    return {"ledger": ledger, "written": len(got[0]), "people": people,
                "counted": [{"item": r["item"], "qty": r["qty"], "held_by": r.get("party")} for r in rows[1:]],
                "full": got[1]}
