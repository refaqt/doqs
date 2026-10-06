# 2026-10-06 — The shared agent kit moves to its newest version

**Role(s):** software

## What happened

This repository uses a shared agent kit, a second repository mounted at
`.agents/`. It holds the writing rules and skills that every Refaqt repository
follows. The version this repository pointed at was from 18 September. It now
points at the newest one.

The new version brings these changes:

- Reports must say what is true now, and where. A change that is only on a
  branch must not be called "fixed" or "removed".
- Work is done only when the result was checked against the real thing, not
  only against the source it was built from. A test must not change the files
  it checks.
- When work starts from a source document, the agent first lists every value in
  it and marks every estimate as an estimate.
- A helper agent's "pass" is not trusted until it is clear how it measured.
- The FreeCAD skill gained several rules: new parts open visible, every part
  sits in a Part container, supplier models are checked against the real part,
  and every dimension is linked to a named value.
- The setup guide for other repositories explains how to check that the kit is
  really there, because the start-up hook can stay silent.

Work done:

- The pointer to the shared agent kit was moved to the newest version and
  saved.
- All project checks and all tests were run against the new version.

## Decisions

The kit now ships a newer start-up hook template. doqs keeps its own hook. The
template is meant for repositories that do not use doqs.

## Next Steps

None. The two license checks that fail when you run the checks in this
repository failed in the same way before the update. They expect the files of a
machine repository.

## Related

- [The shared agent kit moves to its newest version](2026-09-18_agent-kit-update.md)
- [Validators skip the agent kit](2026-09-16_tooling-submodule-skip.md)
