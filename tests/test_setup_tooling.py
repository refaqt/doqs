"""Tests for the tooling-submodule wiring (no git, no network).

These guard two rules that are easy to undo by accident:

* doqs marks its own `.agents` submodule `update = none`, so a machine repo
  that mounts doqs at `doqs/` does not get a second copy of the agent kit at
  `doqs/.agents/` and the `doqs` gitlink does not go dirty.
* The bootstrap helper never combines `--recursive` with `--remote`. That form
  reaches `doqs/.agents` and also un-pins extracted modules under `modules/`,
  which carry no `branch` and so track their remote default branch.
"""
from __future__ import annotations

import configparser
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_HELPERS = _REPO / "templates" / "setup-tooling"


class TestAgentsSubmodule(unittest.TestCase):
    def test_agents_is_not_checked_out_by_consumers(self):
        parser = configparser.ConfigParser()
        parser.read_string(
            (_REPO / ".gitmodules").read_text(encoding="utf-8").replace("\t", "")
        )
        section = 'submodule ".agents"'
        self.assertIn(section, parser.sections())
        self.assertEqual(parser[section]["path"], ".agents")
        self.assertEqual(parser[section]["branch"], "main")
        self.assertEqual(
            parser[section]["update"],
            "none",
            "`update = none` keeps doqs/.agents out of machine repos",
        )


class TestSetupToolingHelpers(unittest.TestCase):
    """The helper text doqs ships to machine repos."""

    def _helpers(self):
        for name in ("setup-tooling.sh", "setup-tooling.bat"):
            path = _HELPERS / name
            self.assertTrue(path.is_file(), f"{name} is missing")
            yield name, path.read_text(encoding="utf-8")

    def test_no_recursive_remote_in_one_command(self):
        for name, text in self._helpers():
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith(("#", "REM ")):
                    continue
                with self.subTest(helper=name, line=stripped):
                    self.assertFalse(
                        "--recursive" in stripped and "--remote" in stripped,
                        "--recursive with --remote reaches doqs/.agents and "
                        "un-pins modules/",
                    )

    def test_pins_first_then_tracks_tooling_submodules(self):
        for name, text in self._helpers():
            with self.subTest(helper=name):
                self.assertIn("git submodule update --init --recursive", text)
                self.assertIn("git submodule update --remote -- doqs .agents", text)
                self.assertLess(
                    text.index("git submodule update --init --recursive"),
                    text.index("git submodule update --remote -- doqs .agents"),
                    "check out recorded pins before tracking main",
                )

    def test_spdx_header_kept(self):
        for name, text in self._helpers():
            with self.subTest(helper=name):
                self.assertIn("SPDX-License-Identifier: GPL-3.0-or-later", text)


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class TestCheckFlag(unittest.TestCase):
    """`--check` only reads the two marker files. It changes nothing."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-setup-check-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.helper = self._tmp / "setup-tooling.sh"
        shutil.copyfile(_HELPERS / "setup-tooling.sh", self.helper)

    def run_check(self) -> subprocess.CompletedProcess:
        # No git repository here: if --check ran a git command, it would fail.
        return subprocess.run(["bash", str(self.helper), "--check"], cwd=self._tmp,
                              capture_output=True, text=True, timeout=60)

    def test_empty_folders_fail_and_name_the_fix(self):
        (self._tmp / ".agents").mkdir()
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL  .agents/rules/core.md is missing", result.stdout)
        self.assertIn("bash setup-tooling.sh", result.stdout)
        self.assertEqual(sorted(p.name for p in self._tmp.iterdir()), [".agents", "setup-tooling.sh"])

    def test_filled_folders_pass(self):
        for marker in (".agents/rules/core.md", "doqs/scripts/validate_all.py"):
            (self._tmp / marker).parent.mkdir(parents=True)
            (self._tmp / marker).write_text("x\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("FAIL", result.stdout)

    def test_the_windows_helper_has_the_flag_too(self):
        self.assertIn('"%~1"=="--check"', (_HELPERS / "setup-tooling.bat").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
