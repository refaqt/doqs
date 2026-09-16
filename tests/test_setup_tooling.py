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


if __name__ == "__main__":
    unittest.main()
