"""Unit tests for DOQS naming rules and fixture validation."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

# Allow importing scripts package from repo
_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from naming_rules import (  # noqa: E402
    BOM_ID,
    OKH_VERSION,
    load_lexicon,
    validate_adapter_slug,
    validate_bom_id,
    validate_module_slug,
)

_FIXTURE = _REPO / "tests" / "fixtures" / "minimal-machine"


class TestRegexes(unittest.TestCase):
    def test_module_slug(self):
        self.assertTrue(validate_module_slug("x-axis"))
        self.assertTrue(validate_module_slug("x-axis-belt"))
        self.assertFalse(validate_module_slug("X-Axis"))
        self.assertFalse(validate_module_slug("x_axis"))

    def test_adapter_slug(self):
        self.assertTrue(validate_adapter_slug("foo-v1-to-v2"))
        self.assertTrue(validate_adapter_slug("spindle-mount-v1-to-v2"))
        self.assertFalse(validate_adapter_slug("foo-v1-v2"))

    def test_bom_id(self):
        ok, _ = validate_bom_id("MEC-001")
        self.assertTrue(ok)
        ok, err = validate_bom_id("SW-01")
        self.assertFalse(ok)
        self.assertIn("PREFIX-NNN", err or "")

    def test_okh_version(self):
        self.assertTrue(OKH_VERSION.match("1.2.0"))
        self.assertTrue(OKH_VERSION.match("0.1.0"))
        self.assertFalse(OKH_VERSION.match("v1.2.0"))

    def test_lexicon_loads(self):
        words = load_lexicon()
        self.assertIn("axis", words)
        self.assertIn("spindle", words)


class TestFixtureValidation(unittest.TestCase):
    def _run(self, script: str, *extra: str) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            str(_SCRIPTS / script),
            "--root",
            str(_FIXTURE),
            *extra,
        ]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO)

    def test_check_names_fixture(self):
        result = self._run("check_names.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validate_okh_fixture(self):
        result = self._run("validate_okh.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validate_okh_expected_version(self):
        result = self._run("validate_okh.py", "--expected-version", "0.1.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        bad = self._run("validate_okh.py", "--expected-version", "9.9.9")
        self.assertNotEqual(bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()
