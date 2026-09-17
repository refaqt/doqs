"""Tests for the session-hook seed and the settings merge.

Two failures these cover, both of which used to be possible:

- A repository gets the hook file but nothing registers it, so the tooling
  submodules are never checked out and nothing says why.
- A repository that already has a settings file never receives the agent-CAD
  deny rules, because the installer only wrote that file when it was missing.
"""
from __future__ import annotations

import json
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cad_rules import hook_is_registered  # noqa: E402
from install_root_tools import (  # noqa: E402
    SETTINGS_DEST,
    SKIP_TEMPLATE_DIRS,
    TOOL_TEMPLATES,
    install_root_tools,
    install_settings,
    install_tools,
    iter_root_launchers,
    merge_settings,
)
from validate_cad import validate_hook_registration  # noqa: E402

_TEMPLATES = _REPO / "templates"
_HOOK_DEST = Path(".claude") / "hooks" / "session-start.sh"

_TEMPLATE_SETTINGS = json.loads(
    (_TEMPLATES / "agent-cad" / "claude-settings.json").read_text(encoding="utf-8")
)


class ConsumerRoot(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-hook-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = self._tmp / "machine"
        self.root.mkdir()
        (self.root / "setup-tooling.sh").write_text("#!/bin/sh\n", encoding="utf-8")


class TestHookInstall(ConsumerRoot):
    def test_the_hook_lands_in_claude_hooks_and_is_executable(self):
        actions = install_tools(self.root, _TEMPLATES)

        dest = self.root / _HOOK_DEST
        self.assertTrue(dest.is_file(), actions)
        # Claude Code runs the file directly; 644 would simply not start.
        self.assertTrue(dest.stat().st_mode & stat.S_IXUSR)
        self.assertEqual(
            dest.read_bytes(),
            (_TEMPLATES / "session-hook" / "session-start.sh").read_bytes(),
        )

    def test_a_stale_copy_is_refreshed(self):
        dest = self.root / _HOOK_DEST
        dest.parent.mkdir(parents=True)
        dest.write_text("#!/usr/bin/env bash\n# an old version\n", encoding="utf-8")

        actions = install_tools(self.root, _TEMPLATES)
        self.assertEqual(actions, [f"updated {_HOOK_DEST}"])
        self.assertIn("Tooling submodules ready", dest.read_text(encoding="utf-8"))

    def test_a_current_copy_is_left_alone(self):
        install_tools(self.root, _TEMPLATES)
        self.assertEqual(install_tools(self.root, _TEMPLATES), [])

    def test_the_hook_is_not_also_dropped_in_the_repository_root(self):
        # It is a .sh under templates/, so the launcher walk would take it too.
        self.assertIn("session-hook", SKIP_TEMPLATE_DIRS)
        names = [p.name for p in iter_root_launchers(_TEMPLATES)]
        self.assertNotIn("session-start.sh", names)

    def test_the_template_exists_where_the_installer_looks(self):
        for rel_src, _ in TOOL_TEMPLATES:
            self.assertTrue((_TEMPLATES / rel_src).is_file(), rel_src)


class TestSettingsMerge(unittest.TestCase):
    def test_a_missing_file_gets_both_halves(self):
        merged = merge_settings({}, _TEMPLATE_SETTINGS)
        self.assertTrue(hook_is_registered(merged))
        self.assertIn("mcp__freecad__reload_document", merged["permissions"]["deny"])

    def test_a_file_with_only_deny_rules_gains_the_hook(self):
        existing = {"permissions": {"deny": ["mcp__freecad__reload_document"]}}
        merged = merge_settings(existing, _TEMPLATE_SETTINGS)
        self.assertTrue(hook_is_registered(merged))
        self.assertIn("mcp__freecad__execute_code_headless", merged["permissions"]["deny"])

    def test_a_file_with_only_the_hook_gains_the_deny_rules(self):
        existing = {"hooks": _TEMPLATE_SETTINGS["hooks"]}
        merged = merge_settings(existing, _TEMPLATE_SETTINGS)
        self.assertEqual(
            merged["permissions"]["deny"], _TEMPLATE_SETTINGS["permissions"]["deny"]
        )

    def test_keys_doqs_knows_nothing_about_survive(self):
        existing = {
            "model": "opus",
            "permissions": {"allow": ["Bash(ls:*)"], "deny": ["something_of_mine"]},
        }
        merged = merge_settings(existing, _TEMPLATE_SETTINGS)
        self.assertEqual(merged["model"], "opus")
        self.assertEqual(merged["permissions"]["allow"], ["Bash(ls:*)"])
        # Nothing is ever removed, and what was there stays first.
        self.assertEqual(merged["permissions"]["deny"][0], "something_of_mine")

    def test_merging_twice_changes_nothing_the_second_time(self):
        once = merge_settings({}, _TEMPLATE_SETTINGS)
        self.assertEqual(merge_settings(once, _TEMPLATE_SETTINGS), once)

    def test_a_hook_registered_under_another_path_is_not_duplicated(self):
        existing = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": "bash tools/session-start.sh"}]}
                ]
            }
        }
        merged = merge_settings(existing, _TEMPLATE_SETTINGS)
        self.assertEqual(len(merged["hooks"]["SessionStart"]), 1)


class TestSettingsOnDisk(ConsumerRoot):
    def settings(self) -> dict:
        return json.loads((self.root / SETTINGS_DEST).read_text(encoding="utf-8"))

    def test_a_missing_settings_file_is_created(self):
        self.assertEqual(install_settings(self.root, _TEMPLATES), [f"created {SETTINGS_DEST}"])
        self.assertTrue(hook_is_registered(self.settings()))

    def test_an_existing_file_is_merged_not_replaced(self):
        dest = self.root / SETTINGS_DEST
        dest.parent.mkdir(parents=True)
        dest.write_text(json.dumps({"model": "opus"}, indent=2) + "\n", encoding="utf-8")

        self.assertEqual(install_settings(self.root, _TEMPLATES), [f"updated {SETTINGS_DEST}"])
        self.assertEqual(self.settings()["model"], "opus")
        self.assertTrue(hook_is_registered(self.settings()))

    def test_a_file_that_is_already_complete_is_not_rewritten(self):
        install_settings(self.root, _TEMPLATES)
        self.assertEqual(install_settings(self.root, _TEMPLATES), [])

    def test_broken_json_fails_loudly_instead_of_being_overwritten(self):
        dest = self.root / SETTINGS_DEST
        dest.parent.mkdir(parents=True)
        dest.write_text("{ not json", encoding="utf-8")

        with self.assertRaises(SystemExit) as caught:
            install_settings(self.root, _TEMPLATES)
        self.assertIn("not valid JSON", str(caught.exception))
        self.assertEqual(dest.read_text(encoding="utf-8"), "{ not json")


class TestTheGate(ConsumerRoot):
    def test_no_hook_file_means_nothing_to_check(self):
        self.assertEqual(validate_hook_registration(self.root), [])

    def test_a_full_install_passes_the_gate(self):
        install_root_tools(self.root, _TEMPLATES)
        self.assertEqual(validate_hook_registration(self.root), [])

    def test_a_hook_nobody_runs_is_reported(self):
        install_root_tools(self.root, _TEMPLATES)
        dest = self.root / SETTINGS_DEST
        settings = json.loads(dest.read_text(encoding="utf-8"))
        del settings["hooks"]
        dest.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

        errors = validate_hook_registration(self.root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("doqs.py setup", errors[0])

    def test_a_hook_with_no_settings_file_at_all_is_reported(self):
        install_tools(self.root, _TEMPLATES)
        errors = validate_hook_registration(self.root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("nothing runs it", errors[0])


if __name__ == "__main__":
    unittest.main()
