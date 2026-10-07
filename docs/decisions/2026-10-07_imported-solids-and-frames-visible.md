# ADR-014 — An imported solid and a mounting frame open visible

- **Date:** 2026-10-07
- **Status:** Accepted

Write this file in B2 English. Follow `.agents/rules/communication.md`. Keep official names, file paths, and numbers exact.

## Context

A build switches on the objects it creates, so a new part does not open as an empty
screen ([log, 2026-10-01](../log/2026-10-01_new-objects-visible.md)). That rule named four
kinds of object: a Part container, a Body, an Assembly and a link. Two kinds were missing.

- A supplier's STEP file comes in as plain solids (`Part::Feature`). The rule left them as
  they were, so a wrapped supplier part opened hidden.
- A mounting frame (`Part::LocalCoordinateSystem`) owns seven axes and planes. The rule hid
  every axis and plane it saw, because it took them for the origin of a container. A frame
  without its axes shows nothing, so a designer could not see where to place it.

When a person adds a frame in the FreeCAD window, FreeCAD saves the frame and its axes
visible. A build did the opposite.

## Decision

A build shows an imported solid, and shows a mounting frame together with its axes and
planes. The origin of a Part, a Body or an Assembly stays hidden, as before. An object that
existed before the build keeps the visibility a person gave it, as before.

The rule lives in one place: `SHOWN_TYPES` in `scripts/cad_rules.py`, read by
`show_new_objects()` and `frame()` in `scripts/cad_build.py`.

## Consequences

- A supplier part wrapped by a tool, and a frame added by a tool, look the same as one made
  by hand in the window.
- A frame a person hid on purpose stays hidden on the next rebuild.
- Tools that import STEP files or add frames (the planned `doqs wrap` and
  `doqs add-interface`) rely on this rule and add nothing of their own.
