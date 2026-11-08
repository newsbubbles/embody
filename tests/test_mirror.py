from embody.mirror import Mirror
from embody.store import Store
from tests.test_world import build, ids


def test_mirror_projects_containment_as_directories(tmp_path):
    w = build(Store())
    i = ids(w)
    m = Mirror(w, tmp_path / "mirror")
    r = m.write()
    root = tmp_path / "mirror"
    assert (root / "WORLD.md").exists()
    cell = root / f"two-rooms.{w.root_id}" / f"cell.{i['Cell']}"
    assert (cell / "index.md").exists()
    door = (cell / f"iron-door.{i['Iron door']}.md").read_text(encoding="utf-8")
    assert "locked" in door and "`unlock`" in door
    assert (root / "schemas" / "door.md").exists()
    assert (root / "scripts" / "go.py").exists()
    assert r["files"] > 10
    # the prisoner picks up the key: the key file moves under the prisoner and the old one is pruned
    w.act(i["Prisoner"], "take", i["Rusty key"])
    r2 = m.write()
    assert r2["removed"] == 2  # the key's old file, and the prisoner's leaf file (now a directory)
    assert not (cell / f"rusty-key.{i['Rusty key']}.md").exists()
    prisoner_dir = cell / f"prisoner.{i['Prisoner']}"
    assert (prisoner_dir / f"rusty-key.{i['Rusty key']}.md").exists()
    assert "moved" in (root / "events.md").read_text(encoding="utf-8")
