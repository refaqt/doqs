"""The three renamed scripts, and the rule the names follow.

A stub that exits 0 is how a repository quietly stops running a gate. These
must fail, and must say what to run instead.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"

#: old name -> new name. The stubs go away after 2026-12-16.
RENAMED = {
    "check_names.py": "validate_names.py",
    "check_links.py": "validate_links.py",
    "build_graph.py": "resolve_graph.py",
}

#: Names that may never move, because a copy-once file in every consumer
#: repository calls them by name and no update can reach it.
FROZEN = {
    "install_root_tools.py": "named inside setup-tooling.sh at every consumer root",
    "cad_build.py": "found by filename in templates/cad/build_model.py:29",
}


class TestStubs(unittest.TestCase):
    def test_each_old_name_exits_two_and_names_its_replacement(self):
        for old, new in RENAMED.items():
            with self.subTest(old=old):
                result = subprocess.run(
                    [sys.executable, str(_SCRIPTS / old)],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(new, result.stderr)
                self.assertIn("doqs.py", result.stderr)

    def test_the_new_names_exist(self):
        for new in RENAMED.values():
            self.assertTrue((_SCRIPTS / new).is_file(), new)

    def test_a_stub_carries_no_logic(self):
        # If someone ever pastes real code back into a stub, this catches it.
        for old in RENAMED:
            text = (_SCRIPTS / old).read_text(encoding="utf-8")
            self.assertLess(len(text.splitlines()), 25, old)
            self.assertNotIn("argparse", text)


class TestNamingRule(unittest.TestCase):
    """Every command script starts with one of the contract verbs."""

    VERBS = ("validate_", "resolve_", "apply_", "aggregate_", "export_",
             "install_", "restore_")

    def command_scripts(self) -> list[Path]:
        skip = set(RENAMED) | {"cli.py", "syson.py"}
        found = []
        for path in sorted(_SCRIPTS.glob("*.py")):
            if path.name in skip or path.name.endswith("_rules.py"):
                continue
            if path.name.startswith("cad_"):
                continue  # the sanctioned exception: it runs inside FreeCAD
            if "__main__" in path.read_text(encoding="utf-8"):
                found.append(path)
        return found

    def test_every_command_script_uses_one_of_the_verbs(self):
        for path in self.command_scripts():
            with self.subTest(script=path.name):
                self.assertTrue(
                    path.name.startswith(self.VERBS),
                    f"{path.name} starts with none of {self.VERBS}",
                )

    def test_libraries_are_named_rules_or_are_the_cad_exception(self):
        for path in sorted(_SCRIPTS.glob("*.py")):
            # A stub has no __main__ block either, and it is not a library.
            if path.name in RENAMED or path.name == "cli.py":
                continue
            if "__main__" in path.read_text(encoding="utf-8"):
                continue
            with self.subTest(script=path.name):
                self.assertTrue(
                    path.name.endswith("_rules.py") or path.name.startswith("cad_"),
                    f"{path.name} is a library, so it should be <topic>_rules.py",
                )

    def test_the_frozen_names_are_still_there(self):
        for name, why in FROZEN.items():
            self.assertTrue((_SCRIPTS / name).is_file(), f"{name} may not move: {why}")

    def test_build_model_still_finds_the_scripts_folder(self):
        # The seed locates doqs/scripts/ by testing for this exact filename.
        seed = (_REPO / "templates" / "cad" / "build_model.py").read_text(encoding="utf-8")
        self.assertIn("cad_build.py", seed)

    def test_setup_tooling_still_calls_the_installer_by_name(self):
        for helper in ("setup-tooling.sh", "setup-tooling.bat"):
            text = (_REPO / "templates" / "setup-tooling" / helper).read_text(encoding="utf-8")
            self.assertIn("install_root_tools.py", text, helper)


if __name__ == "__main__":
    unittest.main()
