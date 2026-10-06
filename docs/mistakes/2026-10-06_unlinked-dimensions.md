# 2026-10-06 — Models had typed numbers and sketches that could still move

## What happened

Agents built FreeCAD models that looked right but were not parametric.

- Some sketches were not fully constrained. A point or a line could still move.
- Many dimensions were typed numbers. They were not linked to the parameter
  sheet, to another dimension, or to any reason.
- A row of 8 holes got 7 typed spacings. To change the pitch, someone had to
  change 7 numbers, and nothing showed that the 7 belonged together.

## Why it went wrong

- The guidance only said "prefer" the parameter sheet. Typing a number was
  shorter, so agents did that.
- Nothing asked where a value comes from. A parameter row had no place for its
  reason.
- No check looked inside a model for free sketches or typed numbers. The
  fingerprint measured the shape, not how the shape was built.

## Prevention rule

- Before you draw, write the parameter table. Mark each value as independent
  (with a reason: requirement, supplier part, standard, simulation or design
  choice) or derived (a formula). Ask the user before you invent a design value.
- Fully constrain every sketch. Drive every dimension and every feature size by
  an expression over `Params`. Use `dim()` and `bind()` from `cad_build`.
- Draw a repeated feature once and pattern it from a count and a pitch.
- Read the build output and the fingerprint's `parametric` section before you
  say a model is done. An empty list is the goal.

## Related

- [ADR-012 — Every dimension has a reason](../decisions/2026-10-06_every-dimension-has-a-source.md)
- [agent-cad.md, Every dimension has a reason](../agent-cad.md#every-dimension-has-a-reason)
