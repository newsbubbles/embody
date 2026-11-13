use("beasts")
# The beasts' day and what they do when something happens near them. Any event kind the world names at install
# (dawn) is a day: forage regrows, beasts age and grow, go hungry or eat, keep or lose their loyalty, give birth,
# conceive and give what they give. `arrived`: a kept guard growls at a stranger. `hit`, `missed`: a kept guard
# takes up its owner's fight, and an owner's blow costs loyalty.

def on(ctx, event):
    k = event.kind
    if k == "arrived":
        growl(ctx, event)
    elif k == "hit" or k == "missed":
        blows(ctx, event)
    else:
        day(ctx)

def growl(ctx, event):
    who = ctx.get(event.payload.get("who"))
    place = ctx.get(event.payload.get("place"))
    if who is None or place is None or who.state.beast or not who.is_a("creature"):
        return
    for b in ctx.children(place, "beast"):
        if not able(b) or b.state.down or b.state.asleep or b.state.owner is None or b.state.owner == who.id:
            continue
        sp = species_of(ctx, b)
        if not sv(b, sp, "guards", False):
            continue
        owner = ctx.get(b.state.owner)
        if owner is not None and owner.state.faction is not None and owner.state.faction == who.state.faction:
            continue
        ctx.emit("growled", target=place, reach=1, by=b.id, at=who.id)
        return

def blows(ctx, event):
    t = ctx.get(event.target) if event.target else None
    by = ctx.get(event.payload.get("by")) if event.payload.get("by") else None
    if t is None or by is None or t.parent is None:
        return
    if t.state.beast and t.state.owner == by.id:
        ctx.patch(t, {"loyalty": max(0, int(t.state.loyalty or 0) - 1)})
        ctx.emit("beast_loyalty", target=t, reach=0, loyalty=max(0, int(t.state.loyalty or 0) - 1), why="struck")
        return
    for b in ctx.children(t.parent, "beast"):
        if b.state.owner != t.id or b.id == by.id or not able(b) or b.state.down:
            continue
        if sv(b, species_of(ctx, b), "guards", False) and b.state.attacked_by != by.id:
            ctx.patch(b, {"attacked_by": by.id, "asleep": False})  # its fighter tick takes up the fight

def day(ctx):
    ended = today(ctx)
    d = ended + 1
    ctx.patch(ctx.root(), {"beast_day": d})
    for p in ctx.find(type="place", limit=100000):
        f = p.state.forage
        if not f:
            continue
        new = {}
        for k, v in f.items():
            row = dict(v)
            mx = int(row.get("max") or 0)
            row["left"] = min(mx, int(row.get("left") or 0) + int(row.get("regrow") or 0)) if mx else int(row.get("left") or 0) + int(row.get("regrow") or 0)
            new[k] = row
        ctx.patch(p, {"forage": new})
    beasts = [b for b in ctx.find(type="beast", limit=100000) if able(b)]
    specs = {}
    for b in beasts:
        if b.state.species not in specs:
            specs[b.state.species] = species_of(ctx, b)
    for b in beasts:
        age(ctx, b, specs[b.state.species])
    beasts = [b for b in beasts if not b.state.dead]
    full = {}
    for b in beasts:
        full[b.id] = int(b.state.fed or 0) >= int(sv(b, specs[b.state.species], "fed_max", 3))
    hunger(ctx, beasts, specs)
    beasts = [b for b in beasts if not b.state.dead]
    for b in beasts:
        if kept(b):
            loyalty(ctx, b, ended, d, full[b.id])
    births(ctx, beasts, specs, d)
    conceive(ctx, [b for b in beasts if not b.state.dead and b.parent is not None], specs, ended, d)
    for b in beasts:
        yields(ctx, b, specs[b.state.species])

def age(ctx, b, sp):
    a = int(b.state.age or 0) + 1
    ctx.patch(b, {"age": a})
    st = stage_for(sp, a)
    if st is not None and st.get("name") != b.state.stage:
        grow_into(ctx, b, sp, st)
    life = sv(b, sp, "lifespan", None)
    if life is not None and a > int(life) and ctx.rand.chance(float(sv(b, sp, "old_death", 0.2))):
        die(ctx, b, "age")

def hunger(ctx, beasts, specs):
    # every beast is a meal shorter; then they eat what the place gives, a meal each first so the land is shared,
    # then the rest of what they are short
    need = {}
    for b in beasts:
        sp = specs[b.state.species]
        fed = max(0, int(b.state.fed if b.state.fed is not None else sv(b, sp, "fed_max", 3)) - 1)
        need[b.id] = [fed, int(sv(b, sp, "fed_max", 3))]
    # the grown first, then the young, the old last: when the land is short it is the old who go
    order = [b for b in beasts if not old(b, specs) and b.state.stage not in ["young"]]
    order = order + [b for b in beasts if b.state.stage == "young" and not old(b, specs)] + [b for b in beasts if old(b, specs)]
    for rnd in [1, 2]:
        for b in order:
            if b.state.down:
                continue
            fed, mx = need[b.id]
            want = min(1, mx - fed) if rnd == 1 else mx - fed
            if want > 0:
                need[b.id][0] = fed + eat_forage(ctx, b.parent, diet(b, specs[b.state.species]), want)
    for b in beasts:
        sp = specs[b.state.species]
        fed = need[b.id][0]
        if fed > 0:
            ctx.patch(b, {"fed": fed, "hungry": False, "hungry_days": 0})
            continue
        hd = int(b.state.hungry_days or 0) + 1
        ctx.patch(b, {"fed": 0, "hungry": True, "hungry_days": hd})
        ctx.emit("beast_hungry", target=b, reach=1, days=hd, species=b.state.species)
        if not kept(b):
            if hd >= int(sv(b, sp, "starve_days", 2)):
                die(ctx, b, "hunger")
            elif not b.state.down:
                wander(ctx, b, diet(b, sp))

def old(b, specs):
    return b.state.stage in tags(sv(b, specs[b.state.species], "old_stages", ["old"]))

def wander(ctx, b, eats):
    # a hungry wild beast goes one way over, to where there is the most it eats
    best = None
    best_n = 0
    for e in ctx.edges(b.parent, "connects_to", "out"):
        p = ctx.get(e["target"])
        if p is None or not open_way(ctx, b, b.parent, p):
            continue
        n = forage_left(p, eats)
        if n > best_n:
            best = p
            best_n = n
    if best is not None:
        walk_to(ctx, b, best, "hunger")

def loyalty(ctx, b, ended, d, was_full):
    l = int(b.state.loyalty if b.state.loyalty is not None else 3)
    fed_by = b.state.fed_by or {}
    why = None
    if b.state.owner is not None:
        owner = ctx.get(b.state.owner)
        if owner is None or owner.state.dead:
            feral(ctx, b, "owner gone")
            return
        if fed_by.get(owner.id) == ended:
            l = l + 1
        elif not was_full:  # a day it could have eaten and its owner gave it nothing: neglect
            l = l - 1
            why = "not fed"
        if owner.parent is not None and b.parent is not None and owner.parent.id == b.parent.id:
            ctx.patch(b, {"with_owner": d})
        elif d - int(b.state.with_owner if b.state.with_owner is not None else d) >= 2:
            l = l - 1
            why = "left alone"
    elif any([v == ended for v in fed_by.values()]):
        l = l + 1
    if b.state.hungry:
        l = l - 1
        why = "hungry"
    l = max(0, min(5, l))
    ctx.patch(b, {"loyalty": l})
    if l <= 0:
        feral(ctx, b, why or "neglect")

def births(ctx, beasts, specs, d):
    for m in beasts:
        c = m.state.carrying
        if not c or m.state.dead or int(c.get("due") or 0) > d:
            continue
        sp = specs[m.state.species]
        ctx.patch(m, {"carrying": None})
        lit = tags(sv(m, sp, "litter", [1, 1]))
        n = ctx.rand.randint(int(lit[0]), int(lit[-1]))
        st0 = stage_for(sp, 0)
        base = sv(m, sp, "young_name", None) or (str(m.state.species).capitalize() + " young")
        young = []
        for i in range(n):
            sex = ctx.rand.choice(["m", "f"])
            state = {"species": m.state.species, "sex": sex, "age": 0, "fed": 2, "beast": True,
                     "owner": m.state.owner, "herd": m.state.herd, "follows": m.state.owner,
                     "loyalty": m.state.loyalty if kept(m) else None, "with_owner": d if m.state.owner else None,
                     "home": m.state.home, "pack": m.state.pack, "stage_names": True, "mother": m.id}
            if st0 is not None:
                state.update(stage_state(st0, sex, False, m))
            y = ctx.spawn(m.type, m.parent, name=unique_name(ctx, base), state=state)
            if st0 is not None:
                give_parts(ctx, y, st0)
            young.append(y.id)
        ctx.emit("beast_born", target=m, reach=1, mother=m.id, young=young, species=m.state.species)

def conceive(ctx, beasts, specs, ended, d):
    for f in beasts:
        sp = specs[f.state.species]
        if f.state.sex != "f" or f.state.carrying or f.state.down or int(f.state.fed or 0) < 2:
            continue
        if f.state.stage not in tags(sv(f, sp, "breeds", ["adult"])):
            continue
        if sv(f, sp, "season", False) and not (sp is not None and sp.state.in_season):
            continue
        mate = None
        for m in beasts:
            if (m.state.sex == "m" and m.state.species == f.state.species and m.parent.id == f.parent.id
                    and not m.state.down and int(m.state.fed or 0) >= 2 and m.state.stage in tags(sv(m, sp, "breeds", ["adult"]))):
                mate = m
                break
        if mate is None:
            continue
        # the land must carry one more: fewer of them here than it regrows a day, unless a keeper fed her by hand. The
        # old do not count: they eat last and go first, so a herd at its limit still makes young to follow them
        here = len([b for b in beasts if b.parent.id == f.parent.id and b.state.species == f.state.species and not old(b, specs)])
        hand = any([v == ended for v in (f.state.fed_by or {}).values()])
        if here >= forage_regrow(f.parent, diet(f, sp)) and not hand:
            continue
        if ctx.rand.chance(float(sv(f, sp, "breed_chance", 0.25))):
            ctx.patch(f, {"carrying": {"due": d + int(sv(f, sp, "gestation", 6)), "sire": mate.id}})
            ctx.emit("beast_carrying", target=f, reach=1, species=f.state.species)

def yields(ctx, b, sp):
    y = sv(b, sp, "yields", None)
    if not y or b.state.dead or not kept(b) or int(b.state.fed or 0) < 2:
        return
    if b.state.stage not in tags(y.get("stages") or ["adult"]):
        return
    if y.get("sex") and y.get("sex") != b.state.sex:
        return
    have = [c for c in ctx.children(b.parent, "thing") if c.state.yield_of == b.id]
    if len(have) >= int(y.get("max") or 2):
        return
    state = dict(y.get("state") or {})
    state["yield_of"] = b.id
    it = ctx.spawn(y.get("type") or "thing", b.parent, name=y.get("name") or "Yield", state=state)
    ctx.emit("beast_yielded", target=b, reach=1, item=it.id)
