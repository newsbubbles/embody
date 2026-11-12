# Shared by the ledger verbs, the recording listener and a world's own verbs (packs/ledgers/pack.py says what a
# device's state holds). Entries live on hidden pages of PAGE in the world's ledger archive; the device keeps their
# ids (`book`), so the device stays small and writing an entry patches one page.

PAGE = 20
KINDS = ["in", "out", "count", "note"]
DEEDS = {"given": {"doer": "out", "other": "in"}, "taken": {"doer": "in", "other": "out"},
         "put": {"doer": "out"}, "dropped": {"doer": "out"}}
SORTS = ["time", "amount", "party", "item", "number"]
GROUPS = ["item", "party", "ledger", "kind", "unit", "all"]

def num(v):
    # a number from a param (4, 2.5, "4", "-1.5"), else None
    if isinstance(v, bool):
        return None
    if isinstance(v, int) or isinstance(v, float):
        return v
    if not isinstance(v, str):
        return None
    s = v.strip()
    if s.startswith("-"):
        s = s[1:]
    if not s or s.count(".") > 1 or not s.replace(".", "").isdigit():
        return None
    x = float(v.strip())
    return int(x) if x == int(x) else x

def words(v):
    # a list of words from a list or from "a, b"
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return [str(x).strip().lower() for x in v if str(x).strip()]
    return [x.strip().lower() for x in str(v).split(",") if x.strip()]

def name_of(ctx, ref):
    e = ctx.get(ref) if isinstance(ref, str) and ref else None
    return e.name if e is not None else None

def party_of(ctx, ref):
    # who or where a deed was with: the body or the place at or above it (glass taken from a pile: the yard)
    e = ctx.get(ref) if isinstance(ref, str) and ref else None
    while e is not None and not e.is_a("creature") and not e.is_a("place"):
        e = e.parent
    return e

def place_of(ctx, x):
    # the place a thing is in, however deep (a slate in a pocket of a rider in a cart: the cart)
    p = x.parent
    while p is not None and not p.is_a("place"):
        p = p.parent
    return p

def day_len(ctx, dev):
    d = num(dev.state.day_seconds) or num(ctx.root().state.day_seconds)
    return float(d or 86400)

def when(ctx, dev, t):
    # day and hour, the hour scaled to the world's day
    D = day_len(ctx, dev)
    day = int(t // D) + 1
    s = t - (day - 1) * D
    return "day " + str(day) + ", " + pad(int(s * 24 // D)) + ":" + pad(int((s * 1440 // D) % 60))

def pad(n):
    return ("0" + str(n)) if n < 10 else str(n)

def quote(v):
    return "'" + str(v) + "'"

# -- the book

def entries(ctx, dev):
    out = []
    for pid in dev.state.book or []:
        pg = ctx.get(pid)
        if pg is not None:
            out.extend(pg.state.entries or [])
    return out

def archive(ctx, dev):
    # where the world's pages are kept: one hidden thing under the root, made the first time it is needed
    a = ctx.get(dev.state.archive) if dev.state.archive else None
    if a is None:
        got = ctx.find(type="ledger_archive", limit=1)
        a = got[0] if got else ctx.spawn("ledger_archive", ctx.root(), "Ledger archive")
    return a

def voids(dev):
    # entry number -> the void that cancels it (kept beside the book as `voided`, so nobody reads the book for it)
    vd = dev.state.voided or {}
    return {int(k): vd[k] for k in vd}

def write_entry(ctx, dev, fields):
    # append one entry; returns it numbered, or a reason it was not written (the device is full)
    got = write_entries(ctx, dev, [fields])
    return got[0][0] if got[0] else got[1]

def write_entries(ctx, dev, many):
    # append entries, one patch a page; returns [the entries written], and why the rest were not (full), or None
    n = int(dev.state.written or 0)
    cap = num(dev.state.cap)
    book = list(dev.state.book or [])
    pg = ctx.get(book[len(book) - 1]) if book else None
    last = list(pg.state.entries or []) if pg is not None else []
    known = dev.state.ledgers or {}
    ch = {}
    out = []
    why = None
    for fields in many:
        if cap is not None and n >= cap:
            why = dev.name + " is full (" + str(int(cap)) + " entries): copy out what you need, or carry another"
            break
        n = n + 1
        e = {"n": n, "t": ctx.t, "ledger": str(fields.get("ledger") or dev.state.default_ledger or "tally"),
             "kind": fields.get("kind") or "note"}
        for k in ["item", "item_id", "qty", "unit", "party", "party_id", "place", "text", "author", "source", "voids"]:
            if fields.get(k) is not None and fields.get(k) != "":
                e[k] = fields[k]
        e["tags"] = words(fields.get("tags"))
        if e.get("text") is not None and len(str(e["text"])) > 400:
            e["text"] = str(e["text"])[:400]
        if pg is None or len(last) >= PAGE:
            if pg is not None:
                ctx.patch(pg, {"entries": last})
            pg = ctx.spawn("ledger_page", archive(ctx, dev), "ledger page", {"device": dev.id})
            book.append(pg.id)
            ch["book"] = book
            ch["archive"] = pg.parent.id
            last = []
        last.append(e)
        if e.get("voids") is not None:
            ch["voided"] = dict(ch.get("voided") or {})
            ch["voided"][str(e["voids"])] = n
        if e["ledger"] not in known:
            known = dict(known)
            known[e["ledger"]] = {"opened": ctx.t}
            ch["ledgers"] = dict(ch.get("ledgers") or {})
            ch["ledgers"][e["ledger"]] = {"opened": ctx.t}
        out.append(e)
    if out:
        ctx.patch(pg, {"entries": last})
        ch["written"] = n
        ctx.patch(dev, ch)
    return [out, why]

def source_label(s):
    if not s or s.get("by") == "hand":
        return "by hand"
    if s.get("by") and s.get("device") is None:
        return "by " + str(s["by"])
    if s.get("event") is not None:
        return "recorded from event " + str(s["event"]) + " (" + str(s.get("kind")) + ")"
    if s.get("device"):
        via = (" by " + s["via"]) if s.get("via") else ""
        return "copied from " + str(s["device"]) + " entry " + str(s.get("entry")) + via
    return "by hand"

def origin(s):
    # the source a copy of a copy came from in the first place
    while s and s.get("origin"):
        s = s["origin"]
    return s or {"by": "hand"}

def source_kind(s):
    if s and s.get("device"):
        return "copied"
    if s and s.get("event") is not None:
        return "recorded"
    return "hand"

def show(ctx, dev, e, vd):
    # an entry as the holder reads it
    out = {"n": e["n"], "when": when(ctx, dev, e["t"]), "t": e["t"], "ledger": e["ledger"], "kind": e["kind"]}
    for k in ["item", "qty", "unit", "party", "place", "text", "author", "voids"]:
        if e.get(k) is not None:
            out[k] = e[k]
    if e.get("tags"):
        out["tags"] = e["tags"]
    out["source"] = source_label(e.get("source"))
    if vd.get(e["n"]) is not None:
        out["voided_by"] = vd[e["n"]]
    return out

# -- choosing entries

def pick(ctx, dev, p, rows, vd, voided):
    # the entries the filters in p choose. Each filter walks the book only when it is set: a script's fuel is
    # counted, and a slate can hold thousands
    led = str(p.get("ledger") or "all").strip().lower()
    if led != "all":
        rows = [e for e in rows if e["ledger"].lower() == led]
    only = [num(x) for x in (p.get("entries") if isinstance(p.get("entries"), list) else words(p.get("entries")))]
    if only:
        rows = [e for e in rows if e["n"] in only]
    kinds = words(p.get("kind"))
    if kinds:
        rows = [e for e in rows if e["kind"] in kinds]
    voided = str(p.get("voided") or voided).strip().lower()
    if voided == "exclude":
        rows = [e for e in rows if e["kind"] != "void" and e["n"] not in vd]
    elif voided == "only":
        rows = [e for e in rows if e["n"] in vd]
    for k in ["party", "item", "place"]:
        want = str(p.get(k) or "").strip().lower()
        if want:
            rows = [e for e in rows if want in str(e.get(k) or "").lower()]
    tags = words(p.get("tag") or p.get("tags"))
    if tags:
        rows = [e for e in rows if any([t in (e.get("tags") or []) for t in tags])]
    text = str(p.get("text") or "").strip().lower()
    if text:
        rows = [e for e in rows if text in " ".join([str(e.get("text") or ""), str(e.get("item") or ""),
                                                      str(e.get("party") or "")] + (e.get("tags") or [])).lower()]
    src = str(p.get("source") or "").strip().lower()
    if src:
        rows = [e for e in rows if source_kind(e.get("source")) == src]
    since = num(p.get("since"))
    until = num(p.get("until"))
    day = num(p.get("day"))
    if day is not None:
        D = day_len(ctx, dev)
        since = (day - 1) * D
        until = day * D - 0.001
    if since is not None:
        rows = [e for e in rows if e["t"] >= since]
    if until is not None:
        rows = [e for e in rows if e["t"] <= until]
    lo = num(p.get("min"))
    if lo is not None:
        rows = [e for e in rows if e.get("qty") is not None and e["qty"] >= lo]
    hi = num(p.get("max"))
    if hi is not None:
        rows = [e for e in rows if e.get("qty") is not None and e["qty"] <= hi]
    return rows

def bad_filter(p):
    # a reason a filter or sort param is unusable, so a typo is refused, not read as "everything"
    for k in ["since", "until", "day", "min", "max"]:
        if p.get(k) is not None and p.get(k) != "" and num(p.get(k)) is None:
            return k + " takes a number, not " + quote(p.get(k))
    for k in words(p.get("kind")):
        if k not in KINDS and k != "void":
            return "kind is one of in, out, count, note or void, not " + quote(k)
    s = str(p.get("source") or "").strip().lower()
    if s and s not in ["hand", "recorded", "copied"]:
        return "source is hand, recorded or copied, not " + quote(s)
    v = str(p.get("voided") or "").strip().lower()
    if v and v not in ["include", "exclude", "only"]:
        return "voided is include, exclude or only, not " + quote(v)
    s = str(p.get("sort") or "").strip().lower()
    if s and s not in SORTS:
        return "sort is one of " + ", ".join(SORTS) + ", not " + quote(s)
    o = str(p.get("order") or "").strip().lower()
    if o and o not in ["asc", "desc"]:
        return "order is asc or desc, not " + quote(o)
    return None

def ordered(rows, p):
    by = str(p.get("sort") or "time").strip().lower()
    desc = str(p.get("order") or "desc").strip().lower() != "asc"
    if by in ["time", "number"]:
        # the book is written in time order and numbered as it goes
        return list(reversed(rows)) if desc else list(rows)
    keyed = []
    for e in rows:
        if by == "amount":
            k = e["qty"] if e.get("qty") is not None else -1e18
        elif by == "party":
            k = str(e.get("party") or "").lower()
        elif by == "item":
            k = str(e.get("item") or "").lower()
        elif by == "number":
            k = e["n"]
        else:
            k = e["t"]
        keyed.append([k, e["n"]])
    keyed = sorted(keyed)
    if desc:
        keyed.reverse()
    at = {}
    for e in rows:
        at[e["n"]] = e
    return [at[k[1]] for k in keyed]

def paged(ctx, dev, rows, p, vd):
    size = num(p.get("size")) or num(dev.state.page_size) or 10
    size = int(max(1, min(50, size)))
    pages = max(1, (len(rows) + size - 1) // size)
    page = num(p.get("page")) or 1
    page = int(page)
    if page < 0:
        page = pages + 1 + page
    page = max(1, min(pages, page))
    chunk = ordered(rows, p)[(page - 1) * size:page * size]
    out = {"device": dev.name, "matched": len(rows), "page": page, "pages": pages, "size": size,
           "entries": [show(ctx, dev, e, vd) for e in chunk]}
    if page < pages:
        out["next"] = "page " + str(page + 1) + " of " + str(pages)
    return out

# -- sums

def stats(xs):
    if not xs:
        return {}
    n = len(xs)
    mean = sum(xs) / n
    seen = {}
    for x in xs:
        seen[x] = seen.get(x, 0) + 1
    top = max(seen.values())
    mode = min([x for x in seen if seen[x] == top])
    var = sum([(x - mean) * (x - mean) for x in xs]) / n
    return {"min": min(xs), "max": max(xs), "mean": round(mean, 3), "mode": mode, "stdev": round(var ** 0.5, 3)}

def totals(rows, by):
    # rows in book order (time), so the balance runs as it was written
    groups = {}
    for e in rows:
        k = e["kind"]
        if k == "void":
            continue
        g = "all" if by == "all" else e.get(by)
        if g is None or g == "":
            g = "(none)"
        r = groups.get(g)
        if r is None:
            r = {"group": g, "entries": 0, "in": 0, "out": 0, "balance": 0, "qtys": []}
            groups[g] = r
        r["entries"] += 1
        q = e.get("qty")
        if q is None:
            continue
        r["qtys"].append(q)
        if k == "in":
            r["in"] += q
            r["balance"] += q
        elif k == "out":
            r["out"] += q
            r["balance"] -= q
        elif k == "count":
            r["balance"] = q
    out = []
    for g in groups:
        r = groups[g]
        row = {"group": str(g), "entries": r["entries"], "in": r["in"], "out": r["out"], "net": r["in"] - r["out"],
               "balance": r["balance"]}
        row.update(stats(r["qtys"]))
        out.append(row)
    keyed = sorted([[-r["entries"], r["group"]] for r in out])
    at = {r["group"]: r for r in out}
    return [at[k[1]] for k in keyed]

# -- who may use it

def shut(ctx, dev, who):
    # why this body may not open the device (bound to another, or its lock shut), or None
    keeper = dev.state.keeper
    mine = (not keeper) or who.id == keeper or who.name == keeper
    lk = None
    for c in dev.children():
        if c.state.attached and c.state.locked is not None:
            lk = c
    if lk is not None and lk.state.locked:
        if keeper and mine:
            return None
        how = []
        if lk.state.pick_dc:
            how.append("pick")
        if lk.state.break_dc:
            how.append("break")
        return (dev.name + " is locked" + (" to its keeper" if keeper else "") +
                ((": " + " or ".join(how) + " " + lk.name + " to open it") if how else ""))
    if lk is not None:
        return None  # its lock is open (unlocked, picked or broken): anyone may
    if not mine:
        return dev.name + " is locked: it answers only to its keeper"
    return None

def line_for(ctx, dev, verb, who):
    ls = dev.state.lines or {}
    t = ls.get(verb) if verb in ls else ls.get("default", "{who} bends over {device}.")
    if t is False or t is None or t == "":
        return
    ctx.emit("scene", target=who, reach=1, text=str(t).replace("{who}", who.name).replace("{device}", dev.name))

# -- copies

def copy_fields(src, e, via, by):
    f = {}
    for k in ["kind", "item", "item_id", "qty", "unit", "party", "party_id", "place", "text", "author", "tags"]:
        if e.get(k) is not None:
            f[k] = e[k]
    f["voids"] = e.get("voids")
    f["ledger"] = e["ledger"]
    if e["kind"] == "void":
        # a correction means nothing on another device: it goes over as a note of what it cancelled
        f["kind"] = "note"
        f["text"] = "void of #" + str(e.get("voids")) + " on " + src.name + ": " + str(e.get("text") or "")
        f.pop("voids")
    f["source"] = {"device": src.name, "device_id": src.id, "entry": e["n"], "via": via, "by": by,
                   "origin": e.get("source") or {"by": "hand"}}
    return f

def device_line(ctx, line):
    # the device that answers to a line, or None
    want = str(line or "").strip().lower()
    if not want:
        return None
    for d in ctx.find(type="ledger", limit=500):
        if str(d.state.line or "").lower() == want:
            return d
    return None
