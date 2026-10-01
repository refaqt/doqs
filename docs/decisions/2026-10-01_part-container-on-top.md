# ADR-010 — A part has a Part container on top, not a Body

- **Date:** 2026-10-01
- **Status:** Accepted
- **Works with:** [ADR-002 master sketches live in a separate Body](2026-06-24_freecad-master-sketches-body.md)

## Context

Agents create FreeCAD parts through a module's `cad/build_model.py`. Nothing told
them how to arrange the model tree, so they often put a `PartDesign::Body` at the
top of the document.

An Assembly inserts and places a part as one object. The FreeCAD object made for
that job is the Part container (`App::Part`). A part with a bare Body on top must
be wrapped by hand before it fits into an assembly. It is also the first thing
people check when a part does not show up in the Assembly insert list (see
ADR-002).

## Decision

1. In a **part document**, the top object of the tree is a Part container. Every
   Body sits inside a Part, directly or inside a group in that Part.
2. `cad_build` gives agents two helpers. `part(doc)` returns the Part container
   and creates it if it is missing. `body(doc)` returns a Body inside it. A rerun
   reuses both. A Body found at the top is moved into the Part.
3. The rule fails, it does not warn. `run()` stops the build and undoes it when a
   Body is left outside a Part. `validate_cad.py` fails a committed part document
   with a Body outside a Part.
4. **Assembly documents are exempt.** A document under `cad/assemblies/`, or a
   document that holds an `Assembly::AssemblyObject`, keeps the ADR-002 layout:
   master sketches in a Body inside a plain group.

## Consequences

A machine repository with an older part that has a Body on top fails the CAD
check after the next tools update. The fix is one rebuild with `body(doc)`, or a
manual move of the Body into a new Part container. The geometry does not change.

The CAD check reads the model tree from the saved file. It needs no FreeCAD, so
it runs in CI. A file that is not a readable FreeCAD document is not checked,
the same as the link check.
