"""Tests for the two session hooks: the one doqs uses and the one it ships.

The failure these cover is the one that happened: a session opened the folder
*above* the repository, so `$CLAUDE_PROJECT_DIR` pointed at a folder that is not
a git work tree. The hook trusted that variable, `cd`-ed there, and every git
call failed for a reason no message named.

Both hooks now find the repository root from their own place on disk. These
tests run them and read what they print, because the shell is where the rule
lives; a comment cannot be tested.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

#: The hook doqs runs on itself, and the hook it ships to machine repositories.
_HOOKS = {
    "own": _REPO / ".claude" / "hooks" / "session-start.sh",
    "template": _REPO / "templates" / "session-hook" / "session-start.sh",
}

_HAS_TOOLS = bool(shutil.which("git") and shutil.which("bash"))


def _install(hook: Path, root: Path) -> Path:
    """Put `hook` where a session would find it, at root/.claude/hooks/."""
    dest = root / ".claude" / "hooks" / "session-start.sh"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(hook, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def _commands(hook: Path) -> str:
    """The hook without its comments, so a flag named in prose is not a use."""
    lines = hook.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def _run(hook: Path, cwd: Path, project_dir: Path | None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    if project_dir is None:
        env.pop("CLAUDE_PROJECT_DIR", None)
    else:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        ["bash", str(hook)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


@unittest.skipUnless(_HAS_TOOLS, "needs git and bash")
class TestTheHookFindsItsOwnRepository(unittest.TestCase):
    """A wrong project folder must not decide where the hook works."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-session-hook-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        # Two levels, like a session that attaches several repositories: the
        # parent is not a repository, the folder inside it is.
        self.parent = Path(os.path.realpath(self._tmp))
        self.machine = self.parent / "machine"
        self.machine.mkdir()
        subprocess.run(
            ["git", "init", "--quiet", str(self.machine)],
            check=True,
            capture_output=True,
        )

    def test_the_hook_ignores_a_wrong_project_dir(self):
        """This is the test that would have caught the bug.

        The hook runs from the parent folder with CLAUDE_PROJECT_DIR set to it.
        It must still work in the repository it sits in, and say which one.
        """
        for name, hook in _HOOKS.items():
            with self.subTest(hook=name):
                installed = _install(hook, self.machine)
                done = _run(installed, cwd=self.parent, project_dir=self.parent)

                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn(
                    str(self.machine),
                    done.stdout,
                    "the hook must name the repository it worked in",
                )
                self.assertNotIn("found no git repository", done.stdout)

    def test_a_hook_outside_a_repository_says_so_and_exits_zero(self):
        for name, hook in _HOOKS.items():
            with self.subTest(hook=name):
                installed = _install(hook, self.parent)
                done = _run(installed, cwd=self.parent, project_dir=None)

                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn("found no git repository", done.stdout)


class TestHookText(unittest.TestCase):
    """Rules that live in the file itself, not in a comment about it."""

    def test_neither_hook_trusts_the_project_dir_alone(self):
        stale = 'root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"'
        for name, hook in _HOOKS.items():
            with self.subTest(hook=name):
                text = hook.read_text(encoding="utf-8")
                self.assertNotIn(stale, text, "the old root line is back")
                self.assertIn("BASH_SOURCE", text)
                self.assertIn("rev-parse --show-toplevel", text)

    def test_the_two_shapes_stay_apart(self):
        # Comments name the flags they explain, so read the commands only.
        own = _commands(_HOOKS["own"])
        template = _commands(_HOOKS["template"])

        # doqs marks its own .agents "update = none", so it needs --checkout.
        self.assertIn("--checkout", own)
        self.assertNotIn("--checkout", template)

        # A machine repository has two tooling submodules; doqs has one.
        self.assertIn("--remote -- doqs .agents", template)
        self.assertNotIn("--remote -- doqs .agents", own)

    def test_neither_hook_can_stop_a_session(self):
        for name, hook in _HOOKS.items():
            with self.subTest(hook=name):
                text = hook.read_text(encoding="utf-8")
                self.assertIsNone(
                    re.search(r"^set -[a-z]*e", text, re.MULTILINE),
                    "a hook that exits on error can stop a session start",
                )
                self.assertIn("set -uo pipefail", text)
                self.assertTrue(text.rstrip().endswith("exit 0"))

    def test_both_hooks_keep_the_licence_header(self):
        for name, hook in _HOOKS.items():
            with self.subTest(hook=name):
                head = hook.read_text(encoding="utf-8").splitlines()[:2]
                self.assertEqual(head[0], "#!/usr/bin/env bash")
                self.assertEqual(head[1], "# SPDX-License-Identifier: GPL-3.0-or-later")


if __name__ == "__main__":
    unittest.main()
