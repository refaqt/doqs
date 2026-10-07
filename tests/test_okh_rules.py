"""Tests for the manifest editor: comments survive, reruns change nothing."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import okh_rules  # noqa: E402

MANIFEST = '''# A module manifest, with comments that must survive.
okhv = "OKH-LOSHv1.0"
name = "Compact Stage"
version = "0.1.0"   # bump on release
function = "A stage."

# Interfaces of the whole stage.
[[provides-interface]]
name        = "BaseMountInterface"
version     = "1.0"
description = "Bottom face of the base."

[[part]]
name = "Base"
source = ["cad/parts/base/base.FCStd"]
'''


class TestAppendTable(unittest.TestCase):
    def test_appends_at_the_end_and_keeps_everything_else(self):
        out = okh_rules.append_table(
            MANIFEST, "[[provides-interface]]",
            {"name": "RailMountInterface", "version": "1.0", "description": "Rail seat."},
            comment="Added by doqs add-interface.")
        self.assertTrue(out.startswith(MANIFEST))
        self.assertTrue(out.endswith(
            '\n# Added by doqs add-interface.\n[[provides-interface]]\n'
            'name        = "RailMountInterface"\nversion     = "1.0"\n'
            'description = "Rail seat."\n'))
        data = okh_rules.load(out)
        self.assertEqual([e["name"] for e in data["provides-interface"]],
                         ["BaseMountInterface", "RailMountInterface"])

    def test_an_existing_entry_is_left_alone(self):
        out = okh_rules.append_table(
            MANIFEST, "[[provides-interface]]",
            {"name": "BaseMountInterface", "version": "1.0", "description": "Other words."},
            match={"name": "BaseMountInterface"})
        self.assertEqual(out, MANIFEST)

    def test_lists_and_dates_are_rendered(self):
        out = okh_rules.append_table(
            "name = \"x\"\n", "[[terms-review]]",
            {"kind": "cad", "decision": "public", "reviewed": okh_rules.RawValue("2026-10-07"),
             "paths": ["a", "b"], "ok": True})
        self.assertIn('reviewed = 2026-10-07\n', out)
        self.assertIn('paths    = ["a", "b"]\n', out)
        self.assertIn('ok       = true\n', out)
        self.assertEqual(okh_rules.load(out)["terms-review"][0]["reviewed"].isoformat(), "2026-10-07")

    def test_bad_toml_is_refused(self):
        with self.assertRaises(okh_rules.OkhError):
            okh_rules.append_table("name = \n", "[[part]]", {"name": "x"})


class TestKeys(unittest.TestCase):
    def test_set_a_root_key_keeps_its_comment(self):
        out = okh_rules.set_key(MANIFEST, "version", "0.2.0")
        self.assertIn('version = "0.2.0"  # bump on release\n', out)
        self.assertNotIn('"0.1.0"', out)

    def test_add_a_root_key_before_the_first_table(self):
        out = okh_rules.set_key(MANIFEST, "bom", "bom/bom.csv")
        self.assertLess(out.index('bom = "bom/bom.csv"'), out.index("[[provides-interface]]"))
        self.assertEqual(okh_rules.get_key(out, "bom"), "bom/bom.csv")

    def test_set_a_key_in_one_table(self):
        out = okh_rules.set_key(MANIFEST, "sysml", "Base", "[[part]]", match={"name": "Base"})
        self.assertTrue(out.endswith('source = ["cad/parts/base/base.FCStd"]\nsysml = "Base"\n'))
        self.assertEqual(okh_rules.get_key(out, "sysml", "[[part]]", {"name": "Base"}), "Base")
        with self.assertRaises(okh_rules.OkhError):
            okh_rules.set_key(MANIFEST, "x", "y", "[[part]]", match={"name": "Nope"})

    def test_find_and_has_table(self):
        self.assertTrue(okh_rules.has_table(MANIFEST, "[[part]]", {"name": "Base"}))
        self.assertFalse(okh_rules.has_table(MANIFEST, "[[part]]", {"name": "Lid"}))
        self.assertFalse(okh_rules.has_table(MANIFEST, "[role]"))
        self.assertEqual(okh_rules.interface_entries(MANIFEST, "provides-interface"),
                         [("BaseMountInterface", "1.0")])
        self.assertEqual(okh_rules.interface_entries(MANIFEST, "consumes-interface"), [])

    def test_render_manifest(self):
        text = okh_rules.render_manifest(
            {"okhv": "OKH-LOSHv1.0", "name": "X", "licensor": ["A", "B"]}, comment="Hello")
        self.assertEqual(text, '# Hello\nokhv = "OKH-LOSHv1.0"\nname = "X"\nlicensor = ["A", "B"]\n')
        self.assertEqual(okh_rules.load(text)["licensor"], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
