"""Tests for own models in a parts library, and the headless build entry point.

An agent built own models of a rail and a block that were wrong in many ways,
and no check noticed. These tests cover each gap. See
docs/mistakes/2026-10-02_own-models-were-not-checked.md and
docs/decisions/2026-10-02_own-models-are-our-designs.md.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import apply_unshare  # noqa: E402
import cad_build  # noqa: E402
import compare_own  # noqa: E402
import compare_rules  # noqa: E402
import intake_rules  # noqa: E402
from naming_rules import forget_library_roots  # noqa: E402
from validate_variants import check_all  # noqa: E402

_STUB = _REPO / "tests" / "freecad_stub"
_SEED = _REPO / "templates" / "cad" / "build_model.py"
_OWN_SEED = _REPO / "templates" / "parts-library" / "cad" / "own" / "build.py"
LIBRARY = _REPO / "tests" / "fixtures" / "parts-library"
FAMILY = "modules/hiwin/modules/hgr-rail"
OWN = f"{FAMILY}/cad/own"
PN = "HGR20R1000"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stub_env(**extra: str) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(_STUB), env.get("PYTHONPATH")]))
    env.update(extra)
    return env


class TempDir(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        forget_library_roots()
        self.addCleanup(forget_library_roots)


# 1. The headless entry point -------------------------------------------------


class TestEntryPoint(TempDir):
    """FreeCADCmd 1.1 sets __name__ to the file stem. The seed must still build."""

    def seeded(self, text: str | None = None) -> Path:
        cad = self.tmp / "modules" / "x-axis" / "cad"
        cad.mkdir(parents=True)
        (self.tmp / "doqs").symlink_to(_REPO, target_is_directory=True)
        script = cad / "build_model.py"
        script.write_text(text if text is not None else _SEED.read_text(encoding="utf-8"),
                          encoding="utf-8")
        return script

    def test_runs_when_freecadcmd_names_it_after_the_file(self):
        script = self.seeded()
        with mock.patch.object(cad_build, "run") as run:
            runpy.run_path(str(script), run_name="build_model")
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs["cad_dir"], script.parent)

    def test_runs_as_a_plain_script(self):
        script = self.seeded()
        with mock.patch.object(cad_build, "run") as run:
            runpy.run_path(str(script), run_name="__main__")
        run.assert_called_once()

    def test_does_not_run_when_imported(self):
        script = self.seeded()
        spec = importlib.util.spec_from_file_location("build_model", script)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.object(cad_build, "run") as run:
            spec.loader.exec_module(module)
        run.assert_not_called()

    def test_the_old_guard_built_nothing(self):
        # The bug itself: under the name FreeCADCmd 1.1 gives it, the old
        # ending skips the build and says nothing.
        old = _SEED.read_text(encoding="utf-8").replace(
            "main(build, globals(), cad_dir=_HERE)",
            'if __name__ == "__main__":\n    main(build, globals(), cad_dir=_HERE)')
        script = self.seeded(old)
        with mock.patch.object(cad_build, "run") as run:
            runpy.run_path(str(script), run_name="build_model")
        run.assert_not_called()

    def test_a_headless_run_that_built_nothing_exits_1(self):
        result = subprocess.run(
            [sys.executable, "-c",
             f"import sys, FreeCAD; sys.path.insert(0, {str(_SCRIPTS)!r}); import cad_build"],
            capture_output=True, text=True, env=stub_env())
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("built nothing", result.stderr)

    def test_a_headless_run_of_the_seed_builds_and_saves(self):
        seed = _SEED.read_text(encoding="utf-8")
        start = seed.index("    raise NotImplementedError(")
        end = seed.index("\n\n\n", start)
        script = self.seeded(seed[:start] + "    pass" + seed[end:])
        (script.parent / "rail.FCStd").write_text("stub\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-c",
             f"import runpy, FreeCAD; runpy.run_path({str(script)!r}, run_name='build_model')"],
            capture_output=True, text=True, env=stub_env(), cwd=self.tmp)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Rebuilt and saved rail", result.stdout)
        self.assertNotIn("built nothing", result.stderr)
        self.assertTrue((script.parent / "rail.fingerprint.json").is_file())


class TestSeveralModelsInOneFolder(TempDir):
    def test_the_script_name_names_the_model(self):
        self.assertEqual(cad_build.document_of_script("cad/own/HGR20R1000.build.py"), "HGR20R1000")
        self.assertIsNone(cad_build.document_of_script("cad/build_model.py"))
        self.assertIsNone(cad_build.document_of_script(None))

    def test_main_passes_the_model_to_run(self):
        own = self.tmp / "own"
        own.mkdir()
        with mock.patch.object(cad_build, "run") as run:
            cad_build.main(lambda d, p: None,
                           {"__name__": "HGR20R1000.build", "__file__": str(own / "HGR20R1000.build.py")})
        self.assertEqual(run.call_args.kwargs["document"], "HGR20R1000")
        self.assertEqual(run.call_args.kwargs["cad_dir"], own)

    def test_fcstd_path_picks_the_named_model(self):
        for name in ("HGR20R1000.FCStd", "HGH20CA.FCStd"):
            (self.tmp / name).write_bytes(b"")
        self.assertEqual(cad_build.fcstd_path(self.tmp, "HGH20CA"), self.tmp / "HGH20CA.FCStd")
        with self.assertRaisesRegex(RuntimeError, "No MISSING.FCStd"):
            cad_build.fcstd_path(self.tmp, "MISSING")

    def test_each_model_reads_its_own_parameters(self):
        (self.tmp / "params.csv").write_text("alias,value\n", encoding="utf-8")
        own = self.tmp / "HGH20CA.params.csv"
        own.write_text("alias,value\n", encoding="utf-8")
        self.assertEqual(cad_build.params_path(self.tmp, fcstd=self.tmp / "HGH20CA.FCStd"), own)
        self.assertEqual(cad_build.params_path(self.tmp, document="HGH20CA"), own)
        self.assertEqual(cad_build.params_path(self.tmp, document="OTHER"), self.tmp / "params.csv")


# 2. validate_cad.py checks own models ----------------------------------------


class LibraryCopy(TempDir):
    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "stoq"
        shutil.copytree(LIBRARY, self.root)
        self.own = self.root / OWN

    def validate_cad(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(_SCRIPTS / "validate_cad.py"), "--root", str(self.root)],
            capture_output=True, text=True)

    def refingerprint(self, pn: str = PN) -> None:
        fp = self.own / f"{pn}.fingerprint.json"
        data = json.loads(fp.read_text(encoding="utf-8"))
        data["sources"] = {f"{pn}.FCStd": sha256(self.own / f"{pn}.FCStd")}
        fp.write_text(json.dumps(data), encoding="utf-8")

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def git_init(self) -> None:
        self.git("init", "-q")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "add", "-A")


class TestValidateCadOwnModels(LibraryCopy):
    def assertFails(self, needle: str) -> None:
        result = self.validate_cad()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(needle, result.stdout)

    def test_the_fixture_passes(self):
        result = self.validate_cad()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"ok    {OWN}/{PN}.FCStd", result.stdout)

    def test_a_model_saved_again_after_its_build_fails(self):
        with open(self.own / f"{PN}.FCStd", "a", encoding="utf-8") as f:
            f.write("saved again in the GUI\n")
        self.assertFails("changed since its fingerprint was written")

    def test_an_unsaved_fingerprint_fails(self):
        fp = self.own / f"{PN}.fingerprint.json"
        data = json.loads(fp.read_text(encoding="utf-8"))
        data["saved"] = False
        fp.write_text(json.dumps(data), encoding="utf-8")
        self.assertFails("measured from an unsaved document")

    def test_a_missing_fingerprint_fails(self):
        (self.own / f"{PN}.fingerprint.json").unlink()
        self.assertFails(f"Rebuild with: FreeCADCmd {OWN}/{PN}.build.py")

    def test_a_missing_build_script_fails(self):
        (self.own / f"{PN}.build.py").unlink()
        self.assertFails("never by hand in the GUI")

    def test_missing_parameters_fail(self):
        (self.own / f"{PN}.params.csv").unlink()
        self.assertFails(f"{PN}.params.csv not found")

    def test_a_build_script_without_axes_fails(self):
        script = self.own / f"{PN}.build.py"
        text = script.read_text(encoding="utf-8")
        script.write_text("\n".join(l for l in text.splitlines() if not l.startswith("AXES")),
                          encoding="utf-8")
        self.assertFails("does not state its axes")

    def test_the_template_axes_text_fails(self):
        shutil.copyfile(_OWN_SEED, self.own / f"{PN}.build.py")
        self.assertFails("AXES still holds the template text")

    def test_an_old_main_guard_fails(self):
        script = self.own / f"{PN}.build.py"
        text = script.read_text(encoding="utf-8").replace(
            "main(build, globals(), cad_dir=_HERE)",
            'if __name__ == "__main__":\n    main(build, globals(), cad_dir=_HERE)')
        script.write_text(text, encoding="utf-8")
        self.assertFails("builds nothing and still exits 0")

    def test_a_body_outside_a_part_fails(self):
        import zipfile
        model = self.own / f"{PN}.FCStd"
        with zipfile.ZipFile(model, "w") as z:
            z.writestr("Document.xml",
                       '<Document><Objects><Object type="PartDesign::Body" name="Body"/>'
                       "</Objects><ObjectData/></Document>")
        self.refingerprint()
        self.assertFails("is not inside a Part container")

    def test_a_build_script_without_its_model_fails(self):
        shutil.copyfile(self.own / f"{PN}.build.py", self.own / "HGR20R2000.build.py")
        self.assertFails("HGR20R2000.FCStd not found")

    def test_every_model_in_the_folder_is_checked(self):
        for suffix in (".FCStd", ".build.py", ".params.csv", ".fingerprint.json"):
            shutil.copyfile(self.own / f"{PN}{suffix}", self.own / f"HGR20R2000{suffix}")
        self.refingerprint("HGR20R2000")
        result = self.validate_cad()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("HGR20R2000.FCStd", result.stdout)
        (self.own / "HGR20R2000.params.csv").unlink()
        self.assertFails("HGR20R2000.params.csv not found")

    def test_a_tracked_backup_or_cache_fails(self):
        (self.own / f"{PN}.FCBak").write_bytes(b"backup")
        cache = self.own / "__pycache__"
        cache.mkdir()
        (cache / "x.pyc").write_bytes(b"")
        self.git_init()
        result = self.validate_cad()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(f"{OWN}/{PN}.FCBak is tracked by git", result.stdout)
        self.assertIn(f"{OWN}/__pycache__/x.pyc is tracked by git", result.stdout)

    def test_a_machine_build_model_with_the_old_guard_fails(self):
        machine = self.tmp / "machine"
        cad = machine / "modules" / "x-axis" / "cad"
        cad.mkdir(parents=True)
        (cad / "build_model.py").write_text(
            "from cad_build import run\n\nif __name__ == '__main__':\n    run(None)\n",
            encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "validate_cad.py"), "--root", str(machine)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FreeCADCmd 1.1 sets __name__", result.stdout)

    def test_the_seed_passes_the_guard_check(self):
        machine = self.tmp / "machine"
        cad = machine / "modules" / "x-axis" / "cad"
        cad.mkdir(parents=True)
        shutil.copyfile(_SEED, cad / "build_model.py")
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "validate_cad.py"), "--root", str(machine)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)


# 3. The feature list ---------------------------------------------------------


def row(**fields: str) -> dict[str, str]:
    base = {"feature": "grease nipple", "kind": "drawn-unsized", "outside_envelope": "yes",
            "source": "docs/datasheets/hg.pdf", "page": "70", "status": "estimated", "reason": ""}
    base.update(fields)
    return base


class TestFeatureRules(unittest.TestCase):
    def test_a_good_row_passes(self):
        self.assertEqual(intake_rules.features_problems([row()]), [])

    def test_an_empty_list_fails(self):
        self.assertIn("empty", intake_rules.features_problems([])[0])

    def test_an_empty_row_fails(self):
        blank = {k: "" for k in intake_rules.FEATURES_HEADERS}
        self.assertIn("row 2 is empty", intake_rules.features_problems([row(), blank])[0])

    def test_a_missing_field_fails(self):
        self.assertIn("grease nipple: page is empty", intake_rules.features_problems([row(page="")]))

    def test_left_out_needs_a_reason(self):
        errors = intake_rules.features_problems([row(outside_envelope="no", status="left-out")])
        self.assertEqual(len(errors), 1)
        self.assertIn("without a reason", errors[0])

    def test_a_feature_that_sticks_out_may_never_be_left_out(self):
        errors = intake_rules.features_problems([row(status="left-out", reason="too small")])
        self.assertTrue(any("may never be left out" in e for e in errors), errors)

    def test_an_unsized_feature_is_not_modelled_from_a_size(self):
        errors = intake_rules.features_problems([row(status="modelled")])
        self.assertTrue(any("estimated or measured" in e for e in errors), errors)

    def test_unknown_values_fail(self):
        errors = intake_rules.features_problems([row(kind="big", outside_envelope="maybe", status="done")])
        self.assertEqual(len(errors), 3, errors)


class TestFeatureListInTheLibrary(LibraryCopy):
    def errors(self) -> list[str]:
        return [f"{f.path}: {f.message}" for f in check_all(self.root)[0]]

    def test_the_fixture_passes(self):
        self.assertEqual(self.errors(), [])

    def test_an_own_model_needs_its_feature_list(self):
        (self.own / f"{PN}.features.csv").unlink()
        self.assertTrue(any("feature list not found" in e for e in self.errors()))

    def test_a_left_out_feature_that_sticks_out_fails(self):
        with open(self.own / f"{PN}.features.csv", "a", encoding="utf-8") as f:
            f.write("end seal lip,drawn-unsized,yes,docs/datasheets/hgr-series.pdf,12,left-out,small\n")
        self.assertTrue(any("may never be left out" in e for e in self.errors()))

    def test_the_template_passes(self):
        template = _REPO / "templates/parts-library/cad/own"
        for name in ("features.csv", "params.csv", "checks.csv"):
            shutil.copyfile(template / name, self.own / f"{PN}.{name}")
        self.assertEqual(self.errors(), [])


# 4. Where each value came from -----------------------------------------------


def check(**fields: str) -> dict[str, str]:
    base = {"dimension": "envelope X", "value_mm": "1000", "basis": "catalogue",
            "source": "docs/datasheets/hg.pdf", "page": "12", "measured_by": "",
            "measured_utc": "", "method": "Bounding box extent along X on both models",
            "result": "pass", "checked_utc": "2026-10-02T00:00:00Z"}
    base.update(fields)
    return base


FULL = [check(), check(dimension="envelope Y"), check(dimension="envelope Z"),
        check(dimension="symmetry XZ", value_mm="-")]


class TestBasisRules(unittest.TestCase):
    def test_a_complete_list_passes(self):
        self.assertEqual(intake_rules.checks_problems(FULL), ([], []))

    def test_catalogue_needs_a_page(self):
        errors, _ = intake_rules.basis_problems("rail width", check(page=""))
        self.assertIn("page is empty", errors[0])

    def test_an_estimate_is_only_a_placeholder(self):
        errors, warnings = intake_rules.basis_problems("nipple", check(basis="estimated"))
        self.assertEqual(errors, [])
        self.assertIn("never with a value from the brand's CAD file", warnings[0])

    def test_a_measurement_names_who_and_when(self):
        errors, _ = intake_rules.basis_problems("nipple", check(basis="measured", source="", page=""))
        self.assertEqual(len(errors), 2, errors)
        errors, _ = intake_rules.basis_problems(
            "nipple", check(basis="measured", measured_by="A. Person", measured_utc="2026-10-02"))
        self.assertEqual(errors, [])

    def test_an_unknown_basis_fails(self):
        errors, _ = intake_rules.basis_problems("x", check(basis="brand-cad"))
        self.assertIn("basis must be one of", errors[0])

    def test_parameters_carry_a_basis(self):
        errors, _ = intake_rules.params_problems(
            [{"alias": "rail_length", "value": "1000", "basis": ""}])
        self.assertIn("rail_length: basis must be one of", errors[0])


# 5. The own-model contract ---------------------------------------------------


class TestCheckListContract(unittest.TestCase):
    def errors(self, rows):
        return intake_rules.checks_problems(rows)[0]

    def test_a_pass_without_a_method_fails(self):
        rows = [*FULL, check(dimension="hole pitch", method="")]
        self.assertIn("hole pitch: pass without a method", self.errors(rows)[0])

    def test_a_method_may_not_hold_a_value(self):
        rows = [*FULL, check(dimension="hole pitch", method="Brand model says 59.98 mm")]
        self.assertIn("the method holds a value", self.errors(rows)[0])
        for text in ("Angle of the flank, 90° on both", "Rotated 45 deg"):
            rows = [*FULL, check(dimension="flank", method=text)]
            self.assertIn("the method holds a value", self.errors(rows)[0])

    def test_the_envelope_rows_are_required(self):
        errors = self.errors(FULL[1:])
        self.assertTrue(any("'envelope X'" in e for e in errors), errors)

    def test_a_symmetry_row_is_required(self):
        errors = self.errors(FULL[:3])
        self.assertTrue(any("no symmetry row" in e for e in errors), errors)

    def test_only_a_symmetry_row_may_have_no_value(self):
        errors = self.errors([*FULL, check(dimension="hole pitch", value_mm="-")])
        self.assertIn("hole pitch: value_mm is empty", errors)


# 6. doqs unshare -------------------------------------------------------------


class TestUnshare(LibraryCopy):
    STEP = f"{FAMILY}/cad/original/HGR20R500.step"

    def setUp(self) -> None:
        super().setUp()
        self.git_init()
        self.private = self.tmp / "stoq-private"
        (self.private / self.STEP).parent.mkdir(parents=True)
        shutil.copyfile(self.root / self.STEP, self.private / self.STEP)

    def unshare(self, *paths: str) -> tuple[int, str]:
        out = io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            with contextlib.redirect_stdout(out):
                code = apply_unshare.main(
                    ["--root", str(self.root), "--from", str(self.private), *paths])
        finally:
            os.chdir(cwd)
        return code, out.getvalue()

    def tracked(self) -> str:
        return subprocess.run(["git", "-C", str(self.root), "ls-files"],
                              capture_output=True, text=True, check=True).stdout

    def test_untracks_ignores_and_keeps_the_file(self):
        code, out = self.unshare(self.STEP)
        self.assertEqual(code, 0, out)
        self.assertNotIn(self.STEP, self.tracked())
        self.assertIn(self.STEP + "\n", (self.root / ".gitignore").read_text(encoding="utf-8"))
        self.assertTrue((self.root / self.STEP).is_file())
        self.assertIn("still on this disk", out)
        self.assertIn(f'rm "{self.STEP}"', out)
        self.assertIn(f"restore-private --from {self.private}", out)
        self.assertIn("its row still says it may be shared", out)

    def test_a_second_run_adds_no_second_line(self):
        self.unshare(self.STEP)
        self.git("add", f"{FAMILY}/cad/original")  # put it back, as a mistake would
        self.unshare(self.STEP)
        text = (self.root / ".gitignore").read_text(encoding="utf-8")
        self.assertEqual(text.count(self.STEP), 1)

    def test_a_different_private_copy_changes_nothing(self):
        (self.private / self.STEP).write_text("other\n", encoding="utf-8")
        code, out = self.unshare(self.STEP)
        self.assertEqual(code, 1)
        self.assertIn("different checksum", out)
        self.assertIn(self.STEP, self.tracked())
        self.assertFalse((self.root / ".gitignore").exists())

    def test_a_missing_private_copy_changes_nothing(self):
        (self.private / self.STEP).unlink()
        code, out = self.unshare(self.STEP)
        self.assertEqual(code, 1)
        self.assertIn("not in the private library", out)
        self.assertIn(self.STEP, self.tracked())

    def test_one_bad_path_stops_every_path(self):
        code, out = self.unshare(self.STEP, f"{FAMILY}/no-such.step")
        self.assertEqual(code, 1)
        self.assertIn("nothing was changed", out)
        self.assertIn(self.STEP, self.tracked())

    def test_gitignore_lines_match_one_file_only(self):
        self.assertEqual(apply_unshare.gitignore_line("a/b [1]*.step"), "a/b \\[1\\]\\*.step")
        self.assertEqual(apply_unshare.gitignore_line("a/#x"), "a/\\#x")


# 7. doqs compare-own ---------------------------------------------------------


class TestCompareRules(unittest.TestCase):
    OWN = [0, -10, 0, 1000, 10, 17.5]

    def test_extent_verdicts(self):
        brand = [0, -10, 0, 1000.05, 10, 19]
        self.assertEqual(compare_rules.extent_verdicts(self.OWN, brand, 0.1),
                         {"X": "pass", "Y": "pass", "Z": "fail"})
        bigger = [0, -10, 0, 1000, 10, 16]
        self.assertEqual(compare_rules.extent_verdicts(self.OWN, bigger, 0.1)["Z"], "not-confirmed")

    def test_axes_and_origin(self):
        self.assertTrue(compare_rules.axes_and_origin(self.OWN, self.OWN, 0.0, 0.1)[0])
        turned = [-10, 0, 0, 10, 1000, 17.5]
        same, words = compare_rules.axes_and_origin(self.OWN, turned, 0.0, 0.1)
        self.assertFalse(same)
        self.assertIn("different axes", words)
        moved = [-500, -10, 0, 500, 10, 17.5]
        same, words = compare_rules.axes_and_origin(self.OWN, moved, 0.2, 0.1)
        self.assertFalse(same)
        self.assertIn("origin is in a different place", words)

    def test_symmetry(self):
        self.assertEqual(compare_rules.symmetry_planes(self.OWN, [500, 0, 8], 0.1), ["XZ"])
        self.assertEqual(compare_rules.symmetry_verdict("XZ", ["XZ"], ["XZ"]), "pass")
        self.assertEqual(compare_rules.symmetry_verdict("XZ", [], ["XZ"]), "fail")
        self.assertEqual(compare_rules.symmetry_verdict("none", [], ["YZ"]), "fail")

    def test_only_pieces_that_stick_out_count(self):
        inside = [400, -2, 10, 410, 2, 17]
        out_top = [400, -2, 17, 410, 2, 19]
        out_end = [1000, -2, 5, 1012, 2, 9]
        self.assertEqual(compare_rules.protrusion_sides(self.OWN, [inside, out_top, out_end], 0.1),
                         [["+Z"], ["+X"]])

    def test_the_verdicts_hold_no_number(self):
        result = compare_rules.verdicts(
            own_box=self.OWN, own_centre=[500, 0, 8], brand_box=[0, -10, 0, 1000, 10, 19.37],
            brand_centre=[500, 0, 8.2], overlap=0.99, missing=[[400, -2, 17, 410, 2, 19.37]], tol=0.1)
        self.assertFalse(compare_rules.holds_a_number(result))
        self.assertTrue(compare_rules.holds_a_number({"a": [1.5]}))


#: A brand value that must never appear in our output or our files.
SECRET = 19.37


class TestCompareOwn(LibraryCopy):
    def setUp(self) -> None:
        super().setUp()
        self.private = self.tmp / "stoq-private"
        self.model = self.own / f"{PN}.FCStd"
        self.write_own({"box": [0, -10, 0, 1000, 10, 17.5], "centre": [500, 0, 8], "volume": 300000})
        self.write_brand({"box": [0, -10, 0, 1000, 10, 17.5], "centre": [500, 0, 8],
                          "volume": 300000, "overlap": 0.999})

    def write_own(self, shape: dict) -> None:
        self.model.write_text(json.dumps({"shape": shape}), encoding="utf-8")
        self.refingerprint()

    def write_brand(self, shape: dict) -> None:
        step = self.private / FAMILY / "cad/original" / f"{PN}.step"
        step.parent.mkdir(parents=True, exist_ok=True)
        step.write_text(json.dumps({"shape": shape}), encoding="utf-8")
        index = self.root / FAMILY / "vendor-index.csv"
        lines = [l for l in index.read_text(encoding="utf-8").splitlines() if f",{PN}," not in l]
        lines.append(f"hiwin,{PN},cad/original/{PN}.step,1,{sha256(step)},,private,2026-10-02T00:00:00Z")
        index.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.step = step

    def compare(self, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(_SCRIPTS / "compare_own.py"), "hiwin/hgr-rail", PN,
             "--root", str(self.root), "--from", str(self.private), "--freecad", sys.executable],
            capture_output=True, text=True, env=stub_env(**env))

    def checks(self) -> str:
        return (self.own / f"{PN}.checks.csv").read_text(encoding="utf-8")

    def test_matching_models_pass_and_change_nothing_else(self):
        before = {p: sha256(p) for p in (self.model, self.step)}
        journal = self.tmp / "journal.jsonl"
        result = self.compare(DOQS_FREECAD_STUB_LOG=str(journal))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("same axes and origin", result.stdout)
        self.assertIn("mirror planes: brand model XZ; ours XZ", result.stdout)
        self.assertIn("no brand feature sticks out", result.stdout)
        self.assertEqual({p: sha256(p) for p in before}, before)
        events = [json.loads(l)["event"] for l in journal.read_text(encoding="utf-8").splitlines()]
        self.assertIn("openDocument", events)
        self.assertNotIn("save", events)
        opened = [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines()]
        for event in opened:
            if "path" in event:
                self.assertFalse(Path(event["path"]).is_relative_to(self.root), event)
        # The rest of the record stays as it was, comments included.
        self.assertTrue(self.checks().startswith("# Every dimension of our own model"))
        self.assertIn("hole pitch P,60,", self.checks())

    def test_a_missing_feature_that_sticks_out_is_reported_without_its_value(self):
        self.write_brand({"box": [0, -10, 0, 1000, 10, SECRET], "centre": [500, 0, 8.2],
                          "volume": 300100, "overlap": 0.99,
                          "missing": [{"box": [400, -2, 17.5, 410, 2, SECRET], "volume": 40}]})
        result = self.compare()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("sticks out of our model on the +Z side", result.stdout)
        self.assertIn("fail", self.checks())
        for text in (result.stdout, result.stderr, self.checks()):
            self.assertNotIn(str(SECRET), text)
        # Only the envelope and symmetry rows were written.
        written = [l for l in self.checks().splitlines() if "doqs compare-own" in l]
        self.assertEqual(len(written), 4)

    def test_other_axes_are_reported(self):
        self.write_brand({"box": [-10, 0, 0, 10, 1000, 17.5], "centre": [0, 500, 8],
                          "volume": 300000, "overlap": 0.01})
        result = self.compare()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("different axes", result.stdout)

    def test_a_model_saved_after_its_build_is_refused(self):
        with open(self.model, "a", encoding="utf-8") as f:
            f.write(" ")
        before = self.checks()
        result = self.compare()
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed since its build", result.stdout)
        self.assertEqual(self.checks(), before)

    def test_a_brand_file_that_changed_is_refused(self):
        self.step.write_text("{}", encoding="utf-8")
        result = self.compare()
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match its recorded checksum", result.stdout)

    def test_a_failed_freecad_run_writes_nothing(self):
        before = self.checks()
        result = self.compare(DOQS_FREECAD_STUB_FAIL="open", DOQS_FREECAD_STUB_SWALLOW_EXIT="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("did not finish the comparison", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertEqual(self.checks(), before)

    def test_a_temporary_folder_inside_the_repository_is_refused(self):
        inside = self.root / "tmp"
        inside.mkdir()
        with mock.patch.object(compare_own.tempfile, "mkdtemp",
                               return_value=str(inside / "doqs-compare-x")):
            (inside / "doqs-compare-x").mkdir()
            with self.assertRaisesRegex(compare_own.CompareError, "inside"):
                compare_own.temporary_folder(self.root)


if __name__ == "__main__":
    unittest.main()
