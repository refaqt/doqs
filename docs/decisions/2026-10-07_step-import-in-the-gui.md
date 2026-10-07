# ADR-017 — A STEP file is imported in the FreeCAD window, never headless

- **Date:** 2026-10-07
- **Status:** Accepted

Write this file in B2 English. Follow `.agents/rules/communication.md`. Keep official names, file paths, and numbers exact.

## Context

A supplier's STEP file carries colours per face and per body. FreeCAD keeps them only
through its GUI importer (`ImportGui.insert`). The headless importer in `FreeCADCmd` has no
view data to put them in, so a part imported headless opens grey. The parts library had
exactly this: the HIWIN block came in grey and had to be imported again by hand in the
window ([refaqt/stoq#8](https://github.com/refaqt/stoq/pull/8)).

Every other FreeCAD job doqs runs (a build, a fingerprint, a frame) works headless, and
headless is what CI has.

## Decision

- The wrapper of a library part (`doqs wrap`) runs in a FreeCAD window: the open one,
  through the RPC server of the freecad-mcp add-on on `127.0.0.1:9875`, or a window started
  for the job that imports, saves and closes itself. `FreeCADCmd` is refused for this job
  with a clear message. On a server without a screen the window runs under a virtual
  display (`xvfb-run`).
- Every other job keeps the order: the open window if it answers, then a window started for
  the job, then `FreeCADCmd`.
- A macro never decides success by the exit code. It prints `DOQS_MACRO_DONE` as its last
  act, and the caller checks the file it expected (`scripts/freecad_rules.py`).
- A job that opens a document saves it and closes it. A job that finds the document already
  open in the window edits it in memory and does not save: the person saves, as
  [agent-cad.md](../agent-cad.md) asks. The report says which happened.
- A tool must never run another FreeCAD than the one it was told to use: an explicit binary
  that does not exist is an error, not a fallback.

## Consequences

- A wrapped part looks the same as one imported by hand: colours, a Part container on top,
  visible objects and `IF_` frames at the origin.
- The machine that runs `doqs wrap` needs a FreeCAD that can open a window. CI does not run
  it; the test suite runs the generated macros against a fake FreeCAD.
- A window started for the job may show a dialog on a fresh FreeCAD profile. The open
  window is the first choice for that reason.
