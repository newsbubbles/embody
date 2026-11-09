"""The workspace: a world is a folder. create_world makes it (and a git repository), live authoring lands in it,
a fresh build replays it, scripts are files that may use() each other, packs are shared define-only folders,
save and restore carry a game as one file, and the old single-file worlds still load."""

import json
from pathlib import Path

import pytest

from embody.cli import init_workspace, load_world, main as cli_main
from embody.ops import AUTHOR, Engine, Rejected
from embody.workspace import Workspace, save_world

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


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
    # a missing include says what to do
    (world / "scripts" / "bad.py").write_text('use("nowhere")\ndef apply(ctx):\n    pass\n')
    gm2 = Engine(workspace=tmp_path).session("gm", capabilities=[AUTHOR])
    with pytest.raises(Rejected, match="nowhere"):
        load_world(gm2, "the-pit")
    with pytest.raises(Rejected, match="no world 'nope'"):
        load_world(gm2, "nope")


def test_the_samples_load_by_id_and_the_legacy_single_file_world_still_loads():
    eng = Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    r = load_world(gm, "glass-reach")
    assert r["packs"] == ["d20", "village"] and set(r["scripts"]) == {"go", "creep", "ward_toggle", "ossa_on", "reach_story"}
    assert r["git"].startswith("inside")
    ids = {s["id"] for s in gm.scripts()}
    assert {"attack", "check", "talk", "take", "go", "reach_story"} <= ids and "_common" not in ids
    r = load_world(gm, "two-rooms")
    assert gm.world_id == r["id"] and r["folder"].endswith("two-rooms")
    ws = Workspace(REPO)
    assert [w["id"] for w in ws.list_worlds()] == ["ferry-at-dusk", "glass-reach", "two-rooms"]
    assert ws.list_packs() == ["d20", "village"]
    assert ws.list_worlds()[0]["manifest"]["requires"] == ["village"]
    with pytest.raises(Rejected, match="already exists"):
        load_world(gm, "glass-reach")


def test_save_and_restore_carry_a_game_as_one_file(tmp_path):
    eng = Engine(tmp_path / "embody.db", workspace=REPO, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "ferry-at-dusk")
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
