"""Unit tests for private parts libraries.

A private library stores supplier files that may not be passed on, for internal
use only. Every file keeps its supplier's licence and nothing is under an open
licence of ours. See docs/decisions/2026-09-29_private-parts-library.md.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from license_rules import (  # noqa: E402
    LIBRARY_LICENSE,
    apply_any_repo,
    check_any_repo,
    expected_private_library_root_license,
    expected_private_library_trademarks,
)
from naming_rules import (  # noqa: E402
    forget_library_roots,
    is_in_private_library,
    is_private_library,
)
from validate_okh import validate  # noqa: E402
from validate_variants import check_all  # noqa: E402

LIBRARY = _REPO / "tests" / "fixtures" / "parts-library"
MACHINE = _REPO / "tests" / "fixtures" / "variant-machine"

FAMILY = "modules/hiwin/modules/hgr-rail"
INTERNAL_ROW = (
    "HGR20R400,HGR20 rail 400 mm,rail width 20 mm; hole pitch 60 mm,1720,"
    "cad/parts/HGR20R500.FCStd,,internal,A,active,\n"
)


def make_private(root: Path) -> None:
    marker = root / "library.toml"
    marker.write_text(marker.read_text(encoding="utf-8") + "private = true\n",
                      encoding="utf-8")


def add_internal_row(family: Path) -> None:
    table = family / "bom" / "parts.csv"
    table.write_text(table.read_text(encoding="utf-8") + INTERNAL_ROW,
                     encoding="utf-8")


def errors_of(root: Path) -> list[str]:
    return [f"{f.path}: {f.message}" for f in check_all(root)[0]]


class TempCopy(unittest.TestCase):
    source = LIBRARY

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        shutil.copytree(self.source, self.root)
        forget_library_roots()
        self.addCleanup(forget_library_roots)


class TestTheFlag(TempCopy):
    def test_a_library_is_public_unless_it_says_otherwise(self) -> None:
        self.assertFalse(is_private_library(self.root))

    def test_private_true_marks_it_private(self) -> None:
        make_private(self.root)
        self.assertTrue(is_private_library(self.root))
        self.assertTrue(is_in_private_library(
            self.root / FAMILY / "bom" / "parts.csv", self.root))

    def test_a_machine_is_never_private(self) -> None:
        self.assertFalse(is_private_library(MACHINE))


class TestLicence(TempCopy):
    def setUp(self) -> None:
        super().setUp()
        make_private(self.root)

    def test_the_root_licence_grants_nothing_open(self) -> None:
        text = expected_private_library_root_license("stoq-private", "REFAQT")
        self.assertIn("internal use", text)
        self.assertIn("supplier", text)
        for open_licence in ("CC BY-SA 4.0", "GPL-3.0", "CERN-OHL"):
            self.assertNotIn(open_licence, text)

    def test_the_trademarks_grant_nothing_open(self) -> None:
        text = expected_private_library_trademarks("stoq-private", "REFAQT")
        self.assertNotIn("CC BY-SA", text)
        self.assertIn("part numbers", text)

    def test_the_old_public_licence_fails_until_regenerated(self) -> None:
        """The fixture carries the CC BY-SA kit, as a library that turned private would."""
        self.assertTrue(any("LICENSE" in e for e in check_any_repo(self.root)))
        apply_any_repo(self.root)
        self.assertEqual(check_any_repo(self.root), [])
        self.assertIn("internal use",
                      (self.root / "LICENSE").read_text(encoding="utf-8"))

    def test_the_generator_never_overwrites_a_suppliers_licence(self) -> None:
        supplier = self.root / FAMILY / "cad" / "LICENSE"
        supplier.write_text("HIWIN CAD download terms, copied verbatim.\n",
                            encoding="utf-8")
        actions = apply_any_repo(self.root)
        self.assertEqual(supplier.read_text(encoding="utf-8"),
                         "HIWIN CAD download terms, copied verbatim.\n")
        self.assertFalse([a for a in actions if "modules" in a], actions)

    def test_a_manifest_names_the_suppliers_licence(self) -> None:
        okh = self.root / "modules/hiwin/okh.toml"
        okh.write_text(okh.read_text(encoding="utf-8").replace(
            LIBRARY_LICENSE, "LicenseRef-HIWIN-CAD-Terms"), encoding="utf-8")
        self.assertEqual(validate(okh, root=self.root), [])

    def test_an_empty_licence_is_refused(self) -> None:
        okh = self.root / "modules/hiwin/okh.toml"
        okh.write_text(okh.read_text(encoding="utf-8").replace(
            f'"{LIBRARY_LICENSE}"', '""'), encoding="utf-8")
        errors = validate(okh, root=self.root)
        self.assertTrue(any("supplier's licence" in e for e in errors), errors)

    def test_a_public_library_still_needs_cc_by_sa(self) -> None:
        marker = self.root / "library.toml"
        marker.write_text(marker.read_text(encoding="utf-8").replace(
            "private = true", "private = false"), encoding="utf-8")
        okh = self.root / "modules/hiwin/okh.toml"
        okh.write_text(okh.read_text(encoding="utf-8").replace(
            LIBRARY_LICENSE, "LicenseRef-HIWIN-CAD-Terms"), encoding="utf-8")
        errors = validate(okh, root=self.root)
        self.assertTrue(any("CC-BY-SA-4.0" in e for e in errors), errors)


class TestInternalTerms(TempCopy):
    def test_internal_is_accepted_in_a_private_library(self) -> None:
        make_private(self.root)
        add_internal_row(self.root / FAMILY)
        self.assertEqual(errors_of(self.root), [])

    def test_internal_is_refused_in_a_public_library(self) -> None:
        """A file that may not be passed on must never reach stoq."""
        add_internal_row(self.root / FAMILY)
        errors = errors_of(self.root)
        self.assertTrue(any("private library" in e for e in errors), errors)

    def test_an_internal_file_must_be_present(self) -> None:
        """Unlike fetch-only, an internal file is stored, so a gap is an error."""
        make_private(self.root)
        family = self.root / FAMILY
        add_internal_row(family)
        (family / "cad/parts/HGR20R500.FCStd").unlink()
        errors = errors_of(self.root)
        self.assertTrue(any("HGR20R400" in e and "not found" in e
                            for e in errors), errors)


class TestMountedInAMachine(TempCopy):
    source = MACHINE

    def test_the_mounted_librarys_own_flag_decides(self) -> None:
        family = self.root / "modules/stoq" / FAMILY
        add_internal_row(family)
        errors = errors_of(self.root)
        self.assertTrue(any("private library" in e for e in errors), errors)
        forget_library_roots()
        make_private(self.root / "modules/stoq")
        self.assertEqual(errors_of(self.root), [])


if __name__ == "__main__":
    unittest.main()
