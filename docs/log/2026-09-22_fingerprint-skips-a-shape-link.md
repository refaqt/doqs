# 2026-09-22 — An analysis mesh no longer blocks a document

**Role(s):** software

## What happened

Three FreeCAD documents in the qarve machine repository could not be measured.
Each one holds a stress analysis, and an analysis mesh keeps a link to the part
it was built from under the same property name that a solid uses for its
geometry. The tool treated that link as geometry, the call failed, and the whole
document was lost instead of the one object.

Work done:

- The tool now measures an object only when the value it holds can answer a
  shape's question. A link to another object is skipped, whatever type holds it.
- Three tests cover this: a mesh next to a part, a document where the mesh comes
  first, and an object with no shape at all. They need no FreeCAD to run.
- `docs/agent-cad.md` says which objects are skipped and why.

## Checked against real models

The three documents that failed were measured again after the change. They
record 3, 4 and 6 objects, and no errors. Before the change each one recorded
nothing and stopped with an error. The meshes themselves are not measured, which
is correct: a mesh is a result of an analysis, not geometry the design owns.

## Decisions

Skip by ability, not by type name. A list of mesh types would need a new entry
every time FreeCAD adds one, and the same trap exists wherever a property called
`Shape` points at an object rather than geometry.

## Next Steps

Machine repositories pick this up with their usual tools update. A repository
whose analysis documents had no fingerprint gets one on the next run.

## Related

- [2026-09-22_fingerprint-shape-that-is-not-a-shape.md](../mistakes/2026-09-22_fingerprint-shape-that-is-not-a-shape.md)
- [agent-cad.md, Fingerprints](../agent-cad.md)
