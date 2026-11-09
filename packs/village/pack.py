"""Village verbs: go, take, drop, give, show, talk, read, follow, stay, watch, and person_on, the listener that
answers from a person's dialog table while nobody embodies them. Extracted from the Ferry at Dusk, used by the
Glass Reach too.

A world names it in its manifest (`"requires": ["village"]`) and the loader defines these scripts before the world's
own, so a world may replace any of them with a file of the same name in its scripts/ (the Glass Reach has its own
`go` for deep sand). The pack defines no schemas: a world's `person` schema binds the verbs it wants.

- go: to a connected place; via a door-like entity when the connection has one (locked doors refuse).
- take, drop: portable things here or held; give: something you hold to someone here (`gives` tables can answer).
- show: something you hold to someone here; they get a `shown` event with its `text` (or description), it stays yours.
- talk: `params {"about": topic}`; the person answers from `dialog` through person_on, or with `default_line`.
- read: the `text` of a thing you hold or that is here.
- follow: someone here; when they `go`, you go with them (`state.follows`). stay: stop following.
- watch: a connected place, without stepping into it: who and what is there now, for your eyes only.
- a whisper is not a verb: `say(text, to=someone, reach=0)` reaches that one person and nobody else in the room.
"""

PACK = {"name": "village", "description": "go, take, drop, give, show, talk, read, follow, stay, watch and the dialog-table listener person_on."}
