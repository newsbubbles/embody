# The clothing model, shared by the pack's verbs and its rule, and by a world's own scripts with use("clothing").
# A garment is worn in slots at a layer; what is over it in a slot hides it there. A carried thing hangs at a
# position from a mount (a worn carrier, or its own strap), or sits in a hand. packs/clothing/README.md is the guide.

SLOTS = ["head", "eyes", "face", "ears", "neck", "shoulders", "torso", "back", "arms", "wrists", "hands", "fingers",
         "waist", "legs", "feet"]
# the body region a slot needs in the wearer's plan (looks.regions), and the regions it covers when worn
SLOT_NEEDS = {"head": "head", "eyes": "eyes", "face": "face", "ears": "head", "neck": "neck", "shoulders": "arms",
              "torso": "torso", "back": "back", "arms": "arms", "wrists": "arms", "hands": "hands", "fingers": "hands",
              "waist": "torso", "legs": "legs", "feet": "feet"}
SLOT_COVERS = {"head": ["head", "hair"], "eyes": ["eyes"], "face": ["face"], "ears": [], "neck": ["neck"],
               "shoulders": [], "torso": ["torso"], "back": ["back"], "arms": ["arms"], "wrists": [], "hands": ["hands"],
               "fingers": [], "waist": [], "legs": ["legs"], "feet": ["feet"]}
REGIONS = ["head", "face", "eyes", "hair", "neck", "torso", "back", "arms", "hands", "legs", "feet", "skin"]
LAYERS = ["skin", "under", "main", "over", "armor", "outer"]
DON_S = {"skin": 30, "under": 20, "main": 30, "over": 40, "armor": 180, "outer": 10}
ACCESSORY_S = 5
ACCESSORY_CAP = {"fingers": 8, "ears": 4, "wrists": 4}
HELP_X = 3  # a needs_help garment put on alone takes this many times as long (taken off alone: two)
SIZES = ["xs", "s", "m", "l", "xl", "xxl"]

POSITIONS = ["hip_left", "hip_right", "small_of_back", "back", "shoulder_left", "shoulder_right", "chest",
             "thigh_left", "thigh_right", "boot_left", "boot_right", "wrist_left", "wrist_right"]
POSITION_NEEDS = {"hip_left": "torso", "hip_right": "torso", "small_of_back": "back", "back": "back",
                  "shoulder_left": "arms", "shoulder_right": "arms", "chest": "torso", "thigh_left": "legs",
                  "thigh_right": "legs", "boot_left": "feet", "boot_right": "feet", "wrist_left": "arms",
                  "wrist_right": "arms"}
POSITION_ROOM = {"back": 2}
STRAP_POSITIONS = ["back", "shoulder_left", "shoulder_right"]
SMALL_POSITIONS = ["hip_left", "hip_right", "small_of_back", "chest", "thigh_left", "thigh_right", "boot_left",
                   "boot_right", "wrist_left", "wrist_right"]
LABELS = {"hip_left": "left hip", "hip_right": "right hip", "small_of_back": "small of the back", "back": "back",
          "shoulder_left": "left shoulder", "shoulder_right": "right shoulder", "chest": "chest",
          "thigh_left": "left thigh", "thigh_right": "right thigh", "boot_left": "left boot", "boot_right": "right boot",
          "wrist_left": "left wrist", "wrist_right": "right wrist", "left": "left hand", "right": "right hand",
          "both": "both hands"}

# What a kind of garment is when the thing does not say: its slots (occupied, they block), hangs (covered, they do
# not block), layer, and the rest. The thing's own fields win. A kind not listed needs slots and a layer of its own.
GARMENTS = {
    "arming_cap": {"slots": ["head"], "layer": "under"},
    "coif": {"slots": ["head", "neck"], "layer": "under"},
    "cap": {"slots": ["head"]},
    "hat": {"slots": ["head"]},
    "headscarf": {"slots": ["head"]},
    "turban": {"slots": ["head"]},
    "hood": {"slots": ["head", "neck"], "layer": "outer"},
    "helm": {"slots": ["head"], "layer": "armor", "fit": "exact"},
    "visored_helm": {"slots": ["head"], "layer": "armor", "fit": "exact",
                     "modes": {"visor_down": {"adds": ["face", "eyes"], "line": "visor down"}}},
    "circlet": {"slots": ["head"], "layer": "outer", "accessory": True},
    "crown": {"slots": ["head"], "layer": "outer", "accessory": True},
    "spectacles": {"slots": ["eyes"], "conceals": False, "plural": True},
    "goggles": {"slots": ["eyes"], "plural": True},
    "eyepatch": {"slots": ["eyes"]},
    "mask": {"slots": ["face"]},
    "veil": {"slots": ["face"], "conceals": False},
    "earring": {"slots": ["ears"], "layer": "skin", "accessory": True},
    "necklace": {"slots": ["neck"], "accessory": True},
    "amulet": {"slots": ["neck"], "accessory": True},
    "pendant": {"slots": ["neck"], "accessory": True},
    "torc": {"slots": ["neck"], "accessory": True},
    "scarf": {"slots": ["neck"], "layer": "over"},
    "collar": {"slots": ["neck"]},
    "gorget": {"slots": ["neck"], "layer": "armor", "fit": "exact"},
    "pauldrons": {"slots": ["shoulders"], "layer": "armor", "plural": True, "fit": "exact"},
    "mantle": {"slots": ["shoulders", "back"], "layer": "outer"},
    "shawl": {"slots": ["shoulders", "back"], "layer": "over"},
    "breastband": {"slots": ["torso"], "layer": "skin"},
    "undershirt": {"slots": ["torso", "back"], "layer": "skin"},
    "chemise": {"slots": ["torso", "back", "arms"], "layer": "under", "hangs": ["legs"]},
    "shirt": {"slots": ["torso", "back", "arms"], "layer": "under",
              "modes": {"sleeves_rolled": {"reveals": ["arms"], "line": "sleeves rolled"}}},
    "blouse": {"slots": ["torso", "back", "arms"], "layer": "under",
               "modes": {"sleeves_rolled": {"reveals": ["arms"], "line": "sleeves rolled"}}},
    "tunic": {"slots": ["torso", "back", "arms"], "hangs": ["legs"]},
    "dress": {"slots": ["torso", "back", "legs"]},
    "gown": {"slots": ["torso", "back", "arms", "legs"]},
    "robe": {"slots": ["torso", "back", "arms"], "hangs": ["legs"]},
    "corset": {"slots": ["torso", "back"], "layer": "over"},
    "vest": {"slots": ["torso", "back"], "layer": "over"},
    "waistcoat": {"slots": ["torso", "back"], "layer": "over"},
    "doublet": {"slots": ["torso", "back", "arms"], "layer": "over"},
    "jerkin": {"slots": ["torso", "back"], "layer": "over"},
    "apron": {"slots": ["torso"], "layer": "over", "hangs": ["legs"]},
    "gambeson": {"slots": ["torso", "back", "arms"], "layer": "over", "hangs": ["legs"]},
    "mail": {"slots": ["torso", "back", "arms"], "layer": "armor", "hangs": ["legs"], "needs_help": True},
    "hauberk": {"slots": ["torso", "back", "arms"], "layer": "armor", "hangs": ["legs"], "needs_help": True},
    "brigandine": {"slots": ["torso", "back"], "layer": "armor", "fit": "exact"},
    "cuirass": {"slots": ["torso", "back"], "layer": "armor", "fit": "exact", "needs_help": True},
    "breastplate": {"slots": ["torso"], "layer": "armor", "fit": "exact"},
    "coat": {"slots": ["torso", "back", "arms"], "layer": "outer", "hangs": ["legs"],
             "hides": ["small_of_back", "chest", "hip_left", "hip_right"],
             "modes": {"open": {"reveals": ["torso", "chest", "hip_left", "hip_right"], "line": "open"}}},
    "jacket": {"slots": ["torso", "back", "arms"], "layer": "outer", "hides": ["small_of_back", "chest"],
               "modes": {"open": {"reveals": ["torso", "chest"], "line": "open"}}},
    "cloak": {"slots": ["shoulders"], "layer": "outer", "hangs": ["back", "torso", "arms"],
              "hides": ["back", "small_of_back", "hip_left", "hip_right", "chest"],
              "modes": {"thrown_back": {"reveals": ["torso", "arms", "hip_left", "hip_right", "chest"],
                                        "line": "thrown back over the shoulders"}}},
    "hooded_cloak": {"slots": ["shoulders"], "layer": "outer", "hangs": ["back", "torso", "arms"],
                     "hides": ["back", "small_of_back", "hip_left", "hip_right", "chest"],
                     "modes": {"hood_up": {"adds": ["head"], "line": "hood up"},
                               "thrown_back": {"reveals": ["torso", "arms", "hip_left", "hip_right", "chest"],
                                               "line": "thrown back over the shoulders"}}},
    "cape": {"slots": ["shoulders"], "layer": "outer", "hangs": ["back"]},
    "poncho": {"slots": ["torso", "back"], "layer": "outer", "hangs": ["arms"], "hides": ["hip_left", "hip_right", "chest"]},
    "tabard": {"slots": ["torso", "back"], "layer": "outer", "hangs": ["legs"]},
    "surcoat": {"slots": ["torso", "back"], "layer": "outer", "hangs": ["legs"]},
    "bracers": {"slots": ["wrists"], "layer": "armor", "plural": True},
    "vambraces": {"slots": ["wrists"], "layer": "armor", "plural": True},
    "bracelet": {"slots": ["wrists"], "accessory": True},
    "armlet": {"slots": ["arms"], "layer": "outer", "accessory": True},
    "gloves": {"slots": ["hands"], "plural": True},
    "mittens": {"slots": ["hands"], "plural": True},
    "gauntlets": {"slots": ["hands"], "layer": "armor", "plural": True},
    "ring": {"slots": ["fingers"], "layer": "skin", "accessory": True},
    "belt": {"slots": ["waist"], "mounts": ["hip_left", "hip_right", "small_of_back"]},
    "swordbelt": {"slots": ["waist"], "mounts": ["hip_left", "hip_right"]},
    "sash": {"slots": ["waist"], "layer": "over"},
    "baldric": {"slots": ["shoulders"], "layer": "over", "accessory": True, "mounts": ["back", "hip_left"]},
    "bandolier": {"slots": ["shoulders"], "layer": "over", "accessory": True, "mounts": ["chest"]},
    "thigh_holster": {"slots": ["legs"], "layer": "outer", "accessory": True, "mounts": ["thigh_right"]},
    "wrist_sheath": {"slots": ["wrists"], "layer": "under", "accessory": True, "mounts": ["wrist_left"]},
    "loincloth": {"slots": ["legs"], "layer": "skin"},
    "smallclothes": {"slots": ["legs"], "layer": "skin", "plural": True},
    "hose": {"slots": ["legs", "feet"], "layer": "under", "plural": True},
    "stockings": {"slots": ["legs", "feet"], "layer": "under", "plural": True},
    "leggings": {"slots": ["legs"], "layer": "under", "plural": True},
    "trousers": {"slots": ["legs"], "plural": True},
    "breeches": {"slots": ["legs"], "plural": True},
    "shorts": {"slots": ["legs"], "plural": True},
    "skirt": {"slots": ["legs"]},
    "kilt": {"slots": ["legs"]},
    "greaves": {"slots": ["legs"], "layer": "armor", "plural": True, "fit": "exact"},
    "chausses": {"slots": ["legs", "feet"], "layer": "armor", "plural": True, "needs_help": True},
    "socks": {"slots": ["feet"], "layer": "under", "plural": True},
    "shoes": {"slots": ["feet"], "plural": True},
    "boots": {"slots": ["feet"], "plural": True},
    "sandals": {"slots": ["feet"], "plural": True, "conceals": False},
    "slippers": {"slots": ["feet"], "plural": True},
    "sabatons": {"slots": ["feet"], "layer": "armor", "plural": True, "fit": "exact"},
}
SPEC_DEFAULTS = {"slots": [], "hangs": [], "layer": "main", "accessory": False, "plural": False, "mounts": [],
                 "modes": {}, "conceals": None, "needs_help": False, "hides": [], "fit": None}
CLOTH_PER_SLOT = {"torso": 2, "legs": 2, "back": 1, "arms": 1}


def lower(x):
    return str(x or "").strip().lower()


def join_or(words):
    words = [str(w) for w in words if w]
    if len(words) < 2:
        return "".join(words)
    return ", ".join(words[:-1]) + " or " + words[-1]


def join_and(words):
    words = [str(w) for w in words if w]
    if len(words) < 2:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def cap1(text):
    text = str(text)
    return text[:1].upper() + text[1:]


def kind_of(it):
    return lower(it.state.garment).replace(" ", "_")


def spec(it):
    # the garment as worn: the thing's own fields over its kind's (GARMENTS) over the defaults
    base = GARMENTS.get(kind_of(it)) or {}
    out = {}
    for k, d in SPEC_DEFAULTS.items():
        v = it.state.get(k)
        if v is None or v == [] or v == {}:
            v = base.get(k, d)
        out[k] = v
    if out["conceals"] is None:
        out["conceals"] = not out["accessory"]  # a ring or a pin hides nothing under it
    if out["layer"] not in LAYERS:
        out["layer"] = "main"
    if it.state.armor and not out["fit"]:
        out["fit"] = "exact"
    if out["layer"] == "armor" and not out["fit"]:
        out["fit"] = "exact"
    return out


def wearable(it):
    return len(spec(it)["slots"]) > 0


def layer_n(sp):
    return LAYERS.index(sp["layer"])


def plan_of(body):
    # the body's regions: its looks plan (the human twelve when it names none) and any a grown or replaced mark added
    lk = body.state.looks or {}
    regs = list(lk.get("regions") or REGIONS)
    for m in (lk.get("marks") or {}).values():
        if isinstance(m, dict) and m.get("kind") in ["grown", "replaced"] and m.get("where") not in regs:
            regs.append(m.get("where"))
    return regs


def slot_need(slot):
    return SLOT_NEEDS.get(slot) or slot  # a slot not in SLOTS is a region of the body's own plan (a tail, flanks)


def species_of(body):
    return str(body.state.species or body.type).replace("_", " ")


def on_me(me, it):
    # a thing's worn, hung or held state counts only while the body it names still has it
    return it.parent is not None and it.parent.id == me.id and it.state.on == me.id


def is_worn(me, it):
    return on_me(me, it) and bool(it.state.worn)


def busy(me):
    # the garment this body is getting into or out of, if any
    for it in me.children():
        d = it.state.donning
        if d and d.get("by") == me.id and it.parent.id == me.id:
            return it
    return None


def worn_list(me):
    return [it for it in me.children() if is_worn(me, it)]


def modes_on(it, sp):
    return [m for m in (it.state.modes_on or []) if m in sp["modes"]]


def mode_list(it, sp, key):
    out = []
    for m in modes_on(it, sp):
        for s in (sp["modes"][m].get(key) or []):
            if s not in out:
                out.append(s)
    return out


def area(it, sp):
    # where the garment is: its slots, what it hangs over, what a mode adds (a hood up adds the head)
    out = []
    for s in sp["slots"] + sp["hangs"] + mode_list(it, sp, "adds"):
        if s not in out:
            out.append(s)
    return out


def covering(it, sp):
    # the slots it hides what is under in: its area less what a mode lays open; nothing when it does not conceal
    if not sp["conceals"]:
        return []
    off = mode_list(it, sp, "reveals")
    return [s for s in area(it, sp) if s not in off]


def hides_at(it, sp):
    # the carry positions a closed outer garment hides
    off = mode_list(it, sp, "reveals")
    return [p for p in sp["hides"] if p not in off] if sp["conceals"] else []


def over_at(me, it, sp, slot, worn):
    # the garment over this one at a slot, if one hides it there
    n = layer_n(sp)
    best = None
    for j in worn:
        if j.id == it.id:
            continue
        sj = spec(j)
        if layer_n(sj) > n and slot in covering(j, sj):
            if best is None or layer_n(sj) > layer_n(spec(best)):
                best = j
    return best


def shown_slots(me, it, sp, worn):
    return [s for s in area(it, sp) if over_at(me, it, sp, s, worn) is None]


def regions_covered(it, sp):
    out = []
    for s in covering(it, sp):
        for r in SLOT_COVERS.get(s, [s]):
            if r not in out:
                out.append(r)
    return out


def size_word(body, it, sp):
    # "" when it fits, "loose" or "tight" one size off, else why it will not go on
    want = lower(it.state.size)
    if not want or it.state.adjustable or want not in SIZES:
        return ""
    have = lower(body.state.size) or "m"
    if have not in SIZES:
        return ""
    d = SIZES.index(want) - SIZES.index(have)
    if d == 0:
        return ""
    if sp["fit"] == "exact":
        return "no:" + it.name + " is cut for a " + want.upper() + " frame and armour must fit: " + body.name + " is " + have.upper() + " (alter it, or find one that fits)"
    if d > 1 or d < -1:
        return "no:" + it.name + " is cut for a " + want.upper() + " frame: " + body.name + " is " + have.upper() + ", too far off to wear"
    return "loose" if d > 0 else "tight"


def hands_used(me):
    used = []
    for it in me.children():
        h = it.state.in_hand
        if h and on_me(me, it):
            if h == "both":
                used = used + ["left", "right"]
            else:
                used.append(h)
    return used


def free_hands(me, but=None):
    used = []
    for it in me.children():
        if but is not None and it.id == but.id:
            continue
        h = it.state.in_hand
        if h and on_me(me, it):
            used = used + (["left", "right"] if h == "both" else [h])
    return [h for h in ["right", "left"] if h not in used]


def hand_check(who, but=None):
    if "hands" not in plan_of(who):
        return ""
    if not free_hands(who, but):
        held = [it.name for it in who.children() if it.state.in_hand and on_me(who, it)]
        return "your hands are full (" + join_and(held) + "): stow or put something down first"
    return ""


def wear_check(me, it, helper=None):
    # why `me` cannot put `it` on now, or "" (and how it fits, as "fit:<word>")
    sp = spec(it)
    if not sp["slots"]:
        return "no:" + it.name + " is not something you wear"
    mine = it.parent is not None and (it.parent.id == me.id or (helper is not None and it.parent.id == helper.id))
    if not mine:
        return "no:" + (helper or me).name + " does not have " + it.name + ": take it first"
    if is_worn(me, it):
        return "no:" + it.name + " is already worn"
    b = busy(me)
    if b is not None and b.id != it.id:
        return "no:" + me.name + " is still getting " + ("into " if b.state.donning.get("doing") == "wear" else "out of ") + b.name
    plan = plan_of(me)
    for s in sp["slots"] + sp["hangs"]:
        if s not in SLOTS and s not in REGIONS and s not in plan:
            return "no:" + it.name + " names a slot no body here has (" + s + "): slots are " + ", ".join(SLOTS) + ", or a region of a body's own plan"
        if slot_need(s) not in plan:
            return "no:a " + species_of(me) + " has no " + slot_need(s) + " for " + it.name
    fit = size_word(me, it, sp)
    if fit.startswith("no:"):
        return fit
    worn = worn_list(me)
    n = layer_n(sp)
    for s in sp["slots"]:
        if sp["accessory"]:
            have = [j for j in worn if spec(j)["accessory"] and s in spec(j)["slots"]]
            room = ACCESSORY_CAP.get(s, 3)
            if len(have) >= room:
                return "no:" + me.name + " already wears " + str(room) + " on the " + s + ": take one off first"
    for j in worn:
        sj = spec(j)
        both = [s for s in sp["slots"] if s in sj["slots"]]
        if not both:
            continue
        if layer_n(sj) == n and not sp["accessory"] and not sj["accessory"]:
            return "no:" + me.name + " already wears " + j.name + " on the " + both[0] + " at that layer: take it off first"
        if layer_n(sj) > n:
            return "no:" + j.name + " is over the " + both[0] + ": take it off first, then put " + it.name + " on under it"
    h = hand_check(helper or me, it)
    if h:
        return "no:" + h
    return "fit:" + fit


def remove_check(me, it, helper=None):
    if not is_worn(me, it):
        return it.name + " is not worn"
    b = busy(me)
    if b is not None and b.id != it.id:
        return me.name + " is still getting " + ("into " if b.state.donning.get("doing") == "wear" else "out of ") + b.name
    sp = spec(it)
    n = layer_n(sp)
    for j in worn_list(me):
        sj = spec(j)
        both = [s for s in sp["slots"] if s in sj["slots"]]
        if both and layer_n(sj) > n:
            return j.name + " is over it: take that off first"
    hung = [c.name for c in me.children() if on_me(me, c) and c.state.stowed_on == it.id]
    if hung:
        return join_and(hung) + " " + ("hang" if len(hung) > 1 else "hangs") + " from " + it.name + ": hold or stow it elsewhere first"
    return hand_check(helper or me, it)


def don_time(it, sp, doing, alone):
    base = it.state.don_s
    if base is None:
        base = ACCESSORY_S if sp["accessory"] else DON_S.get(sp["layer"], 30)
    v = base if doing == "wear" else it.state.doff_s
    if v is None:
        v = float(base) / 2  # off in half the time it takes to go on
    v = float(v)
    if alone and sp["needs_help"]:
        v = v * (HELP_X if doing == "wear" else 2)
    return v


def stows_of(it):
    # where a carried thing can hang: its own `stows`, else by what it is
    if it.state.stows:
        return list(it.state.stows)
    if it.state.strap:
        return list(STRAP_POSITIONS)
    small = it.state.bulk is not None and float(it.state.bulk) <= 0.5
    if it.state.weapon:
        if it.state.hands == 2:
            return ["back"]
        return ["hip_left", "hip_right", "back"] + ([p for p in SMALL_POSITIONS if p not in ["hip_left", "hip_right"]] if small else [])
    if small:
        return list(SMALL_POSITIONS)
    return []


def at_position(me, pos):
    return [c for c in me.children() if on_me(me, c) and c.state.stowed_at == pos]


def mount_for(me, it, pos):
    # what it would hang from at pos: a worn carrier with that mount, or "strap"; "" when nothing can take it
    if it.state.strap and pos in STRAP_POSITIONS:
        return "strap"
    for j in worn_list(me):
        if pos in spec(j)["mounts"] and not j.state.donning:
            return j.id
    return ""


def is_concealed_pos(me, pos, worn):
    for j in worn:
        if pos in hides_at(j, spec(j)):
            return j
    return None


def item_look(it, sp):
    st = it.state
    if st.look:
        return str(st.look)
    words = []
    for k in ["condition", "cut", "color", "pattern", "material"]:
        v = st.get(k)
        if v:
            words.append(str(v))
    words.append((kind_of(it) or lower(it.name)).replace("_", " "))
    text = " ".join(words)
    if not sp["plural"]:
        text = ("an " if text[:1].lower() in "aeiou" else "a ") + text
    det = st.details
    if det:
        text = text + " with " + join_and(det if isinstance(det, list) else [det])
    return text


def extras(it, sp):
    out = []
    for m in modes_on(it, sp):
        out.append(str(sp["modes"][m].get("line") or m.replace("_", " ")))
    if it.state.worn_fit == "loose":
        out.append("a size too large")
    elif it.state.worn_fit == "tight":
        out.append("a size too small")
    return out


def slot_label(slots, plan):
    order = SLOTS + [r for r in plan if r not in SLOTS]
    ss = [s for s in order if s in slots]
    return cap1(join_and(ss))


def worn_line(it, sp, slots, plan, close):
    text = slot_label(slots, plan) + ": " + item_look(it, sp)
    ex = extras(it, sp)
    if ex:
        text = text + ", " + ", ".join(ex)
    if close and it.state.detail:
        text = text + ". " + cap1(str(it.state.detail).rstrip("."))
    return text + "."


def carried_line(it, where, close):
    text = cap1(LABELS.get(where, where)) + ": " + str(it.state.look or it.name)
    if close and it.state.detail:
        text = text + ". " + cap1(str(it.state.detail).rstrip("."))
    return text + "."


def outfit(me, close=False, full=False):
    # [(sort key, line)] as a viewer sees the body: the garments that show somewhere, outermost first in each slot, what
    # hangs at a position nothing hides, what is in hand. full: the body's own view, with what is hidden and by what.
    worn = worn_list(me)
    plan = plan_of(me)
    order = SLOTS + [r for r in plan if r not in SLOTS]
    rows = []
    for it in worn:
        sp = spec(it)
        shown = shown_slots(me, it, sp, worn)
        where = shown if shown else area(it, sp)
        first = min([order.index(s) for s in where if s in order] + [99])
        if shown:
            rows.append((first, 9 - layer_n(sp), worn_line(it, sp, shown, plan, close)))
        elif full:
            over = over_at(me, it, sp, area(it, sp)[0], worn)
            rows.append((first, 9 - layer_n(sp), worn_line(it, sp, area(it, sp), plan, close).rstrip(".") + " (under " + over.name + ")."))
    for it in me.children():
        d = it.state.donning
        if d and d.get("by") == me.id:
            sp = spec(it)
            verb = "getting into " if d.get("doing") == "wear" else "getting out of "
            rows.append((-1, 0, cap1(verb + item_look(it, sp)) + "."))
    for p in POSITIONS:
        for it in at_position(me, p):
            hid = is_concealed_pos(me, p, worn)
            if hid is None:
                rows.append((100 + POSITIONS.index(p), 0, carried_line(it, p, close)))
            elif full:
                rows.append((100 + POSITIONS.index(p), 0, carried_line(it, p, close).rstrip(".") + " (hidden by " + hid.name + ")."))
    for it in me.children():
        h = it.state.in_hand
        if h and on_me(me, it):
            rows.append((200 + ["right", "left", "both"].index(h), 0, carried_line(it, h, close)))
    return [r[2] for r in sorted(rows)]


def visible_tags(me):
    # what a door sees on a body: the tags of what shows, and armor, weapon, drawn, masked, barefoot
    worn = worn_list(me)
    tags = []
    dressed = []  # slots something is worn over (sandals too)
    hidden = []  # slots something hides (a mask, not a sheer veil)
    for it in worn:
        sp = spec(it)
        for s in area(it, sp):
            if s not in dressed:
                dressed.append(s)
        for s in covering(it, sp):
            if s not in hidden:
                hidden.append(s)
        if not shown_slots(me, it, sp, worn):
            continue
        for t in (it.state.tags or []):
            if t not in tags:
                tags.append(t)
        if sp["layer"] == "armor" or it.state.armor:
            if "armor" not in tags:
                tags.append("armor")
    for it in me.children():
        if not on_me(me, it):
            continue
        shows = bool(it.state.in_hand) or (it.state.stowed_at and is_concealed_pos(me, it.state.stowed_at, worn) is None)
        if not shows:
            continue
        for t in (it.state.tags or []):
            if t not in tags:
                tags.append(t)
        if it.state.weapon:
            if "weapon" not in tags:
                tags.append("weapon")
            if it.state.in_hand and "drawn" not in tags:
                tags.append("drawn")
    if "face" in hidden:
        tags.append("masked")
    if "feet" in plan_of(me) and "feet" not in dressed:
        tags.append("barefoot")
    return tags, dressed


def warmth(me):
    # the sum of the worn garments' `warmth` (a world's own scale): a world's cold reads it
    return sum([float(it.state.warmth or 0) for it in worn_list(me)])


def armor_at(me, slot):
    # the `armor` of what is worn over a slot, every layer added: a world's combat reads it
    return sum([float(it.state.armor or 0) for it in worn_list(me) if slot in area(it, spec(it))])


def clear_wear(ctx, it):
    ctx.patch(it, {"worn": False, "covers": [], "on": None, "stowed_at": None, "stowed_on": None, "in_hand": None,
                   "donning": None, "worn_fit": None, "concealed": None})


def refresh(ctx, me):
    # set the body's `attire` from what it has on, write each garment's `covers` (the engine hides marks under it) and
    # `concealed`, and let go of the state of anything that is no longer on this body. Writes only what changed.
    if me is None or not me.is_a("creature"):
        return
    for it in me.children():
        if it.state.on and it.state.on != me.id:
            clear_wear(ctx, it)
        elif it.state.stowed_on and it.state.stowed_on != "strap":
            c = ctx.get(it.state.stowed_on)
            if c is None or not is_worn(me, c):
                ctx.patch(it, {"stowed_at": None, "stowed_on": None})
    worn = worn_list(me)
    for it in me.children():
        if not on_me(me, it):
            continue
        sp = spec(it) if wearable(it) else None
        cov = regions_covered(it, sp) if (sp is not None and it.state.worn) else []
        hid = False
        if sp is not None and it.state.worn:
            hid = len(shown_slots(me, it, sp, worn)) == 0
        elif it.state.stowed_at:
            hid = is_concealed_pos(me, it.state.stowed_at, worn) is not None
        if (it.state.covers or []) != cov:
            ctx.patch(it, {"covers": cov})
        if bool(it.state.concealed) != hid:
            ctx.patch(it, {"concealed": True if hid else None})
    lines = outfit(me)
    if (me.state.attire or []) != lines:
        ctx.patch(me, {"attire": lines if lines else None})


def find_held(me, ref):
    want = lower(ref)
    for it in me.children():
        if it.id == ref or lower(it.name) == want:
            return it
    return None


def lets(who, by):
    # whether `by` may dress or undress `who`: who said so (let_dress), or who is asleep, down or dead
    if who.state.asleep or who.state.down or who.state.dead:
        return True
    ok = who.state.lets_dress or []
    return "anyone" in ok or by.id in ok


def start(ctx, me, it, doing, helper=None):
    # begin putting on or taking off: done at once when it takes under a second, else on the garment's timer
    sp = spec(it)
    dur = don_time(it, sp, doing, helper is None)
    ctx.patch(it, {"donning": {"by": me.id, "doing": doing, "until": ctx.t + dur, "helper": helper.id if helper else None},
                   "on": me.id, "in_hand": None, "stowed_at": None, "stowed_on": None})
    if dur < 1:
        finish_dressing(ctx, it)
        return 0
    ctx.schedule(dur, "clothing_done", target=it, payload={"by": me.id, "doing": doing})
    refresh(ctx, me)
    return dur


def finish_dressing(ctx, it):
    d = it.state.donning
    if not d:
        return
    me = ctx.get(d.get("by"))
    helper = ctx.get(d.get("helper")) if d.get("helper") else None
    ctx.patch(it, {"donning": None})
    if me is None or it.parent is None or it.parent.id != me.id:
        clear_wear(ctx, it)
        return
    if helper is not None and (helper.parent is None or me.parent is None or helper.parent.id != me.parent.id):
        ctx.emit("dressing_stopped", target=me, reach=1, by=me.id, item=it.id, name=it.name, why=helper.name + " walked away")
        if d.get("doing") == "wear":
            clear_wear(ctx, it)
            ctx.patch(it, {"on": None})
        refresh(ctx, me)
        return
    if d.get("doing") == "wear":
        why = wear_check(me, it, helper)
        if why.startswith("no:"):
            clear_wear(ctx, it)
            ctx.emit("dressing_stopped", target=me, reach=1, by=me.id, item=it.id, name=it.name, why=why[3:])
            refresh(ctx, me)
            return
        fit = why[4:]
        ctx.patch(it, {"worn": True, "on": me.id, "worn_fit": fit if fit else None, "modes_on": None})
        refresh(ctx, me)
        ctx.emit("dressed", target=me, reach=1, by=me.id, item=it.id, name=it.name,
                 **({"helper": helper.id} if helper else {}))
        return
    clear_wear(ctx, it)
    if helper is not None:
        ctx.transfer(it, helper)  # what a helper takes off stays in the helper's hands
    refresh(ctx, me)
    if helper is not None:
        refresh(ctx, helper)
    ctx.emit("undressed", target=me, reach=1, by=me.id, item=it.id, name=it.name,
             **({"helper": helper.id} if helper else {}))
