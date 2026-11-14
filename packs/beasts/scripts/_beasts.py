use("common")
# What the beasts pack's scripts share: a beast's species and the values it takes from it, the day count, forage,
# growing up, taming and going feral.

def species_of(ctx, b):
    name = b.state.species
    if not name:
        return None
    for s in ctx.find(type="species", name=str(name), limit=20):
        if s.name.lower() == str(name).lower():
            return s
    return None

def sv(b, sp, key, default):
    # a beast's own value over its species', over the default
    v = b.state.get(key)
    if v is not None:
        return v
    if sp is not None:
        v = sp.state.get(key)
        if v is not None:
            return v
    return default

def by_stage(val, stage):
    # a number for every stage, or a table by stage (a stage it does not name gets None: never)
    if isinstance(val, dict):
        return val.get(stage)
    return val

def tags(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

def diet(b, sp):
    return tags(sv(b, sp, "eats", []))

def kept(b):
    return b.state.owner is not None or b.state.herd is not None

def today(ctx):
    return int(ctx.root().state.beast_day or 0)

def able(b):
    return b.parent is not None and not b.state.dead

def unique_name(ctx, base):
    taken = [e.name.lower() for e in ctx.find(name=base, limit=500)]
    if base.lower() not in taken:
        return base
    n = 2
    while (base + " " + str(n)).lower() in taken:
        n = n + 1
    return base + " " + str(n)

def forage_left(place, eats):
    f = place.state.forage or {}
    return sum([int((f.get(t) or {}).get("left") or 0) for t in eats])

def forage_regrow(place, eats):
    f = place.state.forage or {}
    return sum([int((f.get(t) or {}).get("regrow") or 0) for t in eats])

def eat_forage(ctx, place, eats, need):
    # take up to `need` units from the place's forage, in the order of the diet; returns how many
    f = place.state.forage or {}
    if need <= 0 or not f:
        return 0
    new = {k: dict(v) for k, v in f.items()}
    got = 0
    for t in eats:
        if got >= need:
            break
        row = new.get(t)
        if row is None:
            continue
        take = min(need - got, int(row.get("left") or 0))
        if take > 0:
            row["left"] = int(row.get("left") or 0) - take
            got = got + take
    if got:
        ctx.patch(place, {"forage": new})
    return got

def stage_for(sp, age):
    cur = None
    for s in ((sp.state.stages or []) if sp is not None else []):
        if age >= float(s.get("from") or 0):
            cur = s
    return cur

def stage_state(st_def, sex, growing, b):
    # what a stage sets on the body; growing up keeps the wounds it has (hp moves by what max_hp gains)
    changes = dict(st_def.get("state") or {})
    changes["stage"] = st_def.get("name")
    if growing and "max_hp" in changes:
        old_max = int(b.state.max_hp or 0)
        changes["hp"] = max(1, min(int(changes["max_hp"]), int(b.state.hp or 0) + int(changes["max_hp"]) - old_max))
    return changes

def stage_name(st_def, sex):
    n = st_def.get("names")
    if isinstance(n, dict):
        return n.get(sex) or n.get("any")
    return st_def.get("name_as")

def give_parts(ctx, b, st_def):
    # natural weapons and the like a stage brings (tusks): spawned on the body once
    have = [c.name.lower() for c in b.children()]
    for p in (st_def.get("parts") or []):
        if str(p.get("name", "")).lower() not in have:
            ctx.spawn(p.get("type") or "thing", b, name=p.get("name"), state=dict(p.get("state") or {}))

def grow_into(ctx, b, sp, st_def):
    ctx.patch(b, stage_state(st_def, b.state.sex, True, b))
    give_parts(ctx, b, st_def)
    if b.state.stage_names:
        n = stage_name(st_def, b.state.sex)
        if n and n.lower() != b.name.lower():
            ctx.rename(b, unique_name(ctx, n))
    ctx.emit("beast_grew", target=b, reach=1, stage=st_def.get("name"), species=b.state.species)

def die(ctx, b, why):
    ctx.patch(b, {"dead": True, "down": True, "carrying": None, "follows": None, "hungry": False})
    ctx.emit("beast_died", target=b, reach=1, why=why, species=b.state.species)
    carcass(ctx, b)

def carcass(ctx, b):
    # a dead beast is meat for a day, carrion for two more, then bones: `meals` of it to eat where it lies
    if b.state.carcass_day is not None:
        return
    sp = species_of(ctx, b)
    n = sv(b, sp, "carcass", None)
    if n is None:
        n = max(1, int(b.state.max_hp or 4))
    ctx.patch(b, {"food": ["meat", "carrion"], "meals": int(n), "carcass_day": today(ctx)})

def eat_carcass(ctx, place, eats, need):
    # take up to `need` meals from the dead lying here whose food this diet eats; returns how many
    got = 0
    for c in ctx.children(place):
        if got >= need:
            break
        m = int(c.state.meals or 0)
        if m <= 0 or not [t for t in tags(c.state.food) if t in eats]:
            continue
        take = min(need - got, m)
        ctx.patch(c, {"meals": m - take})
        got = got + take
    return got

def meat_here(place, eats):
    return sum([int(c.state.meals or 0) for c in place.children() if [t for t in tags(c.state.food) if t in eats]])

def ref(ctx, x):
    # an entity by id, or by its exact name
    if not x:
        return None
    e = ctx.get(x)
    if e is not None:
        return e
    for c in ctx.find(name=str(x), limit=50):
        if c.name.lower() == str(x).lower():
            return c
    return None

def walk_to(ctx, b, place, why):
    ctx.move(b, place)
    ctx.emit("arrived", target=place, reach=1, who=b.id, place=place.id, quiet=True, why=why)

def step_home(ctx, b, why):
    # one way nearer its home by ways it could walk now, looking a few places out; True when it moved
    home = ref(ctx, b.state.home)
    if home is None or b.parent is None or b.parent.id == home.id:
        return False
    first = {}
    seen = [b.parent.id]
    edge = [b.parent]
    for depth in range(4):
        nxt = []
        for p in edge:
            for e in ctx.edges(p, "connects_to", "out"):
                q = ctx.get(e["target"])
                if q is None or q.id in seen or not open_way(ctx, b, p, q):
                    continue
                seen.append(q.id)
                first[q.id] = first.get(p.id) or q
                if q.id == home.id:
                    walk_to(ctx, b, first[q.id], why)
                    return True
                nxt.append(q)
        edge = nxt
    return False

def open_way(ctx, b, here, place):
    # a way this body could walk now: no shut or locked door on it, not a hidden place it does not know
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == place.id:
            via = e["data"].get("via")
            door = ctx.get(via) if via else None
            if door is not None and (not door.state.open or ctx.locked(door) is not None):
                return False
            if ctx.locked(place) is not None:
                return False
            return ctx.knows_way(b, place)
    return False

def feral(ctx, b, why):
    # loyalty gone: no owner, no herd, back to the ground it came from
    was = b.state.owner or b.state.herd
    ctx.patch(b, {"owner": None, "herd": None, "follows": None, "loyalty": 0, "trust": {}, "staying": False})
    ctx.emit("beast_feral", target=b, reach=1, was=was, why=why, species=b.state.species)
    home = ref(ctx, b.state.home)
    if home is not None and b.parent is not None and home.id != b.parent.id and not b.state.down:
        walk_to(ctx, b, home, "feral")

def tame(ctx, b, who):
    ctx.patch(b, {"owner": who.id, "herd": None, "follows": who.id, "loyalty": 3, "pack": False, "trust": {},
                  "staying": False, "with_owner": today(ctx), "home": b.state.home or b.parent.id})
    ctx.emit("beast_tamed", target=b, reach=1, by=who.id, species=b.state.species)

def item_in_hand(ctx, who, ref):
    if not ref:
        return None
    r = str(ref).lower()
    for c in who.children():
        if c.id == ref or c.name.lower() == r or str(c.state.kind or "").lower() == r:
            return c
    return None
