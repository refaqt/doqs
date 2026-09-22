# 2026-09-22 — One mesh object cost a whole document its measurements

## What happened

The geometry check reads every object in a FreeCAD document and measures the
shape it holds. Three documents in the qarve machine repository could not be
measured at all. Each of them failed on the same thing: an analysis mesh.

A mesh object keeps a `Shape` property, but it does not hold geometry. It holds
a link to the part the mesh was built from. Asking that link a question that
only a shape can answer raised an error. The error happened while the tool was
still listing the objects to measure, so the error handling further down never
saw it. One mesh object therefore lost the whole document, and the machine
repository could not pass its checks.

Two FreeCAD types do this and both are ordinary: `Fem::FemMeshShapeNetgenObject`
and `Fem::FemMeshShapeBaseObjectPython`. Any document with a stress analysis in
it has one.

## Why it went wrong

The tool decided what to measure by asking whether an object has a `Shape`. That
question looks safe and is not. In FreeCAD a property name does not promise a
type, and `Shape` is a name two different kinds of object use for two different
things.

The error handling made it worse. The tool catches a failure for each object, so
one broken feature cannot lose the rest. But the listing of objects sits outside
that protection. A failure there is not one object lost, it is all of them, and
nothing was watching for it.

This is the second fault of the same shape in the same function. The first one
([2026-09-21](2026-09-21_fingerprint-measured-nothing.md)) assumed every shape
carries the same centre-of-mass property. This one assumes every `Shape` is a
shape. Both were found by a real machine repository, not by the tests.

## Prevention rule

1. **Ask for the ability, not for the name.** Before measuring, check that the
   value can answer a shape's question. A property name is not a type.
2. **Nothing may raise while the work is being listed.** Error handling that
   protects one item is worth nothing if the loop that produces the items can
   fail first. Keep the listing simple enough that it cannot.
3. **The test suite must hold the object types a real document contains.**
   Analysis meshes, links and spreadsheets all live next to the parts, and the
   measuring function needs no FreeCAD to test.

## Related

- [2026-09-21_fingerprint-measured-nothing.md](2026-09-21_fingerprint-measured-nothing.md)
- [2026-09-22_fingerprint-skips-a-shape-link.md](../log/2026-09-22_fingerprint-skips-a-shape-link.md)
- [agent-cad.md, Fingerprints](../agent-cad.md)
