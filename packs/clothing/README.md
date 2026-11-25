# Clothing

A body dresses itself. It wears garments in named slots and layers, hangs what it carries at a hip or across its back,
and everyone else sees what shows. Nobody edits its description to do it: the outfit is play, kept by the world's
rules. `pack.py` is the reference (every field, verb and event); this page is the guide.

## For a world

Name the pack, mix its body verbs into your people, and put its rule on the root:

```python
WORLD = {..., "requires": ["village", "clothing"]}

def define(s):
    clothing = ...  # load packs/clothing/pack.py
    acts = {...your person verbs...}
    acts.update(clothing.BODY_VERBS)  # stow, hold, dress, undress, let_dress, look_over
    s.define_schema("person", extends="creature", actions=acts)
    clothing.install_rules(s, s.summary()["root"])
```

## Making clothes

Every garment kind in the pack's table (89 of them: `coat`, `hooded_cloak`, `boots`, `mail`, `ring`...) is a schema
extending `garment`, so one call makes one, ready to wear. The kind brings where it is worn (slots, layer, what it
hangs over, its modes); you add how it looks. Any field overrides the kind's.

A grey cloak with a hood and a pair of riding boots, live (an author or the owner):

```python
spawn("hooded_cloak", "Ada", "Grey cloak", state={
    "color": "grey", "material": "wool", "size": "m",
    "look": "a grey wool cloak, its hood lined with rabbit fur",
    "detail": "the clasp is a pewter hare"})
spawn("boots", "Ada", "Riding boots", state={
    "color": "black", "material": "leather", "cut": "knee-high", "details": ["brass buckles"]})
```

Where people stand, use `introduce` with the same type and state, so the room learns how it came. Worn, the cloak
reads "Shoulders, torso, back and arms: a grey wool cloak, its hood lined with rabbit fur", and `adjust {"how":
"hood_up"}` adds the head; the boots read "Feet: knee-high black leather boots with brass buckles."

In `build.py`, `make_garment` checks every field before it spawns and says what is wrong (a slot misspelt, a layer
that does not exist):

```python
clothing = ...  # load packs/clothing/pack.py
clothing.make_garment(s, ada, "Grey cloak", "hooded_cloak", color="grey", material="wool", size="m")
clothing.make_garment(s, ada, "Riding boots", "boots", color="black", material="leather", cut="knee-high",
                      details=["brass buckles"])
```

A kind the table lacks is a schema of your own, made the way every schema is:

```python
define_schema("duster", extends="garment", state={
    "garment": "duster", "slots": ["torso", "back", "arms"], "hangs": ["legs"], "layer": "outer",
    "modes": {"open": {"reveals": ["torso", "chest"], "line": "open"}}})
```

The fields: `slots` and `hangs` (from head, eyes, face, ears, neck, shoulders, torso, back, arms, wrists, hands,
fingers, waist, legs, feet), `layer` (skin, under, main, over, armor, outer), `accessory`, `plural`, `size` (xs to xxl;
none or `adjustable` fits anyone), `fit: "exact"` (armour), `color`, `material`, `cut`, `pattern`, `condition`,
`details`, `look`, `detail`, `modes`, `hides` and `mounts` (carry positions), `needs_help`, `don_s`, `doff_s`, `tags`,
`warmth`, `armor`. `pack.py` says what each does.

What the pack gives every world: the slots and layers, order (nothing goes on under a worn coat), sizes, body plans
(a goat wears no gloves), the time each garment takes and the help heavy armour wants, carry positions and the hands,
outer layers that hide what is under them (marks included, through the engine's looks), the `attire` lines others
see, `look_over` for the close detail, sewing and altering, and a rule that keeps worn things on the body until they
come off.

What stays your world's to decide:

- Who may sew or alter: the kits and cloth you hand out, access on them, or a `before_act` rule on `sew`.
- Where cloth comes from, and dye: a garment takes its material and colour from the cloth it is sewn from.
- What `warmth` and `armor` mean: the pack stores them and adds them up (`warmth(me)`, `armor_at(me, slot)` with
  `use("clothing")` in your scripts); your weather and your combat read them.
- Dress codes: a place's `dress_code`, `{"needs": ["feet", "tag:uniform"], "bars": ["drawn", "masked"], "why": "..."}`.
  The pack's rule turns back a `go` by what shows: a dagger under a cloak walks in. Searches at the door are yours.
- Uniforms and marks of office: `tags` on a garment are yours to give. Sewing never makes a tag.
- Looting: `undress` works on the asleep, the down and the dead. Forbid it with a rule if your world does not.

## For a player or a mind

Read `attire` on anyone's card: a line for each piece that shows, outermost first, then what hangs where nothing hides
it and what is in their hands. `look_over` someone for the close detail within two metres, or yourself for every
layer and what hides what.

- `wear` a garment you have; `remove` it once nothing is over it. Both take time and a free hand.
- `adjust` it: `{"how": "hood_up"}`, `"open"`, `"visor_down"`, `"sleeves_rolled"`, whatever its `modes` say.
- Wear a belt, then `stow` a blade `{"at": "hip_left"}`. A two-handed thing hangs on the back and takes both hands to
  `hold`. `stow {"at": "away"}` puts a thing back in your pack, out of sight.
- `let_dress {"who": "a name"}` lets someone `dress` you, faster in heavy armour, or `undress` you.
- You cannot give, drop or burn what you wear: take it off first.

## Sewing

With a sewing kit and cloth in hand, `sew` takes an hour where you stand and spends the cloth (more for a long coat
than for a cap). Params: `name`, `garment` (a kind from the table) or `slots` and `layer`, and as you like `look`,
`detail`, `cut`, `pattern`, `details` (up to six short phrases), `size` (yours by default), `hood`, `opens`,
`sleeves`, `from` (which cloth). A needle makes no armour, and only leather takes a mount: a belt is cut from hide.
`alter` lets a garment out or takes it in one size in half an hour; armour is a smith's work.

## Filling a garment from a picture

The pack never calls a model. An agent with vision does that work on its own side, then writes the fields into the
one call above (`spawn` with the kind's schema, or `sew` for a player). Look at
one garment at a time, from the picture alone, and write what a person standing near would say, not what a catalogue
would: `garment` is the plain noun from the table if one fits (coat, doublet, boots, hooded_cloak), else give `slots`
and `layer` yourself, choosing the layer by what it is worn over and under. `color` is one or two everyday words
("oxblood", "faded indigo"), `material` what it looks made of ("waxed cotton", "riveted mail"), `cut` its shape ("long",
"cropped", "high-collared"), `pattern` only when there is one, `condition` only when it shows (patched, mud-spattered),
and `details` the two to four things that make this one itself (horn toggles, a frayed hem, a guild badge). Put the
whole sentence others should read in `look` (under 200 characters, no ids, no tool words), and the thing you notice
only up close in `detail`. If the picture shows a hood, a front that opens or rolled sleeves, say so (`hood`,
`opens`, `sleeves`), so the garment can do it in play. Leave out what the picture cannot show (the size, the
warmth), and never copy text off a logo or a label into the world: describe it ("a stitched badge of a hawk").
