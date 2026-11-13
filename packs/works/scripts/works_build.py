use("works")

def is_patron(actor, patrons):
    return actor.id in patrons or actor.name in patrons or (actor.state.faction is not None and actor.state.faction in patrons)

def misfit(place, where):
    # why this place will not take the plan, or None
    types = where.get("types") or []
    if types and not any([place.is_a(t) for t in types]):
        return "it has to go on " + " or ".join(types)
    places = where.get("places") or []
    if places and place.name not in places:
        return "it is drawn for " + ", ".join(places) + ", not here"
    for f in where.get("has") or []:
        if not place.state.get(f):
            return "it needs " + f + " ground, and this is not"
    for f in where.get("not") or []:
        if place.state.get(f):
            return "it cannot go up where it is " + f
    return None

def check(ctx):
    plan = ctx.target
    me = ctx.actor
    st = plan.state
    if me.state.down:
        return "you are down"
    if st.built and ctx.get(st.built) is not None:
        return "it is already built: the " + bare(ctx.get(st.built).name) + " stands at " + ctx.get(st.built).parent.name
    if st.project and ctx.get(st.project) is not None:
        return "it is already under way at " + ctx.get(st.project).parent.name + ": work on it there"
    if st.portable:
        if plan.parent is None or plan.parent.id != me.id:
            return "hold the plan to build from it: take it first"
        why = misfit(me.parent, st.where or {})
        if why:
            return why
    else:
        if plan.parent is None or me.parent is None or plan.parent.id != me.parent.id:
            return "the plan is marked out somewhere else: go there"
        patrons = st.patrons or []
        if patrons and not is_patron(me, patrons):
            return "this is for " + ", ".join(patrons) + " to start, not you"
    return True

def apply(ctx):
    plan = ctx.target
    me = ctx.actor
    st = plan.state
    site = me.parent
    becomes = dict(st.becomes or {})
    name = becomes.get("works_name") or ("Works on the " + bare(becomes.get("name") or plan.name))
    proj = ctx.spawn("project", site, name=name, pos=plan.pos if not st.portable else me.pos, state={
        "plan": plan.id, "plan_name": plan.name, "stages": list(st.stages or []), "stage": 0, "labour": 0,
        "becomes": becomes, "patron": me.id, "crew": {}, "hands": [], "hours": st.hours,
        "pay_every": st.pay_every or 86400, "paid_t": ctx.t, "last_t": ctx.t})
    ctx.patch(plan, {"project": proj.id})
    if st.portable:
        ctx.move(plan, proj)
    ctx.emit("scene", target=site, reach=1, works=proj.id,
             text=st.begun_scene or (me.name + " lays out the " + plan.name + " here, and the works begin."))
    ctx.remember(me, "I started the " + name.lower() + " at " + site.name + ", from the " + plan.name + ".")
    describe(ctx, proj)
    b = blockers(ctx, proj, None, None)
    ctx.log("begun: " + name + (" (to go on: " + "; ".join(b) + ")" if b else ""))
