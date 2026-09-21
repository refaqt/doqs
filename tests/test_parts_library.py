"""Unit tests for parts libraries: the marker, the licence profile, the catalogue.

A parts library records components other people design, make and sell. The
rules that differ from a machine repository are all consequences of one fact:
nothing in it is our design. See docs/decisions/2026-09-18_parts-library.md.
"""
from __future__ import annotations

import hashlib
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
    check_any_repo,
    expected_library_stub,
    expected_library_trademarks,
    mapped_library_dirs,
)
from naming_rules import (  # noqa: E402
    _library_roots_cached,
    forget_library_roots,
    is_parts_library,
    is_under_parts_library,
    csv_reader_skipping_comments,
)
from validate_names import check_all as check_names  # noqa: E402
from validate_okh import validate  # noqa: E402
from validate_variants import check_all, check_parts_table  # noqa: E402

LIBRARY = _REPO / "tests" / "fixtures" / "parts-library"
MACHINE = _REPO / "tests" / "fixtures" / "variant-machine"
MINIMAL = _REPO / "tests" / "fixtures" / "minimal-machine"


class LibraryCopy(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        shutil.copytree(LIBRARY, self.root)
        self.addCleanup(self._tmp.cleanup)
        self.family = self.root / "modules/hiwin/modules/hgr-rail"

    def errors(self) -> list[str]:
        return [f"{f.path}: {f.message}" for f in check_all(self.root)[0]]


class TestTheMarker(LibraryCopy):
    """The marker identifies a library, not the path it is mounted at."""

    def test_the_fixture_is_recognised(self) -> None:
        self.assertTrue(is_parts_library(self.root))

    def test_a_machine_is_not(self) -> None:
        self.assertFalse(is_parts_library(MACHINE))

    def test_a_library_is_recognised_wherever_it_is_mounted(self) -> None:
        """The machine fixture mounts one at modules/stoq."""
        inside = MACHINE / "modules/stoq/modules/hiwin/okh.toml"
        self.assertTrue(is_under_parts_library(inside, MACHINE))
        outside = MACHINE / "modules/x-stage/okh.toml"
        self.assertFalse(is_under_parts_library(outside, MACHINE))


class TestLicence(LibraryCopy):
    def test_a_library_manifest_declares_cc_by_sa(self) -> None:
        self.assertEqual(LIBRARY_LICENSE, "CC-BY-SA-4.0")
        self.assertEqual(validate(self.root / "okh.toml", root=self.root), [])

    def test_the_hardware_licence_is_refused_in_a_library(self) -> None:
        """Claiming CERN-OHL-S over a brand's design would simply be false."""
        okh = self.root / "okh.toml"
        okh.write_text(okh.read_text().replace(LIBRARY_LICENSE, "CERN-OHL-S-2.0"))
        errors = validate(okh, root=self.root)
        self.assertTrue(any("CC-BY-SA-4.0" in e for e in errors), errors)

    def test_the_whole_cad_tree_is_carved_out_not_just_cad_vendor(self) -> None:
        """In a library every geometry file is theirs or derived from theirs."""
        kinds = {d.relative_to(self.root).as_posix(): k
                 for d, k in mapped_library_dirs(self.root)}
        self.assertEqual(kinds["modules/hiwin/modules/hgr-rail/cad"], "vendor")
        self.assertEqual(
            kinds["modules/hiwin/modules/hgr-rail/docs/datasheets"], "vendor")
        self.assertEqual(kinds["modules"], "media")

    def test_the_library_vendor_stub_names_no_hardware_licence(self) -> None:
        self.assertNotIn("CERN", expected_library_stub("vendor"))

    def test_the_library_trademarks_name_only_the_licence_a_library_has(self) -> None:
        """The machine template names three licences. A library carries one.

        Naming CERN-OHL-S here would contradict the check beside it, which
        treats a CERN-OHL-S text in a library as an error.
        """
        text = expected_library_trademarks("STOQ", "REFAQT")
        self.assertIn("CC BY-SA", text)
        self.assertNotIn("CERN", text)
        self.assertNotIn("GPL", text)

    def test_the_library_trademarks_say_the_brands_marks_are_not_ours(self) -> None:
        """The one trademark question a parts library actually raises."""
        text = expected_library_trademarks("STOQ", "REFAQT")
        self.assertIn("brand names", text.lower())
        self.assertIn("part numbers", text.lower())

    def test_the_fixture_trademarks_are_the_library_ones(self) -> None:
        self.assertNotIn(
            "CERN", (self.root / "TRADEMARKS.md").read_text(encoding="utf-8"))

    def test_the_fixture_licence_layout_is_complete(self) -> None:
        self.assertEqual(check_any_repo(self.root), [])


class TestCatalogue(LibraryCopy):
    def test_the_fixture_passes(self) -> None:
        self.assertEqual(self.errors(), [])

    def test_a_missing_fetch_only_file_only_warns(self) -> None:
        """CI must stay green on a fresh clone of a library full of links."""
        errors, warnings = check_all(self.root)
        self.assertEqual([f"{f.path}: {f.message}" for f in errors], [])
        self.assertTrue(any("fetch-only" in w.message for w in warnings))

    def test_a_bad_status_is_refused(self) -> None:
        table = self.family / "bom/parts.csv"
        table.write_text(table.read_text().replace(",A,active", ",A,maybe", 1))
        self.assertTrue(any("status must be one of" in e for e in self.errors()))

    def test_a_duplicate_part_number_is_refused(self) -> None:
        table = self.family / "bom/parts.csv"
        lines = table.read_text().splitlines()
        table.write_text("\n".join(lines + [lines[1]]) + "\n")
        self.assertTrue(any("duplicate part number" in e for e in self.errors()))

    def test_a_row_without_geometry_is_normal(self) -> None:
        """The table is the complete catalogue; files are a cache."""
        rows = list(csv_reader_skipping_comments(
            (self.family / "bom/parts.csv").read_text()))
        without = [r for r in rows if not r["cad"]]
        self.assertTrue(without, "fixture should catalogue a part with no file yet")
        self.assertEqual(self.errors(), [])

    def test_a_discontinued_part_keeps_its_row(self) -> None:
        """An existing machine is still made of it."""
        rows = list(csv_reader_skipping_comments(
            (self.family / "bom/parts.csv").read_text()))
        self.assertTrue(any(r["status"] == "eol" for r in rows))
        self.assertEqual(self.errors(), [])


class TestChecksums(LibraryCopy):
    """A brand can revise a file and keep the part number."""

    def test_a_changed_file_is_caught(self) -> None:
        step = self.family / "cad/original/HGR20R500.step"
        step.write_text(step.read_text() + "\n# quietly revised\n")
        errors = self.errors()
        self.assertTrue(any("no longer matches its recorded checksum" in e
                            for e in errors), errors)

    def test_an_unchanged_file_passes(self) -> None:
        step = self.family / "cad/original/HGR20R500.step"
        index = (self.family / "vendor-index.csv").read_text()
        digest = hashlib.sha256(step.read_bytes()).hexdigest()
        self.assertIn(digest, index)
        self.assertEqual(self.errors(), [])


class TestMountedInAMachine(unittest.TestCase):
    """A machine validates a mounted library's contents in neither direction."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "machine"
        shutil.copytree(MACHINE, self.root)   # already mounts modules/stoq
        self.addCleanup(self._tmp.cleanup)

    def test_the_librarys_manifests_do_not_fail_the_machines_licence_rule(self) -> None:
        """The library declares CC BY-SA; the machine demands CERN-OHL-S."""
        failures = []
        for manifest in sorted(self.root.rglob("okh.toml")):
            errors = validate(manifest, root=self.root)
            if errors:
                failures.append((manifest.relative_to(self.root).as_posix(), errors))
        self.assertEqual(failures, [])

    def test_the_machines_own_manifest_still_needs_the_hardware_licence(self) -> None:
        """Skipping the library must not switch the whole machine over."""
        okh = self.root / "modules/x-stage/okh.toml"
        okh.write_text(okh.read_text().replace("CERN-OHL-S-2.0", LIBRARY_LICENSE))
        errors = validate(okh, root=self.root)
        self.assertTrue(any("CERN-OHL-S-2.0" in e for e in errors), errors)

    def test_naming_reports_nothing_from_the_librarys_contents(self) -> None:
        errors, _ = check_names(self.root, strict_lexicon=False)
        self.assertEqual([f"{f.path}: {f.message}" for f in errors], [])


class TestLibraryLookupIsCached(unittest.TestCase):
    """Callers ask once per manifest, so the tree must not be walked each time."""

    def setUp(self) -> None:
        forget_library_roots()
        self.addCleanup(forget_library_roots)

    def test_the_answer_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "machine"
            shutil.copytree(MACHINE, root)
            manifest = root / "modules/stoq/okh.toml"
            self.assertTrue(is_under_parts_library(manifest, root))
            before = _library_roots_cached.cache_info()
            for _ in range(20):
                is_under_parts_library(manifest, root)
            after = _library_roots_cached.cache_info()
            self.assertEqual(after.misses, before.misses)
            self.assertEqual(after.hits, before.hits + 20)

    def test_clearing_the_cache_sees_a_new_library(self) -> None:
        """The cache assumes a read-only pass. Say so with a test, not a comment."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "machine"
            shutil.copytree(MINIMAL, root)   # a machine with no library yet
            probe = root / "modules" / "stoq" / "okh.toml"
            self.assertFalse(is_under_parts_library(probe, root))
            shutil.copytree(LIBRARY, root / "modules" / "stoq")
            self.assertFalse(is_under_parts_library(probe, root))  # stale on purpose
            forget_library_roots()
            self.assertTrue(is_under_parts_library(probe, root))


class TestCommentedTemplates(unittest.TestCase):
    """Every table a person edits ships with comments explaining what to write."""

    def test_the_shipped_templates_parse_as_copied(self) -> None:
        for template in sorted((_REPO / "templates").rglob("*.csv")):
            with self.subTest(template=template.relative_to(_REPO).as_posix()):
                reader = csv_reader_skipping_comments(
                    template.read_text(encoding="utf-8"))
                self.assertIsNotNone(reader.fieldnames)
                first = (reader.fieldnames or [""])[0]
                self.assertFalse(
                    first.lstrip().startswith("#"),
                    "a comment line became the header row",
                )

    def test_the_parts_template_header_is_right(self) -> None:
        findings = check_parts_table(
            _REPO, _REPO / "templates/parts-library/bom/parts.csv")
        self.assertFalse([f for f in findings if not f.warning],
                         [f.message for f in findings])


if __name__ == "__main__":
    unittest.main()
