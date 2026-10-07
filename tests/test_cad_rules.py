"""Tests for geometric fingerprints and the agent-CAD guard (no FreeCAD needed)."""
from __future__ import annotations

import contextlib
import io
import json
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

from cad_rules import (  # noqa: E402
    DENIED_MCP_TOOLS,
    FINGERPRINT_SCHEMA,
    FingerprintError,
    bodies_outside_part,
    compare_fingerprints,
    document_tree,
    file_digest,
    fingerprint_path,
    frames,
    is_assembly_path,
    is_topology_reference,
    joint_references,
    joint_targets,
    joints_on_topology,
    link_targets,
    object_labels,
    resolve_joint_target,
    load_fingerprint,
    missing_guard_rules,
    normalise,
    round_sig,
    visibility_for,
    write_fingerprint,
)
from validate_cad import (  # noqa: E402
    report_joints,
    validate_document,
    validate_guard,
    validate_part_container,
)


class TestRounding(unittest.TestCase):
    def test_keeps_six_significant_figures_across_magnitudes(self):
        self.assertEqual(round_sig(124500.000000001), 124500.0)
        self.assertEqual(round_sig(0.00123456789), 0.00123457)
        self.assertEqual(round_sig(-98765432.1), -98765400.0)

    def test_absorbs_occt_noise_but_not_real_change(self):
        # A rebuild that only jitters in the last bits must not produce a diff.
        self.assertEqual(round_sig(18600.0), round_sig(18600.0 + 1e-9))
        # A tenth of a millimetre on a 500 mm rail still shows up.
        self.assertNotEqual(round_sig(500.0), round_sig(500.1))

    def test_float_noise_around_zero_snaps_to_zero(self):
        self.assertEqual(round_sig(1e-17), 0.0)
        self.assertEqual(round_sig(-1e-17), 0.0)
        self.assertEqual(round_sig(0.0), 0.0)

    def test_rejects_non_finite_measurements(self):
        for bad in (float("nan"), float("inf")):
            with self.assertRaises(FingerprintError):
                round_sig(bad)

    def test_normalise_preserves_non_float_types(self):
        out = normalise({"ok": True, "n": None, "s": "Pad", "i": 3, "f": [1.000000001]})
        self.assertEqual(out, {"ok": True, "n": None, "s": "Pad", "i": 3, "f": [1.0]})
        self.assertIs(out["ok"], True)


class TestGuardRules(unittest.TestCase):
    def test_both_denied_tools_are_required(self):
        self.assertEqual(missing_guard_rules({}), list(DENIED_MCP_TOOLS))

    def test_partial_deny_list_is_still_a_failure(self):
        settings = {"permissions": {"deny": ["mcp__freecad__reload_document"]}}
        self.assertEqual(
            missing_guard_rules(settings), ["mcp__freecad__execute_code_headless"]
        )

    def test_complete_deny_list_passes_alongside_other_rules(self):
        settings = {
            "permissions": {
                "allow": ["Bash(python *)"],
                "deny": [*DENIED_MCP_TOOLS, "Read(./.env)"],
            }
        }
        self.assertEqual(missing_guard_rules(settings), [])


class TestCompare(unittest.TestCase):
    def test_reports_the_field_that_moved_not_the_whole_document(self):
        old = {"objects": {"Pad": {"volume": 100.0, "bbox": [0, 0, 0, 10, 10, 10]}}}
        new = {"objects": {"Pad": {"volume": 140.0, "bbox": [0, 0, 0, 14, 10, 10]}}}
        self.assertEqual(
            compare_fingerprints(old, new),
            ["Pad.bbox[3]: 10 -> 14", "Pad.volume: 100.0 -> 140.0"],
        )

    def test_added_and_removed_objects(self):
        old = {"objects": {"Pad": {"volume": 1.0}}}
        new = {"objects": {"Pocket": {"volume": 1.0}}}
        self.assertEqual(
            sorted(compare_fingerprints(old, new)), ["Pad: removed", "Pocket: added"]
        )

    def test_identical_fingerprints_produce_no_diff(self):
        data = {"objects": {"Pad": {"volume": 1.0}}, "params": {"len": 2.0}}
        self.assertEqual(compare_fingerprints(data, data), [])


class _FixtureCase(unittest.TestCase):
    """A machine repo with one .FCStd, its fingerprint, and the guard installed."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-cad-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = self._tmp / "machine"
        self.cad = self.root / "rail" / "cad"
        self.cad.mkdir(parents=True)
        self.fcstd = self.cad / "rail.FCStd"
        self.fcstd.write_bytes(b"pretend-fcstd-v1\n")
        self.export = self.cad / "rail.stl"
        self.export.write_bytes(b"solid stub\n")
        self.write_guard(list(DENIED_MCP_TOOLS))
        self.write_fp()

    def write_guard(self, deny):
        settings = self.root / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps({"permissions": {"deny": deny}}), encoding="utf-8")

    def write_fp(self, **overrides):
        data = {
            "schema": FINGERPRINT_SCHEMA,
            "document": "rail",
            "saved": True,
            "sources": {
                "rail.FCStd": file_digest(self.fcstd),
                "rail.stl": file_digest(self.export),
            },
            "params": {"rail_length": 500.0},
            "objects": {"Pad": {"volume": 124500.0}},
            "errors": [],
        }
        data.update(overrides)
        return write_fingerprint(fingerprint_path(self.fcstd), data)


class TestValidateDocument(_FixtureCase):
    def test_a_body_on_top_fails_the_document(self):
        _write_fcstd(self.fcstd, BODY_ON_TOP)
        self.write_fp()
        errors = validate_document(self.fcstd, self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("not inside a Part container", errors[0])

    def test_current_fingerprint_passes(self):
        self.assertEqual(validate_document(self.fcstd, self.root), [])

    def test_edited_fcstd_is_caught(self):
        self.fcstd.write_bytes(b"pretend-fcstd-v2-EDITED\n")
        errors = validate_document(self.fcstd, self.root)
        self.assertTrue(any("changed since its fingerprint" in e for e in errors))

    def test_stale_export_is_caught(self):
        self.export.write_bytes(b"solid TAMPERED\n")
        errors = validate_document(self.fcstd, self.root)
        self.assertTrue(any("rail.stl is stale" in e for e in errors))

    def test_missing_export_is_caught(self):
        self.export.unlink()
        errors = validate_document(self.fcstd, self.root)
        self.assertTrue(any("rail.stl is missing" in e for e in errors))

    def test_fingerprint_from_unsaved_document_is_rejected(self):
        # Measured in the GUI before saving: the numbers cannot be reproduced
        # from the committed .FCStd, so committing one would be misleading.
        self.write_fp(saved=False)
        errors = validate_document(self.fcstd, self.root)
        self.assertTrue(any("unsaved document" in e for e in errors))

    def test_missing_fingerprint_names_the_rebuild_command(self):
        fingerprint_path(self.fcstd).unlink()
        errors = validate_document(self.fcstd, self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("build_model.py", errors[0])

    def test_future_schema_is_rejected_rather_than_misread(self):
        self.write_fp(schema=FINGERPRINT_SCHEMA + 1)
        errors = validate_document(self.fcstd, self.root)
        self.assertTrue(any("schema" in e for e in errors))

    def test_build_time_errors_are_surfaced(self):
        self.write_fp(errors=["Pocket: object state is Invalid"])
        errors = validate_document(self.fcstd, self.root)
        self.assertTrue(any("Invalid" in e for e in errors))


class TestValidateGuard(_FixtureCase):
    def test_complete_guard_passes(self):
        self.assertEqual(validate_guard(self.root), [])

    def test_missing_settings_file_explains_the_risk(self):
        (self.root / ".claude" / "settings.json").unlink()
        errors = validate_guard(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("execute_code_headless", errors[0])

    def test_removed_deny_rule_fails(self):
        self.write_guard(["mcp__freecad__reload_document"])
        errors = validate_guard(self.root)
        self.assertTrue(any("execute_code_headless" in e for e in errors))

    def test_malformed_settings_json_fails_clearly(self):
        (self.root / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
        errors = validate_guard(self.root)
        self.assertTrue(any("invalid JSON" in e for e in errors))


class TestLoadFingerprint(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-fp-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def test_missing_file(self):
        with self.assertRaises(FingerprintError):
            load_fingerprint(self._tmp / "absent.fingerprint.json")

    def test_invalid_json(self):
        path = self._tmp / "bad.fingerprint.json"
        path.write_text("{", encoding="utf-8")
        with self.assertRaises(FingerprintError):
            load_fingerprint(path)

    def test_round_trip_is_sorted_and_newline_terminated(self):
        path = self._tmp / "ok.fingerprint.json"
        write_fingerprint(path, {"schema": FINGERPRINT_SCHEMA, "b": 1.0, "a": 2.0})
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertLess(text.index('"a"'), text.index('"b"'))
        self.assertEqual(load_fingerprint(path)["a"], 2.0)


def _document_xml(objects):
    """A minimal Document.xml: ``objects`` is ``[(name, type_id, children)]``."""
    listed = "".join(f'<Object type="{t}" name="{n}" id="{i}"/>'
                     for i, (n, t, _) in enumerate(objects))
    data = ""
    for name, _, children in objects:
        links = "".join(f'<Link value="{c}"/>' for c in children)
        group = (
            '<Property name="Group" type="App::PropertyLinkList">'
            f'<LinkList count="{len(children)}">{links}</LinkList></Property>'
        ) if children else ""
        data += f'<Object name="{name}"><Properties>{group}</Properties></Object>'
    return (
        '<?xml version="1.0" encoding="utf-8"?><Document SchemaVersion="4">'
        f"<Objects Count=\"{len(objects)}\">{listed}</Objects>"
        f"<ObjectData Count=\"{len(objects)}\">{data}</ObjectData></Document>"
    )


def _write_fcstd(path, objects):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Document.xml", _document_xml(objects))


BODY_ON_TOP = [
    ("Body", "PartDesign::Body", ["Pad", "Sketch"]),
    ("Sketch", "Sketcher::SketchObject", []),
    ("Pad", "PartDesign::Pad", []),
]
BODY_IN_PART = [("Part", "App::Part", ["Body"]), *BODY_ON_TOP]


class TestPartContainer(unittest.TestCase):
    """The top object of a part is a Part, with the Body inside it."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-cad-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def test_a_body_on_top_is_reported(self):
        self.assertEqual(bodies_outside_part(BODY_ON_TOP), ["Body"])

    def test_a_body_inside_a_part_passes(self):
        self.assertEqual(bodies_outside_part(BODY_IN_PART), [])

    def test_a_body_in_a_group_inside_a_part_passes(self):
        objects = [
            ("Part", "App::Part", ["Group"]),
            ("Group", "App::DocumentObjectGroup", ["Body"]),
            *BODY_ON_TOP,
        ]
        self.assertEqual(bodies_outside_part(objects), [])

    def test_only_the_loose_body_is_named(self):
        objects = [*BODY_IN_PART, ("Body001", "PartDesign::Body", [])]
        self.assertEqual(bodies_outside_part(objects), ["Body001"])

    def test_an_assembly_document_is_exempt(self):
        objects = [
            ("Assembly", "Assembly::AssemblyObject", []),
            ("Master", "App::DocumentObjectGroup", ["Body_master"]),
            ("Body_master", "PartDesign::Body", []),
        ]
        self.assertEqual(bodies_outside_part(objects), [])

    def test_a_document_with_no_body_passes(self):
        self.assertEqual(bodies_outside_part([("Params", "Spreadsheet::Sheet", [])]), [])

    def test_document_tree_reads_types_and_groups(self):
        fcstd = self._tmp / "rail.FCStd"
        _write_fcstd(fcstd, BODY_IN_PART)
        self.assertEqual(document_tree(fcstd), BODY_IN_PART)

    def test_an_unreadable_file_reads_as_empty(self):
        stub = self._tmp / "stub.FCStd"
        stub.write_bytes(b"not a zip")
        self.assertEqual(document_tree(stub), [])

    def test_assembly_paths(self):
        self.assertTrue(is_assembly_path(Path("x-axis/cad/assemblies/x-axis.FCStd")))
        self.assertFalse(is_assembly_path(Path("x-axis/cad/parts/carriage/carriage.FCStd")))
        self.assertFalse(is_assembly_path(Path("rail/cad/rail.FCStd")))

    def test_validator_reports_a_body_on_top_in_a_part_file(self):
        fcstd = self._tmp / "m" / "rail" / "cad" / "parts" / "rail.FCStd"
        _write_fcstd(fcstd, BODY_ON_TOP)
        errors = validate_part_container(fcstd, self._tmp / "m")
        self.assertEqual(len(errors), 1)
        self.assertIn("'Body' is not inside a Part container", errors[0])

    def test_validator_skips_the_assemblies_folder(self):
        fcstd = self._tmp / "m" / "rail" / "cad" / "assemblies" / "rail.FCStd"
        _write_fcstd(fcstd, BODY_ON_TOP)
        self.assertEqual(validate_part_container(fcstd, self._tmp / "m"), [])


def _joint_xml(name, label, references):
    """One joint as FreeCAD 1.1 saves it. ``references`` maps a property to its subs."""
    props = (f'<Property name="Label" type="App::PropertyString"><String value="{label}"/></Property>'
             '<Property name="JointType" type="App::PropertyEnumeration">'
             '<Integer value="0"/></Property>')
    for ref, subs in references.items():
        if len(subs) == 1:
            link = f'<XLink file="" stamp="" name="Link" sub="{subs[0]}"/>'
        else:
            items = "".join(f'<Sub value="{sub}"/>' for sub in subs)
            link = f'<XLink file="" stamp="" name="Link" count="{len(subs)}">{items}</XLink>'
        props += f'<Property name="{ref}" type="App::PropertyXLinkSub">{link}</Property>'
    return f'<Object name="{name}"><Properties>{props}</Properties></Object>'


def _write_assembly(path, joints):
    path.parent.mkdir(parents=True, exist_ok=True)
    listed = "".join(f'<Object type="App::FeaturePython" name="{j[0]}" id="{i}"/>'
                     for i, j in enumerate(joints))
    data = "".join(_joint_xml(*j) for j in joints)
    xml = ('<?xml version="1.0" encoding="utf-8"?><Document SchemaVersion="4">'
           f'<Objects Count="{len(joints)}">{listed}</Objects>'
           f'<ObjectData Count="{len(joints)}">{data}</ObjectData></Document>')
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Document.xml", xml)


ON_FACE = ("Joint", "Fixed rail", {
    "Reference1": ["Body.Pad.Face6", "Body.Pad.Vertex3"],
    "Reference2": ["IF_mount_bottom.", "IF_mount_bottom."],
})
ON_FRAMES = ("Joint001", "Slider", {
    "Reference1": ["IF_rail_A.X_Axis"],
    "Reference2": ["IF_carriage."],
})


class TestJointsOnTopology(unittest.TestCase):
    """A joint uses a mounting frame, not a face, an edge or a point."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-joints-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def test_topology_names(self):
        for sub in ("Body.Pad.Face6", "Edge12", "Box.Vertex1", "Body.;#7:1;:H1d4,F.Face6"):
            self.assertTrue(is_topology_reference(sub), sub)
        for sub in ("IF_mount.", "IF_mount.X_Axis", "IF_mount.XY_Plane", "", "Body.",
                    "Body.Facet"):
            self.assertFalse(is_topology_reference(sub), sub)

    def test_references_are_read_from_the_saved_file(self):
        fcstd = self._tmp / "x-axis.FCStd"
        _write_assembly(fcstd, [ON_FACE, ON_FRAMES])
        self.assertEqual(joint_references(fcstd), [
            ("Fixed rail", "Reference1", "Body.Pad.Face6"),
            ("Fixed rail", "Reference1", "Body.Pad.Vertex3"),
            ("Fixed rail", "Reference2", "IF_mount_bottom."),
            ("Fixed rail", "Reference2", "IF_mount_bottom."),
            ("Slider", "Reference1", "IF_rail_A.X_Axis"),
            ("Slider", "Reference2", "IF_carriage."),
        ])

    def test_each_reference_is_named_once(self):
        fcstd = self._tmp / "x-axis.FCStd"
        _write_assembly(fcstd, [ON_FACE, ON_FRAMES])
        self.assertEqual(joints_on_topology(joint_references(fcstd)),
                         ["joint 'Fixed rail' Reference1 uses Body.Pad.Face6"])

    def test_a_grounded_joint_and_a_part_file_have_no_references(self):
        fcstd = self._tmp / "x-axis.FCStd"
        _write_assembly(fcstd, [("GroundedJoint", "Grounded", {})])
        self.assertEqual(joint_references(fcstd), [])
        part = self._tmp / "rail.FCStd"
        _write_fcstd(part, BODY_IN_PART)
        self.assertEqual(joint_references(part), [])
        stub = self._tmp / "stub.FCStd"
        stub.write_bytes(b"not a zip")
        self.assertEqual(joint_references(stub), [])

    def test_validator_warns_and_fails_only_when_strict(self):
        fcstd = self._tmp / "m" / "cad" / "assemblies" / "x-axis.FCStd"
        _write_assembly(fcstd, [ON_FACE])
        root = self._tmp / "m"
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertTrue(report_joints([fcstd], root, strict=False))
        self.assertIn("WARN  joints: 1", out.getvalue())
        self.assertIn("cad/assemblies/x-axis.FCStd: joint 'Fixed rail'", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertFalse(report_joints([fcstd], root, strict=True))
        self.assertIn("FAIL  joints", out.getvalue())

    def test_validator_is_quiet_when_every_joint_uses_a_frame(self):
        fcstd = self._tmp / "m" / "cad" / "assemblies" / "x-axis.FCStd"
        _write_assembly(fcstd, [ON_FRAMES])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertTrue(report_joints([fcstd], self._tmp / "m", strict=True))
        self.assertEqual(out.getvalue(), "")


class TestVisibilityFor(unittest.TestCase):
    """A build shows what a person must see and hides the coordinate system."""

    def test_containers_and_links_are_shown(self):
        for type_id in ("App::Part", "PartDesign::Body",
                        "Assembly::AssemblyObject", "App::Link"):
            self.assertIs(visibility_for(type_id), True, type_id)

    def test_imported_solids_and_frames_are_shown(self):
        # A supplier's STEP comes in as Part::Feature objects, and a mounting
        # frame is what a designer must see to place it. Both opened hidden.
        for type_id in ("Part::Feature", "Part::LocalCoordinateSystem"):
            self.assertIs(visibility_for(type_id), True, type_id)

    def test_the_coordinate_system_is_hidden(self):
        for type_id in ("App::Origin", "App::Line", "App::Plane", "App::Point"):
            self.assertIs(visibility_for(type_id), False, type_id)

    def test_features_and_sketches_are_left_alone(self):
        for type_id in ("PartDesign::Pad", "Sketcher::SketchObject"):
            self.assertIsNone(visibility_for(type_id), type_id)


class TestFingerprintPath(unittest.TestCase):
    def test_derives_sibling_name(self):
        self.assertEqual(
            fingerprint_path(Path("m/cad/rail.FCStd")).name, "rail.fingerprint.json"
        )
        self.assertEqual(fingerprint_path(Path("m/cad/rail.FCStd")).parent.name, "cad")


if __name__ == "__main__":
    unittest.main()


def _write_document(path, objects, links=None, joints=None):
    """A Document.xml with labels, links and joints, as FreeCAD saves them.

    ``objects`` is ``[(name, type_id, label)]``; ``links`` is
    ``{link name: file}``; ``joints`` is ``[(name, label, {ref: (link, [subs])})]``.
    """
    links = links or {}
    joints = joints or []
    listed = "".join(f'<Object type="{t}" name="{n}" id="{i}"/>'
                     for i, (n, t, _) in enumerate(objects))
    listed += "".join(f'<Object type="App::FeaturePython" name="{j[0]}" id="{100 + i}"/>'
                      for i, j in enumerate(joints))
    data = ""
    for name, _, label in objects:
        props = ""
        if label is not None:
            props += ('<Property name="Label" type="App::PropertyString">'
                      f'<String value="{label}"/></Property>')
        if name in links:
            props += ('<Property name="LinkedObject" type="App::PropertyXLink">'
                      f'<XLink file="{links[name]}" stamp="" name="Part"/></Property>')
        data += f'<Object name="{name}"><Properties>{props}</Properties></Object>'
    for name, label, refs in joints:
        props = ('<Property name="JointType" type="App::PropertyEnumeration">'
                 '<Integer value="0"/></Property>'
                 '<Property name="Label" type="App::PropertyString">'
                 f'<String value="{label}"/></Property>')
        for ref, (link, subs) in refs.items():
            items = "".join(f'<Sub value="{s}"/>' for s in subs)
            props += (f'<Property name="{ref}" type="App::PropertyXLinkSub">'
                      f'<XLink file="" stamp="" name="{link}" count="{len(subs)}">'
                      f'{items}</XLink></Property>')
        data += f'<Object name="{name}"><Properties>{props}</Properties></Object>'
    count = len(objects) + len(joints)
    xml = ('<?xml version="1.0" encoding="utf-8"?><Document SchemaVersion="4">'
           f'<Objects Count="{count}">{listed}</Objects>'
           f'<ObjectData Count="{count}">{data}</ObjectData></Document>')
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Document.xml", xml)


WRAPPER = [
    ("Part", "App::Part", "HGL15"),
    ("Part__Feature001", "Part::Feature", "HIWIN_HGL15"),
    ("LCS", "Part::LocalCoordinateSystem", "IF_rail"),
    ("Frame", "Part::LocalCoordinateSystem", None),
    ("X_Axis001", "App::Line", "X-axis001"),
]


class TestFrameReaders(unittest.TestCase):
    """Labels, frames and joint targets are read from a saved file, without FreeCAD."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-frames-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.part = self._tmp / "m" / "cad" / "parts" / "block" / "block.FCStd"
        _write_document(self.part, WRAPPER)

    def test_labels_fall_back_to_the_name(self):
        labels = object_labels(self.part)
        self.assertEqual(labels["LCS"], "IF_rail")
        self.assertEqual(labels["Part__Feature001"], "HIWIN_HGL15")
        self.assertEqual(labels["Frame"], "Frame")

    def test_frames_lists_only_coordinate_systems_in_order(self):
        self.assertEqual(frames(self.part), [("LCS", "IF_rail"), ("Frame", "Frame")])

    def test_joint_targets_resolve_through_the_link_to_the_part_file(self):
        assembly = self._tmp / "m" / "cad" / "assemblies" / "stage" / "stage.FCStd"
        _write_document(
            assembly,
            [("Assembly", "Assembly::AssemblyObject", "stage"),
             ("block", "App::Link", "block"),
             ("IF_local", "Part::LocalCoordinateSystem", "IF_local")],
            links={"block": "../../parts/block/block.FCStd"},
            joints=[("Joint", "Fixed block", {
                "Reference1": ("block", ["LCS.XY_Plane001."]),
                "Reference2": ("IF_local", ["IF_local."]),
            })],
        )
        self.assertEqual(link_targets(assembly), {"block": "../../parts/block/block.FCStd"})
        targets = joint_targets(assembly)
        self.assertEqual(targets, [
            ("Fixed block", "Reference1", "block", "LCS.XY_Plane001."),
            ("Fixed block", "Reference2", "IF_local", "IF_local."),
        ])
        file, name = resolve_joint_target(assembly, "block", "LCS.XY_Plane001.")
        self.assertEqual(file.resolve(), self.part.resolve())
        self.assertEqual(name, "LCS")
        self.assertEqual(object_labels(file)[name], "IF_rail")
        file, name = resolve_joint_target(assembly, "IF_local", "IF_local.")
        self.assertEqual(file, assembly)
        self.assertEqual(name, "IF_local")

    def test_an_unreadable_file_reads_as_empty(self):
        stub = self._tmp / "stub.FCStd"
        stub.write_bytes(b"not a zip")
        self.assertEqual(object_labels(stub), {})
        self.assertEqual(frames(stub), [])
        self.assertEqual(link_targets(stub), {})
        self.assertEqual(joint_targets(stub), [])
