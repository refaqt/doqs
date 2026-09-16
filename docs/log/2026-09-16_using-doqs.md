# 2026-09-16 — One page for people who use doqs

**Role(s):** software

## What happened

The install story was told **six times**, in four wordings. The only complete
version sat in `templates/setup-tooling/README.md`, and nothing linked to it.
There was no canonical command list: thirteen partial ones, none marked as the
real one.

New page: [`docs/using-doqs.md`](../using-doqs.md), for someone working in a machine
repository. Eleven sections: the one command, how to add doqs to a repository,
what happens every session, the command table, what to do before a pull request,
the CI snippet, which doqs page to read for which job, **what doqs puts in your
repository**, working in FreeCAD, troubleshooting, and where to change what.

Section 8 is the direct answer to "what should be copied and what for". Every
template, where it lands, and who puts it there: overwritten by the installer,
written once, or copied by hand. Three rules follow from the table, and they are
written out: a launcher is doqs's file, `.mcp.json` and `.claude/settings.json` are
yours, and `build_model.py` is a seed you copy per module.

## What shrank

- **`docs/agent-guide.md` is deleted.** It duplicated README, CONTRIBUTING and
  architecture. It also opened with "# Agent reference" while `AGENTS.md` opened
  with "# Agent guide", which is what made the two impossible to tell apart. Its
  two good tables — which page to read, and where to change what — moved to the
  new page.
- **`CONTRIBUTING.md`: 127 lines to 53.** The machine-repo workflow, the gate table
  and the submodule instructions moved out. What is left is about developing doqs.
- **`AGENTS.md` is now "Working on doqs — agent instructions"** and says in its
  first lines that using doqs in a machine repository is a different job, with the
  link.
- **`docs/architecture.md`** loses the sixth copy of the install story; it links
  instead and keeps only the two rules that belong at that level.

New: [`docs/migration-2026-09.md`](../migration-2026-09.md), four short sections on
what a machine repository has to do. The answer is close to nothing: the only
breaking change is the deleted page.

## Two new gates on ourselves

- `check_links.py --markdown` checks relative markdown links. **Off by default**,
  so no machine repository goes red on a pin bump. doqs CI turns it on, which is
  what proves the deleted page left no dangling link behind. It skips
  `templates/licensing/tools/README-licence-section.md`, whose links resolve from a
  repository root because that file is meant to be pasted into one.
- `tests/test_using_doqs_doc.py` asserts the command table matches `doqs list`,
  that the three FreeCAD scripts are named on the page, and that nothing links to
  the deleted guide.

## Numbers

244 tests pass, up from 240. `CONTRIBUTING.md` is 74 lines shorter.

## Next Steps

Step 4: the session-hook seed in `templates/`, and the `.claude/settings.json`
merge, so a repository that gets the hook also gets it registered.
