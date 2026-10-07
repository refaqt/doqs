"""Tests for the interface gate and the mirror check."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import add_interface  # noqa: E402
import install_module  # noqa: E402
import naming_rules  # noqa: E402
import use_part  # noqa: E402
import validate_interfaces  # noqa: E402
import validate_mirror  # noqa: E402

_MACHINE = _REPO / "tests" / "fixtures" / "variant-machine"
_LIBRARY = _REPO / "tests" / "fixtures" / "parts-library"


def _write_fcstd(path: Path, frames: list[str]) -> None:
    """A saved document with a Part on top and the given frames."""
    objects = [("Part", "App::Part", "Part")] + [(f"Frame{i or ''}", "Part::LocalCoordinateSystem", f) for i, f in enumerate(frames)]
    listed = "".join(f'<Object type="{t}" name="{n}" id="{i}"/>' for i, (n, t, _) in enumerate(objects))
    data = "".join(f'<Object name="{n}"><Properties><Property name="Label" type="App::PropertyString">'
                   f'<String value="{l}"/></Property></Properties></Object>' for n, _, l in objects)
    xml = ('<?xml version="1.0" encoding="utf-8"?><Document SchemaVersion="4">'
           f'<Objects Count="{len(objects)}">{listed}</Objects>'
           f'<ObjectData Count="{len(objects)}">{data}</ObjectData></Document>')
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Document.xml", xml)


class TestInterfaceGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="doqs-ifgate-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "machine"
        shutil.copytree(_MACHINE, self.root)
        naming_rules.forget_library_roots()
        self.addCleanup(naming_rules.forget_library_roots)
        install_module.install_module(self.root, "compact-stage")
        self.module = Path("modules/compact-stage")
        install_module.install_part(self.root, self.module, "base", no_cad=True)
        use_part.use_part(self.root, self.module, "stoq:hiwin/hgr-rail#HGR20R500", usages=["referenceRail"])
        add_interface.add_interface(self.root, self.module, "RailMount", "base.referenceRailMount",
                                    "referenceRail.baseMount", outside="provides", frames=False)
        self.base = self.root / self.module / "cad" / "parts" / "base" / "base.FCStd"

    def run_gate(self, *args):
        return subprocess.run([sys.executable, str(_SCRIPTS / "validate_interfaces.py"), "--root", str(self.root), *args],
                              capture_output=True, text=True, cwd=_REPO)

    def test_a_consistent_module_passes(self):
        _write_fcstd(self.base, ["IF_reference_rail_mount"])
        findings = validate_interfaces.check_module(self.root, self.root / self.module)
        # The rail's wrapper in the fixture library has no frame: the only finding.
        self.assertEqual([f for f in findings if "parts/base/" in f or "compact-stage.sysml" in f], [])
        self.assertTrue(all("HGR20R500.FCStd" in f for f in findings), findings)

    def test_missing_frame_wrong_frame_and_bad_mirror_are_found(self):
        _write_fcstd(self.base, ["IF_rail_reference"])  # the old hand-written name
        okh = self.root / self.module / "okh.toml"
        okh.write_text(re.sub(r'version\s*= "1.0"', 'version = "2.0"', okh.read_text(encoding="utf-8")), encoding="utf-8")
        findings = validate_interfaces.check_module(self.root, self.root / self.module)
        self.assertTrue(any("port referenceRailMount of Base has no frame IF_reference_rail_mount" in f for f in findings), findings)
        self.assertTrue(any("frame IF_rail_reference has no port railReference on Base" in f for f in findings), findings)
        self.assertTrue(any("RailMountInterface 2.0 has no port def RailMountInterface_v2" in f for f in findings), findings)
        result = self.run_gate()
        self.assertEqual(result.returncode, 0)
        self.assertIn("WARN  interfaces:", result.stdout)
        result = self.run_gate("--strict-interfaces")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL  interfaces:", result.stdout)

    def test_connect_and_port_type_problems(self):
        arch = self.root / self.module / "architecture" / "compact-stage.sysml"
        text = arch.read_text(encoding="utf-8")
        text = text.replace("port baseMount : ~RailMountInterface_v1;", "port baseMount : RailMountInterface_v1;")
        text = text.replace("port referenceRailMount : RailMountInterface_v1;",
                            "port referenceRailMount : RailMountInterface_v1;\n        port other : NoSuch_v1;")
        arch.write_text(text, encoding="utf-8")
        findings = validate_interfaces.check_module(self.root, self.root / self.module)
        self.assertTrue(any("one side must be the plain port" in f for f in findings), findings)
        self.assertTrue(any("type NoSuch_v1, which is not defined" in f for f in findings), findings)

    def test_a_part_def_named_nowhere(self):
        okh = self.root / self.module / "okh.toml"
        okh.write_text(re.sub(r'sysml\s*= "Base"', 'sysml = "Nope"', okh.read_text(encoding="utf-8")), encoding="utf-8")
        findings = validate_interfaces.check_module(self.root, self.root / self.module)
        self.assertTrue(any("sysml = 'Nope' names no part def" in f for f in findings), findings)


class TestMirror(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="doqs-mirror-")
        self.addCleanup(self._tmp.cleanup)
        self.public = Path(self._tmp.name) / "stoq"
        self.private = Path(self._tmp.name) / "stoq-private"
        shutil.copytree(_LIBRARY, self.public)
        shutil.copytree(_LIBRARY, self.private)
        (self.private / "library.toml").write_text('schema = "doqs-library-v1"\nname = "p"\nprivate = true\n', encoding="utf-8")

    def run_mirror(self, *args):
        return subprocess.run([sys.executable, str(_SCRIPTS / "validate_mirror.py"), "--root", str(self.public),
                               "--private", str(self.private), *args], capture_output=True, text=True, cwd=_REPO)

    def test_identical_libraries_pass_and_a_difference_fails(self):
        result = self.run_mirror()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("are the same", result.stdout)
        step = self.private / "modules" / "hiwin" / "modules" / "hgr-rail" / "cad" / "original" / "HGR20R300.step"
        step.write_bytes(step.read_bytes() + b"\n")
        result = self.run_mirror()
        self.assertEqual(result.returncode, 1)
        self.assertIn("differs", result.stdout)
        self.assertIn("HGR20R300.step", result.stdout)

    def test_apply_copies_only_what_the_public_rows_allow(self):
        family = Path("modules/hiwin/modules/hgr-rail")
        (self.public / family / "cad" / "original" / "HGR20R500.step").unlink()
        # The fixture row for HGR20R500 says redistributable, so it comes back; a private-only file does not.
        extra = self.private / family / "cad" / "original" / "SECRET.step"
        extra.write_bytes(b"secret")
        index = self.private / family / "vendor-index.csv"
        index.write_text(index.read_text(encoding="utf-8") + "hiwin,SECRET,cad/original/SECRET.step,6,x,,internal,t\n", encoding="utf-8")
        result = self.run_mirror("--apply")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("copied modules/hiwin/modules/hgr-rail/cad/original/HGR20R500.step", result.stdout)
        self.assertTrue((self.public / family / "cad" / "original" / "HGR20R500.step").is_file())
        self.assertFalse((self.public / family / "cad" / "original" / "SECRET.step").exists())
        self.assertIn("SECRET.step: public row says nothing", result.stdout)

    def test_the_roots_must_be_the_right_way_round(self):
        result = subprocess.run([sys.executable, str(_SCRIPTS / "validate_mirror.py"), "--root", str(self.private),
                                 "--private", str(self.public)], capture_output=True, text=True, cwd=_REPO)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
