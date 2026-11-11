use("works")

def roles_named(proj):
    out = []
    for s in proj.state.stages or []:
        for r in (s.get("roles") or {}).keys():
            if r not in out:
                out.append(r)
    return out

def chosen_role(ctx):
    proj = ctx.target
    mine = ((proj.state.crew or {}).get(ctx.actor.id) or {}).get("role")
    want = ctx.params.get("role") if ctx.params else None
    return want or mine

def check(ctx):
    proj = ctx.target
    me = ctx.actor
    if me.state.down:
        return "you are down"
    if not at_site(proj, me):
        return "you are not at the works"
    if me.state.works_on and me.state.works_on != proj.id and ctx.get(me.state.works_on) is not None:
        return "you are on other works, at " + ctx.get(me.state.works_on).parent.name + ": leave them first (assign, who: yourself, role: none)"
    role = chosen_role(ctx)
    names = roles_named(proj)
    if not role:
        return "work as what? the works want: " + ", ".join(names) + " (params {\"role\": ...})"
    if role not in names:
        return "these works want no " + role + ": " + ", ".join(names)
    mine = ((proj.state.crew or {}).get(me.id) or {}).get("role")
    if mine != role and filled(proj, role) >= capacity(proj, role):
        return "every " + role + "'s place is taken: work as another (" + ", ".join(names) + ") or ask the patron"
    for x in blockers(ctx, proj, me.id, role):
        if not x.startswith("no "):  # a missing hand may still come before the hour is out
            return x
    return True

def apply(ctx):
    proj = ctx.target
    me = ctx.actor
    role = chosen_role(ctx)
    old = (proj.state.crew or {}).get(me.id) or {}
    entry = {"role": role, "how": old.get("how") or "volunteered", "busy_until": ctx.t + 3600}
    ctx.patch(proj, {"crew": {me.id: entry}})
    if me.state.works_on != proj.id or me.state.role != role:
        ctx.patch(me, {"works_on": proj.id, "role": role})
    ctx.emit("working", target=proj, reach=1, by=me.id, role=role)
    short = blockers(ctx, proj, me.id, role)
    if short:
        ctx.log("you set to work, but " + short[0].split(":")[0] + " yet: the hour counts only if that is mended before it is out")

def finish(ctx):
    proj = ctx.target
    me = ctx.actor
    if ctx.get(proj.id) is None:
        return
    if not at_site(proj, me) or me.state.down:
        ctx.log("you left the works before the hour was out; it counts for nothing")
        return
    role = chosen_role(ctx)
    b = blockers(ctx, proj, me.id, role)
    if b:
        ctx.log("the hour's work came to nothing: " + b[0])
        return
    ctx.patch(me, {"toil": float(me.state.toil or 0) + 1})
    stage = stage_of(proj)
    add_labour(ctx, proj, 1, [me.id])
    if ctx.get(proj.id) is not None:
        describe(ctx, proj)
        ctx.log("an hour on the " + str(stage.get("name")) + ": " + str(round(float(proj.state.labour or 0), 1)) + " of " + str(stage.get("labour")))
