"""Tests for split-licence apply/check and the minimal-machine fixture."""
from __future__ import annotations

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

from license_rules import (  # noqa: E402
    HARDWARE_LICENSE,
    apply_repo,
    apply_tools_repo,
    check_repo,
    check_tools_repo,
    is_doqs_tools_repo,
)

_FIXTURE = _REPO / "tests" / "fixtures" / "minimal-machine"


class TestLicenseFixture(unittest.TestCase):
    def _run(self, script: str, *extra: str, root: Path | None = None) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            str(_SCRIPTS / script),
            "--root",
            str(root or _FIXTURE),
            *extra,
        ]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO)

    def test_validate_licenses_fixture(self):
        result = self._run("validate_licenses.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_apply_check_fixture(self):
        result = self._run("apply_licenses.py", "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validate_okh_fixture(self):
        result = self._run("validate_okh.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validate_all_includes_licenses(self):
        result = self._run("validate_all.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("validate_licenses.py", result.stdout)


class TestLicenseApplyAndCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-license-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = self._tmp / "machine"
        shutil.copytree(_FIXTURE, self.root)

    def _run(self, script: str, *extra: str) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            str(_SCRIPTS / script),
            "--root",
            str(self.root),
            *extra,
        ]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO)

    def test_missing_stub_fails_then_apply_repairs(self):
        stub = self.root / "modules" / "LICENSE"
        stub.unlink()
        check = self._run("apply_licenses.py", "--check")
        self.assertNotEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("modules/LICENSE", check.stdout)

        apply = self._run("apply_licenses.py")
        self.assertEqual(apply.returncode, 0, apply.stdout + apply.stderr)
        self.assertTrue(stub.is_file())

        check2 = self._run("apply_licenses.py", "--check")
        self.assertEqual(check2.returncode, 0, check2.stdout + check2.stderr)
        validate = self._run("validate_licenses.py")
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

    def test_missing_readme_fails_validate_not_apply_check(self):
        (self.root / "README.md").unlink()
        check = self._run("apply_licenses.py", "--check")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        validate = self._run("validate_licenses.py")
        self.assertNotEqual(validate.returncode, 0)
        self.assertIn("README.md", validate.stdout)

    def test_wrong_okh_license_fails(self):
        okh = self.root / "okh.toml"
        text = okh.read_text(encoding="utf-8").replace(
            f'license = "{HARDWARE_LICENSE}"', 'license = "MIT"'
        )
        okh.write_text(text, encoding="utf-8")
        okh_result = self._run("validate_okh.py")
        self.assertNotEqual(okh_result.returncode, 0)
        self.assertIn(HARDWARE_LICENSE, okh_result.stdout)
        lic_result = self._run("validate_licenses.py")
        self.assertNotEqual(lic_result.returncode, 0)
        self.assertIn(HARDWARE_LICENSE, lic_result.stdout)

    def test_extra_exclusion_paragraph_is_kept(self):
        docs = self.root / "docs"
        docs.mkdir()
        custom = (
            "Files in this directory are documentation and media (text, images, drawings),\n"
            "licensed under Creative Commons Attribution-ShareAlike 4.0 International\n"
            "(CC BY-SA 4.0).\n\n"
            "Full text: [`/LICENSES/CC-BY-SA-4.0.txt`](../LICENSES/CC-BY-SA-4.0.txt)\n\n"
            "**Excluded**: vendor datasheets remain under their original copyright.\n"
        )
        (docs / "LICENSE").write_text(custom, encoding="utf-8")
        apply_repo(self.root)
        kept = (docs / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("vendor datasheets", kept)
        errors = check_repo(self.root)
        self.assertEqual(errors, [])

    def test_apply_recurses_into_extracted_module_not_doqs(self):
        extracted = self.root / "modules" / "spindle"
        extracted.mkdir(parents=True)
        (extracted / "okh.toml").write_text(
            "\n".join(
                [
                    'okhv = "OKH-LOSHv1.0"',
                    'name = "Spindle"',
                    'repo = "https://example.com/spindle"',
                    'version = "0.1.0"',
                    f'license = "{HARDWARE_LICENSE}"',
                    'licensor = "DOQS Tests"',
                    'function = "Extracted submodule fixture"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (extracted / "cad").mkdir()
        (extracted / "README.md").write_text(
            "# Spindle\n\n## Licence\n\nSee [LICENSE](LICENSE).\n",
            encoding="utf-8",
        )
        doqs = self.root / "doqs"
        doqs.mkdir()
        agents = self.root / ".agents"
        agents.mkdir()
        (self.root / ".gitmodules").write_text(
            "[submodule \"modules/spindle\"]\n"
            "\tpath = modules/spindle\n"
            "\turl = https://example.com/spindle.git\n"
            "[submodule \"doqs\"]\n"
            "\tpath = doqs\n"
            "\turl = https://github.com/refaqt/doqs.git\n"
            "[submodule \".agents\"]\n"
            "\tpath = .agents\n"
            "\turl = https://github.com/refaqt/refaqt-agents.git\n",
            encoding="utf-8",
        )

        apply = self._run("apply_licenses.py")
        self.assertEqual(apply.returncode, 0, apply.stdout + apply.stderr)
        self.assertTrue((extracted / "LICENSE").is_file())
        self.assertTrue((extracted / "cad" / "LICENSE").is_file())
        self.assertTrue((extracted / "LICENSES" / "GPL-3.0.txt").is_file())
        self.assertFalse((doqs / "LICENSE").exists())
        self.assertFalse((agents / "LICENSE").exists())

        validate = self._run("validate_licenses.py")
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
        self.assertIn("modules/spindle", validate.stdout)


class TestToolsRepoLicense(unittest.TestCase):
    def test_doqs_root_is_tools_repo(self):
        self.assertTrue(is_doqs_tools_repo(_REPO))
        self.assertFalse(is_doqs_tools_repo(_FIXTURE))

    def test_validate_licenses_tools_root(self):
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "validate_licenses.py"),
                "--root",
                str(_REPO),
            ],
            capture_output=True,
            text=True,
            cwd=_REPO,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("tools", result.stdout)

    def test_apply_check_tools_root(self):
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "apply_licenses.py"),
                "--check",
                "--root",
                str(_REPO),
            ],
            capture_output=True,
            text=True,
            cwd=_REPO,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("tools", result.stdout)

    def test_apply_tools_repo_does_not_write_cern_ohl(self):
        tmp = Path(tempfile.mkdtemp(prefix="doqs-tools-lic-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        root = tmp / "doqs"
        shutil.copytree(
            _REPO, root, ignore=shutil.ignore_patterns(".git", "__pycache__")
        )
        (root / "LICENSE").unlink()
        (root / "TRADEMARKS.md").unlink()
        shutil.rmtree(root / "LICENSES")
        for rel in (
            "scripts/LICENSE",
            "schemas/LICENSE",
            "tests/LICENSE",
            "docs/LICENSE",
            "data/LICENSE",
            "templates/LICENSE",
            "spec/LICENSE",
        ):
            (root / rel).unlink()

        self.assertTrue(is_doqs_tools_repo(root))
        actions = apply_tools_repo(root)
        self.assertTrue(actions)
        errors = check_tools_repo(root)
        self.assertEqual(errors, [])
        self.assertTrue((root / "LICENSES" / "GPL-3.0.txt").is_file())
        self.assertTrue((root / "LICENSES" / "CC-BY-SA-4.0.txt").is_file())
        self.assertFalse((root / "LICENSES" / "CERN-OHL-S-2.0.txt").exists())
        overview = (root / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("GPL-3.0", overview)
        self.assertIn("CC BY-SA", overview)
        self.assertIn("not a hardware machine", overview.lower())


if __name__ == "__main__":
    unittest.main()
