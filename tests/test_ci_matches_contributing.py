"""CI and CONTRIBUTING.md must list the same commands, in the same order.

The two drifted apart before: CONTRIBUTING.md carried a licence check CI never
ran, and CI ran a parameter check CONTRIBUTING.md never mentioned. A reader
then cannot tell which list is real. This test makes the question decidable.
"""
import re
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_CI = _REPO / ".github" / "workflows" / "ci.yml"
_CONTRIBUTING = _REPO / "CONTRIBUTING.md"

#: The fenced block under this heading holds the developer command list.
_HEADING = "## Developing doqs itself"


def ci_commands() -> list[str]:
    """Every `python ...` line a CI step runs, in file order."""
    lines = _CI.read_text(encoding="utf-8").splitlines()
    return [stripped for line in lines
            if (stripped := line.strip().removeprefix("run: ")).startswith("python ")]


def contributing_commands() -> list[str]:
    """Every `python ...` line in the first fenced block after the heading."""
    text = _CONTRIBUTING.read_text(encoding="utf-8")
    start = text.index(_HEADING)
    block = re.search(r"```[a-z]*\n(.*?)```", text[start:], re.DOTALL)
    assert block, f"no fenced command block under {_HEADING!r}"
    return [line.strip() for line in block.group(1).splitlines()
            if line.strip().startswith("python ")]


class TestCiMatchesContributing(unittest.TestCase):
    def test_lists_are_identical(self):
        ci = ci_commands()
        contributing = contributing_commands()
        self.assertEqual(
            contributing, ci,
            "CONTRIBUTING.md and .github/workflows/ci.yml list different commands. "
            "Add the command to both, in the same order.",
        )

    def test_lists_are_not_empty(self):
        # A parsing change that silently matched nothing would make the first
        # test pass for the wrong reason.
        self.assertGreaterEqual(len(ci_commands()), 10)


if __name__ == "__main__":
    unittest.main()
