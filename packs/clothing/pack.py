"""Clothing: wear and take off garments in named slots and layers, hang what you carry where it hangs, and let the
world see a body by what it has on, with no hand on its description. README.md beside this file is the guide (and how
an agent fills a garment from a picture); this docstring is the reference.

A world names it in its manifest (`"requires": ["village", "clothing"]`), mixes BODY_VERBS into its person schema and
calls `install_rules(s, root)`. The pack defines `garment`, one schema a garment kind extending it (KINDS: `coat`,
`hooded_cloak`, `boots` and 86 more), `sewing_kit` and `cloth`.

Making clothes, for an author or an owner: one call. Live, `spawn("hooded_cloak", "Ada", "Grey cloak", state={"color":
"grey", "material": "wool"})`, or `introduce` with the same type and state where people stand; the kind's schema
brings the slots, layer, hangs, modes and the rest, and the state adds the look. In a build, `make_garment(s, parent,
name, kind, **fields)` checks every field first (`garment_state` raises ValueError with the fix). A kind the table
lacks is a schema of the world's own: `define_schema("duster", extends="garment", state={"garment": "duster", "slots":
[...], "layer": "outer"})`, then spawn it like any other. A world schema of a kind's name replaces the pack's.

Slots (a garment's `slots`, from SLOTS in scripts/_clothing.py): head, eyes, face, ears, neck, shoulders, torso,
back, arms, wrists, hands, fingers, waist, legs, feet. Each needs a region of the wearer's body plan (looks.regions:
the human twelve when it names none), so a goat wears no gloves; a region of a beast's own plan (flanks, tail) is a
slot too. Worn, a garment writes `covers` (the engine's looks hide marks under it) from the slots it hides.

Layers (`layer`), inside out: skin, under, main, over, armor, outer. One garment a slot a layer; an `accessory` (a
ring, a pin, a baldric) sits at a layer but takes no slot, at most ACCESSORY_CAP a slot (3, fingers 8, ears and wrists
4). A garment `hangs` over slots it does not take (coat tails over the legs): it hides them, it blocks nothing. What is
over a garment at a higher layer hides it there, unless that one says `conceals: false` (a sheer veil, sandals) or a
mode lays it open. Order is kept: nothing goes on under a worn garment in a slot it takes, nor comes off from under it.

A garment's fields: `garment` (its kind: GARMENTS in scripts/_clothing.py gives the slots, layer and the rest of 89
kinds, and the thing's own fields win), `slots`, `hangs`, `layer`, `accessory`, `plural`, `size` (xs, s, m, l, xl,
xxl; none fits anyone, so does `adjustable`), `fit` ("exact": armour, which never fits a size off), `look` (the line
others see), `detail` (seen within two metres), `condition`, `cut`, `color`, `pattern`, `material`, `details` (short
phrases), `modes` ({name: {adds: [slots], reveals: [slots or positions], line}}: hood_up, open, visor_down,
sleeves_rolled), `hides` (carry positions a closed outer garment hides), `mounts` (positions a carrier gives: a belt
the hips and the small of the back), `needs_help` (alone it takes HELP_X times as long), `don_s`, `doff_s` (world
seconds; else DON_S by layer, half that to take off), `tags` (the world's marks: a uniform), `warmth`, `armor` (a
world's own numbers: the pack reads neither, `warmth(me)` and `armor_at(me, slot)` add them up). Written by play:
`worn`, `on` (the body it is on), `donning`, `worn_fit` (loose, tight), `modes_on`, `covers`, `concealed`.

Carry positions (POSITIONS): hip_left, hip_right, small_of_back, back (room for 2), shoulder_left, shoulder_right,
chest, thigh_left, thigh_right, boot_left, boot_right, wrist_left, wrist_right; and the hands, left, right or both. A
thing hangs at a position from a worn carrier with that mount, or by its own `strap` (back and shoulders). Where a
thing goes is its `stows` list, else by what it is: a weapon at the hips or the back (a two-handed one, `hands: 2`, on
the back only), anything of bulk 0.5 or less at the small positions too. Written by play: `stowed_at`, `stowed_on`,
`in_hand`.

Verbs. On a garment (its own, listed under it): `wear`, `remove`, `adjust` (params how, on), `alter` (params to: one
size, half an hour, a sewing tool in hand; never armour). On a sewing kit: `sew` (an hour; cloth in hand, README).
BODY_VERBS, for a world's person schema: `stow` (params at, or "away"), `hold` (params hand), `dress` and `undress`
(params item: someone here who has let you, or is asleep, down or dead; what you take off is yours), `let_dress`
(params who: a name here, anyone, nobody), `look_over` (someone here, or yourself: what shows, the close detail within
two metres, and your own hidden layers). Putting on or taking off needs a free hand and takes its time: the garment's
timer (`clothing_done`) finishes it, and only then is it worn.

How others see it: the body's `attire`, a line for each garment that shows somewhere (outermost first) and each thing
hung where nothing hides it or held in hand, written by the pack whenever the outfit changes: "Torso, back and arms: a
long oxblood wool coat, open." A garment or a carried thing nothing shows carries `concealed: true`.

The rule (install_rules): a worn thing is not given, dropped, put or burned until it comes off; a place's
`dress_code` {needs: [slots, or "tag:<tag>"], bars: [armor, weapon, drawn, masked, barefoot, or a tag], why} turns
back a `go` into it by what shows; and after given, dropped, put, taken, lifted (d20's search on a sleeper) or burned,
both bodies' attire is set again, and what left a body is no longer worn.

Events, on the body, reach 1: `dressed` and `undressed` {by, item, name, helper?}, `dressing_stopped` {by, item, name,
why}, `adjusted` {by, item, name, how, on}, `stowed` {by, item, name, at}, `holding` {by, item, name, hand}, `sewn`
{by, item, name}, `altered` {by, item, name, size}.

What each world decides: who may sew or alter (the kits and cloth it hands out, access on them, a before_act rule),
dyes and where cloth comes from, what `warmth` and `armor` do, every dress code, whether its people loot the fallen
(undress works on the dead), and which tags mean a uniform. The pack never calls a model: an agent that reads a
picture fills the fields itself (README).
"""

PACK = {"name": "clothing", "description": "Wear garments in slots and layers, hang what you carry at the hip or the back, sew and alter; others see the outfit, never a privileged edit."}

# What the engine reads back from this pack (world.PACK_DECLARES): the chronicle's routine kinds.
CHRONICLE_ROUTINE = ["dressed", "undressed", "dressing_stopped", "adjusted", "stowed", "holding", "altered", "sewn"]

# This pack's rules changelog, oldest first (see d20's RULES).
RULES = [
    {"id": "clothing-pack", "date": "2026-11-24",
     "was": "A body looked like its description and its marks; a coat was a thing in the pocket like any other.",
     "now": "With the clothing pack, a body wears garments in slots and layers (wear, remove, adjust), hangs what it "
            "carries at the hip or the back (stow, hold), and others see its attire, a line for each piece that shows. "
            "Outer layers hide what is under them, marks included. Worn things come off before they are given.",
     "recheck": ["notes that say a character's clothes are in its description"], "guide": ["player", "mind"]},
]

_FUEL = {"check_fuel": 100_000, "fuel": 200_000}


def _a(script, doc, params=None, **kw):
    out = {"script": script, "doc": doc, **_FUEL, **kw}
    if params:
        out["params"] = params
    return out


GARMENT_VERBS = {
    "wear": _a("clothing_wear", "Put it on: it takes its time, and a free hand"),
    "remove": _a("clothing_remove", "Take it off, once nothing is over it"),
    "adjust": _a("clothing_adjust", "One of its ways: hood up, open, visor down, sleeves rolled",
                 {"how": "the way (its modes)", "on": "true or false; leave out to toggle"}),
    "alter": _a("clothing_alter", "Let it out or take it in one size, with a sewing tool in hand: half an hour",
                {"to": "xs, s, m, l, xl or xxl"}, duration=1800),
}

SEW = _a("clothing_sew", "Sew a garment from cloth you carry: an hour, here",
         {"name": "what people call it", "garment": "its kind: coat, shirt, boots... (or slots and layer)",
          "slots": "the slots it takes, if not its kind's", "hangs": "slots it hangs over", "layer": "skin to outer",
          "look": "the line others see", "detail": "what shows within two metres", "cut": "long, cropped...",
          "pattern": "striped, embroidered...", "details": "short phrases: brass buttons, a frayed hem",
          "size": "xs to xxl (default yours)", "hood": "true: it has a hood", "opens": "true: it opens at the front",
          "sleeves": "true: sleeves that roll", "from": "which cloth"}, duration=3600)

# what a world mixes into its person schema: a body's own verbs
BODY_VERBS = {
    "stow": _a("clothing_stow", "Hang it at a position (a belt at the hip, a strap on the back), or put it away",
               {"at": "hip_left, hip_right, small_of_back, back, shoulder_left... or away"},
               targets="thing", scope="held", duration=2),
    "hold": _a("clothing_hold", "Take it in hand, from where it hangs or your pack", {"hand": "left or right"},
               targets="thing", scope="held", duration=1),
    "dress": _a("clothing_dress", "Put a garment you hold on someone here who lets you (or lies asleep, down or dead)",
                {"item": "the garment you hold"}, targets="creature", scope="here"),
    "undress": _a("clothing_undress", "Take a garment off someone here who lets you (or lies asleep, down or dead)",
                  {"item": "the garment they wear"}, targets="creature", scope="here"),
    "let_dress": _a("clothing_let_dress", "Say who may dress or undress you", {"who": "a name here, anyone or nobody"}),
    "look_over": _a("clothing_look_over", "Look someone over: what they wear and carry in sight; yourself: all of it",
                    targets="creature", scope="here", self=True),
}

GARMENT_STATE = {"portable": True, "bulk": 0.5, "worn": False, "covers": [], "garment": None, "slots": None,
                 "hangs": None, "layer": None, "accessory": None, "plural": None, "size": None, "adjustable": False,
                 "look": None, "detail": None, "modes": None, "hides": None, "mounts": None, "conceals": None,
                 "needs_help": None, "tags": [], "secret": ["on", "donning", "stowed_on"]}


def _model():
    """scripts/_clothing.py read as Python: the one table of slots, layers, sizes, positions and garment kinds that the
    verbs use too."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("clothing_model", Path(__file__).resolve().parent / "scripts" / "_clothing.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


MODEL = _model()
KINDS = MODEL.GARMENTS  # each is a schema of its own, extending garment: spawn("boots", ...) is a pair of boots
_LISTS = {"slots": MODEL.SLOTS, "hangs": MODEL.SLOTS, "mounts": MODEL.POSITIONS, "hides": MODEL.POSITIONS}


def _kind_doc(kind, f):
    where = ", ".join(f["slots"]) + (" (hangs over " + ", ".join(f["hangs"]) + ")" if f.get("hangs") else "")
    return (f"A {kind.replace('_', ' ')}: worn on the {where}, at the {f.get('layer', 'main')} layer"
            + (", an accessory" if f.get("accessory") else "") + ". packs/clothing.")


def garment_state(kind=None, regions=(), **fields):
    """The (schema, state) a garment is made with: its kind's schema (KINDS) when the kind is known, else `garment`
    with `garment` set to the kind and the fields saying where it is worn. Checks every field the pack reads and raises
    ValueError with the fix; `regions` names slots of a beast's own plan (tail, flanks) the check lets through."""
    kind = (kind or fields.get("garment") or "").strip().lower().replace(" ", "_") or None
    if kind is None and not fields.get("slots"):
        raise ValueError("say what it is: a kind (" + ", ".join(list(KINDS)[:10]) + "...) or slots and a layer")
    if kind is not None and kind not in KINDS and not fields.get("slots"):
        raise ValueError(f"{kind!r} is no kind the pack knows: give it slots and a layer, or use one of {', '.join(KINDS)}")
    for k, allowed in _LISTS.items():
        v = fields.get(k)
        if v is None:
            continue
        if not isinstance(v, list):
            raise ValueError(f"{k} is a list")
        bad = [x for x in v if x not in allowed and not (k in ("slots", "hangs") and x in regions)]
        if bad:
            raise ValueError(f"{k}: {', '.join(bad)} not one of {', '.join(allowed)}")
    if fields.get("layer") is not None and fields["layer"] not in MODEL.LAYERS:
        raise ValueError(f"layer is one of {', '.join(MODEL.LAYERS)}")
    if fields.get("size") is not None and fields["size"] not in MODEL.SIZES:
        raise ValueError(f"size is one of {', '.join(MODEL.SIZES)}")
    for name, m in (fields.get("modes") or {}).items():
        if not isinstance(m, dict) or set(m) - {"adds", "reveals", "line"}:
            raise ValueError(f"mode {name!r} is {{adds: [slots], reveals: [slots or positions], line}}")
    if isinstance(fields.get("details"), str):
        fields["details"] = [fields["details"]]
    if kind in KINDS:
        return kind, dict(fields)
    return "garment", {"garment": kind, **fields}


def make_garment(s, parent, name, kind=None, regions=(), **fields):
    """One call to make a garment in a build (populate, upgrade): checked by garment_state, then spawned under
    `parent` (a body that has it, a rack, a place). Returns what spawn returns. In a live world, give the same type
    and state to introduce instead, so the room learns how it came."""
    schema, state = garment_state(kind, regions, **fields)
    return s.spawn(schema, parent, name, state=state)


def define(s):
    """The garment schema and one schema a kind (KINDS) extending it, the sewing kit and cloth. Idempotent."""
    s.define_schema("garment", extends="thing",
                    doc="Something worn: in slots, at a layer, seen by others while nothing hides it (packs/clothing).",
                    state=GARMENT_STATE, actions=GARMENT_VERBS,
                    listeners=[{"script": "clothing_timer", "kinds": ["clothing_done"], "fuel": 200_000}])
    for kind, f in KINDS.items():
        s.define_schema(kind, extends="garment", doc=_kind_doc(kind, f), state={"garment": kind, **f})
    s.define_schema("sewing_kit", extends="thing", doc="Needles, thread, shears: sew garments from cloth, alter them.",
                    state={"portable": True, "bulk": 0.5, "tool": "sewing", "description": "A roll of needles, thread and shears."},
                    actions={"sew": SEW})
    s.define_schema("cloth", extends="thing", doc="Cloth by the length, a stack: its material and colour go into what is sewn from it.",
                    state={"portable": True, "bulk": 0.5, "cloth": True, "material": "wool", "color": "undyed"})


def install_rules(s, root, fuel=200_000):
    """The clothing rule on the root: worn things come off before they leave a body, dress codes, attire kept true.
    Idempotent."""
    s.set_rule(root, "clothing_rule", kinds=["before_act", "given", "dropped", "put", "taken", "lifted", "burned"], fuel=fuel)
