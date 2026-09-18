"""Unit tests for role modules: the job container in a machine.

A role is named after what it does, never after the product bought, so changing
brand moves nothing above it. It generates no files: the role names an exact
part number, so a library update cannot substitute a different one and there is
nothing to copy. Checks replace the file.
See docs/decisions/2026-09-18_role-modules.md.
"""
from __future__ import annotations

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

from cad_rules import document_links, links_resolve_to  # noqa: E402
from validate_okh import validate  # noqa: E402
from validate_variants import check_all, family_path_of  # noqa: E402

MACHINE = _REPO / "tests" / "fixtures" / "variant-machine"
ROLE = "modules/linear-guide-x"


def write_document(path: Path, *links: str) -> None:
    """A FreeCAD document is a zip whose Document.xml records its links."""
    objects = "".join(
        f'<Object name="Link{i}"><Properties Count="1">'
        f'<Property name="LinkedObject" type="App::PropertyXLink">'
        f'<XLink file="{link}" stamp="" name="x"/>'
        f"</Property></Properties></Object>"
        for i, link in enumerate(links)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "Document.xml",
            "<?xml version='1.0' encoding='utf-8'?><Document SchemaVersion=\"4\">"
            f"<ObjectData Count=\"{len(links)}\">{objects}</ObjectData></Document>",
        )


class MachineCopy(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "machine"
        shutil.copytree(MACHINE, self.root)
        self.addCleanup(self._tmp.cleanup)
        self.okh = self.root / ROLE / "okh.toml"

    def errors(self) -> list[str]:
        return [f.message for f in check_all(self.root)[0]]

    def warnings(self) -> list[str]:
        return [f.message for f in check_all(self.root)[1]]

    def select(self, part: str) -> None:
        """Rewrite whichever selection is there, so calls can be chained."""
        import re
        text = re.sub(r'selected = "[^"]*"', f'selected = "{part}"',
                      self.okh.read_text(), count=1)
        self.okh.write_text(text)


class TestReference(unittest.TestCase):
    """A reference names the brand and the family, not the folders between."""

    def test_it_expands_to_the_path_inside_the_library(self) -> None:
        self.assertEqual(family_path_of("hiwin/hgr-rail"),
                         "modules/hiwin/modules/hgr-rail")

    def test_a_brand_with_no_family_still_works(self) -> None:
        self.assertEqual(family_path_of("hiwin"), "modules/hiwin")


class TestTheFixturePasses(MachineCopy):
    def test_a_machine_with_a_role_and_a_library_is_clean(self) -> None:
        self.assertEqual(self.errors(), [])


class TestSwappingBrand(MachineCopy):
    """The point of the whole design, so it is tested as a real comparison."""

    def test_only_the_roles_own_manifest_changes(self) -> None:
        def snapshot() -> dict[str, bytes]:
            return {p.relative_to(self.root).as_posix(): p.read_bytes()
                    for p in sorted(self.root.rglob("*")) if p.is_file()}

        before = snapshot()
        self.select("thk/shs-rail#SHS20R500")
        changed = sorted(k for k, v in snapshot().items() if before.get(k) != v)
        self.assertEqual(changed, [f"{ROLE}/okh.toml"])

    def test_the_machine_is_still_valid_after_the_swap(self) -> None:
        self.select("thk/shs-rail#SHS20R500")
        self.assertEqual(self.errors(), [])

    def test_the_parts_list_row_identifiers_do_not_move(self) -> None:
        bom = self.root / ROLE / "bom/bom.csv"
        before = bom.read_text()
        self.select("thk/shs-rail#SHS20R500")
        self.assertEqual(bom.read_text(), before)


class TestTheChecksThatReplaceAFile(MachineCopy):
    def test_a_part_that_is_not_in_the_library_is_refused(self) -> None:
        self.select("hiwin/hgr-rail#HGR20R999")
        self.assertTrue(any("is not in the 'hiwin/hgr-rail' catalogue" in e
                            for e in self.errors()), self.errors())

    def test_a_family_that_does_not_exist_is_refused(self) -> None:
        self.select("hiwin/does-not-exist#X")
        self.assertTrue(any("no family 'hiwin/does-not-exist'" in e
                            for e in self.errors()), self.errors())

    def test_a_part_that_does_not_fit_is_refused_by_interface_name(self) -> None:
        """A screw cannot fill a linear-guide role, and the message says why."""
        self.select("din/din-912#M4X10")
        self.assertTrue(any("does not provide LinearGuide20MountInterface" in e
                            for e in self.errors()), self.errors())

    def test_a_discontinued_part_warns_and_names_the_replacement(self) -> None:
        self.select("hiwin/hgr-rail#HGR20R200")
        warnings = self.warnings()
        self.assertTrue(any("discontinued" in w and "HGR20R300" in w
                            for w in warnings), warnings)

    def test_every_approved_alternative_is_held_to_the_same_rule(self) -> None:
        self.okh.write_text(self.okh.read_text().replace(
            '"thk/shs-rail#SHS20R500",', '"thk/shs-rail#SHS20R999",'))
        self.assertTrue(any("approved" in e for e in self.errors()), self.errors())

    def test_selected_must_be_one_of_the_approved_parts(self) -> None:
        """What you buy today has to be something you decided is acceptable."""
        self.select("din/din-912#M4X10")
        errors = validate(self.okh, root=self.root)
        self.assertTrue(any("selected is not in approved" in e for e in errors),
                        errors)


class TestTheDocumentMustMatchTheText(MachineCopy):
    """The check worth more than any generated file.

    A file written from the text can never catch the text and the model
    disagreeing, because it never looks at the model.
    """

    TARGET = ("../../stoq/modules/hiwin/modules/hgr-rail"
              "/cad/parts/HGR20R500.FCStd")

    def document(self) -> Path:
        return self.root / ROLE / "cad/linear-guide-x.FCStd"

    def test_a_document_linking_the_selected_part_passes(self) -> None:
        write_document(self.document(), self.TARGET)
        self.assertEqual(self.errors(), [])

    def test_a_document_linking_a_different_part_is_refused(self) -> None:
        write_document(self.document(), self.TARGET.replace("R500", "R300"))
        errors = self.errors()
        self.assertTrue(any("but linear-guide-x.FCStd links HGR20R300" in e
                            for e in errors), errors)

    def test_changing_the_text_and_forgetting_the_model_is_caught(self) -> None:
        """The real mistake: the selection moves and the drawing does not."""
        write_document(self.document(), self.TARGET)
        self.assertEqual(self.errors(), [])
        self.select("hiwin/hgr-rail#HGR20R300")
        errors = self.errors()
        self.assertTrue(any("links HGR20R500" in e for e in errors), errors)

    def test_changing_the_model_and_forgetting_the_text_is_caught(self) -> None:
        """And the same mistake the other way round."""
        write_document(self.document(), self.TARGET.replace("R500", "R300"))
        errors = self.errors()
        self.assertTrue(any("selected is 'hiwin/hgr-rail#HGR20R500'" in e
                            for e in errors), errors)

    def test_a_role_with_no_drawing_yet_is_fine(self) -> None:
        self.assertFalse((self.root / ROLE / "cad").exists())
        self.assertEqual(self.errors(), [])


class TestReadingDocuments(unittest.TestCase):
    def test_links_are_read_without_freecad(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "a.FCStd"
            write_document(doc, "../b/c.FCStd", "../d/e.FCStd")
            self.assertEqual(document_links(doc),
                             ["../b/c.FCStd", "../d/e.FCStd"])

    def test_a_relative_link_resolves_against_the_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lib").mkdir()
            target = root / "lib" / "part.FCStd"
            target.write_text("x")
            doc = root / "role" / "role.FCStd"
            write_document(doc, "../lib/part.FCStd")
            self.assertTrue(links_resolve_to(doc, target))
            self.assertFalse(links_resolve_to(doc, root / "lib" / "other.FCStd"))

    def test_a_file_that_is_not_a_document_reports_no_links(self) -> None:
        """A stub or a partial download must not crash a gate."""
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "stub.FCStd"
            stub.write_text("not a zip")
            self.assertEqual(document_links(stub), [])


if __name__ == "__main__":
    unittest.main()
