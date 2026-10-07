"""Tests for the frame findings of validate_cad.py (no FreeCAD needed)."""
from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from validate_cad import frame_findings, report_frames  # noqa: E402


def _document(path: Path, objects, links=None, joints=None):
    """``objects``: ``[(name, type, label)]``; ``links``: ``{name: file}``;
    ``joints``: ``[(name, label, {ref: (link, sub)})]``."""
    links = links or {}
    joints = joints or []
    listed = "".join(f'<Object type="{t}" name="{n}" id="{i}"/>' for i, (n, t, _) in enumerate(objects))
    listed += "".join(f'<Object type="App::FeaturePython" name="{j[0]}" id="{100 + i}"/>' for i, j in enumerate(joints))
    data = ""
    for name, _, label in objects:
        props = f'<Property name="Label" type="App::PropertyString"><String value="{label}"/></Property>'
        if name in links:
            props += ('<Property name="LinkedObject" type="App::PropertyXLink">'
                      f'<XLink file="{links[name]}" stamp="" name="Part"/></Property>')
        data += f'<Object name="{name}"><Properties>{props}</Properties></Object>'
    for name, label, refs in joints:
        props = ('<Property name="JointType" type="App::PropertyEnumeration"><Integer value="0"/></Property>'
                 f'<Property name="Label" type="App::PropertyString"><String value="{label}"/></Property>')
        for ref, (link, sub) in refs.items():
            props += (f'<Property name="{ref}" type="App::PropertyXLinkSub">'
                      f'<XLink file="" stamp="" name="{link}" count="1"><Sub value="{sub}"/></XLink></Property>')
        data += f'<Object name="{name}"><Properties>{props}</Properties></Object>'
    count = len(objects) + len(joints)
    xml = ('<?xml version="1.0" encoding="utf-8"?><Document SchemaVersion="4">'
           f'<Objects Count="{count}">{listed}</Objects><ObjectData Count="{count}">{data}</ObjectData></Document>')
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Document.xml", xml)


class TestFrameFindings(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-framegate-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = self._tmp / "m"
        cad = self.root / "modules" / "stage" / "cad"
        self.base = cad / "parts" / "base" / "base.FCStd"
        self.rail = cad / "parts" / "rail" / "rail.FCStd"
        self.assembly = cad / "assemblies" / "stage" / "stage.FCStd"
        _document(self.base, [("Part", "App::Part", "base"),
                              ("Frame", "Part::LocalCoordinateSystem", "IF_rail_mount"),
                              ("LCS", "Part::LocalCoordinateSystem", "LCS"),
                              ("Pad", "PartDesign::Pad", "Pad")])
        _document(self.rail, [("Part", "App::Part", "rail"),
                              ("LCS", "Part::LocalCoordinateSystem", "IF_base_mount")])
        _document(self.assembly,
                  [("Assembly", "Assembly::AssemblyObject", "stage"),
                   ("base", "App::Link", "base"), ("rail", "App::Link", "rail"),
                   ("missing", "App::Link", "missing")],
                  links={"base": "../../parts/base/base.FCStd", "rail": "../../parts/rail/rail.FCStd",
                         "missing": "../../parts/nope/nope.FCStd"},
                  joints=[("Joint", "Good", {"Reference1": ("base", "Frame.XY_Plane001."),
                                             "Reference2": ("rail", "LCS.")}),
                          ("Joint001", "On the LCS", {"Reference1": ("base", "LCS.XY_Plane002."),
                                                      "Reference2": ("rail", "LCS.X_Axis.")}),
                          ("Joint002", "On a pad", {"Reference1": ("base", "Pad."),
                                                    "Reference2": ("missing", "LCS.")}),
                          ("Joint003", "On a face", {"Reference1": ("base", "Pad.Face3"),
                                                     "Reference2": ("rail", "LCS.")}),
                          ("GroundedJoint", "Grounded", {})])

    def test_findings_name_the_frame_and_the_joint(self):
        findings = frame_findings([self.base, self.rail, self.assembly], self.root)
        self.assertEqual(findings, [
            "modules/stage/cad/parts/base/base.FCStd: coordinate system 'LCS' is labelled 'LCS'; "
            "a mounting frame is named IF_<where>",
            "modules/stage/cad/assemblies/stage/stage.FCStd: joint 'On the LCS' Reference1 ends on "
            "LCS (LCS), Part::LocalCoordinateSystem; attach it to a mounting frame (IF_...) instead",
            "modules/stage/cad/assemblies/stage/stage.FCStd: joint 'On a pad' Reference1 ends on "
            "Pad (Pad), PartDesign::Pad; attach it to a mounting frame (IF_...) instead",
            "modules/stage/cad/assemblies/stage/stage.FCStd: joint 'On a pad' Reference2 points at "
            f"LCS. in a file that is missing: {(self.assembly.parent / '../../parts/nope/nope.FCStd').resolve()}",
        ])

    def test_report_warns_or_fails(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertTrue(report_frames([self.base, self.assembly], self.root, strict=False))
        self.assertIn("WARN  frames: 4 findings", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertFalse(report_frames([self.base, self.assembly], self.root, strict=True))
        self.assertIn("FAIL  frames", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertTrue(report_frames([self.rail], self.root, strict=True))
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
