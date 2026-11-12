use("ledgers")
# Every verb of a ledger device (packs/ledgers/pack.py lists them). It is used in your hands; a fixed one is read from
# alongside, never written. Only the holder gets the entries back; the room hears the world's one line.

WRITES = ["record", "void", "copy", "transfer", "send"]

def check(ctx):
    dev = ctx.target
    who = ctx.actor
    held = dev.parent is not None and dev.parent.id == who.id
    if not held:
        fixed = (not dev.state.portable and dev.parent is not None and who.parent is not None
                 and dev.parent.id == who.parent.id)
        if not fixed:
            return "take " + dev.name + " in your hands first: only its holder reads it"
        if ctx.verb in WRITES:
            return dev.name + " is fixed here: it is read, not written by hand"
    why = shut(ctx, dev, who)
    if why:
        return why
    p = ctx.params or {}
    bad = bad_filter(p)
    if bad:
        return bad
    if ctx.verb == "record":
        k = str(p.get("kind") or "note").strip().lower()
        if k not in KINDS:
            return "kind is one of in, out, count or note, not " + quote(k)
        if p.get("qty") not in [None, ""] and (num(p.get("qty")) is None or num(p.get("qty")) < 0):
            return "qty is a number of 0 or more, not " + quote(p.get("qty"))
    if ctx.verb == "total" and p.get("by") and str(p.get("by")).strip().lower() not in GROUPS:
        return "by is one of " + ", ".join(GROUPS) + ", not " + quote(p.get("by"))
    return True

def apply(ctx):
    dev = ctx.target
    p = ctx.params or {}
    v = ctx.verb
    if v == "ledgers":
        out = do_ledgers(ctx, dev, p)
    elif v == "record":
        out = do_record(ctx, dev, p)
    elif v == "void":
        out = do_void(ctx, dev, p)
    elif v == "total":
        out = do_total(ctx, dev, p)
    elif v == "verify":
        out = do_verify(ctx, dev, p)
    elif v == "copy":
        out = do_copy(ctx, dev, p)
    elif v == "transfer":
        out = do_transfer(ctx, dev, p)
    elif v == "send":
        out = do_send(ctx, dev, p)
    elif v == "contacts":
        out = do_contacts(ctx, dev, p)
    else:
        rows = entries(ctx, dev)
        vd = voids(dev)
        out = paged(ctx, dev, pick(ctx, dev, p, rows, vd, "include"), p, vd)
        out["ledgers"] = sorted(list((dev.state.ledgers or {}).keys()))
    line_for(ctx, dev, v, ctx.actor)
    return out

def known_ledger(ctx, dev, name):
    # the ledger by name (any case), or a refusal that names the ones there are
    names = list((dev.state.ledgers or {}).keys())
    for n in names:
        if n.lower() == str(name).strip().lower():
            return n
    ctx.reject("no ledger " + quote(name) + " on " + dev.name,
               hint="its ledgers: " + (", ".join(names) or "none yet") + "; open one with ledgers params {\"open\": name}")

def do_ledgers(ctx, dev, p):
    name = str(p.get("open") or "").strip()
    if name:
        if name.lower() == "all":
            ctx.reject("all is how a filter means every ledger: pick another name")
        for n in (dev.state.ledgers or {}):
            if n.lower() == name.lower():
                ctx.reject(dev.name + " already has a ledger " + quote(n))
        ctx.patch(dev, {"ledgers": {name: {"opened": ctx.t}}})
    rows = entries(ctx, dev)
    vd = voids(dev)
    out = []
    for n in sorted(list((dev.state.ledgers or {}).keys())):
        mine = [e for e in rows if e["ledger"] == n]
        live = [e for e in mine if e["kind"] != "void" and vd.get(e["n"]) is None]
        row = {"ledger": n, "entries": len(mine), "standing": len(live)}
        if mine:
            row["last"] = when(ctx, dev, mine[len(mine) - 1]["t"])
        out.append(row)
    r = {"device": dev.name, "default": dev.state.default_ledger or "tally", "ledgers": out, "written": len(rows)}
    if dev.state.cap is not None:
        r["cap"] = dev.state.cap
    if dev.state.missed:
        r["missed"] = dev.state.missed
    if name:
        r["opened"] = name
    return r

def text_or_none(v):
    s = str(v).strip() if v is not None else ""
    return s if s else None

def do_record(ctx, dev, p):
    kind = str(p.get("kind") or "note").strip().lower()
    qty = num(p.get("qty")) if p.get("qty") not in [None, ""] else None
    if kind in ["in", "out", "count"] and qty is None:
        ctx.reject("an " + kind + " entry needs qty, how many", hint="or record it as a note")
    led = known_ledger(ctx, dev, p.get("ledger")) if p.get("ledger") else str(dev.state.default_ledger or "tally")
    here = place_of(ctx, ctx.actor)
    got = write_entry(ctx, dev, {"ledger": led, "kind": kind, "item": text_or_none(p.get("item")), "qty": qty,
                                 "unit": text_or_none(p.get("unit")), "party": text_or_none(p.get("party")),
                                 "place": text_or_none(p.get("place")) or (here.name if here is not None else None),
                                 "text": text_or_none(p.get("text")), "tags": p.get("tags"), "author": ctx.actor.name,
                                 "source": {"by": "hand"}})
    if isinstance(got, str):
        ctx.reject(got)
    return {"device": dev.name, "written": show(ctx, dev, got, {})}

def do_void(ctx, dev, p):
    n = num(p.get("n"))
    reason = text_or_none(p.get("reason"))
    if n is None:
        ctx.reject("void needs n, the number of the entry to cancel", hint="read or search shows the numbers")
    if not reason:
        ctx.reject("void needs a reason: it is written beside the correction")
    rows = entries(ctx, dev)
    vd = voids(dev)
    e = None
    for x in rows:
        if x["n"] == n:
            e = x
    if e is None:
        ctx.reject("no entry " + str(n) + " on " + dev.name, hint="its entries run 1 to " + str(len(rows)))
    if e["kind"] == "void":
        ctx.reject("entry " + str(n) + " is itself a correction", hint="record a new entry to set it right")
    if vd.get(n) is not None:
        ctx.reject("entry " + str(n) + " is already voided, by entry " + str(vd[n]))
    got = write_entry(ctx, dev, {"ledger": e["ledger"], "kind": "void", "voids": n, "item": e.get("item"),
                                 "qty": e.get("qty"), "unit": e.get("unit"), "party": e.get("party"), "text": reason,
                                 "author": ctx.actor.name, "source": {"by": "hand"}})
    if isinstance(got, str):
        ctx.reject(got)
    return {"device": dev.name, "written": show(ctx, dev, got, {}), "voided": n}

def do_total(ctx, dev, p):
    by = str(p.get("by") or "item").strip().lower()
    rows = entries(ctx, dev)
    vd = voids(dev)
    got = pick(ctx, dev, p, rows, vd, "exclude")
    groups = totals(got, by)
    out = {"device": dev.name, "matched": len(got), "by": by, "groups": groups[:30]}
    if len(groups) > 30:
        out["groups_more"] = len(groups) - 30
    out["how"] = ("in and out are sums of qty; net is in less out; balance runs in time order, a count sets it; "
                  "min, max, mean, mode and stdev are over the qty of every entry in the group")
    return out

def deed_why(ctx, e, s):
    # why an entry does not match the deed it was recorded from, or None
    ev = ctx.event_at(s.get("event"))
    if ev is None:
        return "no event " + str(s.get("event")) + " in the log"
    if ev.kind != s.get("kind"):
        return "event " + str(ev.seq) + " is " + ev.kind + ", not " + str(s.get("kind"))
    p = ev.payload
    q = num(p.get("count"))
    if q is None and p.get("item"):
        q = 1
    if e.get("item") and q is not None and num(e.get("qty")) != q:
        return "the log says " + str(q) + ", the entry " + str(e.get("qty"))
    if e.get("item_id") and p.get("item") and e["item_id"] != p["item"]:
        return "the log names another thing than " + str(e.get("item"))
    sides = []
    for x in [ev.actor, ev.target, p.get("by"), p.get("who"), p.get("to"), p.get("source")]:
        w = party_of(ctx, x)
        if w is not None:
            sides.append(w.id)
    if e.get("party_id") and e["party_id"] not in sides:
        return "the log names another party than " + str(e.get("party"))
    return None

def do_verify(ctx, dev, p):
    rows = entries(ctx, dev)
    vd = voids(dev)
    got = pick(ctx, dev, p, rows, vd, "include")
    confirmed = 0
    hand = 0
    flagged = []
    each = []
    for e in got:
        if e["kind"] == "void":
            continue
        s = origin(e.get("source"))
        copy = source_kind(e.get("source")) == "copied"
        if s.get("event") is None:
            hand = hand + 1
            st = "unverifiable, " + ("a copy of an entry made " if copy else "") + "by hand"
        else:
            why = deed_why(ctx, e, s)
            if why:
                flagged.append({"n": e["n"], "why": why})
                st = "flagged: " + why
            else:
                confirmed = confirmed + 1
                st = "confirmed" + (" (a copy, by its first record)" if copy else "")
        if len(each) < 50:
            each.append({"n": e["n"], "status": st})
    out = {"device": dev.name, "checked": confirmed + hand + len(flagged), "confirmed": confirmed,
           "unverifiable": hand, "flagged": flagged[:20], "entries": each}
    if len(flagged) > 20:
        out["flagged_more"] = len(flagged) - 20
    return out

def in_hands(ctx, ref):
    want = str(ref or "").strip().lower()
    if not want:
        return None
    for c in ctx.actor.children():
        if c.id == want or c.id == str(ref) or c.name.lower() == want:
            return c
    for c in ctx.actor.children():
        if len(want) >= 4 and want in c.name.lower():
            return c
    return None

def line_of(ctx, dev, e, vd):
    t = "#" + str(e["n"]) + " " + when(ctx, dev, e["t"]) + " [" + e["ledger"] + "] " + e["kind"]
    if e.get("voids") is not None:
        t = t + " of #" + str(e["voids"])
    if e.get("qty") is not None:
        t = t + " " + str(e["qty"])
    if e.get("unit"):
        t = t + " " + str(e["unit"])
    if e.get("item"):
        t = t + " " + str(e["item"])
    if e.get("party"):
        t = t + ", " + str(e["party"])
    if e.get("place"):
        t = t + ", at " + str(e["place"])
    if e.get("text"):
        t = t + ": " + str(e["text"])
    if vd.get(e["n"]) is not None:
        t = t + " (voided by #" + str(vd[e["n"]]) + ")"
    return t

def chosen(ctx, dev, p, most, voided):
    # the entries a copy, a transfer or a sending takes, oldest first, and how many were left over
    rows = entries(ctx, dev)
    vd = voids(dev)
    got = ordered(pick(ctx, dev, p, rows, vd, voided), {"sort": "time", "order": "asc"})
    if not got:
        ctx.reject("no entry on " + dev.name + " matches", hint="search with the same filters to see what does")
    return got[:most], max(0, len(got) - most), vd

def do_copy(ctx, dev, p):
    paper = in_hands(ctx, p.get("onto"))
    if paper is None or paper.id == dev.id:
        ctx.reject("copy needs onto: a paper in your hands to write on",
                   hint="in your hands: " + ", ".join([c.name for c in ctx.actor.children()]))
    if paper.state.text is None and not paper.state.paper:
        ctx.reject(paper.name + " takes no writing", hint="copy onto a paper, a leaf, a letter")
    got, left, vd = chosen(ctx, dev, p, 30, "include")
    head = "From " + dev.name + ", copied by " + ctx.actor.name + ", " + when(ctx, dev, ctx.t) + ":"
    lines = [line_of(ctx, dev, e, vd) for e in got]
    old = str(paper.state.text or "")
    ctx.patch(paper, {"text": (old + "\n" if old else "") + head + "\n" + "\n".join(lines)})
    out = {"device": dev.name, "onto": paper.name, "copied": len(got)}
    if left:
        out["left"] = left
        out["hint"] = "thirty lines a time: narrow the filters, or copy again onto more paper"
    return out

def reachable_device(ctx, dev, ref):
    # another device in reach: in your hands, lying here, or in the hands of someone here
    want = str(ref or "").strip().lower()
    if not want:
        ctx.reject("transfer needs to: the other device", hint="its name or id")
    who = ctx.actor
    pools = [who.children()]
    here = who.parent
    if here is not None:
        pools.append(here.children())
        for c in here.children():
            if c.id != who.id and c.is_a("creature"):
                pools.append(c.children())
    found = []
    for pool in pools:
        for d in pool:
            if d.is_a("ledger") and d.id != dev.id and not d.state.hidden and d.id not in [x.id for x in found]:
                if d.id == str(ref) or d.name.lower() == want or str(d.state.line or "").lower() == want:
                    found.append(d)
    if not found:
        ctx.reject("no other device " + quote(ref) + " in reach", hint="in your hands, lying here, or held by someone here")
    if len(found) > 1:
        ctx.reject("more than one " + quote(ref) + " in reach", hint="name it by id: " + ", ".join([d.id for d in found]))
    return found[0]

def deliver(ctx, dev, far, got, into, via):
    # write copies onto the far device in one go; how many went, and why the rest did not
    led = text_or_none(into)
    many = []
    for e in got:
        f = copy_fields(dev, e, via, ctx.actor.name)
        if led:
            f["ledger"] = led
        many.append(f)
    w = write_entries(ctx, far, many)
    n = len(w[0])
    if n:
        ctx.emit("ledger_received", target=far, reach=1, payload={"from": dev.name, "count": n, "by": ctx.actor.id})
    return n, w[1]

def do_transfer(ctx, dev, p):
    far = reachable_device(ctx, dev, p.get("to"))
    got, left, vd = chosen(ctx, dev, p, 200, "exclude")
    n, why = deliver(ctx, dev, far, got, p.get("into"), "hand")
    out = {"device": dev.name, "to": far.name, "copied": n}
    if why:
        out["stopped"] = why
    if left:
        out["left"] = left
    return out

def relay_of(ctx, dev):
    ref = dev.state.relay
    if not ref:
        return None
    r = ctx.get(ref)
    if r is not None:
        return r
    for c in ctx.find(type="ledger_relay", limit=50):
        if c.name == str(ref):
            return c
    return None

def do_send(ctx, dev, p):
    line = text_or_none(p.get("to"))
    known = [str(c) for c in (dev.state.contacts or [])]
    if not line:
        ctx.reject("send needs to: a line it knows", hint="its contacts: " + (", ".join(known) or "none; learn one with contacts add"))
    hit = None
    for c in known:
        if c.lower() == line.lower():
            hit = c
    if hit is None:
        ctx.reject(line + " is not among " + dev.name + "'s contacts", hint="learn it with contacts params {\"add\": line}")
    far = device_line(ctx, hit)
    if far is None or far.id == dev.id:
        ctx.reject("no device answers to " + hit + " now")
    mode = str(dev.state.delivery or "face")
    relay = None
    if mode == "none":
        ctx.reject(dev.name + " cannot send", hint="carry it to them and transfer face to face")
    elif mode == "face":
        a = place_of(ctx, dev)
        b = place_of(ctx, far)
        if a is None or b is None or a.id != b.id:
            ctx.reject(dev.name + " sends face to face only: " + hit + " is not here",
                       hint="go where its holder is, then send or transfer")
    elif mode == "relay":
        relay = relay_of(ctx, dev)
        if relay is None or relay.state.down or relay.state.broken:
            ctx.reject("the relay is down: nothing goes through", hint="send again when it is up, or carry it")
        if str(far.state.delivery or "face") != "relay":
            ctx.reject(hit + " is not on the relay", hint="it takes entries face to face")
    else:
        ctx.reject(dev.name + " has a delivery nobody knows: " + mode)
    got, left, vd = chosen(ctx, dev, p, 200, "exclude")
    n, why = deliver(ctx, dev, far, got, p.get("into"), mode)
    if relay is not None and n:
        write_entry(ctx, relay, {"ledger": "relay", "kind": "note", "qty": n, "unit": "entries",
                                 "party": str(dev.state.line or dev.name) + " > " + hit, "text": "relayed",
                                 "author": relay.name, "source": {"by": "relay"}})
    out = {"device": dev.name, "to": hit, "sent": n, "via": mode}
    if why:
        out["stopped"] = why
    if left:
        out["left"] = left
    return out

def do_contacts(ctx, dev, p):
    cs = [str(c) for c in (dev.state.contacts or [])]
    add = text_or_none(p.get("add"))
    drop = text_or_none(p.get("drop"))
    if add:
        far = device_line(ctx, add)
        if far is None or far.id == dev.id:
            ctx.reject("no device answers to the line " + quote(add), hint="a line is a device's own name for sending; ask its holder")
        if far.state.line not in cs:
            cs.append(far.state.line)
    if drop:
        keep = [c for c in cs if c.lower() != drop.lower()]
        if len(keep) == len(cs):
            ctx.reject(drop + " is not among its contacts", hint="its contacts: " + (", ".join(cs) or "none"))
        cs = keep
    if add or drop:
        ctx.patch(dev, {"contacts": cs})
    r = relay_of(ctx, dev)
    out = {"device": dev.name, "line": dev.state.line, "delivery": dev.state.delivery or "face", "contacts": cs}
    if r is not None:
        out["relay"] = r.name + (" (down)" if r.state.down or r.state.broken else "")
    return out
