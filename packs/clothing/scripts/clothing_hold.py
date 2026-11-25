use("clothing")

# hold: take a thing you have in hand, from where it hangs or from your pack (params {"hand": "left" or "right"}); a
# thing with hands 2 takes both.

def holding(me, hand):
    return [c.name for c in me.children() if on_me(me, c) and c.state.in_hand in [hand, "both"]]

def check(ctx):
    me = ctx.actor
    it = ctx.target
    if it.parent is None or it.parent.id != me.id:
        return "you do not have " + it.name
    if is_worn(me, it) or (it.state.donning and on_me(me, it)):
        return "you are wearing " + it.name
    if "hands" not in plan_of(me):
        return "a " + species_of(me) + " has no hands to hold it"
    if it.state.in_hand and on_me(me, it):
        return it.name + " is already in your " + LABELS[it.state.in_hand]
    free = free_hands(me, it)
    hand = lower((ctx.params or {}).get("hand"))
    if it.state.hands == 2:
        if len(free) < 2:
            full = "right" if "right" not in free else "left"
            return it.name + " takes both hands: your " + full + " hand holds " + join_and(holding(me, full)) + " (stow it first)"
        return True
    if hand in ["left", "right"]:
        if hand not in free:
            return "your " + hand + " hand holds " + join_and(holding(me, hand)) + ": use the other, or stow it first"
        return True
    if hand:
        return "say which hand: left or right"
    if not free:
        return hand_check(me, it)
    return True

def apply(ctx):
    me = ctx.actor
    it = ctx.target
    free = free_hands(me, it)
    hand = lower((ctx.params or {}).get("hand"))
    if it.state.hands == 2:
        hand = "both"
    elif hand not in ["left", "right"]:
        hand = free[0]
    ctx.patch(it, {"on": me.id, "in_hand": hand, "stowed_at": None, "stowed_on": None})
    refresh(ctx, me)
    ctx.emit("holding", target=me, reach=1, by=me.id, item=it.id, name=it.name, hand=hand)
    ctx.log(it.name + " in your " + LABELS[hand])
    return {"item": it.name, "hand": hand}
