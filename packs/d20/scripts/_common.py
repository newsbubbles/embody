SKILLS = {"blade": "body", "brawl": "body", "climb": "body", "stealth": "wits", "survival": "wits", "lore": "wits", "lockpick": "wits",
          "aim": "wits", "parley": "will", "resolve": "will"}

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

def endless(thing):
    # a source with no level never runs dry: a well, a spring, a place that is a source; drawing from it costs nobody's count
    return thing is not None and bool(thing.state.water_source) and thing.state.left is None

def kept_for(src, who):
    # whether a body's own idle care may drink from this source: `keep_for` names whose water it is (a faction,
    # an id, or a list of them); none means anyone's. A seat that chooses to drink from another's store still can.
    keep = src.state.keep_for
    if who is None or keep is None:
        return True
    names = keep if isinstance(keep, list) else [keep]
    return who.id in names or (who.state.faction is not None and who.state.faction in names)

def water_here(ctx, place, who=None):
    # the place itself if it is a source, else the thing here that is one with the most left (an endless one
    # first). With `who`, only the water kept for them (kept_for).
    if place is None:
        return None
    if place.state.water_source and kept_for(place, who):
        return place
    best = None
    for p in ctx.children(place, "thing"):
        if not p.state.water_source or not kept_for(p, who):
            continue
        if p.state.left is None:
            return p
        if int(p.state.left) > 0 and (best is None or int(p.state.left) > int(best.state.left)):
            best = p
    return best

def known_way(who, place):
    # a hidden place is on a body's map only if it is its own side's
    return not (place.state.hidden and place.state.known_to != who.state.faction)

def first_step(ctx, who, here, goal, limit):
    # breadth-first over connects_to: the first step on the shortest way this body knows to `goal` (a place id), or,
    # with goal None, to the nearest place with water in it. None when there is none within `limit` steps.
    seen = {here.id: True}
    frontier = [[here.id, None]]
    for depth in range(limit):
        nxt = []
        for item in frontier:
            for e in ctx.edges(item[0], "connects_to", "out"):
                tid = e["target"]
                if tid in seen:
                    continue
                seen[tid] = True
                t = ctx.get(tid)
                if t is None:
                    continue
                first = item[1] if item[1] is not None else tid
                if tid == goal:
                    return ctx.get(first)
                if not known_way(who, t):
                    continue
                if goal is None and water_here(ctx, t, who) is not None:
                    return ctx.get(first)
                nxt.append([tid, first])
        frontier = nxt
    return None

def water_near(ctx, who, here):
    # the first step toward the nearest water this body knows the way to (six steps at most)
    return first_step(ctx, who, here, None, 6)

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

# heavy work makes a body sweat: a point of water for a blow in a fight, a harvest, a dig, dressing stone, forcing a
# lock, or a walk to or from open ground under more than half its carry. A world tunes it with `sweat` on its root: a
# table of costs by key (a verb, or "fight" and "heavy_walk") over these, or false for none.
SWEAT = {"fight": 1, "harvest": 1, "dig": 1, "dress": 1, "break": 1, "heavy_walk": 1}

def sweat_cost(ctx, key):
    table = ctx.root().state.sweat
    if table is False:
        return 0
    if table and table.get(key) is not None:
        return table.get(key)
    return SWEAT.get(key, 0)

def sweat(ctx, who, key):
    n = sweat_cost(ctx, key)
    st = who.state
    if not n or st.dead or st.water is None:
        return 0
    water = max(0, int(st.water) - int(n))
    changes = {"water": water}
    if water <= 3 and not st.thirsty:
        changes["thirsty"] = True
    ctx.patch(who, changes)
    ctx.emit("sweated", target=who, reach=0, by=key, cost=n, water=water)
    if changes.get("thirsty"):
        ctx.emit("thirsty", target=who, reach=0, water=water)
    return n

def strike(ctx, me, t, slow):
    # one blow: the opposed roll, the ward, the damage, the conditions. Used by attack and by fighters' ticks.
    sweat(ctx, me, "fight")
    weapon = melee(me)
    wname = weapon.name if weapon else "bare hands"
    ward = held(t, "ward")
    if not t.state.yielded and t.state.attacked_by != me.id:
        ctx.patch(t, {"attacked_by": me.id})
    if t.state.yielded == me.id:
        ctx.emit("dishonor", target=me, reach=-1, against=t.id)
    cx = (weapon.state.cooldown_x if weapon else None) or 1  # a maul's 2: the engine holds the striker off longer
    if ward and ward.state.on and not slow:
        ctx.emit("warded", target=t, reach=1, by=me.id, weapon=wname)
        ctx.log("the ward hardens against the fast blow")
        return {"hit": False, "warded": True, "cooldown_x": cx}
    # a sleeper is struck with advantage (the better of two rolls) and defends with bare hands, unbraced
    asleep = bool(t.state.asleep)
    a_roll = ctx.rand.roll("1d20")
    rolls = [a_roll]
    if asleep:
        rolls.append(ctx.rand.roll("1d20"))
        a_roll = max(rolls)
    a_mod = bonus(me, "blade" if weapon else "brawl")
    if weapon:
        a_mod = a_mod + int(weapon.state.bonus or 0)
    if slow:
        a_mod = a_mod - 2
    d_roll = ctx.rand.roll("1d20")
    d_mod = bonus(t, "blade" if melee(t) and not asleep else "brawl")
    if t.state.braced and not asleep:
        d_mod = d_mod + 3
    attack = a_roll + a_mod
    defence = d_roll + d_mod
    hit = attack > defence
    dmg = 0
    if hit:
        dmg = int(weapon.state.damage or 1) if weapon else 1
        vigor = int(t.state.vigor or 0) - dmg
        ctx.patch(t, {"vigor": vigor, "braced": False})
        ctx.emit("hit", target=t, reach=1, by=me.id, dmg=dmg, weapon=wname, attack=attack, defence=defence, vigor=vigor,
                 rolls=rolls, asleep=asleep)
        settle(ctx, t, me.id)
    else:
        ctx.emit("missed", target=t, reach=1, by=me.id, weapon=wname, attack=attack, defence=defence, rolls=rolls,
                 asleep=asleep)
    if me.state.braced:
        ctx.patch(me, {"braced": False})
    ctx.log(("hit for " + str(dmg) if hit else "miss") + " (" + str(attack) + " vs " + str(defence) + ")")
    return {"hit": hit, "dmg": dmg, "attack": attack, "defence": defence, "cooldown_x": cx}

def melee(who):
    # the first weapon held that is not one that fires: what a blow is struck with
    for it in who.children():
        if it.state.weapon and not it.state.ranged:
            return it
    return None

def ranged(who):
    # the first weapon held that fires (`ranged` on its state); `ammo` names the kind it takes
    for it in who.children():
        if it.state.weapon and it.state.ranged:
            return it
    return None

def ammo_for(who, weapon):
    # what the weapon fires from the shooter's hands: a held thing whose `ammo` or `kind` is the weapon's `ammo`
    # (a stack of arrows, a pouch of glass for a sling). A weapon with no `ammo` needs none.
    kind = weapon.state.ammo
    for it in who.children():
        if kind and it.id != weapon.id and (it.state.ammo == kind or it.state.kind == kind):
            return it
    return None

def can_fire(who, weapon):
    # why it will not fire now, or None: a weapon that must be loaded (`loaded` false) and one out of ammo
    if weapon.state.loaded is False:
        return weapon.name + " is not loaded"
    if weapon.state.ammo and ammo_for(who, weapon) is None:
        return "you have no " + str(weapon.state.ammo) + " left"
    return None

def in_sight(ctx, me, t):
    # someone here, or one way over that the eye can follow: a way you know with no shut door on it
    here = me.parent
    there = t.parent
    if here is None or there is None:
        return False
    if there.id == here.id:
        return True
    if t.state.hidden:
        return False
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == there.id:
            via = ctx.get(e["data"].get("via")) if e["data"].get("via") else None
            if via is not None and not via.state.open:
                return False
            return ctx.knows_way(me, there)
    return False

def cover(place):
    # `cover` on a place: true is +2 to the defence of whoever stands in it, a number is that much
    c = place.state.cover if place is not None else None
    if c is True:
        return 2
    if c:
        return int(c)
    return 0

def ring_blocks(ctx, a, t):
    # the ring holds against shots too: one in a duel shoots only the other, nobody shoots into a duel
    for d in ctx.relations(a, "duel"):
        if t.id not in d["participants"]:
            return "you are in a duel: your aim is for your opponent"
    for d in ctx.relations(t, "duel"):
        if a.id not in d["participants"]:
            return "the ring holds: " + t.name + " is in a duel"
    return None

def shot(ctx, me, t, weapon):
    # one shot from a weapon that fires, at someone in sight (in_sight). The hook a world's own fire verbs call (a
    # crossbow that is loaded, a sling): d20 + wits + aim + the weapon's bonus, -2 one way over, against d20 + wits
    # + the cover where they stand. A ward on stops it: a shot is fast. The ammo is spent and lands where they
    # stand, hit or miss, a pile anyone there can take; a loaded weapon is unloaded.
    ammo = ammo_for(me, weapon)
    far = t.parent.id != me.parent.id
    wname = weapon.name
    if weapon.state.loaded is not None:
        ctx.patch(weapon, {"loaded": False})
    if not t.state.yielded and t.state.attacked_by != me.id:
        ctx.patch(t, {"attacked_by": me.id})
    if t.state.yielded == me.id:
        ctx.emit("dishonor", target=me, reach=-1, against=t.id)
    extra = int(ammo.state.damage or 0) if ammo is not None else 0
    if ammo is not None:
        ctx.transfer(ammo, t.parent, 1 if ammo.state.count is not None else None)
    if far:
        ctx.emit("shot", target=me, reach=1, by=me.id, at=t.id, weapon=wname)  # the shooter's own place sees it fly
    ward = held(t, "ward")
    if ward and ward.state.on:
        ctx.emit("warded", target=t, reach=1, by=me.id, weapon=wname, ranged=True)
        ctx.log("the ward stops the shot")
        return {"hit": False, "warded": True, "cooldown_x": weapon.state.cooldown_x or 1}
    asleep = bool(t.state.asleep)
    a_roll = ctx.rand.roll("1d20")
    rolls = [a_roll]
    if asleep:
        rolls.append(ctx.rand.roll("1d20"))
        a_roll = max(rolls)
    a_mod = bonus(me, "aim") + int(weapon.state.bonus or 0) - (2 if far else 0)
    d_roll = ctx.rand.roll("1d20")
    d_mod = cover(t.parent) + (0 if asleep else bonus(t, "dodge"))  # wits, less the conditions
    attack = a_roll + a_mod
    defence = d_roll + d_mod
    hit = attack > defence
    dmg = 0
    if hit:
        dmg = int(weapon.state.damage or 1) + extra
        vigor = int(t.state.vigor or 0) - dmg
        ctx.patch(t, {"vigor": vigor, "braced": False})
        ctx.emit("hit", target=t, reach=1, by=me.id, dmg=dmg, weapon=wname, attack=attack, defence=defence, vigor=vigor,
                 rolls=rolls, asleep=asleep, ranged=True)
        settle(ctx, t, me.id)
    else:
        ctx.emit("missed", target=t, reach=1, by=me.id, weapon=wname, attack=attack, defence=defence, rolls=rolls,
                 asleep=asleep, ranged=True)
    ctx.log(("hit for " + str(dmg) if hit else "miss") + " (" + str(attack) + " vs " + str(defence) + ")")
    return {"hit": hit, "dmg": dmg, "attack": attack, "defence": defence, "far": far,
            "cooldown_x": weapon.state.cooldown_x or 1}

def faction_of(ctx, who):
    name = who.state.faction
    if not name:
        return None
    for f in ctx.find(type="faction", limit=20):
        if f.name == name:
            return f
    return None

def seen_standing(ctx, who, faction):
    # what the person can read: their out-edge to the faction
    for e in ctx.edges(who, "standing", "out"):
        if e["target"] == faction.id:
            return int(e["data"].get("value") or 0)
    return 0

def standing(ctx, who, faction):
    # where the person stands: what they can read, plus what the faction keeps to itself (`unseen`)
    return seen_standing(ctx, who, faction) + int((faction.state.unseen or {}).get(who.id) or 0)

def keep_secret(ctx, thing, changes):
    # patch keys on a thing and list them in its `secret`, so no body reads them on its card
    secret = list(thing.state.secret or [])
    for k in changes:
        if k not in secret:
            secret.append(k)
    changes = dict(changes)
    changes["secret"] = secret
    ctx.patch(thing, changes)

def shift_standing(ctx, who, faction, delta, why, quiet=False):
    # an out-edge from the person, so they can read where they stand; hostility is kept on the faction.
    # quiet: the deed was done to someone who keeps their faction secret. The faction still counts it, in its own
    # secret `unseen`, and the person's edge and feed name no side they cannot know.
    seen = seen_standing(ctx, who, faction)
    unseen = dict(faction.state.unseen or {})
    if quiet:
        unseen[who.id] = int(unseen.get(who.id) or 0) + delta
        keep_secret(ctx, faction, {"unseen": unseen})
    else:
        seen = seen + delta
        ctx.unlink(who, faction, "standing")
        ctx.link(who, faction, "standing", {"value": seen, "public": True})
        ctx.emit("standing", target=who, reach=0, faction=faction.name, value=seen, delta=delta, why=why)
    value = seen + int(unseen.get(who.id) or 0)
    hostile = dict(faction.state.hostile or {})
    if value <= -4 and not hostile.get(who.id):
        hostile[who.id] = True
        ctx.patch(faction, {"hostile": hostile})
        ctx.emit("outlawed", target=who, reach=1, faction=faction.name)
    elif value > -4 and hostile.get(who.id):
        hostile[who.id] = None
        ctx.patch(faction, {"hostile": hostile})
    return value
