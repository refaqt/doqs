"""Tests for geometric fingerprints and the agent-CAD guard (no FreeCAD needed)."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cad_rules import (  # noqa: E402
    DENIED_MCP_TOOLS,
    FINGERPRINT_SCHEMA,
    FingerprintError,
    compare_fingerprints,
    file_digest,
    fingerprint_path,
    load_fingerprint,
    missing_guard_rules,
    normalise,
    round_sig,
    write_fingerprint,
)
from validate_cad import validate_document, validate_guard  # noqa: E402


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


class TestFingerprintPath(unittest.TestCase):
    def test_derives_sibling_name(self):
        self.assertEqual(
            fingerprint_path(Path("m/cad/rail.FCStd")).name, "rail.fingerprint.json"
        )
        self.assertEqual(fingerprint_path(Path("m/cad/rail.FCStd")).parent.name, "cad")


if __name__ == "__main__":
    unittest.main()
