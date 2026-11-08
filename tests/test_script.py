import pytest

from embody.script import Script, ScriptError, ScriptObject


def run(src, fn="main", *args, env=None, fuel=20_000):
    return Script(src).call(fn, list(args), env=env, fuel=fuel)


def test_arithmetic_and_control_flow():
    src = """
LIMIT = 3
def main(n):
    total = 0
    for i in range(n):
        if i % 2 == 0:
            total += i
        else:
            total -= 1
    while total < LIMIT:
        total += 1
    return total
"""
    assert run(src, "main", 6) == max(0 + 2 + 4 - 3, 3)


def test_helpers_strings_and_collections():
    src = """
def dmg(base, armor):
    return max(0, base - armor)

def main():
    hits = [dmg(5, 2), dmg(1, 4)]
    names = {"a": "Brann", "b": "Ysolde"}
    out = [n.lower() for n in names.values() if n.startswith("B")]
    return f"{sum(hits)}:{','.join(out)}:{names.get('z', 'none')}"
"""
    assert run(src) == "3:brann:none"


def test_fuel_limit():
    src = """
def main():
    x = 0
    while True:
        x += 1
"""
    with pytest.raises(ScriptError) as e:
        run(src, fuel=500)
    assert "fuel" in e.value.reason


@pytest.mark.parametrize(
    "src",
    [
        "import os",
        "def main():\n    return open('x')",
        "def main():\n    return ().__class__",
        "class A: pass",
        "def main():\n    try:\n        pass\n    except Exception:\n        pass",
        "def main():\n    f = lambda: 1",
        "def main():\n    return [].__len__()",
        "x = len('a')",
    ],
)
def test_forbidden_constructs(src):
    with pytest.raises(ScriptError):
        Script(src).call("main") if "def main" in src else Script(src)


def test_script_objects_and_attribute_rules():
    class Door(ScriptObject):
        _script_attrs = ("open", "toggle")

        def __init__(self):
            self.open = False
            self.secret = 1

        def toggle(self):
            self.open = not self.open
            return self.open

        def _script_set(self, name, value):
            if name == "open":
                self.open = bool(value)
            else:
                super()._script_set(name, value)

    d = Door()
    src = """
def main(door):
    door.toggle()
    door.open = door.open and True
    return door.open
"""
    assert run(src, "main", d) is True
    with pytest.raises(ScriptError):
        run("def main(d):\n    return d.secret", "main", d)
    with pytest.raises(ScriptError):
        run("def main(d):\n    return d.toggle.__name__", "main", d)


def test_missing_name_error_points_forward():
    with pytest.raises(ScriptError) as e:
        run("def main():\n    return ctx")
    assert "not defined" in e.value.reason
    assert e.value.hint
