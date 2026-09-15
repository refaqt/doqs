"""Unit tests for sparse parameter overrides and derived values."""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from param_rules import (  # noqa: E402
    ParamError,
    evaluate,
    format_value,
    load_param_csv,
    merge_params,
    declared_models,
    resolve,
    resolve_model,
)

FAMILY = _REPO / "tests" / "fixtures" / "variant-family"
CORE = FAMILY / "modules" / "linear-stage"


def rows(**pairs: str) -> dict[str, dict[str, str]]:
    return {a: {"alias": a, "value": v, "unit": "", "description": ""}
            for a, v in pairs.items()}


class TestExpressions(unittest.TestCase):
    def test_arithmetic_and_functions(self) -> None:
        values = {"a": 10.0, "b": 3.0}
        self.assertEqual(evaluate("=a + b * 2", values), 16.0)
        self.assertEqual(evaluate("=(a - b) / 7", values), 1.0)
        self.assertEqual(evaluate("=max(a, b)", values), 10.0)
        self.assertEqual(evaluate("=ceil(a / b)", values), 4)

    def test_rejects_unknown_alias(self) -> None:
        with self.assertRaisesRegex(ParamError, "unknown alias"):
            evaluate("=nope + 1", {"a": 1.0})

    def test_rejects_arbitrary_code(self) -> None:
        for hostile in ("=__import__('os').system('ls')",
                        "=open('/etc/passwd').read()",
                        "=(1).__class__",
                        "=[1, 2][0]"):
            with self.assertRaises(ParamError):
                evaluate(hostile, {})

    def test_rejects_runaway_exponent(self) -> None:
        with self.assertRaisesRegex(ParamError, "exponent"):
            evaluate("=2 ** 9999", {})

    def test_rejects_division_by_zero(self) -> None:
        with self.assertRaisesRegex(ParamError, "division by zero"):
            evaluate("=1 / 0", {})


class TestResolve(unittest.TestCase):
    def test_derived_values_follow_their_inputs(self) -> None:
        base = rows(rail_length="300", travel="=rail_length - 180",
                    extrusion="=rail_length + 40")
        self.assertEqual(resolve(base)["travel"], "120")

    def test_resolution_order_is_irrelevant(self) -> None:
        base = rows(c="=b + 1", b="=a + 1", a="1")
        self.assertEqual(resolve(base)["c"], "3")

    def test_cycles_are_reported(self) -> None:
        with self.assertRaisesRegex(ParamError, "circular"):
            resolve(rows(x="=y", y="=x"))

    def test_non_numeric_values_pass_through(self) -> None:
        self.assertEqual(resolve(rows(material="6061-T6"))["material"], "6061-T6")

    def test_integers_do_not_grow_a_decimal_point(self) -> None:
        self.assertEqual(format_value(540.0), "540")
        self.assertEqual(format_value(2.5), "2.5")


class TestSparseOverrides(unittest.TestCase):
    def test_one_row_override_propagates_to_every_derived_value(self) -> None:
        """The point of the whole design: a length file is a single row."""
        base = rows(rail_length="300", travel="=rail_length - 180",
                    extrusion="=rail_length + 40", cover="=extrusion - 10")
        merged = merge_params(base, rows(rail_length="500"))
        resolved = resolve(merged)
        self.assertEqual(
            (resolved["travel"], resolved["extrusion"], resolved["cover"]),
            ("320", "540", "530"),
        )

    def test_override_inherits_unit_and_description(self) -> None:
        base = {"a": {"alias": "a", "value": "1", "unit": "mm", "description": "kept"}}
        merged = merge_params(base, {"a": {"alias": "a", "value": "2"}})
        self.assertEqual(merged["a"]["unit"], "mm")
        self.assertEqual(merged["a"]["description"], "kept")

    def test_override_may_add_a_new_alias(self) -> None:
        merged = merge_params(rows(a="1"), rows(b="2"))
        self.assertEqual(sorted(merged), ["a", "b"])

    def test_duplicate_alias_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "default.csv"
            path.write_text("alias,value,unit,description\na,1,,\na,2,,\n")
            with self.assertRaisesRegex(ParamError, "duplicate alias"):
                load_param_csv(path)

    def test_generated_comment_header_is_ignored_on_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "default.csv"
            path.write_text("# GENERATED\n# model: x\nalias,value,unit,description\na,1,mm,d\n")
            self.assertEqual(load_param_csv(path)["a"]["value"], "1")


class TestFixtureFamily(unittest.TestCase):
    def test_declared_models_include_default_first(self) -> None:
        self.assertEqual(declared_models(CORE)[0], "default")
        self.assertIn("500mm", declared_models(CORE))

    def test_each_model_resolves(self) -> None:
        expected = {"default": "300", "500mm": "500", "800mm": "800"}
        for model, rail in expected.items():
            with self.subTest(model=model):
                resolved = resolve_model(CORE, model)
                self.assertEqual(resolved["rail_length"]["value"], rail)
                self.assertEqual(
                    resolved["extrusion_length"]["value"], str(int(rail) + 40))

    def test_unknown_model_is_reported(self) -> None:
        with self.assertRaisesRegex(ParamError, "unknown model"):
            resolve_model(CORE, "640mm")

    def test_override_files_stay_sparse(self) -> None:
        """A length override must not restate the whole parameter set."""
        with open(CORE / "cad" / "params" / "500mm.csv", newline="") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 1)


if __name__ == "__main__":
    unittest.main()
