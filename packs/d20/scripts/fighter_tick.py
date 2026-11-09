use("common")
def tick(ctx):
    # a fighter without a mind: in a duel, strike the other; then whoever struck me last; then anyone my faction has outlawed
    me = ctx.self
    st = me.state
    if st.down or st.dead or st.asleep or me.parent is None:
        return
    for d in ctx.relations(me, "duel"):
        for pid in d["participants"]:
            if pid != me.id:
                other = ctx.get(pid)
                if other is not None and other.parent.id == me.parent.id and not other.state.down and not other.state.dead:
                    strike(ctx, me, other, bool(held(other, "ward")))
                    return
    # outside a duel the ring is law: never strike someone who is in a duel I am not part of
    foe = ctx.get(st.attacked_by) if st.attacked_by else None
    if foe is not None and foe.parent is not None and foe.parent.id == me.parent.id and not foe.state.down and not foe.state.dead and foe.state.yielded != me.id and not in_a_ring(ctx, foe):
        strike(ctx, me, foe, bool(held(foe, "ward")))
        return
    f = faction_of(ctx, me)
    if f is None:
        return
    hostile = f.state.hostile or {}
    for p in ctx.children(me.parent, "creature"):
        if p.id != me.id and hostile.get(p.id) and not p.state.down and not p.state.dead and not in_a_ring(ctx, p):
            strike(ctx, me, p, bool(held(p, "ward")))
            return

def in_a_ring(ctx, who):
    return len(ctx.relations(who, "duel")) > 0
