use("works")
# The project's own clock: the crew nobody plays walks to the works in working hours and home after, works while it
# is there and nothing stops it, is paid at the turn of each pay day (or walks off after two days unpaid), and a
# settling stage sets. Minds and players work by `work`; their hours count in its finish, not here.

def step_to(ctx, w, place, why):
    ctx.move(w, place)
    ctx.emit("arrived", target=place, reach=1, who=w.id, place=place.id, quiet=True, works=why)

def pay(ctx, proj):
    st = proj.state
    if ctx.t - float(st.paid_t or 0) < float(st.pay_every or 86400):
        return
    ctx.patch(proj, {"paid_t": ctx.t})
    crew = st.crew or {}
    for wid in sorted(crew.keys()):
        c = crew[wid]
        wage = c.get("wage")
        w = ctx.get(wid)
        if c.get("how") != "hired" or not wage or w is None:
            continue
        n = int(wage.get("count") or 1)
        got = spend(ctx, proj, wage.get("kind"), n, w)
        if got >= n:
            ctx.patch(proj, {"crew": {wid: {"unpaid": 0}}})
            ctx.emit("paid", target=w, reach=1, works=proj.id, wage=wage)
            continue
        unpaid = int(c.get("unpaid") or 0) + 1
        if unpaid >= 2:
            release(ctx, proj, wid)
            ctx.patch(w, {"hired_by": None})
            ctx.emit("scene", target=proj.parent, reach=1, works=proj.id,
                     text=w.name + " puts down the tools and walks off the works: two days and no pay.")
            ctx.emit("quit", target=w, reach=1, works=proj.id, why="unpaid")
            ctx.remember(w, "I left the " + proj.name.lower() + " at " + site_name(proj) + ": they stopped paying me.")
        else:
            ctx.patch(proj, {"crew": {wid: {"unpaid": unpaid}}})
            ctx.emit("unpaid", target=w, reach=1, works=proj.id, wage=wage)
            ctx.emit("scene", target=proj.parent, reach=1, works=proj.id,
                     text=w.name + " counts the day's pay and finds none. \"One more day like this and I walk.\"")

def tick(ctx):
    proj = ctx.self
    st = proj.state
    site = proj.parent
    t = ctx.t
    last = float(st.last_t if st.last_t is not None else t)
    dt = min(3600.0, max(0.0, t - last))
    ctx.patch(proj, {"last_t": t})
    crew = st.crew or {}
    for wid in list(crew.keys()):
        w = ctx.get(wid)
        if w is None or w.state.dead:
            release(ctx, proj, wid)
    pay(ctx, proj)
    if st.settling_until is not None and t >= float(st.settling_until):
        name = st.settling_name
        ctx.patch(proj, {"settling_until": None, "settling_name": None, "settling_stage": None})
        ctx.emit("settled", target=proj, reach=1, stage=name)
        if stage_of(proj) is None:
            complete(ctx, proj)
            return
    hours = in_hours(ctx, proj)
    working = []
    crew = proj.state.crew or {}
    for wid in sorted(crew.keys()):
        w = ctx.get(wid)
        c = crew[wid]
        if w is None or ctx.embodied(w) or w.state.down:
            continue
        thirsty = w.state.water is not None and int(w.state.water) <= 3
        if hours and not thirsty and not at_site(proj, w) and adjacent(ctx, w.parent, site):
            step_to(ctx, w, site, proj.id)
        elif not hours and at_site(proj, w) and c.get("home") and c.get("home") != site.id:
            home = ctx.get(c.get("home"))
            if home is not None and adjacent(ctx, site, home):
                step_to(ctx, w, home, None)
        if hours and at_site(proj, w) and not thirsty:
            working.append(w)
    stage = stage_of(proj)
    if stage is not None and hours and dt > 0 and not blockers(ctx, proj, None, None):
        roles = stage.get("roles") or {}
        who = []
        for w in working:
            if crew[w.id].get("role") in roles:
                who.append(w.id)
                toil = float(w.state.toil or 0) + dt / 3600
                if toil >= 2 and w.state.water is not None:
                    ctx.patch(w, {"toil": toil - 2, "water": max(0, int(w.state.water) - 1)})
                else:
                    ctx.patch(w, {"toil": toil})
        if who:
            add_labour(ctx, proj, len(who) * dt / 3600, who)
    if ctx.get(proj.id) is not None:
        describe(ctx, proj)
