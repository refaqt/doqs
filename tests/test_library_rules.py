"""Tests for the row and checksum helpers of a parts library."""
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

import library_rules as lr  # noqa: E402
from naming_rules import PARTS_TABLE_HEADERS  # noqa: E402
from validate_variants import VENDOR_INDEX_HEADERS  # noqa: E402


class _Temp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="doqs-lib-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


class TestTerms(unittest.TestCase):
    def test_terms_follow_the_decision_and_the_library(self):
        self.assertEqual(lr.terms_for("public", has_public_url=True, private_library=False), "redistributable")
        self.assertEqual(lr.terms_for("public", has_public_url=False, private_library=True), "redistributable")
        self.assertEqual(lr.terms_for("customers", has_public_url=True, private_library=False), "fetch-only")
        self.assertEqual(lr.terms_for("customers", has_public_url=False, private_library=False), "private")
        self.assertEqual(lr.terms_for("internal", has_public_url=True, private_library=True), "internal")
        self.assertTrue(lr.is_committed("redistributable"))
        self.assertTrue(lr.is_committed("internal"))
        self.assertFalse(lr.is_committed("fetch-only"))


class TestRows(_Temp):
    def test_vendor_row_records_checksum_size_and_time(self):
        step = self.tmp / "X.step"
        step.write_bytes(b"ISO-10303-21;\n")
        row = lr.vendor_row("hiwin", "X", "cad/original/X.step", step,
                            "https://hiwin.example/X", "fetch-only", retrieved_utc="2026-10-07T10:00:00Z")
        digest, size = lr.sha256_and_size(step)
        self.assertEqual(row["sha256"], digest)
        self.assertEqual(row["bytes"], str(size))
        self.assertEqual(tuple(row), VENDOR_INDEX_HEADERS)
        self.assertRegex(lr.utc_now(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        with self.assertRaises(lr.LibraryError):
            lr.vendor_row("hiwin", "X", "a", step, "", "shared")

    def test_parts_row_has_the_table_header(self):
        row = lr.parts_row("X", "A block", spec="size 15", unit_mass_g=140, terms="redistributable")
        self.assertEqual(tuple(row), PARTS_TABLE_HEADERS)
        self.assertEqual(row["unit_mass_g"], "140")
        with self.assertRaises(lr.LibraryError):
            lr.parts_row("X", "A block", terms="nope")

    def test_append_creates_the_table_from_the_template_and_refuses_a_rewrite(self):
        table = self.tmp / "bom" / "parts.csv"
        row = lr.parts_row("X", "A block", terms="fetch-only")
        self.assertTrue(lr.append_row(table, PARTS_TABLE_HEADERS, row, "pn",
                                      template=lr.template_text("bom/parts.csv")))
        text = table.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# One row per ORDERABLE PART NUMBER."))
        self.assertIn("\npn,description,spec,unit_mass_g,cad,datasheet,terms,revision,status,notes\n", text)
        self.assertNotIn("HGR20R300", text)  # the template's example row is not copied
        self.assertTrue(text.endswith("X,A block,,,,,fetch-only,A,active,\n"))
        # The same row again: nothing happens.
        self.assertFalse(lr.append_row(table, PARTS_TABLE_HEADERS, row, "pn"))
        # The same key, other words: refused.
        with self.assertRaises(lr.LibraryError):
            lr.append_row(table, PARTS_TABLE_HEADERS, lr.parts_row("X", "Other"), "pn")
        # A second part: appended after the first, comments kept.
        lr.append_row(table, PARTS_TABLE_HEADERS, lr.parts_row("Y", "Another"), "pn")
        headers, rows = lr.read_rows(table)
        self.assertEqual(headers, PARTS_TABLE_HEADERS)
        self.assertEqual([r["pn"] for r in rows], ["X", "Y"])

    def test_vendor_index_allows_several_files_per_part(self):
        index = self.tmp / "vendor-index.csv"
        f = self.tmp / "f.bin"
        f.write_bytes(b"1")
        base = dict(supplier="hiwin", pn="X", source_url="", terms="fetch-only", retrieved_utc="t")
        a = lr.vendor_row(relpath="cad/original/X.step", file=f, **base)
        b = lr.vendor_row(relpath="docs/datasheets/X.pdf", file=f, **base)
        self.assertTrue(lr.append_row(index, VENDOR_INDEX_HEADERS, a, "pn"))
        self.assertTrue(lr.append_row(index, VENDOR_INDEX_HEADERS, b, "pn"))
        self.assertFalse(lr.append_row(index, VENDOR_INDEX_HEADERS, b, "pn"))
        changed = dict(a, sha256="0" * 64)
        with self.assertRaises(lr.LibraryError):
            lr.append_row(index, VENDOR_INDEX_HEADERS, changed, "pn")

    def test_a_wrong_header_is_refused(self):
        table = self.tmp / "parts.csv"
        table.write_text("pn,other\nX,1\n", encoding="utf-8")
        with self.assertRaises(lr.LibraryError):
            lr.append_row(table, PARTS_TABLE_HEADERS, lr.parts_row("Y", "d"), "pn")

    def test_set_cell_changes_one_cell_and_keeps_comments(self):
        table = self.tmp / "parts.csv"
        table.write_text(
            "# comment\npn,description,spec,unit_mass_g,cad,datasheet,terms,revision,status,notes\n"
            "X,\"A, block\",,,,,fetch-only,A,active,\nY,b,,,,,fetch-only,A,active,\n",
            encoding="utf-8")
        self.assertTrue(lr.set_cell(table, "pn", "X", "cad", "cad/parts/X.FCStd"))
        text = table.read_text(encoding="utf-8")
        self.assertEqual(text, "# comment\npn,description,spec,unit_mass_g,cad,datasheet,terms,revision,status,notes\n"
                               "X,\"A, block\",,,cad/parts/X.FCStd,,fetch-only,A,active,\nY,b,,,,,fetch-only,A,active,\n")
        self.assertFalse(lr.set_cell(table, "pn", "X", "cad", "cad/parts/X.FCStd"))
        with self.assertRaises(lr.LibraryError):
            lr.set_cell(table, "pn", "X", "terms", "private")
        with self.assertRaises(lr.LibraryError):
            lr.set_cell(table, "pn", "X", "nope", "1")


class TestMirror(_Temp):
    def test_mirror_diff_names_each_side(self):
        pub, priv = self.tmp / "stoq", self.tmp / "stoq-private"
        fam = "modules/hiwin/modules/hgl-block"
        for root in (pub, priv):
            (root / fam / "cad" / "original").mkdir(parents=True)
            (root / fam / "okh.toml").write_text('name = "x"\n', encoding="utf-8")
            (root / fam / "vendor-index.csv").write_text(
                ",".join(VENDOR_INDEX_HEADERS) + "\n"
                "hiwin,X,cad/original/X.step,1,abc,,fetch-only,t\n"
                "hiwin,X,docs/datasheets/X.pdf,1,abc,,fetch-only,t\n", encoding="utf-8")
        (priv / fam / "cad" / "original" / "X.step").write_bytes(b"step")
        (pub / fam / "cad" / "original" / "X.step").write_bytes(b"step")
        (priv / fam / "docs" / "datasheets").mkdir(parents=True)
        (priv / fam / "docs" / "datasheets" / "X.pdf").write_bytes(b"pdf")
        (pub / fam / "bom").mkdir()
        (pub / fam / "bom" / "parts.csv").write_text("pn\n", encoding="utf-8")
        (priv / fam / "okh.toml").write_text('name = "y"\n', encoding="utf-8")
        self.assertEqual(lr.mirror_diff(pub, priv), [
            (f"{fam}/bom/parts.csv", "only-public"),
            (f"{fam}/cad/original/X.step", "same"),
            (f"{fam}/docs/datasheets/X.pdf", "only-private"),
            (f"{fam}/okh.toml", "differs"),
            (f"{fam}/vendor-index.csv", "same"),
        ])


if __name__ == "__main__":
    unittest.main()
