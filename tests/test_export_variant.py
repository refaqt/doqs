"""Tests for the on-demand variant exporter.

``export_variant.py`` drives FreeCAD through a *generated macro* — the one
piece of this repository that cannot be reached by importing a module, since
it is written to a file and handed to a separate process.  That is exactly why
it went untested, and why a path bug in it survived a merged pull request.

``tests/freecad_stub/`` closes that gap: pointing ``PYTHONPATH`` at it and
passing ``--freecad`` a Python interpreter runs the real macro, as real Python,
against fake FreeCAD objects that journal everything they are asked to do.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import export_variant  # noqa: E402

_FAMILY = _REPO / "tests" / "fixtures" / "variant-family"
_STUB = _REPO / "tests" / "freecad_stub"
_COMP = "modules/linear-stage-servo-linear"
_CORE = "modules/linear-stage"


class FamilyCopy(unittest.TestCase):
    """A scratch copy of the family fixture, so nothing here mutates it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="doqs-export-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "family"
        shutil.copytree(_FAMILY, self.root)
        self.comp = self.root / _COMP
        self.core = self.root / _CORE
        self.log = Path(self._tmp.name) / "journal.jsonl"

    def cli(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(_SCRIPTS / "export_variant.py"),
             "--root", str(self.root), *args],
            capture_output=True, text=True, cwd=_REPO, env=env,
        )

    def make_source(self, text="ORIGINAL FCSTD BYTES\n") -> Path:
        path = self.comp / "cad" / "assemblies" / f"{self.comp.name}.FCStd"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def stub_env(self, **knobs):
        env = {**os.environ, "PYTHONPATH": str(_STUB),
               "DOQS_FREECAD_STUB_LOG": str(self.log)}
        env.update({k: str(v) for k, v in knobs.items()})
        return env

    def journal(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def snapshot(self) -> dict[str, tuple[int, int]]:
        return {
            str(p.relative_to(self.root)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(self.root.rglob("*")) if p.is_file()
        }


class TestDryRun(FamilyCopy):
    """Parameter resolution, with no FreeCAD anywhere near it."""

    def test_documented_composition_command_resolves(self):
        """The invocation printed in docs/variants.md must actually run.

        A composition holds no cad/params/ — its numbers live in the core its
        [composition] table names. Resolving against the composition directory
        made this exit 1 before FreeCAD was ever reached.
        """
        result = self.cli("--module", _COMP, "--model", "500mm", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("model 500mm", result.stdout)
        self.assertIn("(7 parameters)", result.stdout)
        self.assertIn("dry run", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_dry_run_names_the_core_that_owns_the_parameters(self):
        result = self.cli("--module", _COMP, "--model", "500mm", "--dry-run")
        self.assertIn(f"params {_CORE}", result.stdout)

    def test_core_module_is_unaffected(self):
        """params_owner is a no-op for a module that owns its own parameters."""
        result = self.cli("--module", _CORE, "--model", "800mm", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("(7 parameters)", result.stdout)
        self.assertNotIn("params ", result.stdout)

    def test_source_and_out_default_to_the_composition_not_the_core(self):
        """Only parameters move to the core; the geometry stays the module's."""
        result = self.cli("--module", _COMP, "--model", "500mm", "--dry-run")
        source = next(l for l in result.stdout.splitlines() if l.startswith("source "))
        out = next(l for l in result.stdout.splitlines() if l.startswith("out    "))
        self.assertTrue(source.endswith(f"{_COMP}/cad/assemblies/linear-stage-servo-linear.FCStd"))
        self.assertIn(f"{_COMP}/cad/exports/500mm/", out)

    def test_unknown_model_uses_the_fail_convention(self):
        result = self.cli("--module", _COMP, "--model", "640mm", "--dry-run")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stdout.startswith(f"FAIL  {_COMP}"), result.stdout)
        self.assertIn("unknown model '640mm'", result.stdout)
        self.assertEqual(result.stderr, "", "a ParamError must not surface as a traceback")

    def test_module_with_neither_params_nor_composition_fails_cleanly(self):
        result = self.cli("--module", f"{_CORE}/modules/feedback-none", "--dry-run")
        self.assertEqual(result.returncode, 1)
        self.assertIn("[composition]", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_every_composition_in_the_family_resolves(self):
        """A new composition cannot be added without the export path working."""
        compositions = []
        for okh in sorted(self.root.rglob("okh.toml")):
            with open(okh, "rb") as f:
                if "composition" in tomllib.load(f):
                    compositions.append(okh.parent.relative_to(self.root).as_posix())
        self.assertGreaterEqual(len(compositions), 2, "fixture should carry compositions")
        for module in compositions:
            with self.subTest(module=module):
                result = self.cli("--module", module, "--model", "default", "--dry-run")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        self.cli("--module", _COMP, "--model", "500mm", "--dry-run")
        self.assertEqual(before, self.snapshot())


class TestPrerequisites(FamilyCopy):
    def test_missing_source_document_fails_before_launching_freecad(self):
        result = self.cli("--module", _COMP, "--model", "500mm",
                          "--freecad", sys.executable, env=self.stub_env())
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL  source not found", result.stdout)
        self.assertFalse(self.log.exists(), "FreeCAD must not be started at all")

    def test_no_freecad_binary_is_a_clean_failure(self):
        self.make_source()
        result = self.cli("--module", _COMP, "--model", "500mm",
                          "--freecad", "/nonexistent/freecadcmd")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no FreeCAD binary found", result.stdout)
        self.assertEqual(result.stderr, "")


class TestExportWithStubFreeCAD(FamilyCopy):
    """The generated macro, executed as real Python against the stub."""

    def export(self, *extra, **knobs):
        return self.cli("--module", _COMP, "--model", "500mm",
                        "--freecad", sys.executable, *extra, env=self.stub_env(**knobs))

    def test_export_writes_the_step_file(self):
        self.make_source()
        result = self.export()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue([l for l in result.stdout.splitlines() if l.startswith("wrote ")])
        out = self.comp / "cad" / "exports" / "500mm" / f"{self.comp.name}.step"
        self.assertIn("ISO-10303-21", out.read_text(encoding="utf-8"))
        self.assertEqual(self.journal()[-1]["event"], "closeDocument")

    def test_the_macro_syncs_the_requested_model_not_a_stray_params_csv(self):
        """The direct regression test for the /tmp/params.csv bug.

        The macro used to run the sync script with exec(open(...).read()), so
        __file__ pointed at the temp macro and params.csv resolved to
        /tmp/params.csv. Only an explicitly passed absolute path makes these
        aliases arrive.
        """
        self.make_source()
        result = self.export()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        cells = {e["alias"]: e["value"] for e in self.journal() if e["event"] == "set"}
        self.assertEqual(len(cells), 7)
        self.assertEqual(cells["rail_length"], "500 mm", "the override did not arrive")
        self.assertEqual(cells["carriage_travel"], "320 mm",
                         "a derived value proves the resolver ran, not a raw CSV copy")
        self.assertEqual(cells["rail_count"], "2", "a unitless row gains no trailing space")
        self.assertNotIn("params.csv not found", result.stdout + result.stderr)
        self.assertFalse((self.core / "cad" / "params.csv").exists(),
                         "an export must not write the active model into the family")

    def test_the_source_document_is_never_saved(self):
        """What validate_cad.py --check-clean catches in a machine repo."""
        source = self.make_source()
        before, mtime = source.read_bytes(), source.stat().st_mtime_ns
        result = self.export()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("save", [e["event"] for e in self.journal()])
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(source.stat().st_mtime_ns, mtime)

    def test_a_failed_export_does_not_destroy_a_pinned_build_export(self):
        self.make_source()
        pinned = self.root / "builds" / "serial-0042" / "exports" / "x-stage.step"
        pinned.parent.mkdir(parents=True, exist_ok=True)
        pinned.write_text("PREVIOUS BUILD", encoding="utf-8")
        result = self.export("--out", str(pinned),
                             DOQS_FREECAD_STUB_FAIL="export",
                             DOQS_FREECAD_STUB_SWALLOW_EXIT="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL  export failed", result.stdout)
        self.assertEqual(pinned.read_text(encoding="utf-8"), "PREVIOUS BUILD")

    def test_a_failed_export_is_never_reported_as_success(self):
        """A stale STEP at --out used to satisfy the success check."""
        self.make_source()
        out = self.comp / "cad" / "exports" / "500mm" / f"{self.comp.name}.step"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("STALE GEOMETRY", encoding="utf-8")
        result = self.export(DOQS_FREECAD_STUB_FAIL="export",
                             DOQS_FREECAD_STUB_SWALLOW_EXIT="1")
        self.assertEqual(result.returncode, 1)
        # Line-anchored: the FAIL diagnostic legitimately says "wrote no file".
        self.assertFalse([l for l in result.stdout.splitlines() if l.startswith("wrote ")],
                         result.stdout)
        self.assertEqual(out.read_text(encoding="utf-8"), "STALE GEOMETRY")

    def test_a_failed_export_leaves_no_temporary_files(self):
        self.make_source()
        result = self.export(DOQS_FREECAD_STUB_FAIL="export",
                             DOQS_FREECAD_STUB_SWALLOW_EXIT="1")
        self.assertEqual(result.returncode, 1)
        out_dir = self.comp / "cad" / "exports" / "500mm"
        self.assertEqual(sorted(p.name for p in out_dir.iterdir()), [])

    def test_a_document_without_a_params_spreadsheet_fails_loudly(self):
        """Open question: a composition assembly may carry no Params sheet.

        Whatever the answer, it must be a legible failure rather than a silent
        one. See docs/decisions/2026-09-16_export-variant-contract.md.
        """
        self.make_source()
        result = self.export(DOQS_FREECAD_STUB_NO_SHEET="1",
                             DOQS_FREECAD_STUB_SWALLOW_EXIT="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("No Spreadsheet named 'Params'", result.stderr)

    def test_a_document_with_no_solid_objects_fails(self):
        """Import.export([], path) would otherwise write a valid, empty STEP."""
        self.make_source()
        result = self.export(DOQS_FREECAD_STUB_EMPTY="1",
                             DOQS_FREECAD_STUB_SWALLOW_EXIT="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("nothing to export", result.stderr)


class TestMacroText(unittest.TestCase):
    """Cheap sentinels that stop the deleted pattern coming back."""

    def render(self):
        return export_variant.render_macro(
            scripts=Path("/repo/doqs/scripts"),
            source=Path("/repo/modules/m/cad/assemblies/m.FCStd"),
            params_csv=Path("/staging/params.csv"),
            step=Path("/staging/m.step"),
        )

    def test_macro_compiles(self):
        compile(self.render(), "<macro>", "exec")

    def test_the_macro_imports_the_sync_module_rather_than_exec_ing_it(self):
        macro = export_variant.MACRO
        self.assertIn("sys.path.insert", macro)
        self.assertIn("import cad_sync_params", macro)
        self.assertIn("save=False", macro)
        for banned in ("exec(", "open(", "import Mesh", "doc.save"):
            self.assertNotIn(banned, macro)

    def test_the_macro_carries_no_path_it_has_to_infer(self):
        """Every path the macro needs is substituted in, never derived."""
        rendered = self.render()
        self.assertIn("/staging/params.csv", rendered)
        self.assertIn("/repo/doqs/scripts", rendered)
        self.assertNotIn("__file__", rendered)
        self.assertNotIn("cad_dir", rendered)


class TestFindFreecad(unittest.TestCase):
    def test_explicit_binary_wins(self):
        self.assertEqual(export_variant.find_freecad(sys.executable), sys.executable)

    def test_missing_binary_returns_none(self):
        with mock.patch.object(export_variant.shutil, "which", return_value=None):
            self.assertIsNone(export_variant.find_freecad("/nope/freecadcmd"))


if __name__ == "__main__":
    unittest.main()
