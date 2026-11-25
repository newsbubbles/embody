use("clothing")

# sew: make a garment from cloth you carry, with this kit in hand. An hour of work; the cloth is spent when it is done,
# if you still have the kit and the cloth and stand where you started. The cloth gives its material and colour (dye
# is the world's); the sewer gives the rest in params (README, "Sewing"). A needle makes no armour, and only leather
# takes a mount (a belt). Tags (a uniform's mark) are the world's to give: sewing makes none.

TEXT_MAX = {"name": 40, "garment": 30, "cut": 30, "pattern": 40, "condition": 30, "look": 200, "detail": 300}

def cloth_of(ctx, me):
    ref = (ctx.params or {}).get("from")
    if ref:
        c = find_held(me, ref)
        return c if (c is not None and c.state.cloth) else None
    for c in me.children():
        if c.state.cloth:
            return c
    return None

def slot_list(me, xs):
    # the slots asked for, lower case, each one the pack knows or a region of the sewer's own plan; else a string
    if isinstance(xs, str):
        xs = [xs]
    out = []
    plan = plan_of(me)
    for x in xs or []:
        s = lower(x).replace(" ", "_")
        if s not in SLOTS and s not in plan:
            return "no slot " + s + ": one of " + ", ".join(SLOTS)
        if s not in out:
            out.append(s)
    return out

def need_of(slots, hangs, layer, size, accessory):
    if accessory:
        return 1
    n = 0
    for s in slots:
        n = n + CLOTH_PER_SLOT.get(s, 1)
    if hangs:
        n = n + 1
    if layer == "outer":
        n = n + 1
    if size in ["l", "xl", "xxl"]:
        n = n + 1
    return n

def plan_sew(ctx):
    me = ctx.actor
    kit = ctx.get(ctx.target.id)
    p = ctx.params or {}
    if kit is None or kit.parent is None or kit.parent.id != me.id:
        return "take the kit first: you sew with it in hand"
    state = {}
    for k, most in TEXT_MAX.items():
        v = p.get(k)
        if v is None:
            continue
        v = str(v).strip()
        if len(v) > most:
            return k + " is at most " + str(most) + " characters"
        if ctx.leak(v):
            return "the " + k + " gives the table away (" + str(ctx.leak(v)) + "): say it in the world's words"
        state[k] = v
    if not state.get("name"):
        return "name it: params {\"name\": what people call it, \"garment\": coat, shirt, boots..., and the rest (README)}"
    det = p.get("details") or []
    if isinstance(det, str):
        det = [det]
    if len(det) > 6:
        return "six details at most"
    for d in det:
        if len(str(d)) > 60 or ctx.leak(str(d)):
            return "a detail is a short phrase in the world's words (60 characters at most)"
    kind = lower(state.get("garment")).replace(" ", "_")
    base = GARMENTS.get(kind) or {}
    slots = slot_list(me, p.get("slots") or base.get("slots"))
    if isinstance(slots, str):
        return slots
    if not slots:
        return "say what it is: a garment the pack knows (" + ", ".join(list(GARMENTS.keys())[:12]) + "...) or its slots and layer"
    hangs = slot_list(me, p.get("hangs") or base.get("hangs") or [])
    if isinstance(hangs, str):
        return hangs
    layer = lower(p.get("layer") or base.get("layer") or "main")
    if layer not in LAYERS:
        return "the layer is one of " + ", ".join(LAYERS)
    if layer == "armor" or base.get("fit") == "exact" or p.get("armor"):
        return "a needle does not make armour: that is a smith's work"
    cloth = cloth_of(ctx, me)
    if cloth is None:
        return "you have no cloth to sew it from (a thing whose state says cloth)"
    material = str(cloth.state.material or "cloth")
    mounts = base.get("mounts") or []
    if mounts and "leather" not in lower(material):
        return "a " + kind.replace("_", " ") + " that carries things is sewn from leather, not " + material
    size = lower(p.get("size") or me.state.size or "m")
    if size not in SIZES:
        return "the size is one of " + ", ".join(SIZES)
    accessory = bool(p.get("accessory") if p.get("accessory") is not None else base.get("accessory"))
    need = need_of(slots, hangs, layer, size, accessory)
    have = ctx.count(cloth)
    if have < need:
        return "this takes " + str(need) + " of " + cloth.name + ": you have " + str(have)
    modes = {}
    for k, v in (base.get("modes") or {}).items():
        modes[k] = v
    if p.get("hood"):
        modes["hood_up"] = {"adds": ["head"], "line": "hood up"}
    if p.get("opens"):
        modes["open"] = {"reveals": ["torso", "chest"], "line": "open"}
    if p.get("sleeves"):
        modes["sleeves_rolled"] = {"reveals": ["arms"], "line": "sleeves rolled"}
    state.update({"garment": kind if kind else None, "slots": slots, "hangs": hangs, "layer": layer, "size": size,
                  "material": material, "color": cloth.state.color, "details": [str(d) for d in det],
                  "modes": modes, "accessory": accessory, "made_by": me.id, "portable": True})
    if p.get("plural") is not None:
        state["plural"] = bool(p.get("plural"))
    if p.get("warmth") is not None:
        state["warmth"] = max(0, min(3, int(p.get("warmth"))))
    return {"name": state.pop("name"), "state": state, "cloth": cloth.id, "need": need}

def check(ctx):
    r = plan_sew(ctx)
    return r if isinstance(r, str) else True

def apply(ctx):
    here = ctx.actor.parent
    ctx.patch(ctx.target, {"sewing": {"by": ctx.actor.id, "at": here.id if here is not None else None}})
    r = plan_sew(ctx)
    ctx.log("you cut " + str(r["need"]) + " of the cloth and start to sew " + r["name"] + ": an hour, here, with the kit")

def finish(ctx):
    me = ctx.actor
    kit = ctx.get(ctx.target.id)
    if kit is None:
        return
    sw = kit.state.sewing or {}
    ctx.patch(kit, {"sewing": None})
    if sw.get("by") != me.id or me.parent is None or me.parent.id != sw.get("at"):
        ctx.log("you left the sewing before it was done")
        return
    r = plan_sew(ctx)
    if isinstance(r, str):
        ctx.log("the sewing stopped: " + r)
        return
    cloth = ctx.get(r["cloth"])
    piece = cloth if ctx.count(cloth) == r["need"] else ctx.split(cloth, r["need"])
    ctx.destroy(piece)
    made = ctx.spawn("garment", me, r["name"], state=r["state"])
    ctx.emit("sewn", target=me, reach=1, by=me.id, item=made.id, name=made.name)
    ctx.log("you finish " + made.name + ": wear it when you like")
