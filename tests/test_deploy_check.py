"""tools/deploy_check.py: the checklist before and after a deploy, against a fake host."""
import importlib.util
import io
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def dc():
    spec = importlib.util.spec_from_file_location("deploy_check", REPO / "tools" / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stage(root: Path, worlds: dict[str, int], domains: dict[str, str], remotes: dict[str, str] | None = None,
           at: int = 1) -> Path:
    """A stage like tools/stage_deploy.py makes: worlds/<id>/build.py, a site of n files, deploy/ and its manifest."""
    for wid, n in worlds.items():
        (root / "worlds" / wid).mkdir(parents=True)
        (root / "worlds" / wid / "build.py").write_text("WORLD = {}\n", encoding="utf-8")
        for i in range(n):
            (root / "worlds" / wid / "site").mkdir(exist_ok=True)
            (root / "worlds" / wid / "site" / f"f{i}.html").write_text("x", encoding="utf-8")
    (root / "deploy").mkdir(parents=True)
    (root / "deploy" / "worlds").write_text(",".join(worlds) + "\n", encoding="utf-8")
    man = {"engine": "abc1234", "staged_at": at, "domains": domains, "remotes": remotes or {},
           "worlds": {w: {"commit": f"c{w[:3]}", "site_files": n, "site_bytes": n} for w, n in worlds.items()}}
    (root / "deploy" / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
    return root


class Host:
    """A fake host: /health, the domains' pages, the remotes' /health and a door that knows one token."""

    def __init__(self, health: dict, pages: dict[str, int] | None = None, token: str = "", world: str = ""):
        self.health, self.pages, self.token, self.world = health, pages or {}, token, world

    def __call__(self, url, method="GET", body=None, headers=None, timeout=20):
        if url.endswith("/health"):  # the hub's, else a remote's own server
            h = (self.health() if callable(self.health) else self.health) if url.startswith("https://hub") else {"ok": 1}
            return 200, json.dumps(h)
        if url.endswith("/op/worlds"):
            ok = (headers or {}).get("Authorization") == f"Bearer {self.token}"
            return (200, json.dumps([{"id": self.world}])) if ok else (401, "{}")
        for prefix, code in self.pages.items():
            if url.startswith(prefix):
                return code, ""
        return 0, "ConnectError"


def run(dc, argv, get):
    out = io.StringIO()
    code = dc.main(argv, get=get, out=out)
    return code, out.getvalue()


def test_pre_fails_when_the_stage_drops_a_live_world_a_domain_or_a_site(dc, tmp_path):
    last = _stage(tmp_path / "last", {"alpha": 3, "beta": 0}, {"alpha.example": "alpha"})
    new = _stage(tmp_path / "new", {"alpha": 0}, {}, at=2)
    host = Host({"worlds": {"alpha": "up", "beta": "up"}})
    code, out = run(dc, ["pre", str(new), "--last", str(last), "--url", "https://hub"], host)
    assert code == 1
    assert "[FAIL] world beta: in the last stage, MISSING here" in out
    assert "[FAIL] world alpha: the last stage shipped its site (3 files)" in out
    assert "[FAIL] domain alpha.example: was -> alpha, now GONE" in out
    assert "[FAIL] live world beta (up): NOT in this stage" in out


def test_pre_passes_a_stage_that_only_adds_and_marks_what_changed(dc, tmp_path):
    last = _stage(tmp_path / "last", {"alpha": 3}, {"alpha.example": "alpha"}, {"far": "https://far.example"})
    new = _stage(tmp_path / "new", {"alpha": 3, "gamma": 0}, {"alpha.example": "alpha"}, {"far": "https://far.example"},
                 at=2)
    host = Host({"worlds": {"alpha": "up", "far": "remote"}})
    code, out = run(dc, ["pre", str(new), "--last", str(last), "--url", "https://hub"], host)
    assert code == 0, out
    assert "[note] world gamma: new on this host" in out
    assert "[  ok] live world far (remote): in this stage" in out and "pre: all clear" in out


def test_post_waits_for_the_new_container_then_checks_pages_remotes_and_doors(dc, tmp_path):
    stage = _stage(tmp_path / "stage", {"alpha": 2, "gamma": 0}, {"alpha.example": "alpha", "far.example": "far"},
                   {"far": "https://far.example"})
    sid = dc.read_stage(stage)["id"]
    (tmp_path / "tok.txt").write_text("paste ... Authorization: Bearer " + "t" * 40 + " ...", encoding="utf-8")
    host = Host({}, {"https://alpha.example": 200, "https://far.example": 401}, token="t" * 40, world="gamma")
    seq = iter([{"stage": "old", "worlds": {"alpha": "up"}},
                {"stage": sid, "worlds": {"alpha": "up", "gamma": "starting", "far": "remote"}},
                {"stage": sid, "worlds": {"alpha": "up", "gamma": "up", "far": "remote"}}])
    host.health = lambda: next(seq, {"stage": sid, "worlds": {"alpha": "up", "gamma": "up", "far": "remote"}})
    code, out = run(dc, ["post", str(stage), "--url", "https://hub", "--service", "hub", "--every", "0",
                         "--door", f"gamma={tmp_path / 'tok.txt'}"], host)
    assert code == 0, out
    assert f"[  ok] /health answers from this stage ({sid})" in out
    assert "[  ok] world gamma: up after" in out and "[  ok] world far: remote after" in out
    assert "[  ok] https://alpha.example/: 200 (alpha's site)" in out
    assert "[  ok] https://far.example/: 401 (forwarded to far's own server)" in out
    assert "[  ok] door gamma: a token's worlds() names gamma" in out
    assert "t" * 40 not in out
    assert (tmp_path / ".last-good-hub").read_text(encoding="utf-8").strip() == str(stage)


def test_post_fails_when_the_old_container_keeps_answering(dc, tmp_path):
    stage = _stage(tmp_path / "stage", {"alpha": 0}, {})
    host = Host({"stage": "old", "worlds": {"alpha": "up"}})
    code, out = run(dc, ["post", str(stage), "--url", "https://hub", "--service", "hub", "--wait", "0",
                         "--every", "0"], host)
    assert code == 1
    assert "[FAIL] /health never named this stage" in out and "[FAIL] world alpha:" in out
    assert not (tmp_path / ".last-good-hub").exists()


def test_pre_compares_with_the_services_last_good_stage(dc, tmp_path):
    last = _stage(tmp_path / "last", {"alpha": 0}, {})
    (tmp_path / ".last-good-hub").write_text(str(last), encoding="utf-8")
    new = _stage(tmp_path / "new", {"beta": 0}, {}, at=2)
    code, out = run(dc, ["pre", str(new), "--service", "hub"], Host({}))
    assert code == 1 and f"[note] comparing with {last}" in out and "world alpha: in the last stage, MISSING" in out
