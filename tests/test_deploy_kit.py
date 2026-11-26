"""The single-world deploy kit a new host starts from: deploy/start.sh picks the world (EMBODY_WORLD by name or by path,
deploy/world from the stage, else the only folder under worlds/) and stops with a clear line when there is none, and
tools/stage_deploy.py ships a world that lives only on disk under worlds/ (git ignores it) or a sample by its path."""

import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
SH = shutil.which("sh")

BUILD = 'WORLD = {{"id": "{id}", "name": "{id}", "seed": 0, "requires": []}}\n'


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


# ---- deploy/start.sh ---------------------------------------------------------------


def _start(tmp: Path, env: dict[str, str] | None = None, known: str = "[]", real: bool = False
           ) -> tuple[int, str, list[str]]:
    """Run a copy of start.sh in tmp with `embody` stubbed: it logs its arguments and answers `--json worlds` with
    `known`, or with real=True runs the real CLI for everything but serve. Returns the exit code, stderr (stdout
    too, when real) and the embody calls."""
    shutil.copy(REPO / "deploy" / "start.sh", _write(tmp / "deploy" / "start.sh", ""))
    bin_ = tmp / "bin"
    log = tmp / "calls.log"
    log.unlink(missing_ok=True)
    py =Path(sys.executable).as_posix()
    _write(bin_ / "embody", '#!/bin/sh\necho "$*" >> "$STUB_LOG"\n'
                            'case "$*" in *serve*) echo "env world=$EMBODY_WORLD site=${EMBODY_SITE:-}" >> "$STUB_LOG";'
                            ' exit 0;; esac\n'
                            + (f'exec "{py}" -m embody.cli "$@"\n' if real else
                               'case "$*" in *--json*) echo "$STUB_KNOWN";; esac\n'))
    _write(bin_ / "python", f'#!/bin/sh\nexec "{py}" "$@"\n')
    for f in ("embody", "python"):
        (bin_ / f).chmod(0o755)
    e = {k: v for k, v in os.environ.items() if not k.startswith("EMBODY_")}
    e.update({"PATH": str(bin_) + os.pathsep + e.get("PATH", ""), "STUB_LOG": str(log), "STUB_KNOWN": known,
              "EMBODY_DB": "/data/embody.db", "PORT": "8123"}, **(env or {}))
    r = subprocess.run([SH, "deploy/start.sh"], cwd=tmp, env=e, capture_output=True, text=True, timeout=120)
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return r.returncode, r.stderr + (r.stdout if real else ""), calls


needs_sh = pytest.mark.skipif(SH is None, reason="no POSIX sh on PATH")


@needs_sh
def test_no_world_stops_with_a_clear_line(tmp_path):
    _write(tmp_path / "worlds" / "put_worlds_here.txt", "")
    code, err, calls = _start(tmp_path)
    assert code == 64
    assert "no world to host" in err and "EMBODY_WORLD=examples/ferry-at-dusk" in err
    assert calls == []


@needs_sh
def test_the_only_world_under_worlds_is_built_then_served(tmp_path):
    _write(tmp_path / "worlds" / "mine" / "build.py", BUILD.format(id="mine"))
    code, err, calls = _start(tmp_path)
    assert code == 0, err
    assert calls[1] == "--db /data/embody.db --author load mine --hosted"
    assert calls[-2].startswith("--db /data/embody.db --author serve --http --host 0.0.0.0 --port 8123")
    assert calls[-1] == "env world=mine site="


@needs_sh
def test_several_worlds_ask_which(tmp_path):
    for w in ("one", "two"):
        _write(tmp_path / "worlds" / w / "build.py", BUILD.format(id=w))
    code, err, _ = _start(tmp_path)
    assert code == 64 and "which world" in err and "one two" in err


@needs_sh
def test_a_sample_path_loads_by_path_and_renews_by_its_manifest_id(tmp_path):
    _write(tmp_path / "examples" / "sample" / "build.py", BUILD.format(id="the-sample"))
    _write(tmp_path / "examples" / "sample" / "site" / "index.html", "<p>the sample</p>")
    code, err, calls = _start(tmp_path, {"EMBODY_WORLD": "examples/sample"})
    assert code == 0, err
    assert calls[1] == "--db /data/embody.db --author load examples/sample --hosted"
    assert calls[-1] == "env world=the-sample site=examples/sample/site"  # serve gets the id, not the path
    code, err, calls = _start(tmp_path, {"EMBODY_WORLD": "examples/sample"}, known='[{"id": "the-sample"}]')
    assert code == 0, err
    assert "--db /data/embody.db --author --world the-sample load examples/sample --upgrade --hosted" in calls


@needs_sh
def test_the_staged_choice_wins_over_the_folder_scan(tmp_path):
    for w in ("one", "two"):
        _write(tmp_path / "worlds" / w / "build.py", BUILD.format(id=w))
    _write(tmp_path / "deploy" / "world", "two\n")
    code, err, calls = _start(tmp_path)
    assert code == 0, err
    assert calls[1] == "--db /data/embody.db --author load two --hosted"


def _events(p: Path) -> int:
    c = sqlite3.connect(p)
    try:
        return c.execute("SELECT count(*) FROM event").fetchone()[0]
    finally:
        c.close()


def _volume(tmp: Path) -> tuple[Path, dict[str, str]]:
    """A workspace with the ferry sample as its only world, built once into data/embody.db by a real boot."""
    shutil.copytree(REPO / "examples" / "ferry-at-dusk", tmp / "worlds" / "ferry-at-dusk",
                    ignore=shutil.ignore_patterns("tests", "saves", "__pycache__"))
    shutil.copytree(REPO / "packs" / "village", tmp / "packs" / "village",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    db = tmp / "data" / "embody.db"
    db.parent.mkdir()
    env = {"EMBODY_DB": db.as_posix(), "EMBODY_WORKSPACE": tmp.as_posix(), "EMBODY_AS": "host"}
    code, out, _ = _start(tmp, env, real=True)
    assert code == 0, out
    assert "building ferry-at-dusk" in out
    return db, env


def _on(db: Path, calls: list[str]) -> bool:
    """Every embody call of the boot named this file, serve included."""
    named = [c for c in calls if not c.startswith("env ")]
    return bool(named) and all(c.startswith(f"--db {db.as_posix()} ") for c in named) and "serve" in named[-1]


@needs_sh
def test_with_no_hub_file_the_renew_and_serve_use_embody_db(tmp_path):
    db, env = _volume(tmp_path)
    before = _events(db)
    code, out, calls = _start(tmp_path, env, real=True)
    assert code == 0, out
    assert "renewing ferry-at-dusk" in out and "hub's file" not in out
    assert _events(db) > before
    assert _on(db, calls)


@needs_sh
def test_a_hub_file_is_the_world_and_the_old_embody_db_is_left_alone(tmp_path):
    """After a hub's first boot the world lives in <folder of $EMBODY_DB>/worlds/<id>.db and $EMBODY_DB is the stale
    file it left. The CLI picks the hub's file only for a call naming --world and serve names none, so a boot that
    left it to the CLI renewed the hub's file and served the stale one (the Reach served ten days back)."""
    db, env = _volume(tmp_path)
    hub = db.parent / "worlds" / "ferry-at-dusk.db"
    hub.parent.mkdir()
    shutil.copy(db, hub)
    old, before = db.read_bytes(), _events(hub)
    code, out, calls = _start(tmp_path, env, real=True)
    assert code == 0, out
    assert f"the world is in the hub's file {hub.as_posix()}" in out
    assert _events(hub) > before, "the renew must reach the hub's file"
    assert _on(hub, calls), "serve must read the file the renew upgraded"
    assert db.read_bytes() == old


@needs_sh
def test_embody_db_set_to_the_hub_file_works_the_same(tmp_path):
    db, env = _volume(tmp_path)
    hub = db.parent / "worlds" / "ferry-at-dusk.db"
    hub.parent.mkdir()
    shutil.copy(db, hub)
    old, before = db.read_bytes(), _events(hub)
    code, out, calls = _start(tmp_path, {**env, "EMBODY_DB": hub.as_posix()}, real=True)
    assert code == 0, out
    assert "renewing ferry-at-dusk" in out and "hub's file" not in out
    assert _events(hub) > before
    assert _on(hub, calls)
    assert db.read_bytes() == old


@needs_sh
def test_a_missing_world_names_where_it_looked(tmp_path):
    code, err, calls = _start(tmp_path, {"EMBODY_WORLD": "glass-reach"})
    assert code == 64 and "no world at worlds/glass-reach" in err
    assert calls == []


# ---- tools/stage_deploy.py ---------------------------------------------------------


@pytest.fixture
def stage(tmp_path, monkeypatch):
    """stage_deploy pointed at a small engine repository in tmp: deploy/, worlds/ with only the placeholder tracked,
    and a sample under examples/."""
    spec = importlib.util.spec_from_file_location("stage_deploy", REPO / "tools" / "stage_deploy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    root = tmp_path / "engine"
    _write(root / "deploy" / "start.sh", "#!/bin/sh\n")
    _write(root / "worlds" / "put_worlds_here.txt", "")
    _write(root / ".gitignore", "worlds/*\n!worlds/put_worlds_here.txt\n*.db\n")
    _write(root / "examples" / "sample" / "build.py", BUILD.format(id="sample"))
    git = ["git", "-c", "user.email=test@example.com", "-c", "user.name=test", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "engine"], cwd=root, check=True)
    monkeypatch.setattr(mod, "ROOT", root)
    return mod, root, tmp_path / "stage"


def test_a_world_only_on_disk_ships_without_its_working_files(stage):
    mod, root, out = stage
    w = root / "worlds" / "mine"
    _write(w / "build.py", BUILD.format(id="mine"))
    _write(w / "scripts" / "door.py", "# a script\n")
    _write(w / "private" / "codes.txt", "lock words\n")
    _write(w / "mirror" / "state.json", "{}")
    _write(w / "embody.db", "")
    _write(w / ".embody.json", "{}")
    assert mod.main(["--world", "mine", "--out", str(out)]) == 0
    got = out / "worlds" / "mine"
    assert (got / "build.py").is_file() and (got / "scripts" / "door.py").is_file()
    assert (got / "private" / "codes.txt").is_file()
    assert not (got / "mirror").exists() and not (got / "embody.db").exists() and not (got / ".embody.json").exists()
    assert (out / "deploy" / "world").read_text(encoding="utf-8") == "mine\n"
    assert not (out / "deploy" / "worlds").exists()


def test_a_sample_ships_by_its_path(stage):
    mod, root, out = stage
    assert mod.main(["--world", "examples\\sample", "--out", str(out)]) == 0
    assert (out / "examples" / "sample" / "build.py").is_file()
    assert (out / "deploy" / "world").read_text(encoding="utf-8") == "examples/sample\n"


def test_a_world_that_is_nowhere_is_refused(stage):
    mod, root, out = stage
    with pytest.raises(SystemExit, match="no world nope"):
        mod.main(["--world", "nope", "--out", str(out)])
    with pytest.raises(SystemExit, match="no world at examples/nope"):
        mod.main(["--world", "examples/nope", "--out", str(tmp := out.with_name("stage2"))])
    assert mod.main(["--world", "examples/sample", "--world", "mine", "--out", str(tmp.with_name("s3"))]) == 2


def test_a_world_with_its_own_repository_ships_its_head_or_the_commit_it_is_pinned_to(stage):
    mod, root, out = stage
    w = root / "worlds" / "own"
    git = ["git", "-c", "user.email=test@example.com", "-c", "user.name=test", "-c", "commit.gpgsign=false"]
    _write(w / "build.py", BUILD.format(id="own"))
    subprocess.run(["git", "init", "-q"], cwd=w, check=True)
    subprocess.run(["git", "add", "."], cwd=w, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "live"], cwd=w, check=True)
    live = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=w, capture_output=True, text=True).stdout.strip()
    _write(w / "scripts" / "proposal.py", "# not picked for live yet\n")
    subprocess.run(["git", "add", "."], cwd=w, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "a proposal"], cwd=w, check=True)
    assert mod.main(["--world", "own", "--out", str(out)]) == 0
    assert (out / "worlds" / "own" / "scripts" / "proposal.py").is_file()
    pinned = out.with_name("pinned")
    assert mod.main(["--world", f"own@{live}", "--out", str(pinned)]) == 0
    assert (pinned / "worlds" / "own" / "build.py").is_file()
    assert not (pinned / "worlds" / "own" / "scripts" / "proposal.py").exists()
    man = json.loads((pinned / "deploy" / "manifest.json").read_text(encoding="utf-8"))
    assert man["worlds"]["own"]["commit"] == live and (pinned / "deploy" / "world").read_text(encoding="utf-8") == "own\n"
    with pytest.raises(SystemExit, match="has no commit nope"):
        mod.main(["--world", "own@nope", "--out", str(out.with_name("bad"))])


def test_two_worlds_still_make_a_hub(stage):
    mod, root, out = stage
    for w in ("one", "two"):
        _write(root / "worlds" / w / "build.py", BUILD.format(id=w))
    assert mod.main(["--world", "one", "--world", "two", "--out", str(out)]) == 0
    assert (out / "deploy" / "worlds").read_text(encoding="utf-8") == "one,two\n"
    assert not (out / "deploy" / "world").exists()
    man = json.loads((out / "deploy" / "manifest.json").read_text(encoding="utf-8"))
    assert set(man["worlds"]) == {"one", "two"} and man["engine"] and man["staged_at"]


def test_health_names_the_stage_it_runs(tmp_path, monkeypatch):
    from embody import hub
    (tmp_path / "deploy").mkdir()
    (tmp_path / "deploy" / "manifest.json").write_text('{"staged_at": 1}', encoding="utf-8")
    monkeypatch.setenv("EMBODY_WORKSPACE", str(tmp_path))
    hub.stage_id.cache_clear()
    try:
        assert hub.stage_id() == hashlib.sha256(b'{"staged_at": 1}').hexdigest()[:12]
    finally:
        hub.stage_id.cache_clear()
