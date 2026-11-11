# Shared by the works verbs and the project's tick (packs/works/pack.py says what a blueprint and a project hold).

def units(it):
    # a thing is one unit, unless it is a stack with a count
    return int(it.state.count or 1)

def matches(it, key):
    return it.name == key or it.state.kind == key

def have(ctx, holder, key):
    n = 0
    for it in ctx.children(holder):
        if matches(it, key):
            n = n + units(it)
    return n

def spend(ctx, holder, key, n, to):
    # n units of key out of the holder: used up (to None) or handed to `to`; returns how many came out
    got = 0
    for it in ctx.children(holder):
        if got >= n:
            break
        if not matches(it, key):
            continue
        u = units(it)
        if u <= n - got:
            if to is None:
                ctx.destroy(it)
            else:
                ctx.transfer(it, to)
            got = got + u
        else:
            k = n - got
            if to is None:
                ctx.patch(it, {"count": u - k})
            else:
                ctx.transfer(it, to, k)
            got = n
    return got

def stage_of(proj):
    stages = proj.state.stages or []
    i = int(proj.state.stage or 0)
    if i < len(stages):
        return stages[i]
    return None

def plan_here(ctx, proj):
    plan = ctx.get(proj.state.plan) if proj.state.plan else None
    if plan is None or plan.parent is None:
        return False
    if plan.parent.id == proj.id:
        return True
    return not plan.state.portable and proj.parent is not None and plan.parent.id == proj.parent.id

def at_site(proj, who):
    return who is not None and who.parent is not None and proj.parent is not None and who.parent.id == proj.parent.id

def on_hand(ctx, proj, wid, extra):
    # in the crew, at the site, on their feet; someone a mind or a player holds counts only while working
    if wid == extra:
        return True
    w = ctx.get(wid)
    if w is None or w.state.dead or w.state.down or not at_site(proj, w):
        return False
    if ctx.embodied(w):
        c = (proj.state.crew or {}).get(wid) or {}
        return float(c.get("busy_until") or 0) >= ctx.t
    return True

def role_of(proj, wid, extra, extra_role):
    if wid == extra:
        return extra_role
    return ((proj.state.crew or {}).get(wid) or {}).get("role")

def blockers(ctx, proj, extra, extra_role):
    # what stops the work now, each with what to do about it; [] means it can go on
    out = []
    st = proj.state
    if st.settling_until is not None and ctx.t < float(st.settling_until):
        hrs = round((float(st.settling_until) - ctx.t) / 3600, 1)
        out.append("the " + str(st.settling_name) + " is settling, " + str(hrs) + " more hours: nothing goes on it until it has")
        return out
    stage = stage_of(proj)
    if stage is None:
        out.append("it is finished")
        return out
    if not plan_here(ctx, proj) and float(st.labour or 0) <= 0:
        out.append("the plan is not in the works: nobody knows what comes next until someone puts it back (supply it)")
    needs = stage.get("needs") or {}
    for key in sorted(needs.keys()):
        short = int(needs[key]) - have(ctx, proj, key)
        if short > 0:
            out.append("needs " + str(short) + " more " + key + ": supply it")
    roles = stage.get("roles") or {}
    crew = st.crew or {}
    ids = list(crew.keys())
    if extra is not None and extra not in crew:
        ids.append(extra)
    for role in sorted(roles.keys()):
        n = 0
        for wid in ids:
            if role_of(proj, wid, extra, extra_role) == role and on_hand(ctx, proj, wid, extra):
                n = n + 1
        if n < int(roles[role]):
            out.append("no " + role + " at work (" + str(n) + " of " + str(roles[role]) + "): assign one, hire one, or work as one yourself")
    return out

def capacity(proj, role):
    # a role holds as many as the stage that wants the most of it
    m = 0
    for s in proj.state.stages or []:
        m = max(m, int((s.get("roles") or {}).get(role) or 0))
    return m

def filled(proj, role):
    n = 0
    for wid, c in (proj.state.crew or {}).items():
        if c.get("role") == role:
            n = n + 1
    return n

def in_hours(ctx, proj):
    hours = proj.state.hours
    if not hours:
        return True
    h = (ctx.t % 86400) / 3600
    a = float(hours[0])
    b = float(hours[1])
    if a <= b:
        return a <= h and h < b
    return h >= a or h < b

def describe(ctx, proj):
    st = proj.state
    becomes = (st.becomes or {}).get("name") or "something"
    stage = stage_of(proj)
    if stage is None:
        text = "The works on the " + becomes + ", all but done."
    else:
        text = ("The works on the " + becomes + ": the " + str(stage.get("name")) + " is " +
                str(round(float(st.labour or 0), 1)) + " of " + str(stage.get("labour")) + " hours along")
        b = blockers(ctx, proj, None, None)
        if b:
            text = text + "; " + b[0].split(":")[0]
        text = text + "."
    if st.description != text:
        ctx.patch(proj, {"description": text})

def release(ctx, proj, wid):
    ctx.patch(proj, {"crew": {wid: None}})
    w = ctx.get(wid)
    if w is not None and w.state.works_on == proj.id:
        ctx.patch(w, {"works_on": None, "role": None})

def adjacent(ctx, a, b):
    if a is None or b is None:
        return False
    for e in ctx.edges(a, "connects_to", "out"):
        if e["target"] == b.id:
            return True
    return False

def site_name(proj):
    return proj.parent.name if proj.parent is not None else "the site"

def add_labour(ctx, proj, hours, who):
    # labour on the stage now; the stage completes when it is owed no more
    st = proj.state
    stage = stage_of(proj)
    if stage is None:
        return
    done = float(st.labour or 0) + hours
    hands = list(st.hands or [])
    for w in who:
        if w not in hands:
            hands.append(w)
    ctx.patch(proj, {"labour": done, "hands": hands})
    if done >= float(stage.get("labour") or 0) - 0.001:  # six ten-minute shares make a whole hour
        stage_done(ctx, proj, stage)

def stage_done(ctx, proj, stage):
    st = proj.state
    needs = stage.get("needs") or {}
    for key in needs.keys():
        spend(ctx, proj, key, int(needs[key]), None)
    i = int(st.stage or 0)
    becomes = (st.becomes or {}).get("name") or "works"
    ctx.emit("scene", target=proj.parent, reach=1, text=stage.get("scene") or ("The " + str(stage.get("name")) + " of the " + becomes + " is done."),
             works=proj.id, stage=stage.get("name"))
    for wid in (st.crew or {}).keys():
        if on_hand(ctx, proj, wid, None):
            ctx.remember(wid, "I worked on the " + str(stage.get("name")) + " of the " + becomes + " at " + site_name(proj) + "; it is done.")
    changes = {"stage": i + 1, "labour": 0, "built_stages": list(st.built_stages or []) + [stage.get("name")]}
    if stage.get("settles"):
        changes["settling_until"] = ctx.t + float(stage.get("settles")) * 3600
        changes["settling_name"] = stage.get("name")
        changes["settling_stage"] = i
    ctx.patch(proj, changes)
    ctx.emit("stage_done", target=proj, reach=1, stage=stage.get("name"), settles=stage.get("settles"))
    if i + 1 >= len(st.stages or []) and not stage.get("settles"):
        complete(ctx, proj)

def complete(ctx, proj):
    # the last stage stands: the thing is born with who made it and who saw it, and the works come down
    st = proj.state
    site = proj.parent
    b = st.becomes or {}
    name = b.get("name") or "Works"
    hands = list(st.hands or [])
    state = dict(b.get("state") or {})
    state["provenance"] = {"how": "built", "by": hands, "t": ctx.t, "patron": st.patron, "plan": st.plan}
    new = ctx.spawn(b.get("type") or "thing", site, name=name, state=state, pos=proj.pos)
    ctx.emit("scene", target=site, reach=1, text=b.get("scene") or ("The " + name + " stands finished. The works come down."),
             introduced=new.id, how="built", works=proj.id)
    for w in hands:
        if ctx.get(w) is not None:
            ctx.remember(w, "I helped build the " + name + " at " + site.name + ".")
    if st.patron and st.patron not in hands and ctx.get(st.patron) is not None:
        ctx.remember(st.patron, "I had the " + name + " built at " + site.name + ".")
    for p in ctx.children(site):
        if p.id not in hands and p.id != st.patron and p.is_a("creature") and not p.state.dead:
            ctx.remember(p, "I saw the " + name + " finished at " + site.name + ".")
    for wid in list((st.crew or {}).keys()):
        release(ctx, proj, wid)
    plan = ctx.get(st.plan) if st.plan else None
    if plan is not None:
        ctx.patch(plan, {"project": None, "built": new.id})
    for it in ctx.children(proj):
        ctx.move(it, site)
    ctx.emit("works_done", target=site, reach=1, works=proj.id, made=new.id)
    ctx.destroy(proj)
