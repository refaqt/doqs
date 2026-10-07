"""Tests for `doqs add-interface`: SysML, manifest and frames from one request."""
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

import add_interface  # noqa: E402
import install_module  # noqa: E402
import naming_rules  # noqa: E402
import sysml_rules  # noqa: E402
import use_part  # noqa: E402

_MACHINE = _REPO / "tests" / "fixtures" / "variant-machine"
_STUB = _REPO / "tests" / "freecad_stub"
SEED = (_REPO / "templates" / "cad" / "build_model.py").read_text(encoding="utf-8")


class _Stage(unittest.TestCase):
    """A machine with one module, two own parts and one bought rail."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="doqs-iface-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "machine"
        shutil.copytree(_MACHINE, self.root)
        naming_rules.forget_library_roots()
        self.addCleanup(naming_rules.forget_library_roots)
        install_module.install_module(self.root, "compact-stage", name="Compact Stage")
        self.module = Path("modules/compact-stage")
        self.module_dir = self.root / self.module
        for part in ("base", "carriage-top"):
            install_module.install_part(self.root, self.module, part, no_cad=True)
        use_part.use_part(self.root, self.module, "stoq:hiwin/hgr-rail#HGR20R500", usages=["referenceRail"])
        self.log = Path(self._tmp.name) / "journal.jsonl"

    def arch(self) -> str:
        return (self.module_dir / "architecture" / "compact-stage.sysml").read_text(encoding="utf-8")

    def stub_env(self) -> dict:
        return {**os.environ, "PYTHONPATH": str(_STUB), "DOQS_FREECAD_STUB_LOG": str(self.log)}


class TestSysmlAndManifest(_Stage):
    def test_port_def_ports_connect_and_outside_entry(self):
        report = add_interface.add_interface(
            self.root, self.module, "RailMount", "base.referenceRailMount", "referenceRail.baseMount",
            doc="A guide rail lies on the floor of the base.",
            attributes=["holePitch : LengthValue = 60 [mm]"], outside="provides", frames=False)
        self.assertTrue(report.ok, report.errors)
        root = sysml_rules.parse(self.arch())
        port_def = sysml_rules.find(root, "CompactStage::RailMountInterface_v1")
        self.assertEqual(port_def.kind, "port_def")
        self.assertEqual(port_def.of_kind("attribute")[0].value, "60 [mm]")
        self.assertEqual(sysml_rules.find(root, "CompactStage::Base").child("port", "referenceRailMount").conjugated, False)
        rail_port = sysml_rules.find(root, "CompactStage::HgrRail").child("port", "baseMount")
        self.assertTrue(rail_port.conjugated)
        self.assertEqual(rail_port.type_name, "RailMountInterface_v1")
        self.assertEqual(sysml_rules.connections(root),
                         [("CompactStage::CompactStage", "base.referenceRailMount", "referenceRail.baseMount")])
        data = tomllib.loads((self.module_dir / "okh.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["provides-interface"], [{
            "name": "RailMountInterface", "version": "1.0",
            "description": "A guide rail lies on the floor of the base."}])
        self.assertEqual(report.facts["port_def"], "RailMountInterface_v1")
        # A rerun changes nothing.
        before = self.arch()
        report = add_interface.add_interface(
            self.root, self.module, "RailMount", "base.referenceRailMount", "referenceRail.baseMount",
            outside="provides", frames=False)
        self.assertTrue(report.ok)
        self.assertEqual(report.edited, [])
        self.assertEqual(self.arch(), before)

    def test_unknown_usages_and_bad_port_names_are_refused(self):
        report = add_interface.add_interface(self.root, self.module, "X", "nobody.port", "base.a", frames=False)
        self.assertFalse(report.ok)
        self.assertIn("no part usage 'nobody'", report.errors[0])
        report = add_interface.add_interface(self.root, self.module, "X", "base.BadName", "referenceRail.a", frames=False)
        self.assertFalse(report.ok)
        self.assertIn("lowerCamelCase", report.errors[0])
        report = add_interface.add_interface(self.root, self.module, "X", "base", "referenceRail.a", frames=False)
        self.assertFalse(report.ok)


class TestFrames(_Stage):
    def test_an_own_part_gets_a_frame_call_and_a_frame_in_the_file(self):
        folder = self.module_dir / "cad" / "parts" / "base"
        fcstd = folder / "base.FCStd"
        fcstd.write_text("ORIGINAL\n", encoding="utf-8")  # the stub opens any file
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "add_interface.py"), "--root", str(self.root),
             "--module", self.module.as_posix(), "--name", "RailMount", "--a", "base.referenceRailMount",
             "--b", "referenceRail.baseMount", "--mode", "cmd", "--freecad", sys.executable, "--json"],
            capture_output=True, text=True, cwd=_REPO, env=self.stub_env())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        script = (folder / "build_model.py").read_text(encoding="utf-8")
        self.assertIn('    frame(doc, "IF_reference_rail_mount")\n', script)
        self.assertLess(script.index('frame(doc, "IF_reference_rail_mount")'), script.index("raise NotImplementedError"))
        self.assertIn("modules/compact-stage/cad/parts/base/base.FCStd", data["edited"])
        events = [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines() if l.strip()]
        added = [e for e in events if e["event"] == "addObject" and e["type"] == "Part::LocalCoordinateSystem"]
        self.assertEqual(len(added), 1)
        self.assertIn("save", [e["event"] for e in events])
        self.assertIn("saved-by-stub", fcstd.read_text(encoding="utf-8"))
        # The library side is reported as a next step, because the machine never edits the library.
        self.assertEqual(data["facts"]["frames"]["IF_base_mount"]["kind"], "library")
        self.assertTrue(any("IF_base_mount" in s and "library" in s for s in data["next_steps"]), data["next_steps"])

    def test_the_library_frame_is_applied_in_a_checkout(self):
        checkout = Path(self._tmp.name) / "stoq-checkout"
        shutil.copytree(self.root / "modules" / "stoq", checkout)
        wrapper = checkout / "modules" / "hiwin" / "modules" / "hgr-rail" / "cad" / "parts" / "HGR20R500.FCStd"
        self.assertTrue(wrapper.is_file())
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "add_interface.py"), "--root", str(self.root),
             "--module", self.module.as_posix(), "--name", "RailMount", "--a", "base.referenceRailMount",
             "--b", "referenceRail.baseMount", "--mode", "cmd", "--freecad", sys.executable,
             "--library-checkout", str(checkout), "--json"],
            capture_output=True, text=True, cwd=_REPO, env=self.stub_env())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertIn("modules/hiwin/modules/hgr-rail/cad/parts/HGR20R500.FCStd", data["edited"])
        self.assertIn("saved-by-stub", wrapper.read_text(encoding="utf-8", errors="replace"))
        self.assertTrue(any("pull request" in s for s in data["next_steps"]))

    def test_add_frame_call_is_idempotent_and_ordered(self):
        once = add_interface.add_frame_call(SEED, "IF_a")
        self.assertEqual(add_interface.add_frame_call(once, "IF_a"), once)
        twice = add_interface.add_frame_call(once, "IF_b")
        self.assertIn('    frame(doc, "IF_a")\n    frame(doc, "IF_b")\n', twice)
        self.assertLess(twice.index("# Mounting frames added"), twice.index('frame(doc, "IF_a")'))
        self.assertLess(twice.index('"""'), twice.index("# Mounting frames added"))
        with self.assertRaises(ValueError):
            add_interface.add_frame_call("print(1)\n", "IF_a")

    def test_dry_run_touches_nothing(self):
        before = self.arch()
        report = add_interface.add_interface(
            self.root, self.module, "RailMount", "base.referenceRailMount", "referenceRail.baseMount",
            outside="provides", dry_run=True)
        self.assertTrue(report.ok, report.errors)
        self.assertIn("modules/compact-stage/architecture/compact-stage.sysml", report.edited)
        self.assertEqual(self.arch(), before)


if __name__ == "__main__":
    unittest.main()
