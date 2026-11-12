use("ledgers")
# Tally slates in the Reach (Nate 2026-11-12; build.py SLATE_KINDS for the three looks). On `slates_issue` (scheduled
# once at boot by keep_tally_slates, and again a minute after Rook's crawler comes in) each holder who has no slate yet
# gets one: bound to them with a seal, its contacts, and the first day's counts read off the live world right now (men,
# water, the wall, the house's skins and men, the Keth's grudges, the Guild's strongbox), never from memory. Each
# holder remembers what it is and what it does.
HOLDERS = [
    ["Ossa the Carrier", "tally_slate", "Ossa's tally-slate", "guild-ossa", ["guild-marr", "guild-rook", "hold-reeve", "hold-ruhl"], "guild"],
    ["Sergeant Edda Marr", "tally_slate", "Marr's tally-slate", "guild-marr", ["guild-ossa", "guild-rook"], "strongbox"],
    ["Bellan Rook", "tally_slate", "Rook's tally-slate", "guild-rook", ["guild-ossa", "guild-marr"], "convoy"],
    ["Reeve Ansel Varrick", "tally_slate", "The reeve's tally-slate", "hold-reeve", ["hold-ruhl", "guild-ossa"], "hold"],
    ["Captain Ruhl", "tally_slate", "Ruhl's tally-slate", "hold-ruhl", ["hold-reeve", "guild-ossa"], "men_water"],
    ["Mother Sallow", "house_slate", "Mother Sallow's slate", "house-sallow", ["house-halvard"], "house"],
    ["Halvard Dreyer", "house_slate", "Halvard's slate", "house-halvard", ["house-sallow"], "house_men"],
    ["Elder Taan", "count_cord", "Taan's count-cord", "cord-taan", ["cord-iska"], "keth"],
    ["Iska of the Keth", "count_cord", "Iska's count-cord", "cord-iska", ["cord-taan"], "keth_water"],
]
SEALS = {
    "tally_slate": ["The slate's seal", {"pick_dc": 15, "break_dc": 14,
                    "description": "A brass catch in the slate's rim that knows its keeper's hand. Anyone else has to "
                                   "pick it, or crack the rim."}],
    "house_slate": ["The slate's clasp", {"pick_dc": 12, "break_dc": 10,
                    "description": "An iron clasp over the slate's face. It does not open for strangers."}],
    "count_cord": ["The cord's keeper-knot", {"pick_dc": 13, "break_dc": 8,
                   "description": "A Keth knot that only its tier opens cleanly. Cut, it gives the cord to anyone."}],
}
KNOWS = {
    "tally_slate": "I carry a Guild tally-slate now ({device}). Only I read it. It writes down what I give, take and hire "
                   "on its own; I can record by hand, read and search it, total it (sums, averages, spreads), verify it "
                   "against what happened, copy it onto a leaf, and scan a room into it. It sends to the lines I know "
                   "({contacts}) through the Counting House, where the Guild sees who wrote to whom, never what.",
    "house_slate": "I carry a house slate now ({device}), the house's own make. Only I read it. It keeps what I give, take "
                   "and hire on its own; I can record, read, search and total it, and scan a room, slowly, by hand. It "
                   "passes to {contacts} only face to face: a runner carries it.",
    "count_cord": "I carry a count-cord now ({device}). Only my fingers read it. It keeps what I give, take and hire; I "
                  "can knot in more by hand, read it, search it, total it. It passes to {contacts} only face to face. "
                  "A cord does not count a room: we count by hand.",
}
WAIT_FOR_ROOK = 60

def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def by_name(ctx, name):
    for e in ctx.find(name=name, limit=20):
        if e.name == name:
            return e
    return None

def left_of(ctx, eid):
    e = ctx.get(eid) if eid else None
    if e is None:
        return None
    return int(e.state.left or 0)

def row(ledger, kind, item, qty, text):
    return {"ledger": ledger, "kind": kind, "item": item, "qty": qty, "text": text, "tags": ["first day"]}

def books(ctx, st):
    # what each kind of holder's book says today, off the live world
    men = []
    bought = []
    for pid in [st.hold, st.yard]:
        if not pid:
            continue
        for c in ctx.children(ctx.get(pid)):
            cs = c.state
            if cs.faction == "House Varrick" and not cs.dead and not cs.down:
                if cs.turncoat:
                    bought.append(c.name)
                else:
                    men.append(c.name)
    water = [row("water", "count", "Keth jars", left_of(ctx, st.keth_jars), "the jars in the Hold"),
             row("water", "count", "Hold's ration cask", left_of(ctx, st.hold_ration), "the Guild's ration cask")]
    if st.cistern_mended and st.cistern:
        water.append(row("water", "count", "the cistern", left_of(ctx, st.cistern), "mended, filling from the seep"))
    hold_men = [row("men", "count", "men on the wall", len(men) - len(bought), "fit men of the Hold, the bought taken off")]
    for n in bought:
        hold_men.append(row("men", "note", n, None, "bought by the house: watched, not counted on the wall"))
    wall = []
    if st.yard:
        for c in ctx.children(ctx.get(st.yard)):
            want = ((c.state.becomes or {}).get("state") or {}).get("wall_men")
            if c.type == "project" and want:
                wall.append(row("wall", "count", c.name, len(c.state.built_stages or []), "courses laid"))
            elif c.type == "rubble":
                wall.append(row("wall", "count", "stone in the rubble", int(c.state.stone or 0), c.name))
    skins = 0
    camp = st.dry_camp
    for e in ctx.find(name="House skin", limit=50):
        if e.name == "House skin" and e.parent is not None and e.parent.id == camp:
            skins = skins + 1
    house_men = []
    for e in ctx.find(type="person", limit=500):
        if e.state.drifter and e.state.turncoat and not e.state.dead:
            house_men.append(row("men", "note", e.name, None, "signed for the house; sits in the Hold"))
    grudges = []
    g = st.keth_grudges or {}
    for side in g:
        grudges.append(row("grudges", "count", side, int(g[side]), "glass dug on the Flats against the terms"))
    shards = 0
    box = by_name(ctx, "The Guild strongbox")
    if box is not None:
        for c in ctx.children(box):
            if c.state.kind == "ember":
                shards = shards + int(c.state.count or 1)
    jars = row("water", "count", "Keth jars", left_of(ctx, st.keth_jars), "poured at the Hold")
    strongbox = row("strongbox", "count", "Emberglass", shards, "the Reach leg's glass in the strongbox")
    convoy = row("convoy", "count", "draws aboard the convoy crawler", 8, "three shards, to the first side to pay in full")
    return {"guild": [strongbox, convoy], "strongbox": [strongbox], "convoy": [convoy], "hold": water + hold_men + wall,
            "men_water": hold_men + water, "house": [row("skins", "count", "House skin", skins, "full skins at the camp")] + house_men,
            "house_men": house_men, "keth": [jars] + grudges, "keth_water": [jars]}

def issue(ctx, st, spec, have):
    who = by_name(ctx, spec[0])
    if who is None or who.state.dead or by_name(ctx, spec[2]) is not None:
        return False
    dev = ctx.spawn(spec[1], who, name=spec[2], state={"keeper": spec[0], "line": spec[3], "contacts": list(spec[4])})
    seal = SEALS[spec[1]]
    ctx.spawn("lock", dev, name=seal[0], state=dict(seal[1]))
    rows = []
    for r in have.get(spec[5]) or []:
        if r["qty"] is not None or r["kind"] == "note":
            f = dict(r)
            f["author"] = spec[2]
            rows.append(f)
    if rows:
        write_entries(ctx, dev, rows)
    ctx.remember(who, KNOWS[spec[1]].replace("{device}", spec[2]).replace("{contacts}", ", ".join(spec[4])))
    return True

def on(ctx, event):
    k = event.kind
    if k == "rook_arrives":
        ctx.schedule(WAIT_FOR_ROOK, "slates_issue", ctx.root(), {})
        return
    if k != "slates_issue":
        return
    st = story_of(ctx).state
    have = books(ctx, st)
    n = 0
    for spec in HOLDERS:
        if issue(ctx, st, spec, have):
            n = n + 1
    if n:
        ctx.emit("slates_issued", target=ctx.root(), reach=-1, count=n, quiet=True)
