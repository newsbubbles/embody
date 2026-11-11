use("works")

def apply(ctx):
    proj = ctx.target
    st = proj.state
    lines = []
    stage = stage_of(proj)
    becomes = (st.becomes or {}).get("name") or "works"
    done = st.built_stages or []
    lines.append("The " + becomes + ". Done: " + (", ".join(done) if done else "nothing yet") + ".")
    if stage is not None:
        lines.append("Now: the " + str(stage.get("name")) + ", " + str(round(float(st.labour or 0), 1)) + " of " +
                     str(stage.get("labour")) + " hours of work.")
        needs = stage.get("needs") or {}
        for key in sorted(needs.keys()):
            lines.append("  " + key + ": " + str(have(ctx, proj, key)) + " of " + str(needs[key]) + " here")
        roles = stage.get("roles") or {}
        for role in sorted(roles.keys()):
            lines.append("  " + role + ": wants " + str(roles[role]))
    crew = st.crew or {}
    for wid in sorted(crew.keys()):
        w = ctx.get(wid)
        c = crew[wid]
        if w is not None:
            lines.append("  crew: " + w.name + ", " + str(c.get("role")) + " (" + str(c.get("how")) + ")" +
                         ("" if at_site(proj, w) else ", not here"))
    b = blockers(ctx, proj, None, None)
    lines.append("Stopping it: " + ("; ".join(b) if b else "nothing; it goes on while the crew is here"))
    if st.hours:
        lines.append("Working hours: " + str(st.hours[0]) + " to " + str(st.hours[1]) + ".")
    text = "\n".join(lines)
    ctx.emit("surveyed", target=proj, reach=0, text=text, by=ctx.actor.id)
    ctx.log(text)
    return text
