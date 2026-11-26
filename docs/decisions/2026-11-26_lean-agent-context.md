# ADR-022 — Agents read less at the start, and run commands instead of prose

- **Date:** 2026-11-26
- **Status:** Accepted

Write this file in B2 English. Follow `.agents/rules/communication.md`. Keep official names, file paths, and numbers exact.

## Context

Agents that work in a machine repository spent many tokens before they did any work.

- The rules told them to read `docs/architecture.md` before larger work. That file was 89 KB.
  Three more guides told them to read it first.
- Routines with several steps were written as prose: fill the tooling folders, get ready for a
  pull request, start a log entry. An agent had to read the text, then work out the commands.
- The same long story about the start-up hook that does not always run was written in three
  places.
- The session hook printed lines that asked the agent to read two rule files, which `CLAUDE.md`
  already loads.

At the same time, the shared agent kit (`.agents/`) is getting its own scripts for the root files,
the skill links, the mistakes index and a context budget.

## Decision

- `docs/architecture.md` is a short overview, under 8 KB, with a table of topic pages. The text
  moved to `docs/architecture/` without changes. Guides link to the one topic page they need.
- Each routine is a command:
  - `doqs doctor` says whether `.agents/` and `doqs/` are filled, and what to run when not.
  - `doqs pre-pr` saves FreeCAD work, rebuilds it headless, then runs `generate` and `check`, and
    stops at the first failure.
  - `doqs freecad save` saves the open documents with unsaved changes, inside the window.
  - `doqs log new <slug>` starts a log entry with the four report headings and adds it to the index.
  - `setup-tooling.sh --check` checks the two folders without changing anything.
- doqs calls the kit's scripts and never copies them. `doqs mistakes` and `doqs context` run them;
  `doqs check` runs the mistakes-index check and the root-file check as warnings; `doqs setup` runs
  the root-file script when the repository has a profile. When the kit has no such script yet,
  doqs prints one hint line, or nothing in `doqs check`, and carries on.
- The session hook prints two lines on success. The long story about when it does not run lives
  once, in `templates/session-hook/README.md`.

## Consequences

- An agent reads about 5 KB of architecture overview instead of 89 KB, plus one topic page when
  it needs one.
- A machine repository's CI does not change. The kit checks only warn, so a kit update cannot turn
  CI red.
- `doqs pre-pr` saves first and checks last, so the check sees what goes into the pull request.
- After `doqs pre-pr` rebuilt a document headless, the FreeCAD window still holds the copy from
  before the rebuild. The command says so. The person must close and open the document again
  before they change it.
- The kit scripts did not exist when this was written. doqs was tested with stand-in scripts that
  follow the agreed interface.
