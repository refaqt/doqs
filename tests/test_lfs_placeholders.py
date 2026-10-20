"""A clone without Git LFS content warns about CAD files. It does not fail.

A cloud session clones without `git lfs pull`, to save LFS bandwidth. Each CAD
file is then a small text placeholder, so its checksum can never match. The
checks used to fail with messages that blamed a GUI save or a brand revision.
Now they skip the placeholder and say so in one line. CI runs `git lfs pull`
first, so it still checks the real files.
"""
from __future__ import annotations

import json
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

from cad_rules import (  # noqa: E402
    FINGERPRINT_SCHEMA,
    file_digest,
    fingerprint_path,
    is_lfs_pointer,
    lfs_placeholder_warning,
    write_fingerprint,
)
from naming_rules import forget_library_roots  # noqa: E402
from validate_cad import lfs_placeholders, validate_document  # noqa: E402
from validate_variants import check_all  # noqa: E402

POINTER = _REPO / "tests" / "fixtures" / "lfs-placeholder" / "pointer.txt"
LIBRARY = _REPO / "tests" / "fixtures" / "parts-library"
FAMILY = "modules/hiwin/modules/hgr-rail"
OWN = f"{FAMILY}/cad/own"
PN = "HGR20R1000"


def make_placeholder(path: Path) -> None:
    """Put the placeholder fixture where a CAD file was, as a clone without LFS does."""
    shutil.copyfile(POINTER, path)


class TempDir(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)


class TestRecognisePlaceholder(TempDir):
    def test_the_fixture_is_a_placeholder(self) -> None:
        self.assertTrue(is_lfs_pointer(POINTER))

    def test_a_real_file_is_not(self) -> None:
        step = LIBRARY / FAMILY / "cad/original/HGR20R500.step"
        self.assertFalse(is_lfs_pointer(step))

    def test_a_large_file_that_starts_the_same_is_not(self) -> None:
        """The LFS specification keeps placeholders below 1024 bytes."""
        big = self.tmp / "big.step"
        big.write_bytes(POINTER.read_bytes() + b"x" * 2000)
        self.assertFalse(is_lfs_pointer(big))

    def test_a_missing_file_is_not(self) -> None:
        self.assertFalse(is_lfs_pointer(self.tmp / "absent.FCStd"))


class TestWarningText(unittest.TestCase):
    def test_one_placeholder_is_named(self) -> None:
        text = lfs_placeholder_warning(["a/rail.FCStd"], "checksum")
        self.assertEqual(
            text,
            "a/rail.FCStd is a Git LFS placeholder, so its checksum was not "
            "checked. CI checks it after git lfs pull.",
        )

    def test_many_placeholders_make_one_short_line(self) -> None:
        paths = [f"cad/part{i}.step" for i in range(8)]
        text = lfs_placeholder_warning(paths, "checksum")
        self.assertNotIn("\n", text)
        self.assertIn("8 files are Git LFS placeholders", text)
        self.assertIn("cad/part0.step, cad/part1.step, cad/part2.step and 5 more", text)
        self.assertNotIn("cad/part7.step", text)


class TestFingerprintCheck(TempDir):
    """validate_cad.py: a placeholder .FCStd is not "saved again after its build"."""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "machine"
        cad = self.root / "rail" / "cad"
        cad.mkdir(parents=True)
        self.fcstd = cad / "rail.FCStd"
        self.fcstd.write_bytes(b"pretend-fcstd-v1\n")
        self.export = cad / "rail.step"
        self.export.write_bytes(b"ISO-10303-21;\n")
        write_fingerprint(fingerprint_path(self.fcstd), {
            "schema": FINGERPRINT_SCHEMA,
            "document": "rail",
            "saved": True,
            "sources": {
                "rail.FCStd": file_digest(self.fcstd),
                "rail.step": file_digest(self.export),
            },
            "params": {},
            "objects": {"Pad": {"volume": 1.0}},
            "errors": [],
        })

    def test_a_placeholder_document_does_not_fail(self) -> None:
        make_placeholder(self.fcstd)
        self.assertEqual(validate_document(self.fcstd, self.root), [])
        self.assertEqual(lfs_placeholders(self.fcstd, self.root), ["rail/cad/rail.FCStd"])

    def test_a_placeholder_export_does_not_fail(self) -> None:
        make_placeholder(self.export)
        self.assertEqual(validate_document(self.fcstd, self.root), [])
        self.assertEqual(lfs_placeholders(self.fcstd, self.root), ["rail/cad/rail.step"])

    def test_a_real_edit_still_fails(self) -> None:
        self.fcstd.write_bytes(b"pretend-fcstd-v2-EDITED\n")
        errors = validate_document(self.fcstd, self.root)
        self.assertTrue(any("changed since its fingerprint" in e for e in errors), errors)
        self.assertEqual(lfs_placeholders(self.fcstd, self.root), [])


class LibraryCopy(TempDir):
    def setUp(self) -> None:
        super().setUp()
        forget_library_roots()
        self.root = self.tmp / "stoq"
        shutil.copytree(LIBRARY, self.root)
        self.family = self.root / FAMILY


class TestChecksumCheck(LibraryCopy):
    """validate_variants.py: a placeholder is not a file "the brand changed"."""

    def test_a_placeholder_warns_and_does_not_fail(self) -> None:
        make_placeholder(self.family / "cad/original/HGR20R500.step")
        errors, warnings = check_all(self.root)
        self.assertEqual([f"{f.path}: {f.message}" for f in errors], [])
        lfs = [w.message for w in warnings if "Git LFS placeholder" in w.message]
        self.assertEqual(lfs, [
            f"{FAMILY}/cad/original/HGR20R500.step is a Git LFS placeholder, so "
            "its checksum was not checked. CI checks it after git lfs pull.",
        ])

    def test_many_placeholders_make_one_warning(self) -> None:
        for name in ("HGR20R300.step", "HGR20R500.step"):
            make_placeholder(self.family / "cad/original" / name)
        errors, warnings = check_all(self.root)
        self.assertEqual([f"{f.path}: {f.message}" for f in errors], [])
        lfs = [w.message for w in warnings if "Git LFS placeholder" in w.message]
        self.assertEqual(len(lfs), 1, lfs)
        self.assertIn("2 files are Git LFS placeholders", lfs[0])

    def test_a_real_change_still_fails(self) -> None:
        step = self.family / "cad/original/HGR20R500.step"
        step.write_text(step.read_text() + "\n# quietly revised\n")
        errors, _ = check_all(self.root)
        self.assertTrue(any("no longer matches its recorded checksum" in f.message
                            for f in errors))


class TestValidateCadCommand(LibraryCopy):
    """The whole command, as `doqs check` runs it."""

    def validate_cad(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(_SCRIPTS / "validate_cad.py"), "--root", str(self.root)],
            capture_output=True, text=True)

    def test_a_placeholder_own_model_passes_with_one_warning(self) -> None:
        make_placeholder(self.root / OWN / f"{PN}.FCStd")
        result = self.validate_cad()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("FAIL", result.stdout)
        self.assertNotIn(f"ok    {OWN}/{PN}.FCStd", result.stdout)
        warns = [line for line in result.stdout.splitlines()
                 if line.startswith("WARN") and "Git LFS placeholder" in line]
        self.assertEqual(len(warns), 1, result.stdout)
        self.assertIn(f"{OWN}/{PN}.FCStd", warns[0])

    def test_the_fingerprint_still_has_to_exist(self) -> None:
        """A placeholder skips the digest only, not the rest of the check."""
        make_placeholder(self.root / OWN / f"{PN}.FCStd")
        fp = self.root / OWN / f"{PN}.fingerprint.json"
        data = json.loads(fp.read_text(encoding="utf-8"))
        data["saved"] = False
        fp.write_text(json.dumps(data), encoding="utf-8")
        result = self.validate_cad()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("unsaved document", result.stdout)


if __name__ == "__main__":
    unittest.main()
