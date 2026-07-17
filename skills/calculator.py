"""Skill: evaluate basic arithmetic expressions safely, including common math functions."""

import ast
import math
import operator

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": (
            "Evaluate an arithmetic expression. Supports +, -, *, /, ** as well "
            "as sqrt(), abs(), round(), and pow() -- e.g. 'sqrt(16)' or "
            "'12 * (3 + 4)'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "e.g. '12 * (3 + 4)' or 'sqrt(16)'"}
            },
            "required": ["expression"],
        },
    },
}

_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg,
}

_SAFE_FUNCS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "pow": pow,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.Call):
        func_name = getattr(node.func, "id", None)
        if func_name in _SAFE_FUNCS:
            args = [_safe_eval(arg) for arg in node.args]
            return _SAFE_FUNCS[func_name](*args)
        raise ValueError(f"Unsupported function: {func_name}")
    raise ValueError("Unsupported expression")


def run(expression: str) -> str:
    try:
        result = _safe_eval(ast.parse(expression, mode="eval").body)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"
