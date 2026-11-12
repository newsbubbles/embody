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
| 2 | A "maker" grant: write verbs on what you own, with quotas and review | engine, next |
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

### Phase 2 (next): the maker grant

A grant between player and builder: a person may write verbs and rules on the things they own, nowhere else. It needs
quotas (scripts, fuel, things spawned per hour), a mark on script text written by an outside principal so no agent
reads it as instructions, and an optional owner's review before a verb goes live.

### Phase 3: packs

In-world things that use phases 0 to 2: a charter that adds its holder to a group, a key that is a verb rule, a seal
that sets a mode when pressed onto a thing, a maker's bench that lets you script what is on it. A pack calls `ctx.chmod`,
`ctx.chown` and `ctx.may`; it never replaces the engine's checks.
