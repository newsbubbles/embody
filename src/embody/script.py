"""embody scripts: a subset of Python the engine interprets itself.

Nothing here reaches eval or exec. Source is parsed with the stdlib `ast`
module, validated against a whitelist of node types, and executed by walking
the tree. Scripts get a fuel budget; running out is a clean failure.

What a script can do is exactly what the objects handed to it allow. The
engine passes a `ctx` (see world.py) whose methods are the op table. Attribute
access is allowed only on objects that subclass ScriptObject, on dicts (as key
lookup) and on a whitelist of str/list/dict methods. Names starting with an
underscore are never reachable.
"""

from __future__ import annotations

import ast
from typing import Any, Callable


class ScriptError(Exception):
    """A script failed. `reason` is for the caller, `hint` says what to do next."""

    def __init__(self, reason: str, hint: str | None = None, line: int | None = None):
        self.reason = reason
        self.hint = hint
        self.line = line
        where = f" (line {line})" if line else ""
        super().__init__(reason + where + (f" Hint: {hint}" if hint else ""))


class ScriptObject:
    """Marker base: attribute access from scripts is allowed on subclasses."""

    _script_attrs: tuple[str, ...] = ()

    def _script_get(self, name: str) -> Any:
        if name.startswith("_"):
            raise ScriptError(f"attribute {name!r} is private")
        if self._script_attrs and name not in self._script_attrs:
            raise ScriptError(
                f"{type(self).__name__} has no attribute {name!r}",
                hint=f"available: {', '.join(self._script_attrs)}",
            )
        try:
            return getattr(self, name)
        except AttributeError:
            raise ScriptError(
                f"{type(self).__name__} has no attribute {name!r}",
                hint=f"available: {', '.join(self._script_attrs) or 'none'}",
            ) from None

    def _script_set(self, name: str, value: Any) -> None:
        raise ScriptError(f"cannot assign {type(self).__name__}.{name}; it is read-only")


class _Return(Exception):
    def __init__(self, value: Any):
        self.value = value


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


ALLOWED_NODES: frozenset[type] = frozenset(
    {
        ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Pass,
        ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr, ast.If, ast.For, ast.While,
        ast.Break, ast.Continue,
        ast.BoolOp, ast.And, ast.Or, ast.BinOp, ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
        ast.Is, ast.IsNot,
        ast.Call, ast.keyword, ast.Constant, ast.Name, ast.Load, ast.Store,
        ast.Attribute, ast.Subscript, ast.Slice, ast.IfExp,
        ast.List, ast.Tuple, ast.Dict, ast.Set,
        ast.ListComp, ast.DictComp, ast.comprehension,
        ast.JoinedStr, ast.FormattedValue,
    }
)

METHOD_WHITELIST: dict[type, frozenset[str]] = {
    str: frozenset({"lower", "upper", "strip", "startswith", "endswith", "split", "join",
                    "replace", "title", "capitalize", "isdigit", "count", "find", "format"}),
    list: frozenset({"append", "pop", "extend", "index", "count", "insert", "remove", "reverse", "sort", "copy"}),
    dict: frozenset({"get", "keys", "values", "items", "pop", "setdefault", "update", "copy"}),
    tuple: frozenset({"index", "count"}),
    set: frozenset({"add", "discard", "remove", "pop", "copy"}),
}


def _safe_sorted(xs, key=None, reverse=False):
    return sorted(xs, key=key, reverse=reverse)


BUILTINS: dict[str, Callable] = {
    "len": len, "min": min, "max": max, "abs": abs, "int": int, "float": float, "str": str,
    "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "sorted": _safe_sorted, "range": range, "round": round, "sum": sum, "any": any, "all": all,
    "enumerate": enumerate, "zip": zip, "reversed": reversed, "isinstance": None,  # isinstance handled specially
}

_TYPE_NAMES = {"int": int, "float": float, "str": str, "list": list, "dict": dict, "bool": bool}


class Script:
    """A parsed, validated script. Call its top-level functions with `call`."""
    limits: "dict | None" = None  # a limited grant's reach, from its first line (world.limits_of)

    def __init__(self, source: str, name: str = "<script>"):
        self.name = name
        self.source = source
        try:
            self.tree = ast.parse(source, filename=name, mode="exec")
        except SyntaxError as e:
            raise ScriptError(f"syntax error: {e.msg}", hint="fix the script source", line=e.lineno) from None
        self.functions: dict[str, ast.FunctionDef] = {}
        self.constants: dict[str, Any] = {}
        self._validate()

    # ---- validation -----------------------------------------------------

    def _validate(self) -> None:
        for node in ast.walk(self.tree):
            t = type(node)
            if t not in ALLOWED_NODES:
                raise ScriptError(
                    f"{t.__name__} is not allowed in embody scripts",
                    hint="scripts are a Python subset: functions, if/for/while, expressions, "
                    "calls to ctx and builtins; no imports, classes, try, with, lambda, global",
                    line=getattr(node, "lineno", None),
                )
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise ScriptError(f"name {node.id!r} is not allowed", line=node.lineno)
            if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                raise ScriptError(f"attribute {node.attr!r} is private", line=node.lineno)
            if isinstance(node, ast.FunctionDef):
                a = node.args
                if a.vararg or a.kwarg or a.posonlyargs or a.kwonlyargs:
                    raise ScriptError("only plain positional parameters with optional defaults are allowed",
                                      line=node.lineno)
                if node.decorator_list:
                    raise ScriptError("decorators are not allowed", line=node.lineno)
        for stmt in self.tree.body:
            if isinstance(stmt, ast.FunctionDef):
                self.functions[stmt.name] = stmt
            elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                try:
                    self.constants[stmt.targets[0].id] = ast.literal_eval(stmt.value)
                except (ValueError, SyntaxError):
                    raise ScriptError("top-level assignments must be literal constants",
                                      hint="put logic inside a function", line=stmt.lineno) from None
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                continue  # docstring
            else:
                raise ScriptError("only function definitions and literal constants are allowed at the top level",
                                  line=stmt.lineno)

    def has(self, fn: str) -> bool:
        return fn in self.functions

    # ---- execution -------------------------------------------------------

    def call(self, fn: str, args: list[Any] | None = None, env: dict[str, Any] | None = None,
             fuel: int = 20_000) -> Any:
        """Run top-level function `fn` with positional `args`. `env` adds globals."""
        if fn not in self.functions:
            raise ScriptError(f"script {self.name!r} defines no function {fn!r}",
                              hint=f"defined: {', '.join(self.functions) or 'none'}")
        interp = _Interp(self, env or {}, fuel)
        return interp.call_function(self.functions[fn], list(args or []))


class _Interp:
    def __init__(self, script: Script, env: dict[str, Any], fuel: int):
        self.script = script
        self.globals: dict[str, Any] = dict(script.constants)
        self.globals.update(env)
        self.fuel = fuel

    def burn(self, node: ast.AST | None = None) -> None:
        self.fuel -= 1
        if self.fuel <= 0:
            raise ScriptError("script ran out of fuel",
                              hint="the script loops too much or does too much work for one call; "
                              "simplify it or split the work across ticks",
                              line=getattr(node, "lineno", None))

    # ---- functions

    def call_function(self, fn: ast.FunctionDef, args: list[Any]) -> Any:
        params = fn.args.args
        defaults = fn.args.defaults
        n_required = len(params) - len(defaults)
        if len(args) > len(params) or len(args) < n_required:
            raise ScriptError(
                f"{fn.name}() takes {n_required}"
                + (f" to {len(params)}" if defaults else "")
                + f" arguments, got {len(args)}",
                line=fn.lineno,
            )
        scope: dict[str, Any] = {}
        for i, p in enumerate(params):
            if i < len(args):
                scope[p.arg] = args[i]
            else:
                scope[p.arg] = self.eval(defaults[i - n_required], scope)
        try:
            self.exec_block(fn.body, scope)
        except _Return as r:
            return r.value
        return None

    # ---- statements

    def exec_block(self, body: list[ast.stmt], scope: dict[str, Any]) -> None:
        for stmt in body:
            self.exec(stmt, scope)

    def exec(self, node: ast.stmt, scope: dict[str, Any]) -> None:
        self.burn(node)
        m = getattr(self, "exec_" + type(node).__name__, None)
        if m is None:
            raise ScriptError(f"{type(node).__name__} is not supported", line=node.lineno)
        m(node, scope)

    def exec_Expr(self, node: ast.Expr, scope):
        self.eval(node.value, scope)

    def exec_Pass(self, node, scope):
        pass

    def exec_Return(self, node: ast.Return, scope):
        raise _Return(self.eval(node.value, scope) if node.value is not None else None)

    def exec_Break(self, node, scope):
        raise _Break()

    def exec_Continue(self, node, scope):
        raise _Continue()

    def exec_FunctionDef(self, node, scope):
        raise ScriptError("nested functions are not allowed", line=node.lineno)

    def exec_Assign(self, node: ast.Assign, scope):
        value = self.eval(node.value, scope)
        for target in node.targets:
            self.assign(target, value, scope)

    def exec_AnnAssign(self, node: ast.AnnAssign, scope):
        if node.value is not None:
            self.assign(node.target, self.eval(node.value, scope), scope)

    def exec_AugAssign(self, node: ast.AugAssign, scope):
        current = self.eval(node.target, scope)
        value = self.binop(node.op, current, self.eval(node.value, scope), node)
        self.assign(node.target, value, scope)

    def exec_If(self, node: ast.If, scope):
        if self.eval(node.test, scope):
            self.exec_block(node.body, scope)
        else:
            self.exec_block(node.orelse, scope)

    def exec_For(self, node: ast.For, scope):
        it = self.eval(node.iter, scope)
        if isinstance(it, dict):
            it = list(it.keys())
        try:
            seq = list(it)
        except TypeError:
            raise ScriptError(f"cannot iterate over {type(it).__name__}", line=node.lineno) from None
        for item in seq:
            self.burn(node)
            self.assign(node.target, item, scope)
            try:
                self.exec_block(node.body, scope)
            except _Break:
                break
            except _Continue:
                continue
        else:
            self.exec_block(node.orelse, scope)

    def exec_While(self, node: ast.While, scope):
        while self.eval(node.test, scope):
            self.burn(node)
            try:
                self.exec_block(node.body, scope)
            except _Break:
                break
            except _Continue:
                continue
        else:
            self.exec_block(node.orelse, scope)

    def assign(self, target: ast.expr, value: Any, scope: dict[str, Any]) -> None:
        if isinstance(target, ast.Name):
            scope[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            try:
                items = list(value)
            except TypeError:
                raise ScriptError("cannot unpack a non-sequence", line=target.lineno) from None
            if len(items) != len(target.elts):
                raise ScriptError(f"expected {len(target.elts)} values to unpack, got {len(items)}",
                                  line=target.lineno)
            for t, v in zip(target.elts, items):
                self.assign(t, v, scope)
        elif isinstance(target, ast.Subscript):
            obj = self.eval(target.value, scope)
            key = self.eval(target.slice, scope)
            if isinstance(obj, (dict, list)):
                try:
                    obj[key] = value
                except (IndexError, TypeError) as e:
                    raise ScriptError(str(e), line=target.lineno) from None
            elif isinstance(obj, ScriptObject):
                obj._script_set(key, value)
            else:
                raise ScriptError(f"cannot assign into {type(obj).__name__}", line=target.lineno)
        elif isinstance(target, ast.Attribute):
            obj = self.eval(target.value, scope)
            if isinstance(obj, ScriptObject):
                obj._script_set(target.attr, value)
            elif isinstance(obj, dict):
                obj[target.attr] = value
            else:
                raise ScriptError(f"cannot set attribute on {type(obj).__name__}", line=target.lineno)
        else:
            raise ScriptError("unsupported assignment target", line=getattr(target, "lineno", None))

    # ---- expressions

    def eval(self, node: ast.expr, scope: dict[str, Any]) -> Any:
        self.burn(node)
        m = getattr(self, "eval_" + type(node).__name__, None)
        if m is None:
            raise ScriptError(f"{type(node).__name__} is not supported", line=getattr(node, "lineno", None))
        return m(node, scope)

    def eval_Constant(self, node: ast.Constant, scope):
        return node.value

    def eval_Name(self, node: ast.Name, scope):
        if node.id in scope:
            return scope[node.id]
        if node.id in self.globals:
            return self.globals[node.id]
        if node.id in self.script.functions:
            return self.script.functions[node.id]
        if node.id in BUILTINS:
            return BUILTINS[node.id]
        if node.id in ("True", "False", "None"):
            return {"True": True, "False": False, "None": None}[node.id]
        raise ScriptError(f"name {node.id!r} is not defined",
                          hint="scripts see their parameters, top-level constants, ctx, and builtins",
                          line=node.lineno)

    def eval_JoinedStr(self, node: ast.JoinedStr, scope):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(str(v.value))
            else:
                out.append(self.eval(v, scope))
        return "".join(out)

    def eval_FormattedValue(self, node: ast.FormattedValue, scope):
        val = self.eval(node.value, scope)
        if node.conversion == ord("r"):
            val = repr(val)
        elif node.conversion == ord("s"):
            val = str(val)
        spec = self.eval(node.format_spec, scope) if node.format_spec else ""
        try:
            return format(val, spec)
        except (ValueError, TypeError) as e:
            raise ScriptError(f"bad format: {e}", line=node.lineno) from None

    def eval_List(self, node: ast.List, scope):
        return [self.eval(e, scope) for e in node.elts]

    def eval_Tuple(self, node: ast.Tuple, scope):
        return tuple(self.eval(e, scope) for e in node.elts)

    def eval_Set(self, node: ast.Set, scope):
        return {self.eval(e, scope) for e in node.elts}

    def eval_Dict(self, node: ast.Dict, scope):
        out = {}
        for k, v in zip(node.keys, node.values):
            if k is None:
                out.update(self.eval(v, scope))
            else:
                out[self.eval(k, scope)] = self.eval(v, scope)
        return out

    def _comprehend(self, generators: list[ast.comprehension], scope: dict, emit: Callable[[dict], None]):
        def rec(i: int, sc: dict):
            if i == len(generators):
                emit(sc)
                return
            g = generators[i]
            it = self.eval(g.iter, sc)
            if isinstance(it, dict):
                it = list(it.keys())
            for item in list(it):
                self.burn(g.iter)
                inner = dict(sc)
                self.assign(g.target, item, inner)
                if all(self.eval(cond, inner) for cond in g.ifs):
                    rec(i + 1, inner)
        rec(0, scope)

    def eval_ListComp(self, node: ast.ListComp, scope):
        out: list[Any] = []
        self._comprehend(node.generators, scope, lambda sc: out.append(self.eval(node.elt, sc)))
        return out

    def eval_DictComp(self, node: ast.DictComp, scope):
        out: dict[Any, Any] = {}
        self._comprehend(node.generators, scope,
                         lambda sc: out.__setitem__(self.eval(node.key, sc), self.eval(node.value, sc)))
        return out

    def eval_IfExp(self, node: ast.IfExp, scope):
        return self.eval(node.body, scope) if self.eval(node.test, scope) else self.eval(node.orelse, scope)

    def eval_BoolOp(self, node: ast.BoolOp, scope):
        if isinstance(node.op, ast.And):
            val = True
            for v in node.values:
                val = self.eval(v, scope)
                if not val:
                    return val
            return val
        val = False
        for v in node.values:
            val = self.eval(v, scope)
            if val:
                return val
        return val

    def eval_UnaryOp(self, node: ast.UnaryOp, scope):
        v = self.eval(node.operand, scope)
        if isinstance(node.op, ast.Not):
            return not v
        if isinstance(node.op, ast.USub):
            return -v
        return +v

    def binop(self, op: ast.operator, a: Any, b: Any, node: ast.AST) -> Any:
        try:
            if isinstance(op, ast.Add):
                return a + b
            if isinstance(op, ast.Sub):
                return a - b
            if isinstance(op, ast.Mult):
                if isinstance(a, (str, list, tuple)) and isinstance(b, int) and b > 10_000:
                    raise ScriptError("repeat count too large", line=getattr(node, "lineno", None))
                if isinstance(b, (str, list, tuple)) and isinstance(a, int) and a > 10_000:
                    raise ScriptError("repeat count too large", line=getattr(node, "lineno", None))
                return a * b
            if isinstance(op, ast.Div):
                return a / b
            if isinstance(op, ast.FloorDiv):
                return a // b
            if isinstance(op, ast.Mod):
                return a % b
            if isinstance(op, ast.Pow):
                if isinstance(b, (int, float)) and abs(b) > 64:
                    raise ScriptError("exponent too large", line=getattr(node, "lineno", None))
                return a ** b
        except ScriptError:
            raise
        except (TypeError, ZeroDivisionError, ValueError) as e:
            raise ScriptError(str(e), line=getattr(node, "lineno", None)) from None
        raise ScriptError(f"operator {type(op).__name__} not supported", line=getattr(node, "lineno", None))

    def eval_BinOp(self, node: ast.BinOp, scope):
        return self.binop(node.op, self.eval(node.left, scope), self.eval(node.right, scope), node)

    def eval_Compare(self, node: ast.Compare, scope):
        left = self.eval(node.left, scope)
        for op, comp in zip(node.ops, node.comparators):
            right = self.eval(comp, scope)
            try:
                if isinstance(op, ast.Eq):
                    ok = left == right
                elif isinstance(op, ast.NotEq):
                    ok = left != right
                elif isinstance(op, ast.Lt):
                    ok = left < right
                elif isinstance(op, ast.LtE):
                    ok = left <= right
                elif isinstance(op, ast.Gt):
                    ok = left > right
                elif isinstance(op, ast.GtE):
                    ok = left >= right
                elif isinstance(op, ast.In):
                    ok = left in right
                elif isinstance(op, ast.NotIn):
                    ok = left not in right
                elif isinstance(op, ast.Is):
                    ok = left is right
                elif isinstance(op, ast.IsNot):
                    ok = left is not right
                else:
                    raise ScriptError("comparison not supported", line=node.lineno)
            except TypeError as e:
                raise ScriptError(str(e), line=node.lineno) from None
            if not ok:
                return False
            left = right
        return True

    def eval_Subscript(self, node: ast.Subscript, scope):
        obj = self.eval(node.value, scope)
        if isinstance(node.slice, ast.Slice):
            lo = self.eval(node.slice.lower, scope) if node.slice.lower else None
            hi = self.eval(node.slice.upper, scope) if node.slice.upper else None
            st = self.eval(node.slice.step, scope) if node.slice.step else None
            try:
                return obj[lo:hi:st]
            except TypeError as e:
                raise ScriptError(str(e), line=node.lineno) from None
        key = self.eval(node.slice, scope)
        if isinstance(obj, ScriptObject):
            return obj._script_get(key) if isinstance(key, str) else obj._script_get(str(key))
        try:
            return obj[key]
        except KeyError:
            raise ScriptError(f"key {key!r} not found", hint="use .get(key, default) if the key may be missing",
                              line=node.lineno) from None
        except (IndexError, TypeError) as e:
            raise ScriptError(str(e), line=node.lineno) from None

    def eval_Attribute(self, node: ast.Attribute, scope):
        obj = self.eval(node.value, scope)
        name = node.attr
        if isinstance(obj, ScriptObject):
            try:
                return obj._script_get(name)
            except ScriptError as e:
                e.line = e.line or node.lineno
                raise
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
            if name in METHOD_WHITELIST[dict]:
                return getattr(obj, name)
            raise ScriptError(f"key {name!r} not found", hint="use .get(key, default) if the key may be missing",
                              line=node.lineno)
        for typ, allowed in METHOD_WHITELIST.items():
            if isinstance(obj, typ):
                if name in allowed:
                    return getattr(obj, name)
                raise ScriptError(f"{typ.__name__}.{name} is not allowed",
                                  hint=f"allowed: {', '.join(sorted(allowed))}", line=node.lineno)
        raise ScriptError(f"attribute access on {type(obj).__name__} is not allowed", line=node.lineno)

    def eval_Call(self, node: ast.Call, scope):
        if isinstance(node.func, ast.Name) and node.func.id == "isinstance":
            if len(node.args) != 2 or not isinstance(node.args[1], ast.Name) or node.args[1].id not in _TYPE_NAMES:
                raise ScriptError("isinstance(x, T) where T is int, float, str, list, dict or bool", line=node.lineno)
            return isinstance(self.eval(node.args[0], scope), _TYPE_NAMES[node.args[1].id])
        fn = self.eval(node.func, scope)
        args = [self.eval(a, scope) for a in node.args]
        kwargs = {}
        for kw in node.keywords:
            if kw.arg is None:
                kwargs.update(self.eval(kw.value, scope))
            else:
                kwargs[kw.arg] = self.eval(kw.value, scope)
        if isinstance(fn, ast.FunctionDef):
            if kwargs:
                raise ScriptError("script functions take positional arguments only", line=node.lineno)
            return self.call_function(fn, args)
        if isinstance(node.func, ast.Name) and node.func.id in self.script.functions and node.func.id not in scope:
            return self.call_function(self.script.functions[node.func.id], args)
        if not callable(fn):
            raise ScriptError(f"{type(fn).__name__} is not callable", line=node.lineno)
        try:
            return fn(*args, **kwargs)
        except ScriptError as e:
            e.line = e.line or node.lineno
            raise
        except TypeError as e:
            raise ScriptError(str(e), line=node.lineno) from None

    def eval_Name_function(self, name: str):
        return self.script.functions.get(name)
