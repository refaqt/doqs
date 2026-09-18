# 2026-09-18 — The shared agent kit moves to its newest version

**Role(s):** software

## What happened

This repository uses a shared agent kit, a second repository mounted at
`.agents/`. It holds the writing rules and skills that every Refaqt repository
follows. The version this repository pointed at was a few weeks old. It now
points at the newest one.

The main thing the new version brings is a rule for reporting work. Pull
requests, commit messages, comments on GitHub and log entries now have one
fixed shape, written for a manager rather than for a developer. The rule gives
four standard headings and asks for the technical detail in one closed block at
the end. The rule itself is
[`.agents/rules/reporting.md`](../../.agents/rules/reporting.md).

The new version also carries a short installation guide for the kit, a few
setup templates for repositories that do not use doqs, and small wording fixes
in the language rule.

Work done:

- The pointer to the shared agent kit was moved to the newest version and
  saved.
- All project checks were run against the new version. Nothing broke.

## Decisions

Only the pointer was changed. The new reporting rule asks a repository to copy
a pull request template into its own `.github/` folder. This repository does
not have that template yet. Adding it is a separate choice, so it was left for
a later change.

## Next Steps

From now on, write pull requests, commit messages and log entries in the shape
the reporting rule gives. Anyone who wants the pull request box on GitHub to
start with those headings can copy the template the kit ships.

## Related

- [The session hook is a template now](2026-09-16_session-hook-seed.md)
- [Validators skip the agent kit](2026-09-16_tooling-submodule-skip.md)
