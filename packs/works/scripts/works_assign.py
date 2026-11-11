use("works")

def worker(ctx):
    want = str((ctx.params or {}).get("who", "")).lower()
    if want in ("me", "myself", "yourself", "self") or want == ctx.actor.id or want == (ctx.actor.name or "").lower():
        return ctx.actor
    for p in ctx.find(name=(ctx.params or {}).get("who"), limit=10):
        if p.is_a("creature"):
            return p
    w = ctx.get((ctx.params or {}).get("who"))
    return w

def leads(ctx, me, who):
    # the named leader of who's side has standing over them
    if not who.state.faction:
        return False
    for f in ctx.find(type="faction", name=who.state.faction, limit=1):
        return f.state.leader in (me.id, me.name)
    return False

def check(ctx):
    proj = ctx.target
    me = ctx.actor
    p = ctx.params or {}
    if "who" not in p or "role" not in p:
        return "say who and as what: params {\"who\": <name>, \"role\": <role, or none to take them off>}"
    who = worker(ctx)
    if who is None:
        return "nobody of that name"
    role = p["role"]
    crew = proj.state.crew or {}
    if role == "none":
        if who.id not in crew:
            return who.name + " is not on these works"
        if who.id == me.id or leads(ctx, me, who) or me.id == proj.state.patron:
            return True
        return "you have no standing over " + who.name
    if who.id == me.id:
        return "to work yourself, work"
    if ctx.embodied(who):
        return who.name + " has a mind of their own: ask them, and they take a role by working"
    if not leads(ctx, me, who):
        return "you have no standing over " + who.name + ": only the leader of their side puts them to work (or hire them)"
    if who.state.dead or who.state.down:
        return who.name + " is in no state to work"
    if not at_site(proj, who) and not adjacent(ctx, who.parent, proj.parent):
        return who.name + " is too far off to call over: they must be here or one step away"
    if who.state.works_on and who.state.works_on != proj.id and ctx.get(who.state.works_on) is not None:
        return who.name + " is on other works, at " + ctx.get(who.state.works_on).parent.name
    names = []
    for s in proj.state.stages or []:
        for r in (s.get("roles") or {}).keys():
            if r not in names:
                names.append(r)
    if role not in names:
        return "these works want no " + role + ": " + ", ".join(names)
    if (crew.get(who.id) or {}).get("role") != role and filled(proj, role) >= capacity(proj, role):
        return "every " + role + "'s place is taken"
    return True

def apply(ctx):
    proj = ctx.target
    me = ctx.actor
    who = worker(ctx)
    role = ctx.params["role"]
    if role == "none":
        release(ctx, proj, who.id)
        ctx.emit("unassigned", target=proj, reach=1, who=who.id, by=me.id)
        ctx.log(who.name + " is off the works")
        describe(ctx, proj)
        return
    home = who.state.post or (who.parent.id if who.parent is not None else None)
    ctx.patch(proj, {"crew": {who.id: {"role": role, "how": "assigned", "by": me.id, "home": home}}})
    ctx.patch(who, {"works_on": proj.id, "role": role})
    ctx.emit("assigned", target=proj, reach=1, who=who.id, role=role, by=me.id)
    ctx.remember(who, me.name + " put me to work as " + role + " on the " + proj.name.lower() + " at " + site_name(proj) + ".")
    describe(ctx, proj)
    ctx.log(who.name + " works as " + role)
