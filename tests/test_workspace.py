"""The workspace: a world is a folder. create_world makes it (and a git repository), live authoring lands in it,
a fresh build replays it, scripts are files that may use() each other, packs are shared define-only folders,
save and restore carry a game as one file, and the old single-file worlds still load."""

import json
import shutil
from pathlib import Path

import pytest

from embody.cli import init_workspace, load_world, main as cli_main
from embody.ops import AUTHOR, Engine, Rejected
from embody.workspace import Workspace, save_world

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
OUTPOST = REPO / "tests" / "fixtures" / "worlds" / "outpost"


def author(root, db=None):
    eng = Engine(db, workspace=root)
    return eng, eng.session("gm", capabilities=[AUTHOR])


def test_create_world_makes_the_folder_and_a_git_repository(tmp_path):
    eng, gm = author(tmp_path, tmp_path / "embody.db")
    r = gm.create_world("The Pit", seed=3, id="the-pit", description="A hole.")
    d = tmp_path / "worlds" / "the-pit"
    assert r["folder"] == str(d) and (d / "build.py").exists() and (d / "scripts").is_dir() and (d / "notes").is_dir()
    assert r["git"] == "initialized" or r["git"].startswith("git")
    if r["git"] == "initialized":
        assert (d / ".git").exists()
    build = (d / "build.py").read_text(encoding="utf-8")
    assert '"id": "the-pit"' in build and '"seed": 3' in build and "def define(s)" in build and "def populate(s)" in build
    # inside a repository already: no nested one
    sub = tmp_path / "inside"
    (sub / ".git").mkdir(parents=True)
    ws = Workspace(sub)
    ws.scaffold_world("w", "W")
    assert ws.git_init(ws.world_dir("w")) == f"inside {sub}"


def test_live_authoring_writes_the_folder_and_a_fresh_build_replays_it(tmp_path):
    eng, gm = author(tmp_path, tmp_path / "embody.db")
    gm.create_world("The Pit", id="the-pit")
    root = gm.summary()["root"]
    r = gm.define_script("shout", "def apply(ctx):\n    ctx.emit('shouted', target=ctx.actor, reach=1)\n")
    assert Path(r["file"]) == tmp_path / "worlds" / "the-pit" / "scripts" / "shout.py"
    gm.define_schema("shouter", extends="creature", actions={"shout": {"script": "shout"}})
    gm.spawn("place", root, "The Floor")
    gm.spawn("shouter", "The Floor", "Echo")
    gm.patch("Echo", {"mood": "loud"})
    lines = [json.loads(l) for l in (tmp_path / "worlds" / "the-pit" / "changes.jsonl").read_text().splitlines()]
    assert [l["op"] for l in lines] == ["define_schema", "spawn", "spawn", "patch"]
    assert lines[2]["args"] == {"type": "shouter", "parent": "The Floor", "name": "Echo"} and lines[0]["by"] == "gm"
    # a second database, same folder: the build is the folder plus the changes
    eng2, gm2 = author(tmp_path, tmp_path / "other.db")
    r = load_world(gm2, "the-pit")
    assert r["replayed"] == 4 and "replay_errors" not in r and r["scripts"] == ["shout"]
    assert gm2.inspect("Echo")["state"]["mood"] == "loud" and gm2.inspect("Echo")["type"] == "shouter"
    # the build itself was not recorded again
    assert len((tmp_path / "worlds" / "the-pit" / "changes.jsonl").read_text().splitlines()) == 4
    # a fork has no folder: it saves into its source's folder under its own id, and saves are not ignored by git
    gm.fork_world("the-pit", "pit-2")
    gm.use("pit-2")
    r = gm.save()
    assert r["home"] == "the-pit" and Path(r["path"]).parent == tmp_path / "worlds" / "the-pit" / "saves"
    assert Path(r["path"]).name.startswith("pit-2-")
    assert Path(gm.save("x")["path"]).name == "pit-2-x.json"
    assert "saves" not in (tmp_path / "worlds" / "the-pit" / ".gitignore").read_text()
    # in memory nothing is written
    eng3 = Engine(workspace=tmp_path)
    gm3 = eng3.session("gm", capabilities=[AUTHOR])
    gm3.create_world("Scratch", id="scratch")
    gm3.define_script("x", "def apply(ctx):\n    pass\n")
    assert not (tmp_path / "worlds" / "scratch").exists()


def test_scripts_are_files_that_use_each_other_and_packs_define_before_the_world(tmp_path):
    ws = Workspace(tmp_path)
    pack = tmp_path / "packs" / "shouting"
    (pack / "scripts").mkdir(parents=True)
    (pack / "pack.py").write_text(
        'PACK = {"name": "shouting"}\n\ndef define(s):\n    s.define_schema("shouter", extends="creature", actions={"shout": {"script": "shout"}, "hum": {"script": "hum"}})\n')
    (pack / "scripts" / "_common.py").write_text("LOUD = 'LOUD'\n")
    (pack / "scripts" / "shout.py").write_text('use("common")\ndef apply(ctx):\n    ctx.emit("shouted", target=ctx.actor, reach=1, how=LOUD)\n')
    (pack / "scripts" / "hum.py").write_text('def apply(ctx):\n    ctx.emit("hummed", target=ctx.actor, reach=1, how="pack")\n')
    world = tmp_path / "worlds" / "the-pit"
    (world / "scripts").mkdir(parents=True)
    (world / "build.py").write_text(
        'WORLD = {"id": "the-pit", "name": "The Pit", "seed": 1, "requires": ["shouting"]}\n\n'
        'def populate(s):\n    root = s.summary()["root"]\n    s.spawn("place", root, "The Floor")\n    s.spawn("shouter", "The Floor", "Echo")\n')
    (world / "scripts" / "hum.py").write_text('def apply(ctx):\n    ctx.emit("hummed", target=ctx.actor, reach=1, how="world")\n')
    eng = Engine(workspace=tmp_path)
    gm = eng.session("gm", capabilities=[AUTHOR])
    r = load_world(gm, "the-pit")
    assert r["packs"] == ["shouting"] and r["scripts"] == ["hum"]
    assert "LOUD = 'LOUD'" in gm.script_source("shout")["source"]
    assert [s["id"] for s in gm.scripts()] == ["hum", "shout"]  # the pack's hum was never defined: the world's replaced it
    assert gm.script_source("hum")["version"] == 1
    you = eng.session("you")
    you.join("the-pit", "Echo")
    assert [e["kind"] for e in you.act("shout")["events"] if e["kind"] == "shouted"] == ["shouted"]
    r = you.act("hum")
    assert next(e for e in r["events"] if e["kind"] == "hummed")["payload"]["how"] == "world"
    # defined live, a script's use() lines expand as the loader expands them, and a bad script says why
    gm.define_script("yell", 'use("common")\ndef apply(ctx):\n    ctx.emit("yelled", target=ctx.actor, how=LOUD)\n')
    assert "LOUD = 'LOUD'" in gm.script_source("yell")["source"]
    with pytest.raises(Rejected, match="syntax error"):
        gm.define_script("broken", "def apply(ctx)\n    pass\n")
    # a missing include says what to do
    (world / "scripts" / "bad.py").write_text('use("nowhere")\ndef apply(ctx):\n    pass\n')
    gm2 = Engine(workspace=tmp_path).session("gm", capabilities=[AUTHOR])
    with pytest.raises(Rejected, match="nowhere"):
        load_world(gm2, "the-pit")
    with pytest.raises(Rejected, match="no world 'nope'"):
        load_world(gm2, "nope")


def _shouting_pack(root):
    pack = root / "packs" / "shouting"
    (pack / "scripts").mkdir(parents=True)
    (pack / "pack.py").write_text(
        'PACK = {"name": "shouting"}\nBODY_KEYS = ["voice"]\nRULES = [{"id": "loud", "date": "2026-11-01", "now": "shouts are loud"}]\n\n'
        'def define(s):\n    s.define_schema("shouter", extends="creature", actions={"shout": {"script": "shout"}, "hum": {"script": "hum"}})\n')
    (pack / "scripts" / "_common.py").write_text("LOUD = 'LOUD'\n")
    (pack / "scripts" / "shout.py").write_text('use("common")\ndef apply(ctx):\n    ctx.emit("shouted", target=ctx.actor, reach=1, how=LOUD)\n')
    (pack / "scripts" / "hum.py").write_text('def apply(ctx):\n    ctx.emit("hummed", target=ctx.actor, reach=1, how="pack")\n')
    world = root / "worlds" / "the-pit"
    (world / "scripts").mkdir(parents=True)
    (world / "build.py").write_text(
        'WORLD = {"id": "the-pit", "name": "The Pit", "seed": 1, "requires": ["shouting"]}\n\n'
        'def populate(s):\n    root = s.summary()["root"]\n    s.spawn("place", root, "The Floor")\n    s.spawn("shouter", "The Floor", "Echo")\n')
    return world


def _how(eng, verb, kind):
    you = eng.session("you")
    you.join("the-pit", "Echo")
    return next(e for e in you.act(verb)["events"] if e["kind"] == kind)["payload"]["how"]


def test_a_world_pack_of_the_same_name_overrides_the_workspace_pack(tmp_path):
    world = _shouting_pack(tmp_path)
    own = world / "packs" / "shouting"
    (own / "scripts").mkdir(parents=True)
    (own / "pack.py").write_text(
        'PACK = {"name": "shouting"}\n\ndef define(s):\n    s.define_schema("shouter", extends="creature", actions={"shout": {"script": "shout"}})\n')
    (own / "scripts" / "shout.py").write_text('def apply(ctx):\n    ctx.emit("shouted", target=ctx.actor, reach=1, how="mine")\n')
    eng = Engine(workspace=tmp_path)
    gm = eng.session("gm", capabilities=[AUTHOR])
    r = load_world(gm, "the-pit")
    assert r["packs"] == ["shouting"]
    assert [s["id"] for s in gm.scripts()] == ["shout"]  # the workspace pack's hum and its define never ran
    assert "voice" not in gm.world.declared("BODY_KEYS")
    assert _how(eng, "shout", "shouted") == "mine"


def test_a_world_pack_that_extends_layers_its_files_over_the_workspace_pack(tmp_path):
    world = _shouting_pack(tmp_path)
    (world / "scripts" / "hum.py").write_text('def apply(ctx):\n    ctx.emit("hummed", target=ctx.actor, reach=1, how="world")\n')
    own = world / "packs" / "shouting"
    (own / "scripts").mkdir(parents=True)
    (own / "pack.py").write_text(
        'EXTENDS = True\nBODY_KEYS = ["breath"]\nRULES = [{"id": "hoarse", "date": "2026-11-02", "now": "a long shout leaves you hoarse"}]\n\n'
        'def define(s):\n    s.define_schema("shouter", extends="creature", actions={"shout": {"script": "shout"}, '
        '"hum": {"script": "hum"}, "whisper": {"script": "whisper"}})\n')
    (own / "scripts" / "_common.py").write_text("LOUD = 'HOARSE'\n")  # the workspace pack's shout now reads this one
    (own / "scripts" / "whisper.py").write_text('use("common")\ndef apply(ctx):\n    ctx.emit("whispered", target=ctx.actor, reach=1, how=LOUD.lower())\n')
    eng = Engine(workspace=tmp_path)
    gm = eng.session("gm", capabilities=[AUTHOR])
    r = load_world(gm, "the-pit")
    assert r["packs"] == ["shouting"] and r["scripts"] == ["hum"]
    assert [s["id"] for s in gm.scripts()] == ["hum", "shout", "whisper"]
    assert gm.world.declared("BODY_KEYS") >= {"voice", "breath"}
    w = gm.world
    assert w.store.get("rules_change", w.id, "shouting:loud") and w.store.get("rules_change", w.id, "shouting.world:hoarse")
    assert _how(eng, "shout", "shouted") == "HOARSE" and _how(eng, "whisper", "whispered") == "hoarse"
    assert _how(eng, "hum", "hummed") == "world"  # the world's own scripts/ still win over every pack
    # defined live, use() finds the world pack's include first
    gm.define_script("yell", 'use("common")\ndef apply(ctx):\n    ctx.emit("yelled", target=ctx.actor, how=LOUD)\n')
    assert "LOUD = 'HOARSE'" in gm.script_source("yell")["source"]


def test_a_world_pack_needs_no_workspace_pack_unless_it_extends_one(tmp_path):
    world = _shouting_pack(tmp_path)
    (world / "build.py").write_text((world / "build.py").read_text().replace('["shouting"]', '["shouting", "echoes"]'))
    own = world / "packs" / "echoes"
    (own / "scripts").mkdir(parents=True)
    (own / "pack.py").write_text('def define(s):\n    s.define_schema("cave", extends="place")\n')
    (own / "scripts" / "echo.py").write_text('use("common")\ndef apply(ctx):\n    ctx.emit("echoed", target=ctx.actor, reach=1, how=LOUD)\n')
    gm = Engine(workspace=tmp_path).session("gm", capabilities=[AUTHOR])
    load_world(gm, "the-pit")
    assert "LOUD = 'LOUD'" in gm.script_source("echo")["source"]  # an include of a pack installed before it
    (own / "pack.py").write_text('EXTENDS = True\n')
    with pytest.raises(Rejected, match="extends the pack 'echoes'") as e:
        load_world(Engine(workspace=tmp_path).session("gm", capabilities=[AUTHOR]), "the-pit")
    assert "shouting" in e.value.hint


def test_a_pack_installs_the_packs_it_requires_first_and_each_once(tmp_path):
    # pack audit, 2026-11-28: a pack names what it reads (REQUIRES), so a split pack's parts come in by its name
    world = _shouting_pack(tmp_path)
    for name, req in (("voices", ["shouting"]), ("choir", ["voices", "shouting"])):
        d = tmp_path / "packs" / name
        (d / "scripts").mkdir(parents=True)
        (d / "pack.py").write_text(f"REQUIRES = {req!r}\n")
        (d / "scripts" / f"{name}_sing.py").write_text('use("common")\ndef apply(ctx):\n    ctx.emit("sang", target=ctx.actor, reach=1, how=LOUD)\n')
    (world / "build.py").write_text((world / "build.py").read_text().replace('["shouting"]', '["choir"]'))
    gm = Engine(workspace=tmp_path).session("gm", capabilities=[AUTHOR])
    r = load_world(gm, "the-pit")
    assert r["packs"] == ["shouting", "voices", "choir"]
    assert "LOUD = 'LOUD'" in gm.script_source("choir_sing")["source"]
    (tmp_path / "packs" / "shouting" / "pack.py").write_text('REQUIRES = ["choir"]\n')
    with pytest.raises(Rejected, match="in a ring: choir -> voices -> shouting -> choir"):
        load_world(Engine(workspace=tmp_path).session("gm", capabilities=[AUTHOR]), "the-pit")


def test_the_hosted_world_loads_by_id_the_samples_by_path_and_the_legacy_single_file_world_still_loads(tmp_path):
    # a hosted world is a folder under the workspace's worlds/: the fixture world, copied into a workspace of its own
    # with the packs it requires, as an owner's workspace would hold it
    for p in ("d20", "village", "vehicles", "beasts"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "packs" / "__init__.py").write_text("", encoding="utf-8")
    shutil.copytree(OUTPOST, tmp_path / "worlds" / "outpost", ignore=shutil.ignore_patterns("__pycache__", ".git"))
    made = Workspace(tmp_path).git_init(tmp_path)  # the owner's workspace is a repository
    eng = Engine(workspace=tmp_path)
    gm = eng.session("gm", capabilities=[AUTHOR])
    r = load_world(gm, "outpost")
    assert {"d20", "village"} <= set(r["packs"]) and {"creep", "ward_toggle", "trader_on"} <= set(r["scripts"])
    if made == "initialized":
        assert r["git"] == f"inside {tmp_path}"
    ids = {s["id"] for s in gm.scripts()}
    assert {"attack", "check", "talk", "take", "go", "creep"} <= ids and "_common" not in ids
    # worlds/ is the owner's: the hosted world is there, and whatever else the owner keeps beside it is not a failure
    assert "outpost" in [w["id"] for w in Workspace(tmp_path).list_worlds()]
    with pytest.raises(Rejected, match="already exists"):
        load_world(gm, "outpost")
    gm = Engine(workspace=REPO).session("gm", capabilities=[AUTHOR])
    r = load_world(gm, REPO / "examples" / "two-rooms")
    assert gm.world_id == r["id"] and r["folder"].endswith("two-rooms")
    ws = Workspace(REPO)
    samples = sorted(d.name for d in (REPO / "examples").iterdir() if (d / "build.py").exists())
    assert samples == ["ferry-at-dusk", "two-rooms"]
    assert {"d20", "locks", "village", "works"} <= set(ws.list_packs())  # beside any private pack the owner keeps


def test_a_pack_declares_its_own_mechanics_and_the_core_names_none(tmp_path):
    # 2026-11-22: the core named d20's thirst, factions and chronicle kinds for every world; now each pack declares them
    for p in ("d20", "village", "vehicles", "beasts"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "packs" / "__init__.py").write_text("", encoding="utf-8")
    shutil.copytree(OUTPOST, tmp_path / "worlds" / "outpost", ignore=shutil.ignore_patterns("__pycache__", ".git"))
    eng = Engine(workspace=tmp_path)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "outpost")
    w = eng.world("outpost")
    assert {"water", "faction"} <= w.declared("BODY_KEYS") and "outlawed" in w.declared("CHRONICLE_NEWS")
    assert w.declared("WAYS_OUT")["down (thirst)"].startswith("drink")
    before = w.meta()["pack_declares"]
    load_world(gm, "outpost", upgrade=True)
    assert eng.world("outpost").meta()["pack_declares"] == before  # a renew of the same code changes nothing
    from embody.world import BODY_KEYS
    from embody.ops import _NEWS_KINDS, _WAYS_OUT
    assert not {"water", "thirsty", "faction"} & BODY_KEYS and "outlawed" not in _NEWS_KINDS
    assert not any("thirst" in k or "roll" in v for k, v in _WAYS_OUT.items())


def test_save_and_restore_carry_a_game_as_one_file(tmp_path):
    eng = Engine(tmp_path / "embody.db", workspace=REPO, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, REPO / "examples" / "ferry-at-dusk")
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.act("go", "The Landing")
    t = gm.world.t
    p = tmp_path / "checkpoint.json"
    r = save_world(eng, "ferry-at-dusk", p)
    data = json.loads(p.read_text())
    assert data["embody_save"] == 1 and data["world"]["id"] == "ferry-at-dusk" and r["entities"] > 10
    r2 = gm.restore(str(p), id="ferry-again")
    assert r2["id"] == "ferry-again" and r2["entities"] == r["entities"] and r2["t"] == t
    gm.use("ferry-again")
    assert gm.inspect("Traveler")["parent"] == gm.inspect("The Landing")["id"]
    assert gm.world.meta()["restored_from"]["world"] == "ferry-at-dusk"
    assert gm.world.principal("you") is None
    with pytest.raises(Rejected, match="already exists"):
        gm.restore(str(p))


def test_init_makes_a_workspace_and_the_cli_knows_the_new_commands(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = init_workspace(tmp_path)
    assert (tmp_path / "worlds").is_dir() and (tmp_path / "packs").is_dir() and (tmp_path / ".mcp.json").exists()
    assert "embody.db" in (tmp_path / ".gitignore").read_text()
    assert init_workspace(tmp_path)["made"] == []
    db = tmp_path / "embody.db"
    cli_main(["--db", str(db), "--as", "gm", "--author", "create", "The Pit", "--id", "the-pit"])
    assert (tmp_path / "worlds" / "the-pit" / "build.py").exists()
    cli_main(["--db", str(db), "--as", "gm", "save", "one"])
    out = capsys.readouterr().out
    assert "saved the-pit" in out
    cli_main(["--db", str(db), "--as", "gm", "restore", str(tmp_path / "worlds" / "the-pit" / "saves" / "one.json"), "--id", "pit-2"])
    assert "restored pit-2" in capsys.readouterr().out
    cli_main(["--db", str(db), "--json", "worlds"])
    assert {w["id"] for w in json.loads(capsys.readouterr().out)} == {"the-pit", "pit-2"}


def test_the_database_defaults_to_the_workspace_root_but_a_legacy_worlds_db_keeps_working(tmp_path, monkeypatch):
    from embody.cli import db_path
    import argparse
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EMBODY_DB", raising=False)
    assert db_path(argparse.Namespace(db=None)) == Path("embody.db")
    (tmp_path / "worlds").mkdir()
    (tmp_path / "worlds" / "embody.db").write_bytes(b"")
    assert db_path(argparse.Namespace(db=None)) == Path("worlds") / "embody.db"
    assert Workspace.from_db(tmp_path / "worlds" / "embody.db").root == tmp_path
    assert Workspace.from_db(tmp_path / "embody.db").root == tmp_path


def test_the_global_flags_may_follow_any_subcommand(tmp_path, capsys):
    """.mcp.json writes `embody serve --as claude --author`: the flags after the subcommand broke when new
    subcommands were added above the one that took them (Nate's fresh session, 2026-11-10)."""
    from embody.cli import main
    db = str(tmp_path / "w.db")
    assert main(["worlds", "--db", db, "--as", "claude", "--author", "--json"]) == 0
    for cmd in ("serve", "worlds", "watch", "seats", "invite"):
        try:
            main([cmd, "--db", db, "--as", "claude", "--author", "--world", "x", "--json", "--help"])
        except SystemExit as e:
            assert e.code == 0, cmd
    assert "unrecognized" not in capsys.readouterr().err
