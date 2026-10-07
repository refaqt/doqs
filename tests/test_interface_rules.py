"""Tests for the one naming rule that ties a port, a frame and an okh entry."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import interface_rules as ir  # noqa: E402


class TestFrameNames(unittest.TestCase):
    def test_port_to_frame(self):
        self.assertEqual(ir.frame_label("referenceRailMount"), "IF_reference_rail_mount")
        self.assertEqual(ir.frame_label("baseMount"), "IF_base_mount")
        self.assertEqual(ir.frame_label("strip"), "IF_strip")
        self.assertEqual(ir.frame_label("railA"), "IF_rail_a")
        self.assertEqual(ir.frame_label("IF_already"), "IF_already")

    def test_frame_to_port_round_trips(self):
        for port in ("referenceRailMount", "baseMount", "strip", "clampMountStart"):
            self.assertEqual(ir.port_name_of(ir.frame_label(port)), port)
        self.assertEqual(ir.port_name_of("IF_rail_a"), "railA")
        self.assertEqual(ir.port_name_of("IF_"), "")

    def test_port_names_are_lower_camel(self):
        self.assertTrue(ir.is_port_name("baseMount"))
        self.assertFalse(ir.is_port_name("BaseMount"))
        self.assertFalse(ir.is_port_name("base_mount"))


class TestPortDefNames(unittest.TestCase):
    def test_short_name_gets_suffix_and_version(self):
        self.assertEqual(ir.port_def_name("RailMount"), "RailMountInterface_v1")
        self.assertEqual(ir.port_def_name("RailMountInterface", 2), "RailMountInterface_v2")
        self.assertEqual(ir.port_def_name("RailMountInterface_v3"), "RailMountInterface_v3")

    def test_split_and_okh_entry(self):
        self.assertEqual(ir.split_port_def("RailMountInterface_v1"), ("RailMountInterface", 1))
        self.assertEqual(ir.split_port_def("Foo_v2"), ("FooInterface", 2))
        self.assertIsNone(ir.split_port_def("RailMountInterface"))
        self.assertEqual(ir.okh_entry("RailMountInterface_v1"),
                         {"name": "RailMountInterface", "version": "1.0"})
        with self.assertRaises(ValueError):
            ir.okh_entry("NoVersion")

    def test_okh_matches_on_major_only(self):
        self.assertTrue(ir.okh_matches("RailMountInterface_v1", "RailMountInterface", "1.0"))
        self.assertTrue(ir.okh_matches("RailMountInterface_v1", "RailMountInterface", "1.3"))
        self.assertFalse(ir.okh_matches("RailMountInterface_v2", "RailMountInterface", "1.0"))
        self.assertFalse(ir.okh_matches("RailMountInterface_v1", "BaseMountInterface", "1.0"))


if __name__ == "__main__":
    unittest.main()
