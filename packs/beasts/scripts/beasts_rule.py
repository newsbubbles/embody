use("beasts")
# The beasts' day and what they do when something happens near them. Any event kind the world names at install
# (dawn) is a day: forage regrows, beasts age and grow, go hungry or eat, keep or lose their loyalty, give birth,
# conceive and give what they give. The kinds named as the night (root `beast_night`) are when predators hunt; with
# none they hunt at the start of the day. `arrived`: a kept guard growls at a stranger. `hit`, `missed`: a kept guard
# takes up its owner's fight, and an owner's blow costs loyalty. `killed`: a beast killed leaves a carcass.

def on(ctx, event):
    k = event.kind
    if k == "arrived":
        growl(ctx, event)
    elif k == "hit" or k == "missed":
        blows(ctx, event)
    elif k == "killed":
        t = ctx.get(event.target) if event.target else None
        if t is not None and t.state.beast:
            carcass(ctx, t)
    elif k in (ctx.root().state.beast_night or []):
        hunts(ctx)
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
    rot(ctx, d)
    if not ctx.root().state.beast_night:
        hunts(ctx)
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
    wanders_in(ctx)

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
                eats = diet(b, specs[b.state.species])
                got = eat_forage(ctx, b.parent, eats, want)
                if got < want:
                    got = got + eat_carcass(ctx, b.parent, eats, want - got)
                need[b.id][0] = fed + got
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
                    and not m.state.down and int(m.state.fed or 0) >= 2 and m.state.stage in tags(sv(m, sp, "sires", ["adult", "old"]))):
                mate = m
                break
        if mate is None:
            continue
        # the land must carry one more: fewer of them here than it regrows a day, unless a keeper fed her by hand. The
        # old do not count: they eat last and go first, so a herd at its limit still makes young to follow them
        here = len([b for b in beasts if b.parent.id == f.parent.id and b.state.species == f.state.species and not old(b, specs)])
        hand = any([v == ended for v in (f.state.fed_by or {}).values()])
        # a hunter's room is its prey, not the ground: well fed is enough (`room`: "fed"; grazers "forage")
        room = sv(f, sp, "room", "prey" if sv(f, sp, "preys_on", None) else "forage")
        if room == "forage" and here >= forage_regrow(f.parent, diet(f, sp)) and not hand:
            continue
        if room == "prey" and not hand:
            # a hunter's room is its prey: at least `prey_per` (3) of them within reach for each hunter there, one more
            kinds = tags(sv(f, sp, "preys_on", []))
            prey = 0
            for p in in_range(ctx, f, 1):
                prey = prey + len([c for c in ctx.children(p, "beast") if not c.state.dead and c.state.species in kinds])
            if prey < int(sv(f, sp, "prey_per", 3)) * (here + 1):
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

def rot(ctx, d):
    # meat a day, carrion two more, then bones
    for c in ctx.find(type="beast", limit=100000):
        cd = c.state.carcass_day
        if cd is None or not c.state.dead or c.state.food is None:
            continue
        if d - int(cd) >= 3:
            ctx.patch(c, {"food": None, "meals": 0, "description": "Bones, picked clean."})
        elif d - int(cd) >= 1 and "meat" in tags(c.state.food):
            ctx.patch(c, {"food": ["carrion"]})

def predator(b, sp):
    return bool(sv(b, sp, "preys_on", None)) and not kept(b)

def hunts(ctx):
    # each hungry pack of wild predators (one species in one place) hunts once: the weakest prey within its range
    beasts = [b for b in ctx.find(type="beast", limit=100000) if able(b) and not b.state.down]
    specs = {}
    for b in beasts:
        if b.state.species not in specs:
            specs[b.state.species] = species_of(ctx, b)
    packs = {}
    for b in beasts:
        if predator(b, specs[b.state.species]) and not b.state.asleep:
            key = str(b.state.species) + "@" + b.parent.id
            packs.setdefault(key, []).append(b)
    for key in sorted(packs.keys()):
        pk = [b for b in packs[key] if not b.state.dead and not b.state.down]
        if not pk:
            continue
        sp = specs[pk[0].state.species]
        below = int(sv(pk[0], sp, "hunts_below", 1))  # only the hungry hunt: fed 0 by default
        if min([int(b.state.fed or 0) for b in pk]) >= below:
            continue
        hd = max([int(b.state.hungry_days or 0) for b in pk])
        prey = pick_prey(ctx, pk, sp, hd)
        if prey is not None:
            hunt(ctx, pk, prey, sp)

def in_range(ctx, b, steps):
    # its place, its home, and the places next to its home; one step further when it ranges
    start = ref(ctx, b.state.home) or b.parent
    seen = {b.parent.id: b.parent, start.id: start}
    edge = [start]
    for i in range(steps):
        nxt = []
        for p in edge:
            for e in ctx.edges(p, "connects_to", "out"):
                q = ctx.get(e["target"])
                if q is not None and q.id not in seen and open_way(ctx, b, p, q):
                    seen[q.id] = q
                    nxt.append(q)
        edge = nxt
    return [seen[k] for k in sorted(seen.keys())]

def pick_prey(ctx, pk, sp, hd):
    # the weakest: young or old, hurt, alone, nobody's
    lead = pk[0]
    kinds = tags(sv(lead, sp, "preys_on", []))
    ranging = hd >= int(sv(lead, sp, "range_after", 2))
    places = in_range(ctx, lead, 2 if ranging else 1)
    people = bool(sv(lead, sp, "attacks_people", False)) or ranging
    ids = [x.id for x in pk]
    # scarce prey hide: a species keeps its last `refuge` (default 2) within the pack's reach out of its teeth
    # and the last grown male and the last grown female of it, so a herd can always come back
    count = {}
    for p in places:
        for c in ctx.children(p, "beast"):
            if not c.state.dead and c.state.species in kinds:
                count[c.state.species] = count.get(c.state.species, 0) + 1
                if c.state.stage == "adult":
                    k = c.state.species + ":" + str(c.state.sex)
                    count[k] = count.get(k, 0) + 1
    best = None
    best_s = 0
    for p in places:
        here = ctx.children(p, "creature")
        persons = [c for c in here if not c.state.beast and not c.state.dead and not c.state.down]
        for c in here:
            if c.state.dead or c.state.down or c.id in ids:
                continue
            if c.state.beast:
                if c.state.species not in kinds:
                    continue
                psp = species_of(ctx, c)
                if count.get(c.state.species, 0) <= int(sv(c, psp, "refuge", 2)):
                    continue
                if c.state.stage == "adult" and count.get(c.state.species + ":" + str(c.state.sex), 0) <= 1:
                    continue
            elif not people or len(persons) != 1:
                continue  # a person only alone, and only to the bold or the starving
            herd = len([x for x in here if x.state.beast and x.state.species == c.state.species and not x.state.down and x.id != c.id])
            weak = 0 if c.state.stage in ["young", "old"] else 3
            score = int(c.state.vigor or 0) + weak + 2 * herd + (2 if c.state.owner else 0)
            if best is None or score < best_s:
                best = c
                best_s = score
    return best

def hunt(ctx, pk, prey, sp):
    place = prey.parent
    for h in pk:
        if h.parent.id != place.id:
            walk_to(ctx, h, place, "hunt")
    ctx.emit("beast_hunts", target=place, reach=1, hunters=[h.id for h in pk], prey=prey.id, species=pk[0].state.species)
    if not prey.state.beast:
        for h in pk:  # a person is fought for real, at the pace of the fighters' ticks: they can run or fight
            ctx.patch(h, {"attacked_by": prey.id})
        return
    flee = ctx.rand.roll("1d20") + bonus(prey, "survival")
    if flee >= 10 + 2 * len(pk):
        ways = [ctx.get(e["target"]) for e in ctx.edges(place, "connects_to", "out")]
        ways = [w for w in ways if w is not None and open_way(ctx, prey, place, w)]
        if ways:
            walk_to(ctx, prey, ctx.rand.choice(ways), "fled")
            ctx.emit("beast_fled", target=prey, reach=1, hunters=[h.id for h in pk], roll=flee)
            return
    # the herd stands with its own (wild with wild, kept with kept), and the owner's guard beasts with the owner's
    owner = prey.state.owner
    guard = []
    for b in ctx.children(place, "beast"):
        if b.state.down or b.state.dead or b.id == prey.id:
            continue
        herd = b.state.species == prey.state.species and b.state.stage != "young" and kept(b) == kept(prey)
        dog = owner is not None and b.state.owner == owner and sv(b, species_of(ctx, b), "guards", False)
        if herd or dog:
            guard.append(b)
    for rnd in range(6):
        for h in pk:
            if not h.state.down and not prey.state.down:
                strike(ctx, h, prey, False)
        if prey.state.down:
            break
        standing = [h for h in pk if not h.state.down]
        for g in guard:
            if not g.state.down and standing:
                strike(ctx, g, ctx.rand.choice(standing), False)
        if len([h for h in pk if h.state.down]) * 2 >= len(pk):
            break
    if prey.state.down:
        ctx.patch(prey, {"dead": True})
        ctx.emit("killed", target=prey, reach=1, by=pk[0].id, why="hunt")
        carcass(ctx, prey)
    else:
        ctx.emit("beast_hunt_failed", target=place, reach=1, hunters=[h.id for h in pk], prey=prey.id)

def wanders_in(ctx):
    # a hunter gone from the map comes back from beyond it once its prey is plentiful again
    for sp in ctx.find(type="species", limit=1000):
        w = sp.state.wanders_in
        if not w:
            continue
        mine = [b for b in ctx.find(type="beast", state={"species": sp.name}, limit=100000) if not b.state.dead and not kept(b)]
        if mine:
            continue
        kinds = tags(sp.state.preys_on)
        prey = [b for b in ctx.find(type="beast", limit=100000) if not b.state.dead and b.state.species in kinds]
        if len(prey) < int(w.get("prey") or 4):
            continue
        at = ref(ctx, w.get("at"))
        if at is None:
            continue
        n = tags(w.get("count") or [2, 2])
        st = None
        for s0 in (sp.state.stages or []):
            if s0.get("name") == "adult":
                st = s0
        come = []
        for i in range(ctx.rand.randint(int(n[0]), int(n[-1]))):
            sex = "m" if i == 0 else ctx.rand.choice(["m", "f"])
            state = {"species": sp.name, "sex": sex, "age": int(st.get("from") or 0) if st else 0, "fed": 1, "beast": True,
                     "home": at.id, "pack": True, "stage_names": True}
            if st is not None:
                state.update(stage_state(st, sex, False, sp))
            base = stage_name(st, sex) if st else None
            b = ctx.spawn(w.get("type") or "beast", at, name=unique_name(ctx, base or sp.name.capitalize()), state=state)
            if st is not None:
                give_parts(ctx, b, st)
            come.append(b.id)
        ctx.emit("beast_wandered_in", target=at, reach=1, species=sp.name, beasts=come)
