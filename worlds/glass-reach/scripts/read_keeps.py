# A book that stays with its reader (Nate 2026-11-12, the Guild's shelf room): the rule sits on the book, and whoever
# reads it remembers what it said, once, so a mind that read it on Tuesday still knows it on Friday. What they keep is
# `keeps_in_mind` on the book's state (True for the whole text, or a shorter line of what sticks).

def on(ctx, event):
    if event.kind != "read" or event.target != ctx.self.id or not event.actor:
        return
    book = ctx.self
    keep = book.state.keeps_in_mind
    if not keep:
        return
    readers = list(book.state.read_by or [])
    if event.actor in readers:
        return
    text = book.state.text if keep is True else keep
    ctx.remember(event.actor, "I read " + book.name + ". " + str(text or ""))
    ctx.patch(book, {"read_by": readers + [event.actor]})
