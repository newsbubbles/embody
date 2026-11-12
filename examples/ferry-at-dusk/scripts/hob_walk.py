def tick(ctx):
    me = ctx.self
    st = me.state
    if st.asleep:
        return
    dest = st.haunt if me.parent.id == st.home else st.home
    ctx.move(me, dest)
    ctx.emit("arrived", target=dest, reach=-1, who=me.id, place=dest)
    ctx.say(ctx.rand.choice(st.lines))
