"""Tests for `doqs add-part` and `doqs wrap` on two scratch libraries."""
from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import add_part  # noqa: E402
import export_wrapper  # noqa: E402
import library_rules as lr  # noqa: E402

_LIBRARY = _REPO / "tests" / "fixtures" / "parts-library"
_STUB = _REPO / "tests" / "freecad_stub"
DATE = datetime.date(2026, 10, 7)


class _TwoLibraries(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="doqs-intake-")
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.public = base / "stoq"
        self.private = base / "stoq-private"
        shutil.copytree(_LIBRARY, self.public)
        shutil.copytree(_LIBRARY, self.private)
        (self.private / "library.toml").write_text(
            'schema = "doqs-library-v1"\nname = "stoq-private"\nprivate = true\n', encoding="utf-8")
        self.files = base / "downloads"
        self.files.mkdir()
        self.step = self.files / "HGL15CAZBC+E2.step"
        self.step.write_text(json.dumps({"solids": ["body", "seal", "nipple"]}), encoding="utf-8")
        self.sheet = self.files / "hgl-series.pdf"
        self.sheet.write_bytes(b"%PDF-1.4 datasheet")
        self.terms = self.files / "terms-of-use.pdf"
        self.terms.write_bytes(b"%PDF-1.4 terms")
        self.log = base / "journal.jsonl"

    def intake(self, **over):
        args = dict(private=self.private, public=self.public, brand="hiwin", family="hgl-block",
                    pn="HGL15CAZBC+E2", description="HGL15 flange block, long",
                    spec="size 15; long; standard preload", mass_g="180", step=self.step,
                    datasheets=[self.sheet], terms_pdf=self.terms,
                    source_url="https://hiwin.example/dl/HGL15.step",
                    terms_url="https://hiwin.example/terms", decision="customers", basis="terms",
                    reviewer="Niels Bosmans", website="https://hiwin.example", reviewed=DATE,
                    retrieved_utc="2026-10-07T10:00:00Z", validate=False)
        args.update(over)
        return add_part.intake(**args)

    def family(self, root: Path) -> Path:
        return root / "modules" / "hiwin" / "modules" / "hgl-block"

    def stub_env(self) -> dict:
        return {**os.environ, "PYTHONPATH": str(_STUB), "DOQS_FREECAD_STUB_LOG": str(self.log)}


class TestIntake(_TwoLibraries):
    def test_customers_decision_keeps_files_private_and_rows_public(self):
        report = self.intake()
        self.assertTrue(report.ok, report.errors)
        priv, pub = self.family(self.private), self.family(self.public)
        self.assertTrue((priv / "cad" / "original" / "HGL15CAZBC+E2.step").is_file())
        self.assertTrue((priv / "docs" / "datasheets" / "hgl-series.pdf").is_file())
        self.assertFalse((pub / "cad" / "original" / "HGL15CAZBC+E2.step").exists())
        self.assertFalse((pub / "docs" / "datasheets" / "hgl-series.pdf").exists())
        self.assertTrue((self.private / "evidence" / "hiwin" / "2026-10-07_terms-of-use.pdf").is_file())
        ignore = (self.public / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("modules/hiwin/modules/hgl-block/cad/original/HGL15CAZBC+E2.step", ignore)
        self.assertIn("modules/hiwin/modules/hgl-block/docs/datasheets/hgl-series.pdf", ignore)
        # Rows: same checksums in both, different terms.
        digest, size = lr.sha256_and_size(self.step)
        for root, terms in ((priv, "internal"), (pub, "fetch-only")):
            _, rows = lr.read_rows(root / "vendor-index.csv")
            mine = [r for r in rows if r["pn"] == "HGL15CAZBC+E2"]
            self.assertEqual([r["relpath"] for r in mine],
                             ["cad/original/HGL15CAZBC+E2.step", "docs/datasheets/hgl-series.pdf"])
            self.assertEqual(mine[0]["sha256"], digest)
            self.assertEqual(mine[0]["bytes"], str(size))
            self.assertEqual({r["terms"] for r in mine}, {terms})
            self.assertEqual(mine[0]["retrieved_utc"], "2026-10-07T10:00:00Z")
            _, parts = lr.read_rows(root / "bom" / "parts.csv")
            part = [r for r in parts if r["pn"] == "HGL15CAZBC+E2"][0]
            self.assertEqual(part["terms"], terms)
            self.assertEqual(part["cad"], "")
            self.assertEqual(part["datasheet"], "docs/datasheets/hgl-series.pdf")
            self.assertEqual(part["unit_mass_g"], "180")
        # Reviews on the brand, one per kind, with the evidence path.
        for root in (self.private, self.public):
            data = tomllib.loads((root / "modules" / "hiwin" / "okh.toml").read_text(encoding="utf-8"))
            new = [r for r in data["terms-review"] if r.get("reviewed") == DATE]
            self.assertEqual([(r["kind"], r["decision"], r["basis"]) for r in new],
                             [("cad", "customers", "terms"), ("documentation", "customers", "terms")])
            self.assertEqual(new[0]["evidence"], "evidence/hiwin/2026-10-07_terms-of-use.pdf")
            self.assertEqual(new[0]["reviewer"], "Niels Bosmans")
            self.assertIs(data["brand"]["redistribute"], False)

    def test_public_decision_commits_the_files_in_both(self):
        report = self.intake(decision="public")
        self.assertTrue(report.ok, report.errors)
        pub = self.family(self.public)
        self.assertTrue((pub / "cad" / "original" / "HGL15CAZBC+E2.step").is_file())
        _, parts = lr.read_rows(pub / "bom" / "parts.csv")
        self.assertEqual([r["terms"] for r in parts if r["pn"] == "HGL15CAZBC+E2"], ["redistributable"])
        self.assertFalse((self.public / ".gitignore").is_file()
                         and "HGL15CAZBC+E2" in (self.public / ".gitignore").read_text(encoding="utf-8"))
        data = tomllib.loads((self.public / "modules" / "hiwin" / "okh.toml").read_text(encoding="utf-8"))
        self.assertIs(data["brand"]["redistribute"], True)

    def test_a_new_brand_is_scaffolded_in_both_libraries(self):
        report = self.intake(brand="maxwell", family="mk2-motor", pn="MK2-S", brand_name="MAXWELL",
                             family_name="MAXWELL MK2", decision="internal", source_url="")
        self.assertTrue(report.ok, report.errors)
        for root in (self.private, self.public):
            self.assertTrue((root / "modules" / "maxwell" / "okh.toml").is_file())
            _, parts = lr.read_rows(root / "modules" / "maxwell" / "modules" / "mk2-motor" / "bom" / "parts.csv")
            self.assertEqual(len(parts), 1)
        _, parts = lr.read_rows(self.public / "modules" / "maxwell" / "modules" / "mk2-motor" / "bom" / "parts.csv")
        self.assertEqual(parts[0]["terms"], "private")  # no public address

    def test_a_rerun_changes_nothing(self):
        self.intake()
        snapshot = {p: p.read_bytes() for root in (self.private, self.public)
                    for p in root.rglob("*") if p.is_file()}
        report = self.intake()
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(report.written, [])
        self.assertEqual(report.edited, [])
        after = {p: p.read_bytes() for root in (self.private, self.public)
                 for p in root.rglob("*") if p.is_file()}
        self.assertEqual(snapshot, after)

    def test_a_different_row_for_the_same_part_is_refused(self):
        self.intake()
        report = self.intake(description="Other words")
        self.assertFalse(report.ok)
        self.assertTrue(any("never overwritten" in e for e in report.errors), report.errors)

    def test_bad_inputs_are_refused_before_anything_is_written(self):
        self.assertFalse(self.intake(reviewer="").ok)
        self.assertFalse(self.intake(pn="HGL 15").ok)
        self.assertFalse(self.intake(basis="permission", terms_pdf=None).ok)
        self.assertFalse(self.intake(private=self.public, public=None).ok)  # not marked private
        self.assertFalse((self.private / "modules" / "hiwin" / "modules" / "hgl-block").exists())

    def test_dry_run_reports_and_writes_nothing(self):
        report = self.intake(dry_run=True)
        self.assertTrue(report.ok, report.errors)
        self.assertTrue(any("HGL15CAZBC+E2.step" in w for w in report.written))
        self.assertFalse((self.private / "modules" / "hiwin" / "modules" / "hgl-block").exists())

    def test_the_gates_accept_the_result(self):
        self.intake()
        for root in (self.private, self.public):
            for gate in ("validate_okh.py", "validate_variants.py", "validate_names.py"):
                result = subprocess.run([sys.executable, str(_SCRIPTS / gate), "--root", str(root)],
                                        capture_output=True, text=True, cwd=_REPO)
                mine = [l for l in result.stdout.splitlines() if "hgl-block" in l or "HGL15" in l]
                self.assertEqual([l for l in mine if "FAIL" in l or "error" in l.lower()], [], result.stdout)

    def test_the_command_line(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "add_part.py"), "--private", str(self.private),
             "--public", str(self.public), "--brand", "hiwin", "--family", "hgl-block",
             "--pn", "HGL15CAZBC+E2", "--description", "Block", "--step", str(self.step),
             "--reviewer", "N. B.", "--no-validate", "--json"],
            capture_output=True, text=True, cwd=_REPO)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["facts"]["pn"], "HGL15CAZBC+E2")
        self.assertTrue(any("doqs wrap" in s for s in data["next_steps"]))


class TestWrap(_TwoLibraries):
    def setUp(self):
        super().setUp()
        self.intake()

    def _wrap(self, library: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(_SCRIPTS / "export_wrapper.py"), "--library", str(library),
             "--part", "hiwin/hgl-block#HGL15CAZBC+E2", "--frames", "IF_rail,IF_carriage",
             "--json", *extra],
            capture_output=True, text=True, cwd=_REPO, env=self.stub_env())

    def test_the_wrapper_is_built_in_a_gui_window_and_the_row_points_at_it(self):
        result = self._wrap(self.private, "--mode", "gui", "--freecad", sys.executable, "--mirror", str(self.public))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        out = self.family(self.private) / "cad" / "parts" / "HGL15CAZBC+E2.FCStd"
        self.assertTrue(out.is_file())
        self.assertEqual(data["facts"]["freecad"], "gui")
        events = [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines() if l.strip()]
        kinds = [e["event"] for e in events]
        self.assertIn("insert", kinds)
        self.assertIn("saveAs", kinds)
        self.assertIn("closeMainWindow", kinds)
        saved = json.loads(out.read_text(encoding="utf-8"))
        by_type = {}
        for obj in saved["objects"]:
            by_type.setdefault(obj["type"], []).append(obj)
        self.assertEqual(len(by_type["App::Part"]), 1)
        self.assertEqual(by_type["App::Part"][0]["label"], "HGL15CAZBC+E2")
        self.assertEqual(len(by_type["Part::Feature"]), 3)
        self.assertEqual(sorted(o["label"] for o in by_type["Part::LocalCoordinateSystem"]),
                         ["IF_carriage", "IF_rail"])
        self.assertTrue(all(o["visible"] for o in saved["objects"] if o["type"] != "Spreadsheet::Sheet"))
        self.assertEqual(sorted(by_type["App::Part"][0]["group"]),
                         sorted(o["name"] for o in saved["objects"] if o["type"] != "App::Part"))
        _, parts = lr.read_rows(self.family(self.private) / "bom" / "parts.csv")
        self.assertEqual([r["cad"] for r in parts if r["pn"] == "HGL15CAZBC+E2"], ["cad/parts/HGL15CAZBC+E2.FCStd"])
        # The public library may not hold the file (decision customers): row set, file ignored.
        _, parts = lr.read_rows(self.family(self.public) / "bom" / "parts.csv")
        self.assertEqual([r["cad"] for r in parts if r["pn"] == "HGL15CAZBC+E2"], ["cad/parts/HGL15CAZBC+E2.FCStd"])
        self.assertFalse((self.family(self.public) / "cad" / "parts" / "HGL15CAZBC+E2.FCStd").exists())
        self.assertIn("modules/hiwin/modules/hgl-block/cad/parts/HGL15CAZBC+E2.FCStd",
                      (self.public / ".gitignore").read_text(encoding="utf-8"))

    def test_headless_freecad_is_refused_because_colours_are_lost(self):
        result = self._wrap(self.private, "--mode", "cmd", "--freecad", sys.executable)
        self.assertEqual(result.returncode, 1, result.stdout)
        data = json.loads(result.stdout)
        self.assertTrue(any("colours" in e for e in data["errors"]), data["errors"])
        self.assertFalse((self.family(self.private) / "cad" / "parts" / "HGL15CAZBC+E2.FCStd").exists())

    def test_a_missing_frame_in_the_result_is_an_error(self):
        env = {**self.stub_env(), "DOQS_FREECAD_STUB_FAIL": "insert", "DOQS_FREECAD_STUB_SWALLOW_EXIT": "1"}
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "export_wrapper.py"), "--library", str(self.private),
             "--part", "hiwin/hgl-block#HGL15CAZBC+E2", "--frames", "IF_rail", "--json",
             "--mode", "gui", "--freecad", sys.executable],
            capture_output=True, text=True, cwd=_REPO, env=env)
        self.assertEqual(result.returncode, 1, result.stdout)
        data = json.loads(result.stdout)
        self.assertTrue(any("did not wrap" in e for e in data["errors"]), data["errors"])

    def test_the_public_library_without_the_step_says_where_to_get_it(self):
        result = self._wrap(self.public, "--mode", "gui", "--freecad", sys.executable)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("restore-private", json.loads(result.stdout)["errors"][0])

    def test_a_public_decision_mirrors_the_wrapper(self):
        # A newer review says public, for a second part of the same brand.
        step = self.files / "HGL20CA.step"
        step.write_text(json.dumps({"solids": ["body"]}), encoding="utf-8")
        report = self.intake(decision="public", pn="HGL20CA", step=step, datasheets=[],
                             reviewed=DATE + datetime.timedelta(days=1))
        self.assertTrue(report.ok, report.errors)
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "export_wrapper.py"), "--library", str(self.private),
             "--part", "hiwin/hgl-block#HGL20CA", "--frames", "IF_rail", "--json",
             "--mode", "gui", "--freecad", sys.executable, "--mirror", str(self.public)],
            capture_output=True, text=True, cwd=_REPO, env=self.stub_env())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.family(self.public) / "cad" / "parts" / "HGL20CA.FCStd").is_file())
        _, parts = lr.read_rows(self.family(self.public) / "bom" / "parts.csv")
        self.assertEqual([r["cad"] for r in parts if r["pn"] == "HGL20CA"], ["cad/parts/HGL20CA.FCStd"])

    def test_checks_on_the_printed_tree(self):
        printed = {"objects": [["Part", "App::Part", ["Part__Feature", "Frame"]],
                               ["Part__Feature", "Part::Feature", []],
                               ["Frame", "Part::LocalCoordinateSystem", []]],
                   "labels": {"Frame": "IF_rail"}}
        out = self.files / "x.FCStd"
        out.write_text("{}", encoding="utf-8")
        self.assertEqual(export_wrapper.check_wrapper(out, ["IF_rail"], printed), [])
        self.assertEqual(export_wrapper.check_wrapper(out, ["IF_rail", "IF_top"], printed), ["frame IF_top is missing"])
        printed["objects"][0][1] = "PartDesign::Body"
        self.assertTrue(export_wrapper.check_wrapper(out, [], printed)[0].startswith("expected one Part"))


if __name__ == "__main__":
    unittest.main()
