"""Tests for the one entry point: `python doqs/doqs.py <command>`."""
from __future__ import annotations

import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import cli  # noqa: E402
import validate_all  # noqa: E402

_DOQS_PY = _REPO / "doqs.py"
_FIXTURE = _REPO / "tests" / "fixtures" / "minimal-machine"


_HAS_GIT = bool(shutil.which("git"))


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   cwd=cwd, check=True, capture_output=True)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _kit_script(root: Path, name: str, code: int) -> Path:
    """A stand-in for a shared-kit script: it prints its arguments and exits `code`."""
    return _write(root / ".agents" / "scripts" / name, textwrap.dedent(f"""\
        import sys
        print("KIT", *sys.argv[1:])
        raise SystemExit({code})
        """))


class _TempRoot(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-cli-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = self._tmp / "machine"
        self.root.mkdir()


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
                "validate_names.py",
                "validate_links.py",
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
        for command in ("check", "generate", "setup", "doctor", "pre-pr", "log new", "mistakes",
                        "context", "syson", "export", "bom", "run", "list"):
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


class TestDoctor(_TempRoot):
    def test_empty_folders_fail_and_name_the_command(self):
        (self.root / ".agents").mkdir()
        (self.root / "doqs").mkdir()
        result = run_doqs("doctor", "--root", str(self.root))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL  .agents", result.stdout)
        self.assertIn("FAIL  doqs", result.stdout)
        self.assertIn("bash setup-tooling.sh", result.stdout)
        self.assertLessEqual(len(result.stdout.splitlines()), 6)

    @unittest.skipUnless(_HAS_GIT, "needs git")
    def test_filled_folders_show_their_commit_and_their_pin(self):
        _git(self.root, "init", "--quiet")
        for name, marker in cli.MARKERS.items():
            folder = self.root / name
            _write(self.root / marker, "x\n")
            _git(folder, "init", "--quiet")
            _git(folder, "add", ".")
            _git(folder, "commit", "--quiet", "-m", "first")
        # Record both as gitlinks, the way a submodule pin is stored.
        _git(self.root, "add", ".agents", "doqs")
        _git(self.root, "commit", "--quiet", "-m", "pin")
        _write(self.root / ".agents" / "rules" / "new.md", "y\n")
        _git(self.root / ".agents", "add", ".")
        _git(self.root / ".agents", "commit", "--quiet", "-m", "second")

        result = run_doqs("doctor", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 commits ahead of its pin", result.stdout)
        self.assertIn("doqs", result.stdout)
        self.assertIn("at its pin", result.stdout)
        self.assertLessEqual(len(result.stdout.splitlines()), 6)

    def test_the_tools_repo_needs_only_the_kit(self):
        self.assertEqual(cli.update_command(_REPO), "git submodule update --init --remote --checkout .agents")


class TestKitWrappers(_TempRoot):
    def test_a_missing_kit_script_is_one_hint_line_and_success(self):
        for command in ("mistakes", "context"):
            with self.subTest(command=command):
                result = run_doqs(command, "--root", str(self.root))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(result.stdout.strip().splitlines()), 1)
                self.assertIn("skip", result.stdout)

    def test_mistakes_passes_the_root_and_the_check_flag(self):
        _kit_script(self.root, "mistakes_index.py", 1)
        result = run_doqs("mistakes", "--check", "--root", str(self.root))
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"KIT --root {self.root.resolve()} --check", result.stdout)

    def test_context_passes_the_budget(self):
        _kit_script(self.root, "context_budget.py", 0)
        result = run_doqs("context", "--budget", "4000", "--root", str(self.root))
        self.assertEqual(result.returncode, 0)
        self.assertIn("--budget 4000", result.stdout)


class TestCheckRunsTheKitChecksAsWarnings(_TempRoot):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root)
        shutil.copytree(_FIXTURE, self.root)

    def test_kit_drift_warns_but_the_check_passes(self):
        _kit_script(self.root, "mistakes_index.py", 1)
        _kit_script(self.root, "sync_root.py", 1)
        _write(self.root / "docs" / "mistakes" / "README.md", "# Mistakes\n")
        _write(self.root / "CLAUDE.md", "# fixture\n")
        # A new docs/ folder needs its licence file, or the licence gate fails.
        subprocess.run([sys.executable, str(_SCRIPTS / "apply_licenses.py"), "--root", str(self.root)],
                       check=True, capture_output=True)
        result = run_doqs("check", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARN  mistakes_index.py", result.stdout)
        self.assertIn("WARN  sync_root.py", result.stdout)

    def test_a_kit_without_the_scripts_is_skipped_silently(self):
        result = run_doqs("check", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("mistakes_index.py", result.stdout)
        self.assertNotIn("skip", result.stdout)


class TestLogNew(_TempRoot):
    INDEX = textwrap.dedent("""\
        # Activity log

        | Date | Topic | Role(s) | Images |
        | ---- | ----- | ------- | -----: |
        | 2026-01-01 | [Old](2026-01-01_old.md) | software | 0 |

        Text after the table.
        """)

    def test_it_writes_the_entry_and_adds_one_index_row(self):
        index = _write(self.root / "docs" / "log" / "README.md", self.INDEX)
        result = run_doqs("log", "new", "lean-context", "--title", "Agents read less",
                          "--date", "2026-11-26", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = self.root / "docs" / "log" / "2026-11-26_lean-context.md"
        text = entry.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# 2026-11-26 — Agents read less\n"))
        for heading in ("What changed", "Why it matters", "What you need to do", "How it was checked"):
            self.assertIn(f"## {heading}\n", text)
        lines = index.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            lines[5], "| 2026-11-26 | [Agents read less](2026-11-26_lean-context.md) | software | 0 |")
        self.assertEqual(lines[7], "Text after the table.")

    def test_it_never_overwrites_an_entry(self):
        entry = _write(self.root / "docs" / "log" / "2026-11-26_x.md", "mine\n")
        result = run_doqs("log", "new", "x", "--date", "2026-11-26", "--root", str(self.root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(entry.read_text(encoding="utf-8"), "mine\n")

    def test_an_index_without_a_table_is_left_alone(self):
        index = _write(self.root / "docs" / "log" / "README.md", "# Log\n")
        result = run_doqs("log", "new", "x", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(index.read_text(encoding="utf-8"), "# Log\n")

    def test_it_refuses_a_name_that_is_not_a_slug(self):
        result = run_doqs("log", "new", "Not A Slug", "--root", str(self.root))
        self.assertEqual(result.returncode, 2)


class TestPrePr(_TempRoot):
    def run_main(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["pre-pr", "--root", str(self.root), *args])
        return code, out.getvalue()

    def test_it_runs_the_steps_in_order(self):
        calls: list[str] = []
        with mock.patch.object(cli, "save_and_rebuild", lambda root: calls.append("freecad") or 0), \
                mock.patch.object(cli, "cmd_generate", lambda a: calls.append("generate") or 0), \
                mock.patch.object(cli, "cmd_check", lambda a: calls.append("check") or 0), \
                mock.patch.object(cli.subprocess, "run") as run:
            code, out = self.run_main()
        self.assertEqual(code, 0, out)
        self.assertEqual(calls, ["freecad", "generate", "check"])
        self.assertEqual(run.call_args.args[0], ["git", "status", "--short"])

    def test_it_stops_at_the_first_failure(self):
        calls: list[str] = []
        with mock.patch.object(cli, "save_and_rebuild", lambda root: 0), \
                mock.patch.object(cli, "cmd_generate", lambda a: calls.append("generate") or 1), \
                mock.patch.object(cli, "cmd_check", lambda a: calls.append("check") or 0):
            code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertEqual(calls, ["generate"])
        self.assertIn("STOP  'doqs generate' failed", out)


class TestSaveAndRebuild(_TempRoot):
    """The FreeCAD part of pre-pr, with a fake window and a fake FreeCADCmd."""

    def patches(self, rpc: bool, gui: bool, saved: list[str], binary: str | None = None):
        import freecad_rules
        import freecad_session
        result = {"saved": saved, "unchanged": [], "unnamed": [], "outside": [], "failed": [], "missing": []}
        return (mock.patch.object(freecad_rules, "rpc_available", return_value=rpc),
                mock.patch.object(freecad_session, "gui_running", return_value=gui),
                mock.patch.object(freecad_session, "save_documents", return_value=result),
                mock.patch.object(freecad_rules, "find_freecad", return_value=binary))

    def call(self, *patches) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.ExitStack() as stack, contextlib.redirect_stdout(out):
            for patch in patches:
                stack.enter_context(patch)
            code = cli.save_and_rebuild(self.root)
        return code, out.getvalue()

    def fake_freecadcmd(self, says: str) -> str:
        script = _write(self._tmp / "freecadcmd", f"#!/bin/sh\necho '{says}'\n")
        script.chmod(0o755)
        return str(script)

    def test_no_freecad_means_nothing_to_save(self):
        code, out = self.call(*self.patches(rpc=False, gui=False, saved=[]))
        self.assertEqual(code, 0)
        self.assertIn("nothing to save", out)

    def test_a_window_that_does_not_answer_stops_the_run(self):
        code, out = self.call(*self.patches(rpc=False, gui=True, saved=[]))
        self.assertEqual(code, 1)
        self.assertIn("Start RPC Server", out)

    @unittest.skipIf(sys.platform == "win32", "uses a shell script as FreeCADCmd")
    def test_a_saved_document_is_rebuilt_headless(self):
        fcstd = _write(self.root / "cad" / "rail.FCStd", "")
        _write(self.root / "cad" / "build_model.py", "")
        binary = self.fake_freecadcmd("Rebuilt and saved rail")
        code, out = self.call(*self.patches(rpc=True, gui=True, saved=[str(fcstd)], binary=binary))
        self.assertEqual(code, 0, out)
        self.assertIn("rebuilt", out)

    @unittest.skipIf(sys.platform == "win32", "uses a shell script as FreeCADCmd")
    def test_a_rebuild_that_built_nothing_fails(self):
        fcstd = _write(self.root / "cad" / "rail.FCStd", "")
        _write(self.root / "cad" / "build_model.py", "")
        binary = self.fake_freecadcmd("ERROR: this FreeCADCmd run built nothing")
        code, out = self.call(*self.patches(rpc=True, gui=True, saved=[str(fcstd)], binary=binary))
        self.assertEqual(code, 1)
        self.assertIn("built nothing", out)


if __name__ == "__main__":
    unittest.main()
