use("common")
def tick(ctx):
    # a fighter without a mind: in a duel, strike the other; then whoever struck me last, while that grudge holds
    # (grudge_holds); then anyone my faction has outlawed. With a bow that will fire, it also shoots them one way
    # over, so wardens can cover a road. Every deed waits out its cooldown on that foe (blow).
    me = ctx.self
    st = me.state
    if st.down or st.dead or st.asleep or me.parent is None:
        return
    for d in ctx.relations(me, "duel"):
        for pid in d["participants"]:
            if pid != me.id:
                other = ctx.get(pid)
                if other is not None and other.parent.id == me.parent.id and not other.state.down and not other.state.dead:
                    blow(ctx, me, other, None)
                    return
    bow = ranged(me)
    if bow is not None and can_fire(me, bow):
        bow = None
    # outside a duel the ring is law: never strike someone who is in a duel I am not part of
    foe = ctx.get(st.attacked_by) if st.attacked_by else None
    if st.attacked_by and not grudge_holds(ctx, me, foe, bow):
        ctx.patch(me, {"attacked_by": None, "attacked_at": None})
        foe = None
    if foe is not None and standing_foe(foe) and not in_a_ring(ctx, foe) and not spared(ctx, me, foe):
        blow(ctx, me, foe, bow)
        return
    f = faction_of(ctx, me)
    if f is None:
        return
    hostile = f.state.hostile or {}
    for p in ctx.children(me.parent, "creature"):
        if p.id != me.id and hostile.get(p.id) and standing_foe(p) and not in_a_ring(ctx, p) and not spared(ctx, me, p) and outlaw_of(ctx, f, p):
            blow(ctx, me, p, bow)
            return
    if bow is None:
        return
    for e in ctx.edges(me.parent, "connects_to", "out"):
        place = ctx.get(e["target"])
        if place is None:
            continue
        for p in ctx.children(place, "creature"):
            if hostile.get(p.id) and standing_foe(p) and not in_a_ring(ctx, p) and not spared(ctx, me, p) and in_sight(ctx, me, p) and outlaw_of(ctx, f, p):
                blow(ctx, me, p, bow)
                return

def grudge_holds(ctx, me, foe, bow):
    # whoever struck me last stays my foe while they are here (or in my bow's sight), have not yielded to me, and
    # struck me within the world's grudge_for (default a world hour). Walking away ends it, and so does peace.
    if foe is None or foe.parent is None or foe.state.dead or spared(ctx, me, foe):
        return False
    if foe.parent.id != me.parent.id and not (bow is not None and in_sight(ctx, me, foe)):
        return False
    if me.state.attacked_at is None:
        ctx.patch(me, {"attacked_at": ctx.t})  # a grudge from before grudges had a clock: it starts now
        return True
    return ctx.t - float(me.state.attacked_at) < grudge_for(ctx)

def spared(ctx, me, p):
    # one who yielded to me, or to anyone of my faction, is out of my fight: a fighter without a mind never strikes
    # them (a mind may, and pays the dishonor). Two guards who kept cutting a man who had yielded to the first one
    # killed him (a player's report, 2026-11-23).
    to = p.state.yielded
    if not to:
        return False
    if to == me.id:
        return True
    if not me.state.faction:
        return False
    other = ctx.get(to)
    return other is not None and other.state.faction == me.state.faction

def standing_foe(p):
    return p.parent is not None and not p.state.down and not p.state.dead

def blow(ctx, me, foe, bow):
    # one deed at a foe: a shot when they stand one way over (held while their ward is on), or here when I have no
    # blade and their ward is down; else a blow, slow against a ward. Each waits out my cooldown on them, as an
    # act's strike does (the engine's: longer when a player or a mind holds either side), x the weapon's cooldown_x.
    if ctx.strike_wait(me, foe) > 0:
        return
    ward = held(foe, "ward")
    warded = bool(ward and ward.state.on)
    if foe.parent.id != me.parent.id:
        if bow is None or warded:
            return  # a ward stops every shot: hold the arrow until it is down or they come close
        r = shot(ctx, me, foe, bow)
    elif bow is not None and melee(me) is None and not warded:
        r = shot(ctx, me, foe, bow)
    else:
        r = strike(ctx, me, foe, bool(held(foe, "ward")))
    ctx.mark_strike(me, foe, r.get("cooldown_x") or 1)

def in_a_ring(ctx, who):
    return len(ctx.relations(who, "duel")) > 0
