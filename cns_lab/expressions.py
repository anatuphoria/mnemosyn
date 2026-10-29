from __future__ import annotations

import ast
import keyword
import math
import types
from collections.abc import Callable

FUNCTIONS = {"exp": 1, "log": 1, "cos": 1, "sin": 1, "min": 2, "max": 2, "hill": 3, "pos": 1}
CONSTANTS = {"pi": math.pi}
_OPERATORS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)


class ExpressionError(ValueError):
    pass


def hill(x: float, k: float, n: float) -> float:
    return 1.0 / (1.0 + (x / k) ** n)


def pos(x: float) -> float:
    return max(0.0, x)


_GLOBALS = {"__builtins__": {}, "exp": math.exp, "log": math.log, "cos": math.cos,
            "sin": math.sin, "min": min, "max": max, "hill": hill, "pos": pos, **CONSTANTS}


def _check(node: ast.AST, text: str, found: set[str]) -> None:
    if isinstance(node, ast.Expression):
        _check(node.body, text, found)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, _OPERATORS):
        _check(node.left, text, found)
        _check(node.right, text, found)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        _check(node.operand, text, found)
    elif (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
          and not isinstance(node.value, bool)):
        return
    elif isinstance(node, ast.Name):
        if node.id in FUNCTIONS:
            raise ExpressionError(f"{text!r}: {node.id} is a function")
        if node.id not in CONSTANTS:
            found.add(node.id)
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        arity = FUNCTIONS.get(node.func.id)
        if arity is None:
            raise ExpressionError(f"{text!r}: unknown function {node.func.id}")
        if node.keywords or len(node.args) != arity:
            raise ExpressionError(f"{text!r}: {node.func.id} takes {arity} values")
        for arg in node.args:
            _check(arg, text, found)
    else:
        raise ExpressionError(f"{text!r}: not allowed in a model expression")


def names(text: str) -> frozenset[str]:
    if not isinstance(text, str) or not text.strip():
        raise ExpressionError("an expression must not be empty")
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"{text!r}: {exc.msg}") from exc
    found: set[str] = set()
    _check(tree, text, found)
    return frozenset(found)


def compile_function(exprs: dict[str, str], args: tuple[str, ...]) -> Callable[..., tuple]:
    bad = [n for n in (*args, *exprs) if not n.isidentifier() or keyword.iskeyword(n)
           or n in _GLOBALS]
    if bad:
        raise ExpressionError(f"not usable as names: {sorted(bad)}")
    known = set(args)
    for key, text in exprs.items():
        missing = names(text) - known
        if missing:
            raise ExpressionError(f"{key}: unknown names {sorted(missing)}")
        known.add(key)
    source = "\n".join([f"def _f({', '.join(args)}):",
                         *(f"    {key} = {text.strip()}" for key, text in exprs.items()),
                         f"    return ({''.join(f'{key}, ' for key in exprs)})"])
    module = compile(source, "<model>", "exec")
    code = next(c for c in module.co_consts if isinstance(c, types.CodeType))
    return types.FunctionType(code, dict(_GLOBALS))
