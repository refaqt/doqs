"""`docs/using-doqs.md` must list the same commands as `doqs list`.

The command list was the thing people could not find: there were thirteen partial
lists and no canonical one. Now there is one page and one command, and this test
keeps them saying the same thing.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import cli  # noqa: E402

_PAGE = _REPO / "docs" / "using-doqs.md"


def documented_commands() -> set[str]:
    """The first column of the command table in section 4, as bare names."""
    text = _PAGE.read_text(encoding="utf-8")
    start = text.index("## 4. The commands")
    end = text.index("### What each gate checks")
    names = set()
    for row in re.findall(r"^\| `doqs ([^`]+)`", text[start:end], re.MULTILINE):
        names.add(row.split()[0])
    return names


class TestPageMatchesCli(unittest.TestCase):
    def test_every_command_is_documented(self):
        expected = {"check", "generate", "setup", "run", "list"} | set(cli.PASSTHROUGH)
        self.assertEqual(documented_commands(), expected)

    def test_the_page_exists_and_is_not_a_stub(self):
        self.assertGreater(len(_PAGE.read_text(encoding="utf-8").splitlines()), 120)

    def test_the_freecad_scripts_are_named_on_the_page(self):
        # They can never be subcommands, so the page has to say where they live.
        text = _PAGE.read_text(encoding="utf-8")
        for name, _ in cli.FREECAD_ONLY:
            self.assertIn(name, text, f"{name} is not named in using-doqs.md")

    def test_the_page_names_both_marker_files(self):
        # The hook cannot start itself in every session, so the page has to say
        # which two files prove the tooling folders are really filled.
        text = _PAGE.read_text(encoding="utf-8")
        for marker in (".agents/rules/core.md", "doqs/scripts/validate_all.py"):
            self.assertIn(marker, text, f"{marker} is not named in using-doqs.md")

    def test_the_deleted_agent_guide_is_not_linked_anywhere(self):
        # Naming the file in prose is fine, and the migration note has to. A
        # link to it is not: the file is gone.
        link_to_guide = re.compile(r"\]\([^)]*agent-guide\.md[^)]*\)")
        for md in _REPO.rglob("*.md"):
            if ".agents" in md.parts or ".git" in md.parts:
                continue
            self.assertIsNone(
                link_to_guide.search(md.read_text(encoding="utf-8")),
                f"{md.relative_to(_REPO)} still links to the deleted agent guide",
            )


if __name__ == "__main__":
    unittest.main()
