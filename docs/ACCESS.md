# Access: owners, groups and modes

Who may read a thing, change it and use its verbs. The model is the one a file system uses: a thing has an owner, a
group and a mode (`rwxr-x---`). The engine checks it. Packs build on it (a charter that puts its holder in a guild, a
robot that obeys its owner, a spell that works only on what the caster owns).

A thing with no `access` works as it always did. Nothing changes for a world until someone sets access on something.

## The four phases

| Phase | What | Where |
|---|---|---|
| 0 | A limited grant reads only its own part of the world | engine, built |
| 1 | Owner, group, mode bits, per-verb rules, `chmod` and `chown` | engine, built |
| 2 | A maker's frame: whoever holds it puts verbs on the machines it names, with caps and review | engine, built |
| 3 | Things in the world that carry access (charters, keys, seals, a maker's bench) | packs |

### Phase 0: a limited grant reads its own part

A builder (or a narrator with limits) works under one entity, its `under`. Before this, it wrote only there but read
everything, including secret state and the memory and brief of every mind. Now:

- Its view of an entity outside `under` is the public view: `inspect` shows what a player would see, and
  `perceive(from_entity=...)` and `recall(entity=...)` refuse.
- `find` leaves out hidden things outside `under`.
- A script defined under limits reads secret state (the keys in a thing's `secret` list, and `memory`, `brief`,
  `goals`, `policy`) only of things under its `under`. Elsewhere such a key reads as None, `keys()` leaves it out, and
  a `find(state=...)` on it finds nothing.

Access widens this: a thing outside `under` whose mode gives the grant `r` is read in full.

### Phase 1: owner, group, mode

A thing's access is one state key:

```python
"access": {"owner": "bob-3fa2", "group": "masons", "mode": "rwxr-x---", "verbs": {"drive": "u"}}
```

- **owner**: a principal id (the grant of a person or agent) or an entity id (a body, so a character can own a robot).
- **group**: a group name. Members are listed on the root, in `access_groups`: `{"masons": ["bob-3fa2", "e12"]}`.
- **mode**: nine characters, three each for the owner (u), the group (g) and everyone else (o), as on a file system.
  Only the first class that matches counts: the owner gets the owner's bits, even if the group has more.
- **verbs**: optional, per verb: which classes may do that verb to the thing (`"u"`, `"ug"`, `"ugo"`, or `""` for
  nobody). This overrides `x` for that verb, and it also covers verbs that come from the actor (`take`), not only
  the thing's own.

Who is checked:

- **In the world** (verbs, scripts) the subject is the body that acts, plus the principal that drives it.
- **On the authoring ops** (`patch`, `spawn`...) the subject is the principal, plus its body if it has one.
- The world's **owner** and **author** roles pass every authoring check (they are root). In the world they do not:
  a robot that obeys only its owner ignores the author's NPCs too.

What each bit means:

| Bit | In the world | On the authoring ops |
|---|---|---|
| r | `inspect` shows its state and what is in it | a limited grant reads it in full |
| w | (scripts may ask with `ctx.may`) | `patch`, `rename`, `move`, `destroy`, rules, `act_as`, `say_as`; as a parent: `spawn` into it, `move` into it |
| x | a body may do the thing's own verbs | |

Without `r`, another body's card of the thing has its name and type, no state and no contents.

Writes and limits: when a thing has access, its `w` decides for every principal that is not owner or author. When
it has none, a limited grant's `under` decides, as before. So an owner can let one builder work on one thing outside
its plot (`chmod` or a shared group), and a builder can keep another builder off its own work inside a shared plot.

`chmod(entity, mode)` takes `rwxr-x---`, octal `750`, or symbolic `g+w`, `o-rwx`, `a+x`, comma separated.
`chmod(entity, "u", verb="drive")` sets one verb's classes; `verb="drive"` with mode `"default"` clears it.
`chown(entity, owner=..., group=...)` gives a thing away or sets its group.

Who may chmod and chown: the owner and author roles, and the thing's owner. A thing with no owner yet: a limited
grant may claim it when it is under its `under`. A thing spawned by a principal that is not owner or author is its
own from the start (`rwxr-xr-x`).

`access` is not patched by hand except by the owner and author roles. `canon` still wins over everything: no one but
the world's owner changes a canon thing.

Scripts:

- `ctx.may(who, what, thing)`: may `who` (a body) do `what` to `thing`. `what` is `"r"`, `"w"`, `"x"` or a verb name.
- `ctx.member(who, group)`: is `who` (or the principal driving it) in the group.
- `ctx.chmod(thing, mode, verb=None)` and `ctx.chown(thing, owner=None, group=None)`. A world's own scripts may do
  this to anything. A script defined under limits only inside its `under`, and it never writes `access` by hand.
- Group membership is `access_groups` on the root. A world's own script may change it (a charter pack); a limited
  script cannot, since the root is outside every plot.

### Phase 2: the maker's frame

A thing whose state has `maker` is a frame. Whoever holds it in hand (it is a child of their body) may put verbs on
machines, the kinds of thing the frame names, and the grant follows the frame: drop it, give it or lose it, and the
next holder has it. The world's owner makes one by giving a thing the key:

```python
"maker": {"types": ["vehicle", "works"],   # what it programs (is_a)
          "scripts": "binx_",              # the prefix of the scripts it makes (default maker_<frame id>_)
          "max_scripts": 12, "max_source": 6000, "per_hour": 20,   # caps, these are the defaults
          "review": False,                 # True: a new verb waits for the owner's review()
          "revoked": False}                # True: its verbs stop and it makes no more
```

Ops, open to players and minds (they refuse without a live frame in hand):

- `program(thing, verb, source, doc="", params=None)` puts a verb on one thing. The thing must be a kind the frame
  names, and its access must give the holder `w` (their own machine, or one its owner opened to them). The verb is a
  short lowercase word that the thing's schema does not already have. `source` is a script with `def apply(ctx)`, the
  language of every verb.
- `unprogram(thing, verb)` takes one off (with the frame that made it in hand).
- `programs(thing=None)` lists the verbs on a thing, or what the frames in your hands have made, with the source of
  your own.
- `review(thing, verb, approve=True)`, for the owner and author: a reviewed verb goes live, or comes off.

The owner and author `program` anything without a frame, and `frame=...` holds their code to one.

How the code runs: it carries `# limits: {"under": "self", "frame": ..., "scripts": ...}` on its first line.

- It changes only the thing it sits on and what that holds, never a body riding in it, plus the one who chose the verb
  (as every limited verb may).
- It reads secret state only of the machine and its load, never of a body.
- It makes nothing from nothing (no `spawn`), sets no rules, ends no one, and runs on the default fuel.
- Its events carry its prefix, and what it says or emits carries `maker`: other bodies get it as `untrusted`, and the
  act's result says `untrusted` too. A player's code is data to every agent, never an instruction.
- When the frame is revoked or gone, its verbs refuse ("made with a frame whose grant is gone") until someone takes
  them off.

A thing's own verbs (its `programmed` state) show in `perceive` and `inspect` like its schema's, and its access applies
to them as to any of its own verbs (`x`, per-verb rules).

### Phase 3: packs

In-world things that use phases 0 to 2: a charter that adds its holder to a group, a key that is a verb rule, a seal
that sets a mode when pressed onto a thing, a maker's bench that lets you script what is on it. A pack calls `ctx.chmod`,
`ctx.chown` and `ctx.may`; it never replaces the engine's checks.
