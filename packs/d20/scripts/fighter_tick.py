use("common")
def tick(ctx):
    # a fighter without a mind: in a duel, strike the other; then whoever struck me last; then anyone my faction has
    # outlawed. With a bow that will fire, it also shoots them one way over, so wardens can cover a road.
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
    if foe is not None and standing_foe(foe) and foe.state.yielded != me.id and not in_a_ring(ctx, foe) and (
            foe.parent.id == me.parent.id or (bow is not None and in_sight(ctx, me, foe))):
        blow(ctx, me, foe, bow)
        return
    f = faction_of(ctx, me)
    if f is None:
        return
    hostile = f.state.hostile or {}
    for p in ctx.children(me.parent, "creature"):
        if p.id != me.id and hostile.get(p.id) and standing_foe(p) and not in_a_ring(ctx, p):
            blow(ctx, me, p, bow)
            return
    if bow is None:
        return
    for e in ctx.edges(me.parent, "connects_to", "out"):
        place = ctx.get(e["target"])
        if place is None:
            continue
        for p in ctx.children(place, "creature"):
            if hostile.get(p.id) and standing_foe(p) and not in_a_ring(ctx, p) and in_sight(ctx, me, p):
                blow(ctx, me, p, bow)
                return

def standing_foe(p):
    return p.parent is not None and not p.state.down and not p.state.dead

def blow(ctx, me, foe, bow):
    # one deed at a foe: a shot when they stand one way over (held while their ward is on), or here when I have no
    # blade and their ward is down; else a blow, slow against a ward. A seated foe gets their beat first.
    if not ready(ctx, me, foe):
        return
    ward = held(foe, "ward")
    warded = bool(ward and ward.state.on)
    if foe.parent.id != me.parent.id:
        if bow is None or warded:
            return  # a ward stops every shot: hold the arrow until it is down or they come close
        shot(ctx, me, foe, bow)
    elif bow is not None and melee(me) is None and not warded:
        shot(ctx, me, foe, bow)
    else:
        strike(ctx, me, foe, bool(held(foe, "ward")))
    paced(ctx, me, foe)

def in_a_ring(ctx, who):
    return len(ctx.relations(who, "duel")) > 0
