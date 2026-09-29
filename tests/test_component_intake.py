"""Unit tests for taking a supplier's files into a parts library.

Each kind of file (cad, documentation) gets a dated decision approved by a
named person. Files we may not share never enter git. Models we draw ourselves
live under cad/own/ with a check list. See
docs/decisions/2026-09-29_component-intake.md.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from license_rules import expected_library_stub, mapped_library_dirs  # noqa: E402
from restore_private import sync  # noqa: E402
from validate_okh import validate  # noqa: E402
from validate_variants import check_all  # noqa: E402

LIBRARY = _REPO / "tests" / "fixtures" / "parts-library"

REVIEW = """
[[terms-review]]
kind = "{kind}"
decision = "{decision}"
basis = "{basis}"
source = "https://example.com/terms"
evidence = "evidence/x.pdf"
reviewer = "Test Reviewer"
reviewed = {date}
"""


class LibraryCopy(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        shutil.copytree(LIBRARY, self.root)
        self.brand = self.root / "modules/hiwin/okh.toml"
        self.family = self.root / "modules/hiwin/modules/hgr-rail"
        self.thk = self.root / "modules/thk/modules/shs-rail"

    def errors(self) -> list[str]:
        return [f"{f.path}: {f.message}" for f in check_all(self.root)[0]]

    def warnings(self) -> list[str]:
        return [f"{f.path}: {f.message}" for f in check_all(self.root)[1]]

    def okh_errors(self) -> list[str]:
        return validate(self.brand, root=self.root)

    def strip_reviews(self) -> None:
        text = self.brand.read_text()
        self.brand.write_text(text[: text.index("# One dated decision")])

    def add_review(self, kind: str, decision: str, basis: str = "terms",
                   date: str = "2026-09-20") -> None:
        self.brand.write_text(self.brand.read_text() + REVIEW.format(
            kind=kind, decision=decision, basis=basis, date=date))


class TestReviews(LibraryCopy):
    def test_the_fixture_passes(self) -> None:
        self.assertEqual(self.errors(), [])
        self.assertEqual(self.okh_errors(), [])

    def test_a_shared_file_needs_a_review(self) -> None:
        self.strip_reviews()
        errors = self.errors()
        self.assertTrue(any("no [[terms-review]] for 'cad'" in e for e in errors), errors)
        self.assertTrue(any("for 'documentation'" in e for e in errors), errors)

    def test_each_file_is_reported_once(self) -> None:
        """A catalogue names the same datasheet on every row."""
        self.strip_reviews()
        sheet = [e for e in self.errors() if "hgr-series.pdf is shared" in e]
        self.assertEqual(len(sheet), 1, sheet)

    def test_the_newest_review_counts(self) -> None:
        self.add_review("documentation", "internal", date="2026-09-25")
        errors = self.errors()
        self.assertTrue(any("says 'internal'" in e for e in errors), errors)

    def test_an_older_review_does_not_count(self) -> None:
        self.add_review("documentation", "internal", date="2026-01-01")
        self.assertEqual(self.errors(), [])

    def test_a_review_needs_a_named_person(self) -> None:
        self.brand.write_text(self.brand.read_text().replace(
            'reviewer = "Test Reviewer"', 'reviewer = ""', 1))
        self.assertTrue(any("named person" in e for e in self.okh_errors()))

    def test_a_review_needs_a_date(self) -> None:
        self.brand.write_text(self.brand.read_text().replace(
            "reviewed = 2026-09-18", 'reviewed = "soon"', 1))
        self.assertTrue(any("must be a date" in e for e in self.okh_errors()))

    def test_a_permission_needs_its_evidence(self) -> None:
        self.brand.write_text(self.brand.read_text() + """
[[terms-review]]
kind = "cad"
decision = "public"
basis = "permission"
reviewer = "Test Reviewer"
reviewed = 2026-09-20
""")
        self.assertTrue(any("evidence must name" in e for e in self.okh_errors()))

    def test_unknown_values_are_refused(self) -> None:
        self.add_review("drawings", "maybe", basis="hope")
        errors = self.okh_errors()
        for word in ("kind must be", "decision must be", "basis must be"):
            self.assertTrue(any(word in e for e in errors), errors)

    def test_public_without_a_basis_only_warns(self) -> None:
        """The honest record of a decision nobody could back up yet."""
        self.add_review("cad", "public", basis="none", date="2026-09-20")
        self.assertEqual(self.errors(), [])
        self.assertTrue(any("basis = 'none'" in w for w in self.warnings()))

    def test_redistribute_must_agree_with_the_cad_review(self) -> None:
        self.add_review("cad", "customers", date="2026-09-25")
        self.assertTrue(any("disagrees" in e for e in self.okh_errors()))

    def test_a_fetch_only_brand_needs_no_review(self) -> None:
        """Storing the link needs no decision at all."""
        thk = self.root / "modules/thk/okh.toml"
        text = thk.read_text()
        thk.write_text(text[: text.index("[[terms-review]]")])
        self.assertEqual(self.errors(), [])


class TestPrivateFiles(LibraryCopy):
    def test_a_missing_private_file_only_warns(self) -> None:
        errors, warnings = check_all(self.root)
        self.assertEqual([f.message for f in errors], [])

    def test_an_unknown_term_is_refused(self) -> None:
        index = self.thk / "vendor-index.csv"
        index.write_text(index.read_text().replace(",private,", ",secret,"))
        self.assertTrue(any("terms must be one of" in e for e in self.errors()))

    def _git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.root), *args], check=True,
                       capture_output=True)

    def _init_git(self) -> None:
        self._git("init", "-q")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "T")

    def test_a_tracked_private_file_fails(self) -> None:
        """History is never rewritten, so a leak could not be taken back."""
        self._init_git()
        manual = self.thk / "docs/manuals/shs-manual.pdf"
        manual.parent.mkdir(parents=True)
        manual.write_text("their manual")
        self._git("add", "-A")
        errors = self.errors()
        self.assertTrue(any("git tracks it" in e for e in errors), errors)

    def test_an_untracked_private_file_is_fine(self) -> None:
        self._init_git()
        self._git("add", "-A")
        manual = self.thk / "docs/manuals/shs-manual.pdf"
        manual.parent.mkdir(parents=True)
        manual.write_text("their manual")
        self.assertEqual(self.errors(), [])

    def test_a_tracked_fetch_only_file_fails_too(self) -> None:
        self._init_git()
        model = self.thk / "cad/parts/SHS20R300.FCStd"
        model.parent.mkdir(parents=True, exist_ok=True)
        model.write_text("their model")
        self._git("add", "-A")
        self.assertTrue(any("fetch-only, but git tracks it" in e for e in self.errors()))


class TestOwnModels(LibraryCopy):
    def setUp(self) -> None:
        super().setUp()
        self.table = self.family / "bom/parts.csv"
        self.checks = self.family / "cad/own/HGR20R1000.checks.csv"

    def test_an_own_model_must_sit_under_cad_own(self) -> None:
        self.table.write_text(self.table.read_text().replace(
            "cad/own/HGR20R1000.FCStd", "cad/parts/HGR20R1000.FCStd"))
        self.assertTrue(any("under cad/own/" in e for e in self.errors()))

    def test_an_own_model_is_always_committed(self) -> None:
        (self.family / "cad/own/HGR20R1000.FCStd").unlink()
        self.assertTrue(any("always committed" in e for e in self.errors()))

    def test_an_own_model_needs_its_check_list(self) -> None:
        self.checks.unlink()
        self.assertTrue(any("check list not found" in e for e in self.errors()))

    def test_a_failed_dimension_fails(self) -> None:
        self.checks.write_text(self.checks.read_text().replace(",pass,", ",fail,", 1))
        self.assertTrue(any("never from the brand's model" in e for e in self.errors()))

    def test_a_list_that_checks_nothing_fails(self) -> None:
        lines = self.checks.read_text().splitlines()
        header = [line for line in lines if line.startswith("dimension,")]
        self.checks.write_text("\n".join(header) + "\n")
        self.assertTrue(any("no dimensions" in e for e in self.errors()))

    def test_an_unconfirmed_dimension_only_warns(self) -> None:
        self.checks.write_text(self.checks.read_text().replace(",pass,", ",not-confirmed,", 1))
        self.assertEqual(self.errors(), [])
        self.assertTrue(any("not confirmed" in w for w in self.warnings()))

    def test_every_dimension_names_its_page(self) -> None:
        self.checks.write_text(self.checks.read_text().replace(",12,", ",,", 1))
        self.assertTrue(any("page is empty" in e for e in self.errors()))

    def test_the_list_holds_no_extra_columns(self) -> None:
        """No column for a value read from the brand's model."""
        self.checks.write_text(self.checks.read_text().replace(
            "checked_utc", "checked_utc,step_value"))
        self.assertTrue(any("header must be exactly" in e for e in self.errors()))

    def test_own_models_carry_our_licence(self) -> None:
        kinds = {d.relative_to(self.root).as_posix(): k
                 for d, k in mapped_library_dirs(self.root)}
        self.assertEqual(kinds["modules/hiwin/modules/hgr-rail/cad"], "vendor")
        self.assertEqual(kinds["modules/hiwin/modules/hgr-rail/cad/own"], "own")
        stub = expected_library_stub("own")
        self.assertIn("CC BY-SA", stub)
        self.assertNotIn("Third-party", stub)

    def test_an_own_model_needs_no_brand_review(self) -> None:
        """It is ours: no brand decides whether we may share it."""
        self.strip_reviews()
        self.assertFalse(any("HGR20R1000" in e for e in self.errors()))


class TestPrivateSync(LibraryCopy):
    def setUp(self) -> None:
        super().setUp()
        self.private = Path(self._tmp.name) / "private"
        self.rel = "modules/thk/modules/shs-rail/docs/manuals/shs-manual.pdf"
        source = self.private / self.rel
        source.parent.mkdir(parents=True)
        source.write_text("their manual")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        index = self.thk / "vendor-index.csv"
        index.write_text(index.read_text().replace(
            "shs-manual.pdf,,,", f"shs-manual.pdf,12,{digest},"))

    def test_it_copies_a_private_file_into_place(self) -> None:
        done, missing, errors = sync(self.root, self.private, check=False)
        self.assertEqual(errors, [])
        self.assertTrue((self.root / self.rel).is_file())
        self.assertTrue(any("copied" in d for d in done))

    def test_check_mode_changes_nothing(self) -> None:
        sync(self.root, self.private, check=True)
        self.assertFalse((self.root / self.rel).exists())

    def test_a_changed_private_copy_is_refused(self) -> None:
        (self.private / self.rel).write_text("someone edited it")
        done, missing, errors = sync(self.root, self.private, check=False)
        self.assertTrue(errors)
        self.assertFalse((self.root / self.rel).exists())

    def test_files_nobody_has_are_reported(self) -> None:
        done, missing, errors = sync(self.root, self.private, check=False)
        self.assertIn("modules/thk/modules/shs-rail/cad/parts/SHS20R300.FCStd", missing)

    def test_it_never_writes_to_the_private_copy(self) -> None:
        before = sorted(p.as_posix() for p in self.private.rglob("*"))
        sync(self.root, self.private, check=False)
        self.assertEqual(sorted(p.as_posix() for p in self.private.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
