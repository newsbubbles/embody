use("works")
def apply(ctx):
    plan = ctx.target
    st = plan.state
    b = st.becomes or {}
    lines = [st.text or ("A plan for the " + bare(b.get("name") or "something") + ".")]
    lines.append("It makes: " + str(b.get("name")) + ".")
    for s in st.stages or []:
        needs = s.get("needs") or {}
        roles = s.get("roles") or {}
        parts = [str(s.get("labour")) + " hours of work"]
        if needs:
            parts.append("needs " + ", ".join([str(needs[k]) + " " + k for k in sorted(needs.keys())]))
        if roles:
            parts.append("wants " + ", ".join([str(roles[k]) + " " + k for k in sorted(roles.keys())]))
        if s.get("settles"):
            parts.append("then settles " + str(s.get("settles")) + " hours")
        lines.append("- " + str(s.get("name")) + ": " + "; ".join(parts))
    if st.portable:
        w = st.where or {}
        where = []
        if w.get("places"):
            where.append("at " + ", ".join(w.get("places")))
        for f in w.get("has") or []:
            where.append("on " + f + " ground")
        for f in w.get("not") or []:
            where.append("not where it is " + f)
        lines.append("Whoever holds it can build it " + (", ".join(where) if where else "anywhere") + ".")
    elif st.patrons:
        lines.append("It is for " + ", ".join(st.patrons) + " to start, here.")
    if st.built and ctx.get(st.built) is not None:
        lines.append("It has been built: the " + bare(ctx.get(st.built).name) + ".")
    elif st.project and ctx.get(st.project) is not None:
        lines.append("It is under way, at " + ctx.get(st.project).parent.name + ".")
    text = "\n".join(lines)
    ctx.emit("read", target=plan, reach=0, text=text)
    ctx.log(text)
    return text
