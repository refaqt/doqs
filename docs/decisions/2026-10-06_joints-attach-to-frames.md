# ADR-013 — Assembly joints attach to named mounting frames

- **Date:** 2026-10-06
- **Status:** Accepted
- **Works with:** [ADR-002 master sketches live in a separate Body](2026-06-24_freecad-master-sketches-body.md),
  [ADR-010 a part has a Part container on top](2026-10-01_part-container-on-top.md),
  [ADR-012 every dimension has a reason](2026-10-06_every-dimension-has-a-source.md)

## Context

Assemblies broke too often after small design changes. A joint in the FreeCAD
Assembly workbench usually points at one face, edge or point of a solid, saved
with a number such as `Face6`. FreeCAD 1.0 and later keep these numbers more
stable than before, but they still change when a feature is added, removed or
moved in the history. A supplier part imported again from a STEP file has no
history at all, so all its numbers can change. The joint then holds the wrong
face, or no face, and the part jumps to a wrong place. Often nothing reports
an error.

We also want the opposite effect: when a hole pattern or a mounting face moves
on purpose, the parts fastened to it should follow.

Three ways were compared:

| Way | Survives a changed solid | Follows a designed change | Shows motion |
| --- | --- | --- | --- |
| Joint on a face, an edge or a point | No | Yes, while the number holds | Yes |
| Placement typed or driven by expressions | Yes | Only if the expression is right | No |
| Joint on a named mounting frame | Yes | Yes | Yes |

A FreeCAD bug once made joints on the axis of a coordinate system turn around
the wrong axis ([FreeCAD issue 24938](https://github.com/FreeCAD/FreeCAD/issues/24938)).
The issue is closed, and the user tested it on 2026-10-06 in their FreeCAD 1.1
build: the joints behaved correctly.

## Decision

1. **Each part carries mounting frames.** A mounting frame is a named
   coordinate system (`Part::LocalCoordinateSystem`) inside the part's Part
   container, one for each place where another part attaches. Its label starts
   with `IF_` (interface), like `IF_mount_bottom` or `IF_rail_A`.
2. **A frame is placed by expressions over `Params`**, from the same values
   that place the holes or the face it stands for. It is never attached to a
   face of the solid. So a designed change moves the frame, and an unplanned
   change in face numbers does not. The rule of ADR-012 applies: no typed
   numbers in its placement.
3. **Joints attach to frames only**, to the whole frame or to one of its axes
   or planes. Never to a face, an edge or a point of a solid. A joint offset,
   if one is needed, is an expression over `Params` as well.
4. **Supplier parts get their frames in our part file** that holds the
   supplier geometry, placed from catalogue values. A new STEP file then
   changes nothing in the assemblies.
5. **Frame names are part of a module's interface.** Adding a frame is safe.
   Renaming or removing one breaks every assembly that uses it, so it is a
   breaking change and needs a new major version of the module.
6. **Placement by expression is the exception**, for a part that never moves
   and has no joint. Even then it reads the placement of a frame, and it is
   never mixed with joints on the same part.
7. **Checked, warn now and fail later.** `validate_cad.py` reads every joint
   from the saved file and reports each one that uses a face, an edge or a
   point. It is a warning; `--strict-parametric` makes it a failure, the same
   switch as ADR-012. `cad_build.frame()` creates a frame the right way, and the
   fingerprint now also checks the placement of a frame for typed numbers.

## Consequences

- A machine repository that updates doqs keeps passing. It sees a warning for
  every joint on a face, an edge or a point. Each one needs a frame in the part
  and the joint moved to it. Then its CI can add `--strict-parametric`.
- The check reads the joint properties `Reference1` and `Reference2` as FreeCAD
  1.1 saves them. If a later FreeCAD release renames them, the check finds no
  joints and stays quiet. Check it against a real assembly when FreeCAD
  changes, and test a joint on a frame axis again after each FreeCAD update.
- A part file gets a few more objects. They are small and hidden in the tree
  under the Part container.
