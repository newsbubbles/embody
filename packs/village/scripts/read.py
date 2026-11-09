def apply(ctx):
    text = ctx.target.state.text or "nothing is written on it"
    ctx.emit("read", target=ctx.target, reach=0, text=text)
    ctx.log(text)
    return text
