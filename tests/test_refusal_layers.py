"""Every refusal says which part of the call to change: its layer (call, target or rule) and one stable code, so a
mind's harness branches on it without reading the words (asked by a mind harness, 2026-11-24)."""

import pytest

from embody.ops import Rejected, call
from tests.test_ops import engine_with_two_rooms


def _refusal(fn, *a, **kw):
    with pytest.raises(Rejected) as r:
        fn(*a, **kw)
    return r.value.to_dict()


def test_the_call_layer_is_the_calls_own_shape():
    eng, w, i = engine_with_two_rooms()
    s = eng.session("nate")
    s.join("two-rooms", "Prisoner")
    assert call(s, "fly")["layer"] == "call" and call(s, "fly")["code"] == "unknown_op"
    assert call(s, "perceive", wings=2)["code"] == "bad_args"
    r = _refusal(s.act, "take", "Rusty key", {"wings": 2})
    assert (r["layer"], r["code"], r["param"]) == ("call", "unknown_param", "wings") and r["accepts"] == []
    r = _refusal(s.act, "take")
    assert (r["layer"], r["code"]) == ("call", "missing_target")


def test_the_target_layer_is_what_the_call_names():
    eng, w, i = engine_with_two_rooms()
    s = eng.session("nate")
    s.join("two-rooms", "Prisoner")
    r = _refusal(s.act, "take", "Golden key")
    assert (r["layer"], r["code"]) == ("target", "no_target")
    r = _refusal(s.act, "attack", "Guard")  # in the other room
    assert (r["layer"], r["code"]) == ("target", "not_here")
    r = _refusal(s.act, "juggle", "Rusty key")
    assert (r["layer"], r["code"]) == ("target", "unknown_verb") and "take" in r["accepts"]


def test_the_world_saying_no_is_the_rule_layer_by_default():
    eng, w, i = engine_with_two_rooms()
    s = eng.session("nate")
    s.join("two-rooms", "Prisoner")
    r = _refusal(s.act, "open", "Iron door")  # locked
    assert (r["layer"], r["code"]) == ("rule", "refused") and "param" not in r and "accepts" not in r
    assert set(Rejected("no").to_dict()) == {"ok", "reason", "hint", "alternatives", "layer", "code"}


def test_a_refused_program_leaves_a_trace_only_the_hosts_read():
    # a world's keeper, 2026-11-24: a maker's refused code left no trace, so nobody saw what it had tried
    from tests.test_grants import owner
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    s = eng.session("nate")
    s.join("two-rooms", "Prisoner")
    for _ in range(2):  # the same refusal again is logged once
        with pytest.raises(Rejected):
            gm.program("Iron door", "Knock Twice", "def apply(ctx):\n    return 1\n")
    rows = gm.history(kinds=["program_refused"])
    rows = rows.get("events", rows) if isinstance(rows, dict) else rows
    assert len(rows) == 1
    p = rows[0]["payload"]
    assert p["verb"] == "Knock Twice" and p["thing"] == "Iron door" and "lowercase" in p["reason"] and "source" not in p
    assert not [e for e in s.perceive()["events"] if e.get("kind") == "program_refused"]


def test_a_harness_reads_the_case_from_fields_never_the_words():
    # body-harness, 2026-11-28 (Nate: "ask engine dev for the refusal codes"): five places a harness still read wording
    from tests.test_limits import builder
    from tests.test_grants import owner
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    b, inv = builder(eng, gm)
    b.use("two-rooms")
    r = call(b, "spawn", type="thing", parent="Cell", name="Crate")
    assert (r["layer"], r["code"]) == ("target", "out_of_grant")
    r = call(b, "clock", rate=2)
    assert (r["layer"], r["code"]) == ("call", "out_of_grant")
    s = eng.session("nate")
    s.join("two-rooms", "Prisoner")
    r = call(s, "perceive", wings=2)
    assert (r["code"], r["param"]) == ("bad_args", "wings")
    for until in ("1 +", "nobody_knows_me", "me.get("):
        r = call(s, "wait", until=until, timeout=0)
        assert (r["layer"], r["code"], r["param"]) == ("call", "bad_until", "until"), until
    w.define_script("brittle", "def on(ctx, event):\n    return 1 / 0\n")
    w.set_rule(w.root_id, "brittle", ["tally"])
    with pytest.raises(Rejected) as e:
        w.emit("tally", target=w.root_id)
    assert e.value.code == "script_error"
    brief = s.join("two-rooms", "Prisoner")
    brief = brief.get("briefing", brief)
    assert isinstance(brief["pace_rate"], float)
