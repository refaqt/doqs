"""Tests for the one entry point: `python doqs/doqs.py <command>`."""
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

import cli  # noqa: E402
import validate_all  # noqa: E402

_DOQS_PY = _REPO / "doqs.py"
_FIXTURE = _REPO / "tests" / "fixtures" / "minimal-machine"


def run_doqs(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_DOQS_PY), *args],
        capture_output=True, text=True, cwd=_REPO,
    )


class TestGateLists(unittest.TestCase):
    def test_validate_all_runs_exactly_the_seven_gates(self):
        # The contract a machine repo relies on: bumping the doqs pin must not
        # add gates to its CI. validate_all.py runs cli.GATES and nothing else.
        self.assertEqual(
            [name for name, _ in cli.GATES],
            [
                "validate_okh.py",
                "validate_licenses.py",
                "check_names.py",
                "check_links.py",
                "validate_build.py",
                "validate_variants.py",
                "validate_cad.py",
            ],
        )

    def test_check_is_the_gates_plus_the_staleness_checks(self):
        names = {name for name, _ in cli.GATES}
        extra = {name for name, _ in cli.STALENESS}
        self.assertTrue(names.isdisjoint(extra))
        self.assertEqual(extra, {"resolve_params.py", "resolve_instance.py", "apply_licenses.py"})

    def test_every_named_script_exists(self):
        for name, _ in cli.GATES + cli.STALENESS + cli.GENERATE:
            self.assertTrue((_SCRIPTS / name).is_file(), f"{name} is missing")
        for name in cli.PASSTHROUGH.values():
            self.assertTrue((_SCRIPTS / name).is_file(), f"{name} is missing")
        for name, _ in cli.FREECAD_ONLY:
            self.assertTrue((_SCRIPTS / name).is_file(), f"{name} is missing")

    def test_validate_all_still_has_its_own_entry_point(self):
        self.assertTrue(callable(validate_all.main))


class TestList(unittest.TestCase):
    def test_list_names_every_command_and_the_freecad_scripts(self):
        result = run_doqs("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("check", "generate", "setup", "syson", "export", "bom", "run", "list"):
            self.assertIn(command, result.stdout)
        # The three that can never be subcommands must be named, with the reason.
        for name, _ in cli.FREECAD_ONLY:
            self.assertIn(name, result.stdout)
        self.assertIn("FreeCAD", result.stdout)

    def test_no_arguments_prints_help_and_succeeds(self):
        result = run_doqs()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("doqs list", result.stdout)


class TestCheck(unittest.TestCase):
    def test_check_passes_on_a_clean_fixture(self):
        result = run_doqs("check", "--root", str(_FIXTURE))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all gates passed", result.stdout)

    def test_check_only_runs_one_gate(self):
        result = run_doqs("check", "--root", str(_FIXTURE), "--only", "validate_okh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("validate_okh.py", result.stdout)
        self.assertNotIn("validate_variants.py", result.stdout)

    def test_check_only_rejects_an_unknown_gate(self):
        result = run_doqs("check", "--root", str(_FIXTURE), "--only", "no-such-gate")
        self.assertEqual(result.returncode, 2)
        self.assertIn("doqs list", result.stderr)


class TestOneFailingGateDoesNotStopTheRest(unittest.TestCase):
    """A broken repository must still get a full report, not the first failure."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-cli-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = self._tmp / "machine"
        shutil.copytree(_FIXTURE, self.root)

    def test_a_bad_manifest_fails_check_but_the_later_gates_still_run(self):
        okh = self.root / "okh.toml"
        okh.write_text(okh.read_text(encoding="utf-8").replace("version", "verzion", 1), encoding="utf-8")

        result = run_doqs("check", "--root", str(self.root))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAILED", result.stdout)
        # The gate after the failing one, and the last staleness check, both ran.
        self.assertIn("validate_licenses.py", result.stdout)
        self.assertIn("apply_licenses.py", result.stdout)


class TestRun(unittest.TestCase):
    def test_run_reaches_any_script(self):
        result = run_doqs("run", "validate_okh", "--root", str(_FIXTURE))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_run_rejects_an_unknown_script(self):
        result = run_doqs("run", "no_such_script")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no script called", result.stderr)

    def test_run_needs_a_name(self):
        result = run_doqs("run")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
