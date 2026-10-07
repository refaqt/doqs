"""Tests for `doqs use-part`: a library part enters a machine module."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import install_module  # noqa: E402
import library_rules as lr  # noqa: E402
import naming_rules  # noqa: E402
import sysml_rules  # noqa: E402
import use_part  # noqa: E402

_MACHINE = _REPO / "tests" / "fixtures" / "variant-machine"
PART = "stoq:hiwin/hgr-rail#HGR20R500"


class _MachineCopy(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="doqs-use-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "machine"
        shutil.copytree(_MACHINE, self.root)
        naming_rules.forget_library_roots()
        self.addCleanup(naming_rules.forget_library_roots)
        install_module.install_module(self.root, "compact-stage", name="Compact Stage")
        self.module = Path("modules/compact-stage")


class TestUsePart(_MachineCopy):
    def test_a_part_gets_a_bom_row_a_manifest_entry_and_sysml(self):
        report = use_part.use_part(self.root, self.module, PART, qty="2", name="Guide rail",
                                   category="MEC", usages=["referenceRail", "secondRail"])
        self.assertTrue(report.ok, report.errors)
        _, rows = lr.read_rows(self.root / self.module / "bom" / "bom.csv")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], "MEC-001")
        self.assertEqual(row["name"], "Guide rail")
        self.assertEqual(row["qty"], "2")
        self.assertEqual(row["brand_pn"], "HGR20R500")
        self.assertEqual(row["part"], PART)
        self.assertEqual(row["unit_mass_g"], "2150")
        self.assertIn("20 mm", row["spec"])
        data = tomllib.loads((self.root / self.module / "okh.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["bom"], "bom/bom.csv")
        self.assertEqual(data["bought-part"], [{"bom": "MEC-001", "part": PART, "sysml": "HgrRail"}])
        arch = (self.root / self.module / "architecture" / "compact-stage.sysml").read_text(encoding="utf-8")
        root = sysml_rules.parse(arch)
        self.assertEqual(sysml_rules.find(root, "CompactStage::HgrRail").kind, "part_def")
        self.assertIn("bought: stoq:hiwin/hgr-rail#HGR20R500", sysml_rules.find(root, "CompactStage::HgrRail").doc)
        self.assertEqual(sysml_rules.find(root, "CompactStage::CompactStage.secondRail").type_name, "HgrRail")
        self.assertEqual(report.facts["bom_id"], "MEC-001")
        # The machine gates accept it.
        for gate in ("validate_okh.py", "validate_names.py", "validate_links.py"):
            result = subprocess.run([sys.executable, str(_SCRIPTS / gate), "--root", str(self.root)],
                                    capture_output=True, text=True, cwd=_REPO)
            self.assertEqual(result.returncode, 0, gate + "\n" + result.stdout + result.stderr)
        result = subprocess.run([sys.executable, str(_SCRIPTS / "validate_variants.py"), "--root", str(self.root)],
                                capture_output=True, text=True, cwd=_REPO)
        self.assertEqual([l for l in result.stdout.splitlines() if "compact-stage" in l and "FAIL" in l], [],
                         result.stdout)

    def test_ids_count_up_per_prefix_and_a_rerun_changes_nothing(self):
        use_part.use_part(self.root, self.module, PART, category="MEC")
        use_part.use_part(self.root, self.module, "stoq:din/din-912#M4X10", category="STD", sysml="CapScrew")
        report = use_part.use_part(self.root, self.module, "stoq:thk/shs-rail#SHS20R500", category="MEC", sysml="ShsRail")
        self.assertTrue(report.ok, report.errors)
        _, rows = lr.read_rows(self.root / self.module / "bom" / "bom.csv")
        self.assertEqual([r["id"] for r in rows], ["MEC-001", "STD-001", "MEC-002"])
        snapshot = {p: p.read_bytes() for p in (self.root / self.module).rglob("*") if p.is_file()}
        report = use_part.use_part(self.root, self.module, PART, category="MEC")
        self.assertTrue(report.ok)
        self.assertEqual(report.edited, [])
        self.assertEqual(report.facts["bom_id"], "MEC-001")
        after = {p: p.read_bytes() for p in (self.root / self.module).rglob("*") if p.is_file()}
        self.assertEqual(snapshot, after)

    def test_an_unknown_part_names_the_pin_bump(self):
        report = use_part.use_part(self.root, self.module, "stoq:hiwin/hgr-rail#HGR20R9999")
        self.assertFalse(report.ok)
        self.assertIn("--bump-pin merged", report.errors[0])
        report = use_part.use_part(self.root, self.module, "other:hiwin/hgr-rail#HGR20R500")
        self.assertFalse(report.ok)
        self.assertIn("no parts library named 'other'", report.errors[0])
        self.assertFalse(use_part.use_part(self.root, self.module, PART, category="XYZ").ok)

    def test_next_bom_id(self):
        self.assertEqual(use_part.next_bom_id([], "MEC"), "MEC-001")
        self.assertEqual(use_part.next_bom_id([{"id": "MEC-007"}, {"id": "STD-002"}, {"id": "bad"}], "MEC"), "MEC-008")

    def test_the_command_line(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "use_part.py"), "--root", str(self.root), "--module",
             self.module.as_posix(), "--part", PART, "--usages", "rail", "--json"],
            capture_output=True, text=True, cwd=_REPO)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["facts"]["usages"], ["rail"])
        self.assertTrue(any("add-interface" in s for s in data["next_steps"]))


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)


@unittest.skipIf(shutil.which("git") is None, "git is not installed")
class TestBumpPin(unittest.TestCase):
    """A real submodule, a real remote: the pin moves only to merged commits."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="doqs-pin-")
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        env = ["-c", "user.name=T", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
        self.env = env
        # The library: a work copy pushed to a bare remote.
        self.lib_remote = base / "stoq.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.lib_remote)], check=True)
        lib = base / "stoq-work"
        subprocess.run(["git", "clone", "-q", str(self.lib_remote), str(lib)], check=True, capture_output=True)
        (lib / "library.toml").write_text('schema = "doqs-library-v1"\nname = "stoq"\n', encoding="utf-8")
        subprocess.run(["git", "-C", str(lib), *env, "add", "."], check=True)
        subprocess.run(["git", "-C", str(lib), *env, "commit", "-q", "-m", "first"], check=True)
        subprocess.run(["git", "-C", str(lib), "push", "-q", "-u", "origin", "HEAD:main"], check=True, capture_output=True)
        self.first = _git(lib, "rev-parse", "HEAD").stdout.strip()
        # The machine, with the library as a submodule at the first commit.
        self.root = base / "machine"
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), *env, "-c", "protocol.file.allow=always",
                        "submodule", "add", "-q", str(self.lib_remote), "modules/stoq"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.root), *env, "commit", "-q", "-m", "mount"], check=True)
        # A second library commit on main, and a third on a branch.
        (lib / "new.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "-C", str(lib), *env, "add", "."], check=True)
        subprocess.run(["git", "-C", str(lib), *env, "commit", "-q", "-m", "second"], check=True)
        subprocess.run(["git", "-C", str(lib), "push", "-q", "origin", "HEAD:main"], check=True, capture_output=True)
        self.second = _git(lib, "rev-parse", "HEAD").stdout.strip()
        subprocess.run(["git", "-C", str(lib), "checkout", "-q", "-b", "feat/x"], check=True)
        (lib / "branch.txt").write_text("y", encoding="utf-8")
        subprocess.run(["git", "-C", str(lib), *env, "add", "."], check=True)
        subprocess.run(["git", "-C", str(lib), *env, "commit", "-q", "-m", "third"], check=True)
        subprocess.run(["git", "-C", str(lib), "push", "-q", "origin", "feat/x"], check=True, capture_output=True)
        self.third = _git(lib, "rev-parse", "HEAD").stdout.strip()

    def test_merged_moves_to_origin_main_and_stages_the_gitlink(self):
        sha, message = use_part.bump_pin(self.root, "modules/stoq", "merged")
        self.assertEqual(sha, self.second, message)
        self.assertEqual(_git(self.root / "modules" / "stoq", "rev-parse", "HEAD").stdout.strip(), self.second)
        staged = _git(self.root, "diff", "--cached", "--name-only").stdout.split()
        self.assertEqual(staged, ["modules/stoq"])

    def test_an_unmerged_commit_is_refused_unless_allowed(self):
        sha, message = use_part.bump_pin(self.root, "modules/stoq", self.third)
        self.assertIsNone(sha)
        self.assertIn("not on origin/main", message)
        self.assertEqual(_git(self.root / "modules" / "stoq", "rev-parse", "HEAD").stdout.strip(), self.first)
        sha, message = use_part.bump_pin(self.root, "modules/stoq", self.third, allow_unmerged=True)
        self.assertEqual(sha, self.third)
        self.assertIn("not on origin/main!", message)

    def test_dry_run_and_already_there(self):
        sha, message = use_part.bump_pin(self.root, "modules/stoq", "merged", dry_run=True)
        self.assertEqual(sha, self.second)
        self.assertIn("would move", message)
        self.assertEqual(_git(self.root / "modules" / "stoq", "rev-parse", "HEAD").stdout.strip(), self.first)
        sha, message = use_part.bump_pin(self.root, "modules/stoq", self.first)
        self.assertEqual(sha, self.first)
        self.assertIn("already at", message)

    def test_local_changes_in_the_submodule_block_the_bump(self):
        (self.root / "modules" / "stoq" / "library.toml").write_text("changed\n", encoding="utf-8")
        sha, message = use_part.bump_pin(self.root, "modules/stoq", "merged")
        self.assertIsNone(sha)
        self.assertIn("local changes", message)


if __name__ == "__main__":
    unittest.main()
