"""Tests for the SysML reader and editor (no parser, no FreeCAD, no network)."""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import sysml_rules as sr  # noqa: E402

FIXTURE = _REPO / "tests" / "fixtures" / "sysml" / "stage.sysml"
TEXT = FIXTURE.read_text(encoding="utf-8")


def _kinds(node):
    return [c.kind for c in node.children]


class TestParse(unittest.TestCase):
    """The scanner finds every statement and keeps its exact span."""

    def setUp(self):
        self.root = sr.parse(TEXT)
        self.pkg = self.root.children[0]

    def test_spans_cover_the_whole_text_in_order(self):
        self.assertEqual(self.pkg.kind, "package")
        self.assertEqual(self.pkg.name, "Stage")
        self.assertEqual(TEXT[self.pkg.start:self.pkg.start + 13], "package Stage")
        self.assertEqual(TEXT[self.pkg.end - 1], "}")
        last = 0
        for node in sr.walk(self.root):
            self.assertGreaterEqual(node.start, last if node.parent is self.root else 0)
            self.assertLess(node.start, node.end)
            for child in node.children:
                self.assertGreaterEqual(child.start, node.body_start)
                self.assertLessEqual(child.end, node.body_end)
            if node.parent is self.root:
                last = node.end

    def test_top_level_statements_of_the_package(self):
        self.assertEqual(_kinds(self.pkg), [
            "import", "import", "import",
            "port_def", "port_def", "port_def",
            "part_def", "part_def", "part_def",
            "package", "requirement_def",
        ])

    def test_port_def_with_doc_and_attributes(self):
        rail = self.pkg.child("port_def", "RailMountInterface_v1")
        self.assertEqual(rail.doc, 'A guide rail lies on the floor of the base; see "notes {x}".')
        attrs = rail.of_kind("attribute")
        self.assertEqual([(a.name, a.type_name, a.value) for a in attrs], [
            ("holePitch", "LengthValue", "60 [mm]"),
            ("holesPerRail", "Natural", "7"),
        ])
        # A statement without a body.
        self.assertIsNone(self.pkg.child("port_def", "ClampMountInterface_v1").body_start)

    def test_ports_know_their_side(self):
        base = self.pkg.child("part_def", "Base")
        rail = self.pkg.child("part_def", "GuideRail")
        self.assertFalse(base.child("port", "referenceRailMount").conjugated)
        self.assertTrue(rail.child("port", "baseMount").conjugated)
        self.assertEqual(rail.child("port", "baseMount").type_name, "RailMountInterface_v1")

    def test_requirement_short_names_and_constraints(self):
        reqs = sr.requirements(self.root)
        self.assertEqual([(r["short"], r["name"], r["package"]) for r in reqs], [
            ("STG-01", "Width", "Stage::Mandatory"),
            ("STG-03", "Length", "Stage::Mandatory"),
            (None, "StageSpecification", "Stage"),
        ])
        self.assertEqual(reqs[0]["constraint"], "stage.width <= 210 [mm]")
        self.assertEqual(reqs[1]["constraint"],
                         "stage.length <= stage.travel + 340 [mm] - 2 * stage.height")
        self.assertEqual(reqs[0]["subject"], {"name": "stage", "type": "Stage"})
        self.assertEqual([m["type"] for m in reqs[2]["members"]],
                         ["Mandatory::Width", "Mandatory::Length"])

    def test_find_by_path(self):
        self.assertEqual(sr.find(self.root, "Stage::Base").kind, "part_def")
        self.assertEqual(sr.find(self.root, "Stage::Stage.base").type_name, "Base")
        self.assertEqual(sr.find(self.root, "Stage::Mandatory::Width").short_name, "STG-01")
        self.assertIsNone(sr.find(self.root, "Stage::Nothing"))
        self.assertEqual(sr.path_of(sr.find(self.root, "Stage::Mandatory::Width")),
                         "Stage::Mandatory::Width")

    def test_readers(self):
        self.assertEqual([i["name"] for i in sr.interfaces(self.root)], [
            "BaseMountInterface_v1", "RailMountInterface_v1", "ClampMountInterface_v1"])
        self.assertEqual(sr.interfaces(self.root)[0]["version"], 1)
        self.assertEqual(sr.connections(self.root), [
            ("Stage::Stage", "base.referenceRailMount", "referenceRail.baseMount")])
        stage = [p for p in sr.parts(self.root) if p["name"] == "Stage"][0]
        self.assertEqual([u["name"] for u in stage["usages"]], ["base", "referenceRail"])
        self.assertEqual(sr.version_of("Foo_v12"), 12)
        self.assertIsNone(sr.version_of("Foo"))

    def test_comments_and_strings_do_not_confuse_the_scanner(self):
        text = (
            "package P {\n"
            "    // a comment with { a brace ; and part def Fake\n"
            "    /* block comment } */\n"
            "    attribute label : String = \"a;b{c}\";\n"
            "    part def Real { doc /* has ; and } inside */ }\n"
            "}\n"
        )
        root = sr.parse(text)
        pkg = root.children[0]
        self.assertEqual(_kinds(pkg), ["attribute", "part_def"])
        self.assertEqual(pkg.child("attribute", "label").value, '"a;b{c}"')
        self.assertEqual(pkg.child("part_def", "Real").doc, "has ; and } inside")

    def test_redefinitions_are_read(self):
        text = (
            "package P {\n"
            "    part current : LinearMotorStage {\n"
            "        part :>> encoder {\n"
            "            attribute :>> signal = EncoderSignal::sinCos1Vpp;\n"
            "        }\n"
            "        attribute :>> maxSpeed = 3 [m/s];\n"
            "    }\n"
            "}\n"
        )
        usage = sr.parse(text).children[0].children[0]
        self.assertEqual((usage.kind, usage.name, usage.type_name), ("part", "current", "LinearMotorStage"))
        encoder = usage.children[0]
        self.assertTrue(encoder.redefines)
        self.assertEqual(encoder.name, "encoder")
        self.assertEqual(usage.children[1].value, "3 [m/s]")


class TestEdits(unittest.TestCase):
    """Every edit touches only the lines it adds, and a rerun changes nothing."""

    def assertAddsLines(self, before, after, lines):
        added = Counter(after.splitlines()) - Counter(before.splitlines())
        self.assertEqual(sorted(added.elements()), sorted(lines))
        removed = Counter(before.splitlines()) - Counter(after.splitlines())
        self.assertEqual(list(removed.elements()), [])

    def test_add_port_def_goes_after_the_last_port_def(self):
        out = sr.add_port_def(TEXT, "Stage", "BlockMountInterface_v1",
                              doc="A guide block screws onto the carriage.",
                              attributes=("holePitch : LengthValue = 30 [mm]",))
        self.assertAddsLines(TEXT, out, [
            "", "    port def BlockMountInterface_v1 {",
            "        doc /* A guide block screws onto the carriage. */",
            "        attribute holePitch : LengthValue = 30 [mm];", "    }",
        ])
        self.assertLess(out.index("port def BlockMountInterface_v1"), out.index("part def Base"))
        self.assertGreater(out.index("port def BlockMountInterface_v1"),
                           out.index("port def ClampMountInterface_v1;"))
        self.assertEqual(sr.add_port_def(out, "Stage", "BlockMountInterface_v1"), out)

    def test_add_port_def_wraps_a_long_doc(self):
        out = sr.add_port_def(TEXT, "Stage", "X_v1", doc="word " * 30)
        self.assertIn("        doc /*\n         * word word", out)
        self.assertIn("\n         */\n", out)

    def test_add_part_def_with_ports(self):
        out = sr.add_part_def(TEXT, "Stage", "GuideBlock", doc="Bought: stoq:hiwin/hgl-block#HGL15.",
                              ports=(("railMount", "BlockRailInterface_v1", True),))
        self.assertAddsLines(TEXT, out, [
            "", "    part def GuideBlock {",
            "        doc /* Bought: stoq:hiwin/hgl-block#HGL15. */",
            "        port railMount : ~BlockRailInterface_v1;", "    }",
        ])
        # After the last part def (Stage), before the Mandatory package.
        self.assertLess(out.index("part def GuideBlock"), out.index("package Mandatory"))
        self.assertGreater(out.index("part def GuideBlock"), out.index("part def Stage"))

    def test_add_port_to_a_part_def(self):
        out = sr.add_port(TEXT, "Stage::Base", "blockMount", "BlockMountInterface_v1")
        self.assertAddsLines(TEXT, out, ["        port blockMount : BlockMountInterface_v1;"])
        base = sr.find(sr.parse(out), "Stage::Base")
        self.assertEqual([p.name for p in base.of_kind("port")],
                         ["machineMount", "referenceRailMount", "blockMount"])
        self.assertEqual(sr.add_port(out, "Stage::Base", "blockMount", "BlockMountInterface_v1"), out)
        with self.assertRaises(sr.SysmlError):
            sr.add_port(out, "Stage::Base", "blockMount", "BlockMountInterface_v1", conjugated=True)
        with self.assertRaises(sr.SysmlError):
            sr.add_port(out, "Stage::Nope", "x", "Y_v1")

    def test_add_port_to_a_part_def_without_ports_goes_after_the_doc(self):
        text = "package P {\n    part def A {\n        doc /* a */\n    }\n}\n"
        out = sr.add_port(text, "P::A", "x", "Y_v1", conjugated=True)
        self.assertEqual(out, "package P {\n    part def A {\n        doc /* a */\n"
                              "        port x : ~Y_v1;\n    }\n}\n")

    def test_add_part_usage_and_connect(self):
        out = sr.add_part_usage(TEXT, "Stage::Stage", "secondRail", "GuideRail")
        self.assertAddsLines(TEXT, out, ["        part secondRail : GuideRail;"])
        out2 = sr.add_connect(out, "Stage::Stage", "base.secondRailMount", "secondRail.baseMount")
        self.assertAddsLines(out, out2, [
            "        connect base.secondRailMount to secondRail.baseMount;"])
        # Same pair, either order: nothing happens.
        self.assertEqual(sr.add_connect(out2, "Stage::Stage", "secondRail.baseMount",
                                        "base.secondRailMount"), out2)
        self.assertEqual(sr.add_part_usage(out2, "Stage::Stage", "secondRail", "GuideRail"), out2)
        with self.assertRaises(sr.SysmlError):
            sr.add_part_usage(out2, "Stage::Stage", "secondRail", "Other")

    def test_add_connect_with_a_comment_keeps_a_blank_line(self):
        out = sr.add_connect(TEXT, "Stage::Stage", "a.x", "b.y", comment="The block")
        self.assertIn("        connect base.referenceRailMount to referenceRail.baseMount;\n\n"
                      "        // The block\n        connect a.x to b.y;\n    }\n", out)

    def test_add_requirement_def_and_member(self):
        out = sr.add_requirement_def(
            TEXT, "Stage::Mandatory", "STG-02", "Height",
            doc="The stage is at most 60 mm high.", subject="stage : Stage",
            constraint="stage.height <= 60 [mm]")
        self.assertAddsLines(TEXT, out, [
            "", "        requirement def <'STG-02'> Height {",
            "            doc /* The stage is at most 60 mm high. */",
            "            subject stage : Stage;",
            "            require constraint { stage.height <= 60 [mm] }", "        }",
        ])
        self.assertEqual(sr.add_requirement_def(out, "Stage::Mandatory", "STG-02", "Height", "x"), out)
        out2 = sr.add_requirement_member(out, "Stage::StageSpecification", "height", "Mandatory::Height")
        self.assertAddsLines(out, out2, ["        requirement height : Mandatory::Height;"])
        reqs = sr.requirements(sr.parse(out2))
        self.assertEqual([r["short"] for r in reqs][:3], ["STG-01", "STG-03", "STG-02"])

    def test_set_doc_replaces_or_adds(self):
        out = sr.set_doc(TEXT, "Stage::GuideRail", "A HIWIN HGR15R rail, 418 mm long.")
        self.assertIn("        doc /* A HIWIN HGR15R rail, 418 mm long. */\n"
                      "        port baseMount : ~RailMountInterface_v1;", out)
        self.assertNotIn("A bought rail from the parts library.", out)
        text = "package P {\n    part def A {\n        port x : Y_v1;\n    }\n}\n"
        self.assertEqual(sr.set_doc(text, "P::A", "New."),
                         "package P {\n    part def A {\n        doc /* New. */\n"
                         "        port x : Y_v1;\n    }\n}\n")

    def test_add_import(self):
        out = sr.add_import(TEXT, "Stage", "'../../modules/stoq/x.sysml'::HglBlock::*")
        self.assertAddsLines(TEXT, out, [
            "    private import '../../modules/stoq/x.sysml'::HglBlock::*;"])
        self.assertEqual(sr.add_import(out, "Stage", "'../../modules/stoq/x.sysml'::HglBlock::*"), out)

    def test_insert_into_an_empty_body(self):
        text = "package P {\n}\n"
        self.assertEqual(sr.add_port_def(text, "P", "A_v1"), "package P {\n    port def A_v1;\n}\n")
        text = "package P {}\n"
        self.assertEqual(sr.add_part_def(text, "P", "A"),
                         "package P {\n    part def A {\n    }\n}\n")

    def test_new_module_text_parses(self):
        text = sr.new_module_text("XAxis", "XAxis", "The X axis.", imports=("ScalarValues::*",))
        root = sr.parse(text)
        self.assertEqual(sr.find(root, "XAxis::XAxis").doc, "The X axis.")
        self.assertEqual(root.children[0].of_kind("import")[0].name, "ScalarValues::*")


if __name__ == "__main__":
    unittest.main()
