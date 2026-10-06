# 2026-10-06 — Assemblies broke after small changes to a part

## What happened

Parts in FreeCAD assemblies jumped to wrong places, or their joints failed,
after small design changes or after a new version of a module came in. The
joints pointed at one face, edge or point of a solid, saved with a number such
as `Face6`. When the part changed, FreeCAD gave its faces new numbers, and the
joint held the wrong face or none.

## Why it went wrong

- Nothing said what a joint should attach to. Clicking a face is the quickest
  way in the Assembly workbench, so that is what people and agents did.
- A part had no fixed places for other parts to attach to. So the assembly
  depended on the inside of the solid, which changes with every edit.
- No check looked at joints. A broken assembly often shows no error, so it was
  found late, by eye.

## Prevention rule

- Give every part a named mounting frame (`IF_...`) for each place where
  another part attaches. Place it with expressions over `Params`, with
  `frame()` from `cad_build`.
- Attach every joint to a frame, or to one of its axes or planes. Never to a
  face, an edge or a point.
- Treat a frame name as part of the module's interface. Do not rename or
  remove one without a new major version.
- Read the joint warnings from `validate_cad.py` before you say an assembly
  is done.

## Related

- [ADR-013 — Assembly joints attach to named mounting frames](../decisions/2026-10-06_joints-attach-to-frames.md)
- [agent-cad.md, Joints attach to mounting frames](../agent-cad.md#joints-attach-to-mounting-frames)
