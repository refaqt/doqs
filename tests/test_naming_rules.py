"""Unit tests for DOQS naming rules and fixture validation."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Allow importing scripts package from repo
_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from naming_rules import (  # noqa: E402
    BOM_ID,
    OKH_VERSION,
    is_under_tooling_submodule,
    load_lexicon,
    validate_adapter_slug,
    validate_bom_id,
    validate_module_slug,
)
from validate_names import check_module_directories  # noqa: E402

_FIXTURE = _REPO / "tests" / "fixtures" / "minimal-machine"


class TestRegexes(unittest.TestCase):
    def test_module_slug(self):
        self.assertTrue(validate_module_slug("x-axis"))
        self.assertTrue(validate_module_slug("x-axis-belt"))
        self.assertFalse(validate_module_slug("X-Axis"))
        self.assertFalse(validate_module_slug("x_axis"))

    def test_adapter_slug(self):
        self.assertTrue(validate_adapter_slug("foo-v1-to-v2"))
        self.assertTrue(validate_adapter_slug("spindle-mount-v1-to-v2"))
        self.assertFalse(validate_adapter_slug("foo-v1-v2"))

    def test_bom_id(self):
        ok, _ = validate_bom_id("MEC-001")
        self.assertTrue(ok)
        ok, err = validate_bom_id("SW-01")
        self.assertFalse(ok)
        self.assertIn("PREFIX-NNN", err or "")

    def test_okh_version(self):
        self.assertTrue(OKH_VERSION.match("1.2.0"))
        self.assertTrue(OKH_VERSION.match("0.1.0"))
        self.assertFalse(OKH_VERSION.match("v1.2.0"))

    def test_lexicon_loads(self):
        words = load_lexicon()
        self.assertIn("axis", words)
        self.assertIn("spindle", words)


class TestFixtureValidation(unittest.TestCase):
    def _run(self, script: str, *extra: str) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            str(_SCRIPTS / script),
            "--root",
            str(_FIXTURE),
            *extra,
        ]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO)

    def test_validate_names_fixture(self):
        result = self._run("validate_names.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validate_okh_fixture(self):
        result = self._run("validate_okh.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validate_okh_expected_version(self):
        result = self._run("validate_okh.py", "--expected-version", "0.1.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        bad = self._run("validate_okh.py", "--expected-version", "9.9.9")
        self.assertNotEqual(bad.returncode, 0)


class TestToolingSubmodules(unittest.TestCase):
    """A machine repo mounts doqs at `doqs/` and the agent kit at `.agents/`."""

    ROOT = Path("/machine")

    def test_tooling_paths_are_skipped(self):
        self.assertTrue(
            is_under_tooling_submodule(self.ROOT / "doqs" / "scripts" / "validate_names.py", self.ROOT)
        )
        self.assertTrue(
            is_under_tooling_submodule(self.ROOT / ".agents" / "skills" / "okh.toml", self.ROOT)
        )

    def test_nested_tooling_paths_are_skipped(self):
        """An extracted module under modules/ mounts the same two submodules."""
        self.assertTrue(
            is_under_tooling_submodule(
                self.ROOT / "modules" / "x-axis" / ".agents" / "rules" / "core.md", self.ROOT
            )
        )
        self.assertTrue(
            is_under_tooling_submodule(
                self.ROOT / "modules" / "x-axis" / "doqs" / "okh.toml", self.ROOT
            )
        )

    def test_machine_paths_are_kept(self):
        self.assertFalse(is_under_tooling_submodule(self.ROOT / "okh.toml", self.ROOT))
        self.assertFalse(
            is_under_tooling_submodule(self.ROOT / "modules" / "x-axis" / "okh.toml", self.ROOT)
        )

    def test_path_outside_root_is_not_tooling(self):
        self.assertFalse(is_under_tooling_submodule(Path("/elsewhere/okh.toml"), self.ROOT))


class TestAgentKitNotValidated(unittest.TestCase):
    """Validators walk the machine root, so they must step over `.agents/`.

    The shared agent kit is a separate repository. Its example files are not
    machine files, and a validator that reads them fails on content the
    machine repo does not own.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "machine"
        shutil.copytree(_FIXTURE, self.root)
        kit = self.root / ".agents" / "skills" / "doqs-naming"
        kit.mkdir(parents=True)
        (kit / "okh.toml").write_text('name = "example manifest in the kit"\n', encoding="utf-8")
        (kit / "catalog.toml").write_text('example = true\n', encoding="utf-8")
        (kit / "example.sysml").write_text(
            "import '../nowhere/missing.sysml'::Missing::*;\n", encoding="utf-8"
        )

    def _run(self, script: str) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(_SCRIPTS / script), "--root", str(self.root)]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO)

    def test_validators_skip_the_kit(self):
        for script in (
            "validate_okh.py",
            "validate_names.py",
            "validate_links.py",
            "validate_variants.py",
        ):
            with self.subTest(script=script):
                result = self._run(script)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn(".agents", result.stdout)


class TestOrphanModuleWarning(unittest.TestCase):
    """`modules/` holds modules. Everything inside a module is content.

    A module sits directly under a `modules/` directory, or under
    `modules/adapters/`. The orphan warning must look only at those places.
    A folder such as `docs/` is content and must stay silent, wherever the
    repository itself happens to be checked out.
    """

    def _machine(self, parent_name: str = "work") -> Path:
        """A machine repo with one module, inside a folder named parent_name."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / parent_name / "demo-machine"
        (root / "modules" / "demo").mkdir(parents=True)
        (root / "okh.toml").write_text('version = "0.1.0"\n', encoding="utf-8")
        (root / "modules" / "demo" / "okh.toml").write_text(
            'version = "0.1.0"\n', encoding="utf-8"
        )
        return root

    def _orphan(self, parent: Path, name: str) -> Path:
        stray = parent / name
        stray.mkdir(parents=True)
        (stray / "README.md").write_text("no manifest here\n", encoding="utf-8")
        return stray

    def _warned_paths(self, root: Path) -> list[str]:
        findings = check_module_directories(root, root / "modules")
        self.assertTrue(all(f.warning for f in findings), "orphans stay warnings")
        return sorted(f.path for f in findings)

    def test_content_folders_are_not_orphans(self):
        """A module's own docs/ folder, and what it holds, are content."""
        root = self._machine()
        log = root / "modules" / "demo" / "docs" / "log"
        log.mkdir(parents=True)
        (log / "a.md").write_text("a note\n", encoding="utf-8")
        self.assertEqual(self._warned_paths(root), [])

    def test_directory_beside_a_module_is_an_orphan(self):
        root = self._machine()
        self._orphan(root / "modules", "stray")
        findings = check_module_directories(root, root / "modules")
        self.assertEqual(len(findings), 1, [f.path for f in findings])
        self.assertEqual(findings[0].path, str(Path("modules") / "stray"))
        self.assertTrue(findings[0].warning)
        self.assertIn("orphan", findings[0].message)

    def test_parent_folder_named_cad_still_reports_the_orphan(self):
        """The check reads the path inside the repo, not the path to it."""
        root = self._machine(parent_name="cad")
        self._orphan(root / "modules", "stray")
        self.assertEqual(self._warned_paths(root), [str(Path("modules") / "stray")])

    def test_nested_modules_follow_the_same_rule(self):
        """A module carries its own modules/ folder, at every depth."""
        root = self._machine()
        nested = root / "modules" / "demo" / "modules" / "drive-belt"
        nested.mkdir(parents=True)
        (nested / "okh.toml").write_text('version = "0.1.0"\n', encoding="utf-8")
        (nested / "cad" / "parts" / "pulley").mkdir(parents=True)
        (nested / "cad" / "parts" / "pulley" / "pulley.step").write_text(
            "geometry\n", encoding="utf-8"
        )
        self.assertEqual(self._warned_paths(root), [])

        self._orphan(root / "modules" / "demo" / "modules", "stray")
        self.assertEqual(
            self._warned_paths(root),
            [str(Path("modules") / "demo" / "modules" / "stray")],
        )

    def test_adapters_group_is_not_an_orphan_but_its_children_are_checked(self):
        root = self._machine()
        adapter = root / "modules" / "adapters" / "spindle-mount-v1-to-v2"
        adapter.mkdir(parents=True)
        (adapter / "okh.toml").write_text('version = "0.1.0"\n', encoding="utf-8")
        self.assertEqual(self._warned_paths(root), [])

        self._orphan(root / "modules" / "adapters", "stray")
        self.assertEqual(
            self._warned_paths(root),
            [str(Path("modules") / "adapters" / "stray")],
        )


if __name__ == "__main__":
    unittest.main()
