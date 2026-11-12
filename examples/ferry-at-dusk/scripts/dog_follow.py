def tick(ctx):
    me = ctx.self
    friend = me.state.friend
    if not friend:
        return
    f = ctx.get(friend)
    if f is None or f.parent is None:
        return
    if f.parent.id != me.parent.id:
        ctx.move(me, f.parent)
        ctx.say("pads in after you, tail going")
