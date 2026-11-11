use("works")

def hand(ctx):
    want = (ctx.params or {}).get("who")
    for p in ctx.find(name=want, limit=10):
        if p.is_a("creature"):
            return p
    return ctx.get(want)

def check(ctx):
    proj = ctx.target
    me = ctx.actor
    p = ctx.params or {}
    if "who" not in p:
        return "say who: params {\"who\": <name>, \"role\": <role>}"
    who = hand(ctx)
    if who is None:
        return "nobody of that name"
    if me.id != proj.state.patron:
        return "only the one who started the works hires for them"
    offer = who.state.for_hire
    if not offer:
        return who.name + " is not looking for work"
    if ctx.embodied(who):
        return who.name + " has a mind of their own: talk terms with them"
    if not at_site(proj, who) and not adjacent(ctx, who.parent, proj.parent):
        return who.name + " is too far off: they must be here or one step away"
    if who.state.works_on and ctx.get(who.state.works_on) is not None:
        return who.name + " is already on works at " + ctx.get(who.state.works_on).parent.name
    role = p.get("role") or (offer.get("roles") or [None])[0]
    if not role:
        return "hire them as what? params {\"role\": ...}"
    if offer.get("roles") and role not in offer.get("roles"):
        return who.name + " works only as " + ", ".join(offer.get("roles"))
    if capacity(proj, role) == 0:
        return "these works want no " + role
    if filled(proj, role) >= capacity(proj, role):
        return "every " + role + "'s place is taken"
    wage = offer.get("wage") or {}
    if wage and have(ctx, proj, wage.get("kind")) < int(wage.get("count") or 1):
        return (who.name + " asks " + str(wage.get("count") or 1) + " " + str(wage.get("kind")) + " a day, paid from the works, "
                "and the works hold too little: supply it first")
    return True

def apply(ctx):
    proj = ctx.target
    me = ctx.actor
    who = hand(ctx)
    offer = who.state.for_hire
    role = (ctx.params or {}).get("role") or (offer.get("roles") or [None])[0]
    home = who.parent.id if who.parent is not None else None
    ctx.patch(proj, {"crew": {who.id: {"role": role, "how": "hired", "by": me.id, "wage": offer.get("wage"),
                                       "unpaid": 0, "home": home}}})
    ctx.patch(who, {"works_on": proj.id, "role": role, "hired_by": me.id})
    ctx.emit("hired", target=proj, reach=1, who=who.id, role=role, by=me.id)
    ctx.remember(who, me.name + " hired me as " + role + " on the " + proj.name.lower() + " at " + site_name(proj) + ".")
    if offer.get("line"):
        ctx.emit("scene", target=proj.parent, reach=1, works=proj.id, text=who.name + ": \"" + offer.get("line") + "\"")
    describe(ctx, proj)
    ctx.log(who.name + " is hired as " + role)
