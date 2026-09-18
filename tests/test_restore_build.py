"""Unit tests for build records: pins you can act on, and getting files back.

A build record describes a machine that exists. It is only worth having if you
can still open it. See docs/decisions/2026-09-18_build-records.md.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import restore_build  # noqa: E402
from validate_build import check_pins  # noqa: E402

MACHINE = _REPO / "tests" / "fixtures" / "variant-machine"


def make_repo(path: Path, contents: dict[str, str]) -> str:
    """A real git repository, so a fetch is a real fetch. Returns the commit."""
    path.mkdir(parents=True, exist_ok=True)

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=path,
                              capture_output=True, text=True)

    git("init", "--quiet", "-b", "main", ".")
    git("config", "user.email", "tests@example.com")
    git("config", "user.name", "DOQS Tests")
    for name, text in contents.items():
        (path / name).write_text(text)
    git("add", ".")
    git("commit", "--quiet", "-m", "a version somebody built a machine from")
    return git("rev-parse", "HEAD").stdout.strip()


def write_record(build_dir: Path, repo: Path | str, commit: str) -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "build.toml").write_text(
        'schema = "doqs-build-v1"\nmachine = "test"\n\n'
        f'[[module]]\npath = "modules/thing"\nrepo = "{repo}"\n'
        f'version = "v1.0.0"\ncommit = "{commit}"\n'
    )


class TestPins(unittest.TestCase):
    """Three things make a record openable: where, which version, which commit."""

    def entry(self, **over: str) -> dict:
        base = {"path": "modules/x", "repo": "https://example.com/x",
                "version": "v1.0.0", "commit": "a" * 40}
        base.update(over)
        return {"module": [base]}

    def test_a_complete_pin_passes(self) -> None:
        self.assertEqual(check_pins(self.entry()), [])

    def test_a_missing_commit_is_refused(self) -> None:
        errors = check_pins({"module": [{"path": "modules/x",
                                         "repo": "https://example.com/x",
                                         "version": "v1.0.0"}]})
        self.assertTrue(any("can be moved or deleted" in e for e in errors), errors)

    def test_a_missing_repo_is_refused(self) -> None:
        errors = check_pins({"module": [{"path": "modules/x",
                                         "version": "v1.0.0",
                                         "commit": "a" * 40}]})
        self.assertTrue(any("where to fetch" in e for e in errors), errors)

    def test_a_short_commit_is_refused(self) -> None:
        errors = check_pins(self.entry(commit="a" * 7))
        self.assertTrue(any("40-character" in e for e in errors), errors)

    def test_a_version_that_is_not_a_tag_is_refused(self) -> None:
        errors = check_pins(self.entry(version="1.0.0"))
        self.assertTrue(any("is not a tag" in e for e in errors), errors)

    def test_the_fixture_record_is_fully_pinned(self) -> None:
        import tomllib
        with open(MACHINE / "builds/serial-0001/build.toml", "rb") as f:
            self.assertEqual(check_pins(tomllib.load(f)), [])


class TestRestoring(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.origin = self.tmp / "origin"
        self.commit = make_repo(self.origin, {"design.txt": "the version built\n"})
        # Development carries on after the machine was built.
        subprocess.run(["git", "commit", "--quiet", "--allow-empty",
                        "-m", "later work"], cwd=self.origin, capture_output=True)
        (self.origin / "design.txt").write_text("a later version\n")
        subprocess.run(["git", "add", "."], cwd=self.origin, capture_output=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "changed"],
                       cwd=self.origin, capture_output=True)
        self.build = self.tmp / "builds" / "serial-0001"
        write_record(self.build, self.origin, self.commit)

    def test_it_returns_the_version_the_machine_was_built_from(self) -> None:
        """Not the latest. That is the entire point of a build record."""
        out = self.tmp / "restored"
        entry = restore_build.pinned_entries(restore_build.load_build(self.build))[0]
        where = Path(restore_build.restore_one(entry, out))
        self.assertEqual((where / "design.txt").read_text(), "the version built\n")

    def test_a_reachable_pin_reports_nothing(self) -> None:
        gone, unknown = restore_build.check(self.build)
        self.assertEqual((gone, unknown), ([], []))

    def test_a_commit_that_is_gone_is_reported(self) -> None:
        write_record(self.build, self.origin, "0" * 40)
        gone, unknown = restore_build.check(self.build)
        self.assertTrue(any("no longer in" in g for g in gone), gone)
        self.assertEqual(unknown, [])

    def test_a_record_with_no_pins_says_so(self) -> None:
        (self.build / "build.toml").write_text(
            'schema = "doqs-build-v1"\nmachine = "t"\n\n'
            '[[module]]\npath = "modules/thing"\nversion = "v1.0.0"\n')
        code = restore_build.main([str(self.build), "--out", str(self.tmp / "x")])
        self.assertEqual(code, 1)

    def test_a_missing_build_directory_is_reported(self) -> None:
        code = restore_build.main([str(self.tmp / "nope"), "--check"])
        self.assertEqual(code, 1)


class TestUnreachableIsNotTheSameAsGone(unittest.TestCase):
    """Blaming the record for a network problem sends people hunting."""

    def test_a_network_failure_is_classified_apart(self) -> None:
        self.assertEqual(
            restore_build._failure_kind("fatal: unable to access 'https://x/'"),
            "network")
        self.assertEqual(
            restore_build._failure_kind("fatal: could not resolve host: x"),
            "network")

    def test_a_missing_object_is_classified_apart(self) -> None:
        self.assertEqual(
            restore_build._failure_kind(
                "error: Server does not allow request for unadvertised object"),
            "missing")

    def test_an_unreachable_repository_exits_two_not_one(self) -> None:
        """Exit 1 means act. Exit 2 means nothing was confirmed either way."""
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp) / "builds" / "serial-0001"
            write_record(build, "https://no-such-host.invalid/x", "a" * 40)
            self.assertEqual(restore_build.main([str(build), "--check"]), 2)


if __name__ == "__main__":
    unittest.main()
