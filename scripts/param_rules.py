"""Sparse parameter merging and safe expression evaluation for DOQS variant models.

A module's parameter set lives in ``cad/params/``:

* ``default.csv`` lists **every** alias (the dense base set).
* ``<model>.csv`` is a **sparse override** — only the rows that differ.

A ``value`` may start with ``=`` to make it a *derived* parameter, an arithmetic
expression over other aliases.  Derived rows live once, in ``default.csv``, so a
length override usually shrinks to a single row.  See ``docs/variants.md``.
"""
from __future__ import annotations

import ast
import csv
import math
import operator
from pathlib import Path

PARAM_HEADERS = ("alias", "value", "unit", "description")

#: Cap on ``**`` exponents so a stray formula cannot hang the resolver.
MAX_EXPONENT = 64

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_FUNCTIONS = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
}


class ParamError(Exception):
    """Raised for malformed parameter files, bad expressions, or cycles."""


def _eval_node(node: ast.AST, values: dict[str, float], alias: str) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, values, alias)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ParamError(f"alias {alias!r}: only numeric constants are allowed")
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in values:
            raise ParamError(f"alias {alias!r}: unknown alias {node.id!r} in expression")
        return values[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand, values, alias))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_node(node.left, values, alias)
        right = _eval_node(node.right, values, alias)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise ParamError(f"alias {alias!r}: exponent {right} exceeds {MAX_EXPONENT}")
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise ParamError(f"alias {alias!r}: division by zero")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            allowed = ", ".join(sorted(_FUNCTIONS))
            raise ParamError(f"alias {alias!r}: only these functions are allowed: {allowed}")
        if node.keywords:
            raise ParamError(f"alias {alias!r}: keyword arguments are not allowed")
        args = [_eval_node(a, values, alias) for a in node.args]
        return _FUNCTIONS[node.func.id](*args)
    raise ParamError(
        f"alias {alias!r}: expression element {type(node).__name__} is not allowed"
    )


def evaluate(expression: str, values: dict[str, float], alias: str = "?") -> float:
    """Evaluate one ``=``-prefixed expression against already-resolved aliases."""
    text = expression.lstrip("=").strip()
    if not text:
        raise ParamError(f"alias {alias!r}: empty expression")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ParamError(f"alias {alias!r}: cannot parse expression {text!r}: {exc}") from exc
    return _eval_node(tree, values, alias)


def is_expression(value: str) -> bool:
    return value.strip().startswith("=")


def format_value(value: float) -> str:
    """Render a resolved number the way a hand-written CSV would."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _strip_comments(lines):
    """Drop ``#`` comment lines so a generated file can carry a provenance header.

    Only params CSVs may carry comments.  Generated BOM files must not:
    ``check_names.check_bom_file`` reads them with a plain ``csv.DictReader``
    and requires the first row to be exactly ``naming_rules.BOM_HEADERS``.
    """
    for line in lines:
        if line.lstrip().startswith("#"):
            continue
        yield line


def load_param_csv(path: Path) -> dict[str, dict[str, str]]:
    """Read a params CSV into an ordered ``alias -> row`` mapping."""
    if not path.exists():
        raise ParamError(f"params file not found: {path}")
    rows: dict[str, dict[str, str]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(_strip_comments(f))
        if reader.fieldnames is None:
            raise ParamError(f"empty params file: {path}")
        headers = tuple(h.strip() for h in reader.fieldnames)
        if headers[0] != "alias" or "value" not in headers:
            raise ParamError(
                f"{path}: header must start with 'alias' and contain 'value'; got {list(headers)}"
            )
        for line_no, row in enumerate(reader, start=2):
            alias = (row.get("alias") or "").strip()
            if not alias or alias.startswith("#"):
                continue
            if alias in rows:
                raise ParamError(f"{path}:{line_no}: duplicate alias {alias!r}")
            rows[alias] = {k: (v or "").strip() for k, v in row.items() if k}
    return rows


def merge_params(
    base: dict[str, dict[str, str]],
    *overrides: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Apply sparse overrides onto a dense base set.

    An override row replaces the base ``value``.  ``unit`` and ``description``
    are inherited from the base when the override leaves them empty, so an
    override file can be a single ``alias,value`` pair.
    """
    merged = {alias: dict(row) for alias, row in base.items()}
    for override in overrides:
        for alias, row in override.items():
            if alias in merged:
                target = merged[alias]
                target["value"] = row.get("value", "")
                for key in ("unit", "description"):
                    if row.get(key):
                        target[key] = row[key]
            else:
                merged[alias] = dict(row)
    return merged


def resolve(params: dict[str, dict[str, str]]) -> dict[str, str]:
    """Evaluate every ``=`` expression, returning ``alias -> literal value``.

    Resolution is iterative so derived parameters may reference each other in
    any order.  A parameter that can never be resolved is reported as a cycle.
    """
    literal: dict[str, float] = {}
    text: dict[str, str] = {}
    pending: dict[str, str] = {}

    for alias, row in params.items():
        value = row.get("value", "")
        if is_expression(value):
            pending[alias] = value
            continue
        try:
            literal[alias] = float(value)
        except ValueError:
            text[alias] = value

    while pending:
        progressed = False
        for alias in list(pending):
            try:
                literal[alias] = evaluate(pending[alias], literal, alias)
            except ParamError as exc:
                if "unknown alias" in str(exc):
                    continue
                raise
            del pending[alias]
            progressed = True
        if not progressed:
            stuck = ", ".join(sorted(pending))
            raise ParamError(
                f"cannot resolve (circular reference or unknown alias): {stuck}"
            )

    resolved = {alias: format_value(value) for alias, value in literal.items()}
    resolved.update(text)
    return {alias: resolved[alias] for alias in params if alias in resolved}


def params_dir(module_dir: Path) -> Path:
    return module_dir / "cad" / "params"


def declared_models(module_dir: Path) -> list[str]:
    """Model slugs implied by the CSV files present in ``cad/params/``."""
    directory = params_dir(module_dir)
    if not directory.is_dir():
        return []
    names = sorted(p.stem for p in directory.glob("*.csv"))
    return ["default"] + [n for n in names if n != "default"]


def resolve_model(module_dir: Path, model: str = "default") -> dict[str, dict[str, str]]:
    """Merge ``default.csv`` with ``<model>.csv`` and evaluate expressions.

    Returns the full rows with ``value`` replaced by the resolved literal, so
    callers keep ``unit`` and ``description`` for writing back out.
    """
    directory = params_dir(module_dir)
    merged = load_param_csv(directory / "default.csv")
    if model != "default":
        override_path = directory / f"{model}.csv"
        if not override_path.exists():
            raise ParamError(f"unknown model {model!r}: {override_path} does not exist")
        merged = merge_params(merged, load_param_csv(override_path))
    values = resolve(merged)
    out: dict[str, dict[str, str]] = {}
    for alias, row in merged.items():
        resolved_row = dict(row)
        resolved_row["value"] = values.get(alias, row.get("value", ""))
        out[alias] = resolved_row
    return out


def write_param_csv(path: Path, rows: dict[str, dict[str, str]], *, header: str = "") -> None:
    """Write resolved params, sorted by alias, with an optional comment header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        for line in header.strip().splitlines() if header else []:
            f.write(f"# {line.lstrip('# ')}\n")
        writer = csv.DictWriter(f, fieldnames=list(PARAM_HEADERS))
        writer.writeheader()
        for alias in sorted(rows):
            row = rows[alias]
            writer.writerow({k: row.get(k, "") for k in PARAM_HEADERS})
