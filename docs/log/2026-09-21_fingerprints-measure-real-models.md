# 2026-09-21 — Geometry fingerprints now measure real models

**Role(s):** software

## What happened

The geometry check wrote an empty file for every model that was not a single
solid. It asked each shape for its centre of mass using a property that FreeCAD
does not offer on a compound, and a compound is what an `App::Part`, an
`App::Link`, an assembly, a PartDesign `Body` and every PartDesign feature
return. Every object failed, so every file was written with no measurements in
it and the check failed on a model that was perfectly sound.

Work done:

- The centre of mass is now read from whichever property the shape carries:
  `CenterOfMass` for a solid, a shell, a face, a wire or an edge, and
  `CenterOfGravity` for a compound. For a compound of solids the two return the
  same number, so files written by either route compare directly.
- A shape with no mass at all, such as a vertex, records nothing for that one
  field and keeps the rest of its entry. It no longer costs the whole object.
- An origin's point joins its line and its plane on the list of datum objects
  that are skipped. It was missing, so every document tried to measure its
  origin points.
- The tool now says plainly when a run measured nothing at all. Every object
  failing used to look the same as a finished file. A document that genuinely
  holds no geometry stays quiet, because that is correct.
- Twelve tests cover the measuring function. It had none: it needs FreeCAD to
  run for real, but it only reads attributes, so a stand-in shape tests it
  without one.
- `docs/agent-cad.md` explains which property covers which shape.

## Checked against real models

Five FreeCAD documents from a machine repository, measured before and after.
Before: zero objects and five recorded errors, every time. After: 25, 6, 0, 4
and 13 objects, and no errors. The document with none is a spreadsheet and has
no geometry, which is correct.

The compound fallback was checked against the volume-weighted centroid of the
solids inside each compound, on 19 objects. The two agree exactly, so the
recorded number keeps its meaning.

## Decisions

Read whichever property the shape carries, rather than picking one and hoping.
FreeCAD splits this measurement over two names by shape type, and neither name
covers everything on its own.

## Next Steps

Machine repositories pick this up with their usual tools update, then rebuild
their fingerprints once. A repository that has no fingerprints yet, because they
could never be written, gets them for the first time.

## Related

- [2026-09-21_fingerprint-measured-nothing.md](../mistakes/2026-09-21_fingerprint-measured-nothing.md)
- [agent-cad.md, Fingerprints](../agent-cad.md)
