"""A bounded interpreter for expression-only benchmark functions.

This is NOT a Python jail. It never invokes eval/exec/compile/import on source.
Normal Python repositories must use the Docker backend.
"""
import ast
import math
import operator
import time
from pathlib import Path

from .types import TestResult


class Unsupported(ValueError):
    pass


def bounded(value, depth=0, budget=None):
    if budget is None:
        budget = [0, 0]
    budget[0] += 1
    if budget[0] > 5000:
        raise Unsupported("Aggregate value node limit")
    if depth > 12:
        raise Unsupported("Value nesting limit")
    if type(value) not in (str, bytes, int, float, bool, list, tuple, dict, set, type(None)):
        raise Unsupported("Unsupported value type")
    if type(value) is int and value.bit_length() > 256:
        raise Unsupported("Integer limit")
    if type(value) is float and not math.isfinite(value):
        raise Unsupported("Non-finite number")
    if isinstance(value, (str, bytes, list, tuple, dict, set)):
        if len(value) > 1024:
            raise Unsupported("Value size limit")
        if isinstance(value, (str, bytes)):
            budget[1] += len(value)
            if budget[1] > 16_384:
                raise Unsupported("Aggregate string size limit")
        if isinstance(value, (list, tuple, set)):
            for v in value:
                bounded(v, depth + 1, budget)
        if isinstance(value, dict):
            for k, v in value.items():
                bounded(k, depth + 1, budget)
                bounded(v, depth + 1, budget)
    return value


OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
CMPS = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
        ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
        ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
        ast.Is: operator.is_, ast.IsNot: operator.is_not}
BUILTINS = {"len": len, "abs": abs, "min": min, "max": max, "sum": sum,
            "sorted": sorted, "set": set, "list": list, "tuple": tuple,
            "round": round, "int": int, "float": float, "str": str, "bool": bool,
            "all": all, "any": any}
METHODS = {str: {"strip", "lower", "upper", "startswith", "endswith", "encode", "split", "replace"},
           list: {"count", "index"}, tuple: {"count", "index"}, dict: {"get"}}


class ExpressionVM:
    def __init__(self, source: str, function: str):
        if len(source.encode()) > 64_000:
            raise Unsupported("Source size limit")
        tree = ast.parse(source)
        if len(list(ast.walk(tree))) > 1000:
            raise Unsupported("AST node limit")
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
            raise Unsupported("Exactly one function; no imports or top-level statements")
        self.fn = tree.body[0]
        a = self.fn.args
        if (self.fn.name != function or self.fn.decorator_list or self.fn.returns
                or a.defaults or a.kw_defaults or a.vararg or a.kwarg or a.kwonlyargs
                or a.posonlyargs or any(x.annotation for x in a.args)):
            raise Unsupported("Only a plain positional function is supported")
        if len(self.fn.body) != 1 or not isinstance(self.fn.body[0], ast.Return):
            raise Unsupported("Only a single return expression is supported")
        self.steps = 0

    def call(self, args: list):
        if len(args) != len(self.fn.args.args):
            raise Unsupported("Argument count mismatch")
        self.env = {p.arg: bounded(v) for p, v in zip(self.fn.args.args, args)}
        self.steps = 0
        return self.visit(self.fn.body[0].value)

    def visit(self, n, depth=0):
        self.steps += 1
        if self.steps > 5000 or depth > 40:
            raise Unsupported("Expression evaluation budget exceeded")
        def v(x):
            return self.visit(x, depth + 1)
        if isinstance(n, ast.Constant):
            out = n.value
        elif isinstance(n, ast.Name):
            if n.id not in self.env:
                raise Unsupported("Unknown name")
            out = self.env[n.id]
        elif isinstance(n, (ast.List, ast.Tuple, ast.Set)):
            out = {ast.List: list, ast.Tuple: tuple, ast.Set: set}[type(n)](v(x) for x in n.elts)
        elif isinstance(n, ast.Dict):
            if any(x is None for x in n.keys):
                raise Unsupported("No dictionary unpacking")
            out = {v(k): v(x) for k, x in zip(n.keys, n.values)}
        elif isinstance(n, ast.IfExp):
            out = v(n.body) if v(n.test) else v(n.orelse)
        elif isinstance(n, ast.BoolOp):
            out = v(n.values[0])
            for x in n.values[1:]:
                if (isinstance(n.op, ast.And) and not out) or (isinstance(n.op, ast.Or) and out):
                    break
                out = v(x)
        elif isinstance(n, ast.UnaryOp) and type(n.op) in (ast.Not, ast.USub, ast.UAdd):
            out = {ast.Not: operator.not_, ast.USub: operator.neg, ast.UAdd: operator.pos}[type(n.op)](v(n.operand))
        elif isinstance(n, ast.BinOp) and type(n.op) in OPS:
            a, b = v(n.left), v(n.right)
            if isinstance(n.op, ast.Mult):
                for seq, num in ((a, b), (b, a)):
                    if isinstance(seq, (str, bytes, list, tuple)) and type(num) is int and len(seq) * max(0, num) > 1024:
                        raise Unsupported("Sequence multiplication limit")
            if isinstance(n.op, ast.Mod) and isinstance(a, (str, bytes)):
                raise Unsupported("String formatting is disabled")
            out = OPS[type(n.op)](a, b)
        elif isinstance(n, ast.Compare):
            a, out = v(n.left), True
            for op, other in zip(n.ops, n.comparators):
                if type(op) not in CMPS:
                    raise Unsupported("Comparison denied")
                b = v(other)
                if not CMPS[type(op)](a, b):
                    out = False
                    break
                a = b
        elif isinstance(n, ast.Subscript):
            s = n.slice
            key = slice(v(s.lower) if s.lower else None, v(s.upper) if s.upper else None,
                        v(s.step) if s.step else None) if isinstance(s, ast.Slice) else v(s)
            out = v(n.value)[key]
        elif isinstance(n, ast.Call):
            if len(n.args) > 8 or any(k.arg is None for k in n.keywords):
                raise Unsupported("Call argument limit or unpacking denied")
            args = [v(x) for x in n.args]
            kwargs = {k.arg: v(k.value) for k in n.keywords}
            if isinstance(n.func, ast.Name) and n.func.id in BUILTINS:
                # Only sorted(reverse=...) is a supported keyword API.
                if kwargs and (n.func.id != "sorted" or set(kwargs) != {"reverse"} or type(kwargs["reverse"]) is not bool):
                    raise Unsupported("Keyword call denied")
                out = BUILTINS[n.func.id](*args, **kwargs)
            elif isinstance(n.func, ast.Attribute):
                obj, method = v(n.func.value), n.func.attr
                if method not in METHODS.get(type(obj), set()) or kwargs:
                    raise Unsupported("Method denied")
                if method == "encode" and args not in ([], ["utf-8"], ["utf8"]):
                    raise Unsupported("Only UTF-8 encoding is allowed")
                # replace can allocate product-sized output; bound before invoking.
                if method == "replace" and len(args) >= 2 and isinstance(args[1], str) and (len(obj) + 1) * len(args[1]) > 1024:
                    raise Unsupported("Replacement expansion limit")
                out = getattr(obj, method)(*args)
            else:
                raise Unsupported("Call denied")
        else:
            raise Unsupported(f"Syntax denied: {type(n).__name__}")
        return bounded(out)


def run_contract(source: str, function: str, cases: list[dict], hidden=False) -> TestResult:
    started = time.monotonic()
    passed, failed, failures = 0, 0, []
    try:
        vm = ExpressionVM(source, function)
        for index, case in enumerate(cases):
            try:
                actual = vm.call(case["args"])
                if type(actual) != type(case["expected"]) or actual != case["expected"]:
                    raise AssertionError(f"expected {case['expected']!r}; got {actual!r}")
                passed += 1
            except Exception as exc:
                failed += 1
                failures.append(f"case {index + 1}: {type(exc).__name__}: {exc}" if not hidden else "Hidden contract assertion failed")
    except Exception as exc:
        failed = max(1, len(cases))
        failures = [f"Interpreter rejected source: {type(exc).__name__}: {exc}"]
    return TestResult("passed" if passed and not failed else "failed", passed, failed,
                      "\n".join(failures)[:16_000], time.monotonic() - started, "bounded-ast")


class ContractSandbox:
    name = "bounded-ast"

    def __init__(self, task: dict):
        self.task = task

    def run(self, root: Path, hidden=False) -> TestResult:
        cases = self.task["hidden_cases" if hidden else "public_cases"]
        return run_contract((root / "src/solution.py").read_text(encoding="utf-8"),
                            self.task["function"], cases, hidden)

