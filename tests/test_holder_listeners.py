"""A carried thing's `holder` listener hears what its holder does and has done to it, wherever that is; ctx.event_at
reads one event of the log back."""

from embody.ops import AUTHOR, Engine

RING = '''
def on(ctx, ev):
    ctx.patch(ctx.self, {"heard": (ctx.self.state.heard or []) + [ev.kind]})
'''

WAVE = '''
def apply(ctx):
    return ctx.emit("waved", target=ctx.actor, reach=1)
'''

POKE = '''
def apply(ctx):
    ctx.emit("poked", target=ctx.target, reach=1, by=ctx.actor.id)
'''

HUSH = '''
def on(ctx, ev):
    ctx.stop()
'''

RECALL = '''
def apply(ctx):
    ev = ctx.event_at(ctx.params.get("seq"))
    return ev.kind if ev is not None else None
'''


def world():
    eng = Engine()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.create_world("Hall", seed=1)
    for name, src in (("ring", RING), ("wave", WAVE), ("poke", POKE), ("hush", HUSH), ("recall", RECALL)):
        gm.define_script(name, src)
    gm.define_schema("ring", extends="thing", state={"portable": True}, listeners=[{"script": "ring", "holder": True}])
    gm.define_schema("hall", extends="place", listeners=[{"script": "hush", "kinds": ["waved"]}])
    gm.define_schema("person", extends="creature",
                     actions={"wave": {"script": "wave", "doc": "Wave"},
                              "poke": {"script": "poke", "doc": "Poke someone", "targets": "creature"},
                              "recall": {"script": "recall", "doc": "Look an event up", "params": {"seq": "its number"}}})
    hall = gm.spawn("hall", gm.world.root_id, "Hall")["id"]
    ash = gm.spawn("person", hall, "Ash")["id"]
    gm.spawn("person", hall, "Bone")
    worn = gm.spawn("ring", ash, "Worn ring")["id"]
    floor = gm.spawn("ring", hall, "Floor ring")["id"]
    a, b = eng.session("ash"), eng.session("bone")
    a.join("hall", "Ash")
    b.join("hall", "Bone")
    return gm, a, b, worn, floor


def test_a_carried_thing_hears_its_holder_and_a_stop_up_the_tree_does_not_silence_it():
    gm, ash, bone, worn, floor = world()
    seq = ash.act("wave")["result"]  # the hall stops `waved` from bubbling; the ring is not above Ash, so it hears
    bone.act("poke", "Ash")  # done to its holder
    ash.act("poke", "Bone")  # done by its holder
    heard = gm.world.get(worn)["state"]["heard"]
    assert heard.count("waved") == 1 and heard.count("poked") == 2 and heard.count("act") == 3
    assert "before_act" not in heard  # only a listener whose kinds name it hears a deed before it happens
    assert not gm.world.get(floor)["state"].get("heard")  # lying in the hall it is nobody's
    assert ash.act("recall", params={"seq": seq})["result"] == "waved"
    assert ash.act("recall", params={"seq": 10**6})["result"] is None
