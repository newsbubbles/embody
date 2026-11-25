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


def test_the_trimming_and_splitting_methods_an_author_reaches_for():
    src = """
def main(text):
    head, _, tail = text.partition(":")
    return [text.rstrip("."), text.lstrip("M"), head, tail.removesuffix("..").rsplit(" ", 1)[0], "a\\nb".splitlines()]
"""
    assert run(src, "main", "Marr: the gate is open..") == [
        "Marr: the gate is open", "arr: the gate is open..", "Marr", " the gate is", ["a", "b"]]
    with pytest.raises(ScriptError, match="not allowed"):
        run('def main():\n    return "x".ljust(10)\n')  # padding grows a string past its input: still out


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


def test_a_call_on_a_dicts_method_name_is_the_method_even_with_a_key_of_that_name():
    # a phrase table whose keys came from players held the key "get", and table.get(k) called the entry
    src = """
def main(t):
    return [t.get('hello', 'none'), t.get('nope', 'none'), t.get, len(t.keys()), t.height]
"""
    assert run(src, "main", {"get": "a word", "hello": "hi", "height": 3}) == ["hi", "none", "a word", 3, 3]
