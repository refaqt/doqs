"""Tests for "every dimension has a reason": parameter sources and the CAD audit.

No FreeCAD is needed. The audit runs on small stand-in objects that carry only
what ``cad_fingerprint.audit()`` reads.
"""
from __future__ import annotations

import io
import math
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
_STUB = _REPO / "tests" / "freecad_stub"
for _path in (_SCRIPTS, _STUB):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import cad_fingerprint  # noqa: E402
import parametric_rules as rules  # noqa: E402
from cad_rules import FINGERPRINT_SCHEMA, file_digest, fingerprint_path, write_fingerprint  # noqa: E402
from param_rules import param_source_problems, sysml_names  # noqa: E402
from validate_cad import parametric_findings, report_parametric  # noqa: E402
from validate_variants import check_all  # noqa: E402

FAMILY = _REPO / "tests" / "fixtures" / "variant-family"


def row(value, basis="", source=""):
    return {"value": value, "basis": basis, "source": source}


class _Repo(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="doqs-param-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        arch = self.root / "architecture"
        arch.mkdir()
        (arch / "stage.sysml").write_text(
            "package Stage {\n"
            "    requirement def TravelRequirement {\n"
            "        attribute travel_mm : Real;\n"
            "    }\n"
            "}\n", encoding="utf-8")

    def check(self, rows, override=False):
        return param_source_problems(rows, self.root, self.root, override=override)


class TestParamSources(_Repo):
    def test_independent_value_without_basis_is_reported(self):
        problems, _ = self.check({"plate_t": row("8")})
        self.assertEqual(len(problems), 1)
        self.assertIn("plate_t", problems[0])
        self.assertIn("no basis", problems[0])

    def test_derived_value_needs_no_basis(self):
        problems, notes = self.check({"a": row("1", "design", "why"), "b": row("=a * 2")})
        self.assertEqual((problems, notes), ([], []))

    def test_derived_value_with_a_basis_is_reported(self):
        problems, _ = self.check({"a": row("1", "design", "why"), "b": row("=a * 2", "design", "x")})
        self.assertIn("expression is its reason", problems[0])

    def test_unknown_basis_and_empty_source(self):
        problems, _ = self.check({"a": row("1", "guess", "x"), "b": row("1", "standard")})
        self.assertIn("basis must be one of", problems[0])
        self.assertIn("source must give", problems[1])

    def test_requirement_must_exist_in_sysml(self):
        good = row("300", "requirement", "Stage::TravelRequirement.travel_mm")
        self.assertEqual(self.check({"a": good}), ([], []))
        problems, _ = self.check({"a": row("300", "requirement", "Stage::Nope")})
        self.assertIn("no requirement called 'Nope'", problems[0])
        problems, _ = self.check({"a": row("300", "requirement", "TravelRequirement.width")})
        self.assertIn("no attribute called 'width'", problems[0])

    def test_simulation_and_design_paths_must_exist(self):
        problems, _ = self.check({"a": row("3", "simulation", "simulation/beam/result.csv")})
        self.assertIn("does not exist", problems[0])
        target = self.root / "simulation" / "beam" / "result.csv"
        target.parent.mkdir(parents=True)
        target.write_text("x\n")
        self.assertEqual(self.check({"a": row("3", "simulation", "simulation/beam/result.csv")}), ([], []))
        problems, _ = self.check({"a": row("3", "design", "docs/decisions/nope.md")})
        self.assertIn("does not exist", problems[0])
        self.assertEqual(self.check({"a": row("3", "design", "Stiff enough by hand")}), ([], []))

    def test_an_estimate_is_a_note_not_a_problem(self):
        problems, notes = self.check({"a": row("3", "estimated", "catalogue figure 4")})
        self.assertEqual(problems, [])
        self.assertIn("placeholder", notes[0])

    def test_override_inherits_an_empty_basis(self):
        self.assertEqual(self.check({"a": row("500")}, override=True), ([], []))

    def test_sysml_in_the_tooling_submodules_is_ignored(self):
        kit = self.root / ".agents" / "examples"
        kit.mkdir(parents=True)
        (kit / "x.sysml").write_text("requirement def KitOnly { }\n", encoding="utf-8")
        requirements, attributes = sysml_names(self.root)
        self.assertEqual(requirements, {"TravelRequirement"})
        self.assertEqual(attributes, {"travel_mm"})


class TestValidateVariantsSources(unittest.TestCase):
    def test_the_worked_family_gives_a_source_for_every_value(self):
        errors, warnings = check_all(FAMILY, strict_parametric=True)
        self.assertEqual(errors, [])
        self.assertFalse([w for w in warnings if "basis" in w.message])

    def test_a_missing_basis_warns_by_default_and_fails_when_strict(self):
        tmp = Path(tempfile.mkdtemp(prefix="doqs-family-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        family = tmp / "family"
        shutil.copytree(FAMILY, family)
        params = family / "modules" / "linear-stage" / "cad" / "params" / "default.csv"
        text = params.read_text(encoding="utf-8")
        params.write_text(text.replace("rail_count,2,,design,", "rail_count,2,,,"), encoding="utf-8")

        errors, warnings = check_all(family)
        self.assertEqual(errors, [])
        self.assertTrue(any("rail_count" in w.message for w in warnings))

        errors, _ = check_all(family, strict_parametric=True)
        self.assertTrue(any("rail_count" in e.message for e in errors))


class TestSketchRules(unittest.TestCase):
    def test_typed_distance_is_reported_and_a_bound_one_is_not(self):
        constraints = [
            {"type": "Coincident"},
            {"type": "DistanceX", "name": "", "value": 12.5},
            {"type": "DistanceX", "name": "pitch", "value": 20.0},
            {"type": "Radius", "name": "", "value": 3.0},
        ]
        keys = rules.expression_keys([(".Constraints.pitch", "Params.hole_pitch"),
                                      (".Constraints[3]", "Params.hole_d / 2")])
        found = rules.sketch_findings(constraints, keys, dof=0, fully_constrained=True)
        self.assertEqual(found, ["Constraint2 (DistanceX) is a typed number: 12.5 mm"])

    def test_seven_typed_spacings_are_seven_findings(self):
        constraints = [{"type": "DistanceX", "name": "", "value": 20.0} for _ in range(7)]
        found = rules.sketch_findings(constraints, set(), dof=0, fully_constrained=True)
        self.assertEqual(len(found), 7)

    def test_free_sketch_is_reported(self):
        found = rules.sketch_findings([], set(), dof=2, fully_constrained=False)
        self.assertIn("2 degrees of freedom left", found[0])
        found = rules.sketch_findings([], set(), dof=None, fully_constrained=False)
        self.assertIn("not fully constrained", found[0])

    def test_zero_reference_and_inactive_dimensions_pass(self):
        constraints = [
            {"type": "Distance", "value": 0.0},
            {"type": "Distance", "value": 5.0, "driving": False},
            {"type": "Distance", "value": 5.0, "active": False},
        ]
        self.assertEqual(rules.sketch_findings(constraints, set(), dof=0, fully_constrained=True), [])

    def test_angle_is_shown_in_degrees(self):
        found = rules.sketch_findings([{"type": "Angle", "value": math.pi / 4}], set(),
                                      dof=0, fully_constrained=True)
        self.assertIn("45 deg", found[0])


class TestFeatureRules(unittest.TestCase):
    def test_pad_length_counts_only_when_used(self):
        self.assertEqual(rules.feature_findings("PartDesign::Pad", {"Length": 8.0, "Type": "Length"}, set()),
                         ["Length is a typed number: 8"])
        self.assertEqual(rules.feature_findings("PartDesign::Pad", {"Length": 8.0, "Type": "ThroughAll"}, set()), [])
        self.assertEqual(rules.feature_findings("PartDesign::Pad", {"Length": 8.0, "Type": "Length"}, {"Length"}), [])

    def test_linear_pattern_follows_its_mode(self):
        props = {"Occurrences": 8, "Length": 140.0, "Offset": 10.0, "Mode": "Extent"}
        found = rules.feature_findings("PartDesign::LinearPattern", props, set())
        self.assertEqual(found, ["Occurrences is a typed number: 8", "Length is a typed number: 140"])
        bound = {"Occurrences", "Length"}
        self.assertEqual(rules.feature_findings("PartDesign::LinearPattern", props, bound), [])
        props["Mode"] = "Spacing"
        self.assertEqual(rules.feature_findings("PartDesign::LinearPattern", props, bound),
                         ["Offset is a typed number: 10"])

    def test_full_turn_and_single_copy_need_no_parameter(self):
        self.assertEqual(rules.feature_findings("PartDesign::Revolution", {"Angle": 360.0}, set()), [])
        self.assertEqual(rules.feature_findings("PartDesign::PolarPattern",
                                                {"Occurrences": 1, "Angle": 360.0, "Mode": "Extent"}, set()), [])

    def test_typed_attachment_offset(self):
        self.assertEqual(rules.placement_findings("AttachmentOffset", (0, 0, 0), 0.0, set()), [])
        found = rules.placement_findings("AttachmentOffset", (0, 0, 5.0), 0.0, set())
        self.assertIn("(0, 0, 5) mm", found[0])
        self.assertEqual(rules.placement_findings("AttachmentOffset", (0, 0, 5.0), 0.0,
                                                  {"AttachmentOffset.Base.z"}), [])


class _Constraint:
    def __init__(self, type_, value=0.0, name=""):
        self.Type, self.Value, self.Name = type_, value, name
        self.Driving, self.IsActive = True, True


class _Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class _Placement:
    def __init__(self, z=0.0):
        self.Base = _Vec(z=z)
        self.Rotation = type("R", (), {"Angle": 0.0})()


class _Quantity:
    def __init__(self, value):
        self.Value = value


class _Obj:
    def __init__(self, name, type_id, expressions=(), **props):
        self.Name = self.Label = name
        self.TypeId = type_id
        self.ExpressionEngine = list(expressions)
        for key, value in props.items():
            setattr(self, key, value)


class _Doc:
    def __init__(self, objects):
        self.Objects = objects


class TestAudit(unittest.TestCase):
    def test_audit_reads_sketches_and_features(self):
        sketch = _Obj("Sketch", "Sketcher::SketchObject",
                      expressions=[(".Constraints[1]", "Params.w")],
                      Constraints=[_Constraint("Coincident"), _Constraint("DistanceX", 40.0),
                                   _Constraint("DistanceY", 12.0)],
                      DoF=0, FullyConstrained=True, MapMode="FlatFace",
                      AttachmentOffset=_Placement())
        pad = _Obj("Pad", "PartDesign::Pad", Length=_Quantity(8.0), Type="Length")
        good = _Obj("Pocket", "PartDesign::Pocket", expressions=[(".Length", "Params.d")],
                    Length=_Quantity(3.0), Type="Length")
        other = _Obj("Box", "App::Origin")
        result = cad_fingerprint.audit(_Doc([sketch, pad, good, other]))
        self.assertEqual(result["audited"], 3)
        self.assertEqual(sorted(result["objects"]), ["Pad", "Sketch"])
        self.assertEqual(result["objects"]["Sketch"]["unlinked"],
                         ["Constraint3 (DistanceY) is a typed number: 12 mm"])
        self.assertEqual(result["objects"]["Pad"]["unlinked"], ["Length is a typed number: 8"])

    def test_one_odd_object_does_not_stop_the_audit(self):
        class _Broken(_Obj):
            @property
            def Constraints(self):
                raise RuntimeError("boom")

        broken = _Broken("Bad", "Sketcher::SketchObject")
        pad = _Obj("Pad", "PartDesign::Pad", Length=_Quantity(8.0), Type="Length")
        result = cad_fingerprint.audit(_Doc([broken, pad]))
        self.assertIn("could not be checked", result["objects"]["Bad"]["unlinked"][0])
        self.assertIn("Pad", result["objects"])


class TestValidateCadParametric(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="doqs-cad-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        cad = self.root / "rail" / "cad"
        cad.mkdir(parents=True)
        self.fcstd = cad / "rail.FCStd"
        self.fcstd.write_bytes(b"pretend\n")

    def write_fp(self, **extra):
        data = {"schema": FINGERPRINT_SCHEMA, "document": "rail", "saved": True,
                "sources": {"rail.FCStd": file_digest(self.fcstd)}, "params": {},
                "objects": {}, "errors": [], **extra}
        write_fingerprint(fingerprint_path(self.fcstd), data)

    def run_report(self, strict):
        out = io.StringIO()
        with redirect_stdout(out):
            ok = report_parametric([(self.fcstd, None)], self.root, strict)
        return ok, out.getvalue()

    def test_old_fingerprint_asks_for_a_rebuild(self):
        self.write_fp()
        found = parametric_findings(self.fcstd, self.root)
        self.assertIn("older doqs", found[0])
        self.assertIn("FreeCADCmd rail/cad/build_model.py", found[0])

    def test_findings_warn_by_default_and_fail_when_strict(self):
        self.write_fp(parametric={"audited": 2, "objects": {
            "Sketch": {"label": "Holes", "unlinked": ["Constraint2 (DistanceX) is a typed number: 20 mm"]}}})
        ok, text = self.run_report(strict=False)
        self.assertTrue(ok)
        self.assertIn("WARN", text)
        self.assertIn("Holes: Constraint2", text)
        ok, text = self.run_report(strict=True)
        self.assertFalse(ok)
        self.assertIn("FAIL", text)

    def test_clean_model_passes(self):
        self.write_fp(parametric={"audited": 4, "objects": {}})
        ok, text = self.run_report(strict=True)
        self.assertTrue(ok)
        self.assertIn("every dimension is linked", text)


if __name__ == "__main__":
    unittest.main()
