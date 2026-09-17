"""Tests for the markdown link gate, including the case that broke CI.

CI checks this repository out **without** submodules, so `.agents/` is an empty
folder there. `AGENTS.md` links into `.agents/rules/*.md`. Those links are not
broken; the other repository is simply not on disk. The gate has to know that.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from validate_links import check_markdown  # noqa: E402


class TestCheckMarkdown(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-links-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = self._tmp / "repo"
        self.root.mkdir()

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_link_to_a_missing_file_is_reported(self):
        self.write("README.md", "See [the spec](docs/spec.md).\n")
        errors = check_markdown(self.root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("docs/spec.md", errors[0])

    def test_a_link_to_a_file_that_exists_is_not_reported(self):
        self.write("docs/spec.md", "# Spec\n")
        self.write("README.md", "See [the spec](docs/spec.md).\n")
        self.assertEqual(check_markdown(self.root), [])

    def test_links_into_a_tooling_submodule_are_skipped_when_it_is_missing(self):
        # This is the CI case. Neither folder exists here.
        self.write("AGENTS.md",
                   "Read [core](.agents/rules/core.md) and [arch](doqs/docs/architecture.md).\n")
        self.assertEqual(check_markdown(self.root), [])

    def test_links_into_a_tooling_submodule_are_skipped_when_it_is_present(self):
        # Same answer either way: those files belong to another repository.
        self.write(".agents/rules/core.md", "# Core\n")
        self.write("AGENTS.md", "Read [core](.agents/rules/core.md).\n")
        self.assertEqual(check_markdown(self.root), [])

    def test_markdown_inside_a_tooling_submodule_is_not_walked(self):
        self.write("doqs/README.md", "A [dangling link](nope.md).\n")
        self.assertEqual(check_markdown(self.root), [])

    def test_external_and_anchor_links_are_left_alone(self):
        self.write("README.md",
                   "[web](https://example.com) [mail](mailto:a@b.c) [here](#section)\n")
        self.assertEqual(check_markdown(self.root), [])

    def test_an_anchor_on_a_real_file_is_checked_by_path_only(self):
        self.write("docs/spec.md", "# Spec\n")
        self.write("README.md", "[part](docs/spec.md#licensing)\n")
        self.assertEqual(check_markdown(self.root), [])

    def test_the_paste_in_licence_snippet_is_skipped(self):
        # Its links resolve from a repository root, not from its own folder.
        self.write("templates/licensing/tools/README-licence-section.md",
                   "[GPL](LICENSES/GPL-3.0.txt)\n")
        self.assertEqual(check_markdown(self.root), [])


class TestThisRepository(unittest.TestCase):
    def test_every_markdown_link_in_doqs_resolves(self):
        self.assertEqual(check_markdown(_REPO), [])


if __name__ == "__main__":
    unittest.main()
