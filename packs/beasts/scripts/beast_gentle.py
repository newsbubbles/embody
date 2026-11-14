use("beasts")
# Gentle a beast toward you: a calm, fed beast you fed by hand today. A check (survival, or the species' tame_skill)
# against its tame_dc for its stage; once a day per beast per person. Each success is a point of trust toward you; at
# tame_at it is yours. Fail by 5 or more and it bites, and you lose a point. A leader, or a stage with no tame_dc
# (old age), is never tamed.

def check(ctx):
    b = ctx.target
    me = ctx.actor
    if b.parent is None or me.parent is None or b.parent.id != me.parent.id:
        return b.name + " is not here"
    if b.state.dead or b.state.down:
        return b.name + " is in no state for it"
    if b.state.owner == me.id:
        return b.name + " is yours already"
    if b.state.owner is not None:
        return b.name + " is someone else's"
    sp = species_of(ctx, b)
    if b.state.leader or by_stage(sv(b, sp, "tame_dc", None), b.state.stage) is None:
        return b.name + " will never be tamed"
    foe = ctx.get(b.state.attacked_by) if b.state.attacked_by else None
    if b.state.riled or b.state.hungry or (foe is not None and foe.parent is not None and foe.parent.id == b.parent.id and not foe.state.down):
        return b.name + " is not calm enough to come near"
    d = today(ctx)
    if (b.state.fed_by or {}).get(me.id) != d:
        return "feed " + b.name + " from your hand first, today"
    if (b.state.gentled or {}).get(me.id) == d:
        return b.name + " has had enough of you today: come back after dawn"
    return True

def apply(ctx):
    b = ctx.target
    me = ctx.actor
    sp = species_of(ctx, b)
    stage = b.state.stage
    dc = int(by_stage(sv(b, sp, "tame_dc", 12), stage))
    need = int(by_stage(sv(b, sp, "tame_at", 3), stage) or 3)
    skill = sv(b, sp, "tame_skill", "survival")
    g = dict(b.state.gentled or {})
    g[me.id] = today(ctx)
    trust = dict(b.state.trust or {})
    n = int(trust.get(me.id) or 0)
    roll = ctx.rand.roll("1d20")
    total = roll + bonus(me, skill, ctx)
    if total >= dc:
        n = n + 1
        trust[me.id] = n
        ctx.patch(b, {"gentled": g, "trust": trust})
        ctx.emit("beast_trust", target=b, reach=1, by=me.id, trust=n, of=need, roll=total, dc=dc)
        if n >= need:
            tame(ctx, b, me)
        ctx.log(b.name + " trusts you a little more: " + str(n) + " of " + str(need) + " (" + str(total) + " vs " + str(dc) + ")")
        return
    if total <= dc - 5:
        trust[me.id] = max(0, n - 1)
        ctx.patch(b, {"gentled": g, "trust": trust})
        ctx.emit("beast_bit", target=b, reach=1, at=me.id, roll=total, dc=dc)
        strike(ctx, b, me, False)
        ctx.log(b.name + " bites (" + str(total) + " vs " + str(dc) + "): trust " + str(max(0, n - 1)))
        return
    ctx.patch(b, {"gentled": g})
    ctx.emit("beast_shied", target=b, reach=1, by=me.id, roll=total, dc=dc)
    ctx.log(b.name + " shies away (" + str(total) + " vs " + str(dc) + "): trust stays " + str(n))
