"""Tests for `doqs scaffold`: a module, an own part, a brand and a family."""
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

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import install_module  # noqa: E402
import sysml_rules  # noqa: E402

_MACHINE = _REPO / "tests" / "fixtures" / "minimal-machine"
_LIBRARY = _REPO / "tests" / "fixtures" / "parts-library"
_STUB = _REPO / "tests" / "freecad_stub"


def _gate(script: str, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(_SCRIPTS / script), "--root", str(root), *args],
                          capture_output=True, text=True, cwd=_REPO)


class _MachineCopy(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="doqs-scaffold-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "machine"
        shutil.copytree(_MACHINE, self.root)
        self.log = Path(self._tmp.name) / "journal.jsonl"

    def stub_env(self) -> dict:
        return {**os.environ, "PYTHONPATH": str(_STUB), "DOQS_FREECAD_STUB_LOG": str(self.log)}

    def journal(self) -> list[dict]:
        if not self.log.is_file():
            return []
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines() if l.strip()]


class TestModule(_MachineCopy):
    def test_a_new_module_passes_the_gates(self):
        report = install_module.install_module(self.root, "guide-block", name="Guide Block",
                                               function="Holds the guide blocks.")
        self.assertTrue(report.ok, report.errors)
        module = self.root / "modules" / "guide-block"
        for rel in ("okh.toml", "README.md", "bom/bom.csv", "cad/params/default.csv",
                    "architecture/guide-block.sysml", "docs/log/README.md",
                    "docs/decisions/README.md", "docs/mistakes/README.md"):
            self.assertTrue((module / rel).is_file(), rel)
        data = tomllib.loads((module / "okh.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["repo"], "https://example.com/minimal-machine/tree/main/modules/guide-block")
        self.assertEqual(data["licensor"], "DOQS Tests")
        parent = tomllib.loads((self.root / "okh.toml").read_text(encoding="utf-8"))
        self.assertEqual(parent["hasComponent"][-1]["component"],
                         "https://example.com/minimal-machine/blob/main/modules/guide-block/okh.toml")
        root = sysml_rules.parse((module / "architecture" / "guide-block.sysml").read_text(encoding="utf-8"))
        self.assertIsNotNone(sysml_rules.find(root, "GuideBlock::GuideBlock"))
        for gate in ("validate_okh.py", "validate_names.py", "validate_links.py"):
            result = _gate(gate, self.root)
            self.assertEqual(result.returncode, 0, gate + "\n" + result.stdout + result.stderr)
        # The licence stubs come from `doqs generate`; after it, the licence gate passes.
        _gate("apply_licenses.py", self.root)
        result = _gate("validate_licenses.py", self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_rerun_changes_nothing(self):
        install_module.install_module(self.root, "guide-block")
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        report = install_module.install_module(self.root, "guide-block")
        self.assertTrue(report.ok)
        self.assertEqual(report.written, [])
        self.assertEqual(report.edited, [])
        after = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_a_nested_module_goes_under_its_parent(self):
        report = install_module.install_module(self.root, "drive-belt", parent=Path("modules/x-axis"))
        self.assertTrue(report.ok, report.errors)
        self.assertTrue((self.root / "modules" / "x-axis" / "modules" / "drive-belt" / "okh.toml").is_file())
        parent = tomllib.loads((self.root / "modules" / "x-axis" / "okh.toml").read_text(encoding="utf-8"))
        self.assertIn("modules/x-axis/modules/drive-belt/okh.toml", parent["hasComponent"][0]["component"])

    def test_a_bad_slug_is_refused_and_dry_run_writes_nothing(self):
        self.assertFalse(install_module.install_module(self.root, "GuideBlock").ok)
        report = install_module.install_module(self.root, "guide-block", dry_run=True)
        self.assertTrue(report.ok)
        self.assertIn("modules/guide-block/okh.toml", report.written)
        self.assertFalse((self.root / "modules" / "guide-block").exists())

    def test_the_command_line_prints_json(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "install_module.py"), "--root", str(self.root),
             "--json", "module", "guide-block"], capture_output=True, text=True, cwd=_REPO)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["command"], "scaffold module")
        self.assertIn("modules/guide-block/okh.toml", data["written"])


class TestPart(_MachineCopy):
    def setUp(self):
        super().setUp()
        install_module.install_module(self.root, "guide-block", name="Guide Block")
        self.module = Path("modules/guide-block")

    def _cli(self, *args):
        return subprocess.run(
            [sys.executable, str(_SCRIPTS / "install_module.py"), "--root", str(self.root),
             "--json", "part", self.module.as_posix(), *args],
            capture_output=True, text=True, cwd=_REPO, env=self.stub_env())

    def test_a_part_gets_a_script_a_manifest_entry_and_a_part_def(self):
        report = install_module.install_part(self.root, self.module, "carriage-top", no_cad=True)
        self.assertTrue(report.ok, report.errors)
        folder = self.root / self.module / "cad" / "parts" / "carriage-top"
        self.assertTrue((folder / "build_model.py").is_file())
        self.assertIn("main(build, globals()", (folder / "build_model.py").read_text(encoding="utf-8"))
        data = tomllib.loads((self.root / self.module / "okh.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["part"][0]["source"], ["cad/parts/carriage-top/carriage-top.FCStd"])
        self.assertEqual(data["part"][0]["sysml"], "CarriageTop")
        arch = (self.root / self.module / "architecture" / "guide-block.sysml").read_text(encoding="utf-8")
        root = sysml_rules.parse(arch)
        self.assertEqual(sysml_rules.find(root, "GuideBlock::CarriageTop").kind, "part_def")
        self.assertEqual(sysml_rules.find(root, "GuideBlock::GuideBlock.carriageTop").type_name, "CarriageTop")
        self.assertFalse((folder / "carriage-top.FCStd").exists())
        self.assertTrue(any("Create the document" in s for s in report.next_steps))

    def test_the_document_is_made_by_freecad_through_a_macro(self):
        (self.root / self.module / "cad" / "params" / "default.csv").write_text(
            "alias,value,unit,basis,source,description\nplate_t,8,mm,design,note,Plate thickness\n",
            encoding="utf-8")
        result = self._cli("carriage-top", "--mode", "cmd", "--freecad", sys.executable)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        fcstd = self.root / self.module / "cad" / "parts" / "carriage-top" / "carriage-top.FCStd"
        self.assertTrue(fcstd.is_file())
        self.assertIn("modules/guide-block/cad/parts/carriage-top/carriage-top.FCStd", data["written"])
        self.assertEqual(data["facts"]["freecad"], "cmd")
        events = [e["event"] for e in self.journal()]
        self.assertIn("newDocument", events)
        self.assertIn("saveAs", events)
        self.assertIn("closeDocument", events)
        sets = [e for e in self.journal() if e["event"] == "setAlias"]
        self.assertEqual(sets, [{"event": "setAlias", "cell": "B1", "alias": "plate_t"}])
        saved = json.loads(fcstd.read_text(encoding="utf-8"))
        kinds = {o["type"]: o for o in saved["objects"]}
        self.assertIn("App::Part", kinds)
        self.assertTrue(kinds["App::Part"]["visible"])
        self.assertIn("Spreadsheet::Sheet", kinds)

    def test_a_failed_freecad_run_is_reported_not_hidden(self):
        env_fail = {**self.stub_env(), "DOQS_FREECAD_STUB_SWALLOW_EXIT": "1", "DOQS_FREECAD_STUB_FAIL": "open"}
        # The macro never opens a document, so make it fail by pointing at no binary.
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "install_module.py"), "--root", str(self.root),
             "--json", "part", self.module.as_posix(), "carriage-top", "--mode", "cmd",
             "--freecad", "/nonexistent/freecadcmd"],
            capture_output=True, text=True, cwd=_REPO, env=env_fail)
        self.assertEqual(result.returncode, 1, result.stdout)
        data = json.loads(result.stdout)
        self.assertTrue(any("FreeCAD did not create" in e for e in data["errors"]))

    def test_a_rerun_keeps_the_document(self):
        self._cli("carriage-top", "--mode", "cmd", "--freecad", sys.executable)
        result = self._cli("carriage-top", "--mode", "cmd", "--freecad", "/nonexistent")
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data["written"], [])
        self.assertTrue(any("carriage-top.FCStd (exists)" in u for u in data["unchanged"]))


class TestLibrary(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="doqs-scaffold-lib-")
        self.addCleanup(self._tmp.cleanup)
        self.library = Path(self._tmp.name) / "stoq"
        shutil.copytree(_LIBRARY, self.library)

    def test_a_brand_and_a_family_pass_the_gates(self):
        report = install_module.install_brand(self.library, "maxwell", name="MAXWELL",
                                              website="https://maxwell.example", cad_terms="https://maxwell.example/terms")
        self.assertTrue(report.ok, report.errors)
        data = tomllib.loads((self.library / "modules" / "maxwell" / "okh.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["license"], "CC-BY-SA-4.0")
        self.assertEqual(data["brand"]["name"], "MAXWELL")
        self.assertIs(data["brand"]["redistribute"], False)
        report = install_module.install_family(self.library, "maxwell", "mk2-motor",
                                               name="MAXWELL MK2 motor", function="Iron core linear motors.")
        self.assertTrue(report.ok, report.errors)
        family = self.library / "modules" / "maxwell" / "modules" / "mk2-motor"
        self.assertTrue((family / "bom" / "parts.csv").is_file())
        self.assertTrue((family / "vendor-index.csv").is_file())
        self.assertTrue((family / "cad" / "original" / ".gitkeep").is_file())
        fam = tomllib.loads((family / "okh.toml").read_text(encoding="utf-8"))
        self.assertEqual(fam["brand"]["website"], "https://maxwell.example")
        for gate in ("validate_okh.py", "validate_names.py"):
            result = _gate(gate, self.library)
            self.assertEqual(result.returncode, 0, gate + "\n" + result.stdout + result.stderr)
        # The fixture's own rows fail their checksums on a Windows checkout
        # (line endings), so only the new family's lines count here.
        result = _gate("validate_variants.py", self.library)
        self.assertEqual([l for l in result.stdout.splitlines() if "maxwell" in l], [], result.stdout)

    def test_a_family_needs_its_brand(self):
        report = install_module.install_family(self.library, "nobody", "thing")
        self.assertFalse(report.ok)
        self.assertIn("scaffold brand nobody", report.errors[0])

    def test_a_private_library_names_the_suppliers_terms(self):
        (self.library / "library.toml").write_text(
            'schema = "doqs-library-v1"\nname = "stoq-private"\nprivate = true\n', encoding="utf-8")
        report = install_module.install_brand(self.library, "maxwell")
        self.assertTrue(report.ok, report.errors)
        data = tomllib.loads((self.library / "modules" / "maxwell" / "okh.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["license"], "LicenseRef-maxwell-terms")


if __name__ == "__main__":
    unittest.main()
