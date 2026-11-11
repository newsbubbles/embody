use("works")

def guards(ctx, proj):
    n = 0
    for wid, c in (proj.state.crew or {}).items():
        if c.get("role") == "guard" and on_hand(ctx, proj, wid, None):
            n = n + 1
    return n

def check(ctx):
    proj = ctx.target
    st = proj.state
    if ctx.actor.state.down:
        return "you are down"
    if not at_site(proj, ctx.actor):
        return "you are not at the works"
    if st.settling_until is None or ctx.t >= float(st.settling_until):
        return "nothing here is soft enough to undo: only a stage that is still settling comes down"
    return True

def apply(ctx):
    ctx.emit("undoing", target=ctx.target, reach=1, by=ctx.actor.id, stage=ctx.target.state.settling_name)

def finish(ctx):
    proj = ctx.target
    me = ctx.actor
    if ctx.get(proj.id) is None:
        return
    st = proj.state
    if st.settling_until is None or ctx.t >= float(st.settling_until) or not at_site(proj, me) or me.state.down:
        ctx.log("too late: it has set, or you are not there to finish it")
        return
    roll = ctx.rand.roll("1d20")
    total = roll + int(me.state.body or 0)
    dc = 10 + 4 * guards(ctx, proj)
    name = str(st.settling_name)
    if total >= dc:
        i = int(st.settling_stage or 0)
        stage = (st.stages or [])[i]
        built = list(st.built_stages or [])
        if built and built[-1] == name:
            built = built[:-1]
        ctx.patch(proj, {"stage": i, "labour": 0, "settling_until": None, "settling_name": None, "settling_stage": None,
                         "built_stages": built})
        ctx.emit("scene", target=proj.parent, reach=1, works=proj.id,
                 text=stage.get("undone") or ("The " + name + " comes down while it is still soft. It will all have to be done again."))
        ctx.emit("undone", target=proj, reach=1, by=me.id, stage=name, roll=roll, total=total, dc=dc)
        describe(ctx, proj)
        ctx.log("undone: the " + name + " (" + str(total) + " against " + str(dc) + ")")
    else:
        ctx.emit("undo_failed", target=proj, reach=1, by=me.id, stage=name, roll=roll, total=total, dc=dc)
        ctx.log("it holds (" + str(total) + " against " + str(dc) + "), and anyone here saw you try")
