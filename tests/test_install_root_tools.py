"""Tests for consumer-root launcher install (no git / no Docker)."""
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

from install_root_tools import (  # noqa: E402
    CONFIG_TEMPLATES,
    SKIP_TEMPLATE_DIRS,
    install_configs,
    install_root_tools,
    iter_root_launchers,
)
from license_rules import is_doqs_tools_repo  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


class TestIterRootLaunchers(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-launchers-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def test_skips_setup_tooling_and_readmes(self):
        templates = self._tmp / "templates"
        _write(templates / "setup-tooling" / "setup-tooling.bat", "@echo off\n")
        _write(templates / "setup-tooling" / "setup-tooling.sh", "#!/bin/sh\n")
        _write(templates / "syson" / "syson.bat", "@echo off\n")
        _write(templates / "syson" / "syson.sh", "#!/bin/sh\n")
        _write(templates / "syson" / "README.md", "# not a launcher\n")
        names = {p.name for p in iter_root_launchers(templates)}
        self.assertEqual(names, {"syson.bat", "syson.sh"})
        self.assertIn("setup-tooling", SKIP_TEMPLATE_DIRS)


class TestInstallRootTools(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-install-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = self._tmp / "machine"
        self.templates = self.root / "doqs" / "templates"
        _write(self.templates / "syson" / "syson.bat", "@echo off\r\nREM syson\r\n")
        _write(self.templates / "syson" / "syson.sh", "#!/bin/sh\necho syson\n")
        _write(self.templates / "syson" / "README.md", "# skip\n")
        _write(
            self.templates / "setup-tooling" / "setup-tooling.bat",
            "@echo off\r\nREM bootstrap\r\n",
        )

    def test_creates_missing_launchers(self):
        actions = install_root_tools(self.root)
        self.assertEqual(
            sorted(actions),
            ["created syson.bat", "created syson.sh"],
        )
        self.assertEqual(
            (self.root / "syson.bat").read_bytes(),
            (self.templates / "syson" / "syson.bat").read_bytes(),
        )
        self.assertFalse((self.root / "README.md").exists())
        self.assertFalse((self.root / "setup-tooling.bat").exists())

    def test_skips_identical_bytes(self):
        install_root_tools(self.root)
        actions = install_root_tools(self.root)
        self.assertEqual(actions, [])

    def test_overwrites_when_template_changed(self):
        install_root_tools(self.root)
        (self.templates / "syson" / "syson.bat").write_bytes(b"@echo off\r\nREM v2\r\n")
        actions = install_root_tools(self.root)
        self.assertEqual(actions, ["updated syson.bat"])
        self.assertEqual((self.root / "syson.bat").read_bytes(), b"@echo off\r\nREM v2\r\n")

    def test_discovers_a_new_tool_directory(self):
        _write(self.templates / "foo" / "foo.bat", "@echo off\r\nREM foo\r\n")
        actions = install_root_tools(self.root)
        self.assertIn("created foo.bat", actions)
        self.assertTrue((self.root / "foo.bat").is_file())

    def test_tools_repo_is_noop(self):
        tools = self._tmp / "doqs"
        _write(tools / "scripts" / "license_rules.py", "# stub\n")
        (tools / "templates" / "licensing").mkdir(parents=True)
        _write(tools / "templates" / "syson" / "syson.bat", "@echo off\n")
        self.assertTrue(is_doqs_tools_repo(tools))
        self.assertEqual(install_root_tools(tools), [])
        self.assertFalse((tools / "syson.bat").exists())


class TestInstallRootToolsCli(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-cli-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = self._tmp / "machine"
        _write(
            self.root / "doqs" / "templates" / "syson" / "syson.bat",
            "@echo off\r\n",
        )

    def test_cli_creates_and_is_idempotent(self):
        cmd = [
            sys.executable,
            str(_SCRIPTS / "install_root_tools.py"),
            "--root",
            str(self.root),
        ]
        first = subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn("created syson.bat", first.stdout)
        second = subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("already current", second.stdout)

    def test_cli_tools_repo_noop(self):
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "install_root_tools.py"),
                "--root",
                str(_REPO),
            ],
            capture_output=True,
            text=True,
            cwd=_REPO,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("doqs tools repo", result.stdout)
        self.assertFalse((_REPO / "syson.bat").exists())


class TestInstallConfigs(unittest.TestCase):
    """`.mcp.json` is copy-once: it is the user's file.

    `.claude/settings.json` moved out of this path. doqs owns two keys in it —
    the deny rules and the session-hook registration — so it is merged instead of
    copied. See tests/test_install_session_hook.py.
    """

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-config-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = self._tmp / "machine"
        self.root.mkdir()
        self.templates = _REPO / "templates"

    def test_creates_both_agent_config_files(self):
        actions = install_configs(self.root, self.templates)
        for _, dest in CONFIG_TEMPLATES:
            self.assertTrue((self.root / dest).is_file(), dest)
        self.assertEqual(len(actions), len(CONFIG_TEMPLATES))

    def test_never_overwrites_user_edits(self):
        install_configs(self.root, self.templates)
        mcp = self.root / ".mcp.json"
        edited = mcp.read_text(encoding="utf-8").replace("{", '{"mine": true,', 1)
        mcp.write_text(edited, encoding="utf-8")
        self.assertEqual(install_configs(self.root, self.templates), [])
        self.assertIn("mine", mcp.read_text(encoding="utf-8"))

    def test_shipped_guard_template_denies_both_hazardous_tools(self):
        # The installed default must satisfy validate_cad.py out of the box.
        sys.path.insert(0, str(_SCRIPTS))
        import json

        from cad_rules import missing_guard_rules
        from install_root_tools import install_settings

        install_settings(self.root, self.templates)
        settings = json.loads(
            (self.root / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        self.assertEqual(missing_guard_rules(settings), [])
