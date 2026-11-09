SKILLS = {"blade": "body", "brawl": "body", "climb": "body", "stealth": "wits", "survival": "wits", "lore": "wits",
          "parley": "will", "resolve": "will"}

def stat_for(skill):
    return SKILLS.get(skill, "wits")

def bonus(who, skill):
    # stat + skill rank, less the conditions everyone can see
    st = who.state
    skills = st.skills or {}
    b = int(st.get(stat_for(skill)) or 0) + int(skills.get(skill) or 0)
    if st.wounded:
        b = b - 2
    if st.thirsty:
        b = b - 2
    return b

def held(who, flag):
    # the first thing held whose state has the flag set
    for it in who.children():
        if it.state.get(flag):
            return it
    return None

def water_here(ctx, place):
    # the place itself if it is a source, else a thing here that is one and has something left
    if place is None:
        return None
    if place.state.water_source:
        return place
    for p in ctx.children(place, "thing"):
        if p.state.water_source and (p.state.left is None or int(p.state.left) > 0):
            return p
    return None

def water_near(ctx, who, here):
    # a connected place with water, one step away, that this body knows the way to
    for e in ctx.edges(here, "connects_to", "out"):
        t = ctx.get(e["target"])
        if t is None:
            continue
        if t.state.hidden and t.state.known_to != who.state.faction:
            continue
        if water_here(ctx, t) is not None:
            return t
    return None

def revive(ctx, who, water):
    # a body thirst put down gets up when it has drunk; a blade's work stays done until someone sees to it
    st = who.state
    if st.down and st.downed_by == "thirst" and water > 3:
        ctx.patch(who, {"down": False, "downed_by": None, "vigor": max(1, int(st.vigor or 0))})
        ctx.emit("rose", target=who, reach=1, by="water")

def settle(ctx, who, cause):
    # derive the conditions from vigor and say what changed
    st = who.state
    v = int(st.vigor or 0)
    mx = int(st.max_vigor or 6)
    if v <= 0 and not st.down:
        ctx.patch(who, {"down": True, "wounded": True, "vigor": 0, "braced": False})
        ctx.emit("downed", target=who, reach=1, by=cause)
    elif v <= mx // 2 and not st.wounded:
        ctx.patch(who, {"wounded": True})
        ctx.emit("wounded", target=who, reach=1, by=cause)

def strike(ctx, me, t, slow):
    # one blow: the opposed roll, the ward, the damage, the conditions. Used by attack and by fighters' ticks.
    weapon = held(me, "weapon")
    wname = weapon.name if weapon else "bare hands"
    ward = held(t, "ward")
    if not t.state.yielded and t.state.attacked_by != me.id:
        ctx.patch(t, {"attacked_by": me.id})
    if t.state.yielded == me.id:
        ctx.emit("dishonor", target=me, reach=-1, against=t.id)
    if ward and ward.state.on and not slow:
        ctx.emit("warded", target=t, reach=1, by=me.id, weapon=wname)
        ctx.log("the ward hardens against the fast blow")
        return {"hit": False, "warded": True}
    a_roll = ctx.rand.roll("1d20")
    a_mod = bonus(me, "blade" if weapon else "brawl")
    if weapon:
        a_mod = a_mod + int(weapon.state.bonus or 0)
    if slow:
        a_mod = a_mod - 2
    d_roll = ctx.rand.roll("1d20")
    d_mod = bonus(t, "blade" if held(t, "weapon") else "brawl")
    if t.state.braced:
        d_mod = d_mod + 3
    attack = a_roll + a_mod
    defence = d_roll + d_mod
    hit = attack > defence
    dmg = 0
    if hit:
        dmg = int(weapon.state.damage or 1) if weapon else 1
        vigor = int(t.state.vigor or 0) - dmg
        ctx.patch(t, {"vigor": vigor, "braced": False})
        ctx.emit("hit", target=t, reach=1, by=me.id, dmg=dmg, weapon=wname, attack=attack, defence=defence, vigor=vigor)
        settle(ctx, t, me.id)
    else:
        ctx.emit("missed", target=t, reach=1, by=me.id, weapon=wname, attack=attack, defence=defence)
    if me.state.braced:
        ctx.patch(me, {"braced": False})
    ctx.log(("hit for " + str(dmg) if hit else "miss") + " (" + str(attack) + " vs " + str(defence) + ")")
    return {"hit": hit, "dmg": dmg, "attack": attack, "defence": defence}

def faction_of(ctx, who):
    name = who.state.faction
    if not name:
        return None
    for f in ctx.find(type="faction", limit=20):
        if f.name == name:
            return f
    return None

def standing(ctx, who, faction):
    for e in ctx.edges(who, "standing", "out"):
        if e["target"] == faction.id:
            return int(e["data"].get("value") or 0)
    return 0

def shift_standing(ctx, who, faction, delta, why):
    # an out-edge from the person, so they can read where they stand; hostility is kept on the faction
    value = standing(ctx, who, faction) + delta
    ctx.unlink(who, faction, "standing")
    ctx.link(who, faction, "standing", {"value": value, "public": True})
    ctx.emit("standing", target=who, reach=0, faction=faction.name, value=value, delta=delta, why=why)
    hostile = dict(faction.state.hostile or {})
    if value <= -4 and not hostile.get(who.id):
        hostile[who.id] = True
        ctx.patch(faction, {"hostile": hostile})
        ctx.emit("outlawed", target=who, reach=1, faction=faction.name)
    elif value > -4 and hostile.get(who.id):
        hostile[who.id] = None
        ctx.patch(faction, {"hostile": hostile})
    return value
