# 2026-09-21 — The geometry check measured nothing, and said so quietly

## What happened

A fingerprint records what a model measures, so an agent can check its own work
and so the build server catches geometry that moved. Since the tool was written,
it produced an empty file for every real model.

It asked each shape for `CenterOfMass`. FreeCAD offers that property on a solid,
a shell, a face, a wire and an edge. It does not offer it on a compound — and a
compound is what an `App::Part`, an `App::Link`, an assembly, a PartDesign
`Body` and every PartDesign feature hand back. In other words, almost every
object in a real document.

Reading the missing property raised an error. The caller caught it, wrote the
error into the file, and moved to the next object. Every object failed the same
way, so the file was written with zero measurements and one error per object.
Nothing crashed and nothing said "this tool does not work".

A second, smaller fault sat beside it. The list of datum objects to skip named
an origin's line and its plane but not its point. Every document therefore also
tried to measure its origin points, which are vertices and have no mass either.

The first machine repository to commit a real model hit it at once: five
documents, five empty files, five failing checks, and no way to fix it from
inside that repository.

## Why it went wrong

The tool was only ever exercised against a single solid. A solid is the one
shape that has the property it asked for. Nothing in the test suite touched the
measuring function at all, because it needs FreeCAD and the tests run without
it.

The error handling then hid the result. Catching a failure per object is right —
one broken feature should not lose the whole document. But nothing asked the
obvious question afterwards: *every* object failed, so the file is empty, so the
measurement is worthless. An empty result was written and reported as a written
file.

## Prevention rule

Two rules.

1. **A tool that measures must fail loudly when it measures nothing.** Catching
   an error per item is fine. Writing a file with zero items and calling it done
   is not. `measured_nothing()` in
   [`scripts/cad_rules.py`](../../scripts/cad_rules.py) now decides this, and
   the tool prints an error telling you not to commit the result. A document
   that genuinely holds no geometry stays quiet.
2. **Test the shape types the tool will actually meet, not the easy one.** The
   measuring function needs no FreeCAD to test: it reads attributes off an
   object. Twelve tests in
   [`tests/test_cad_build.py`](../../tests/test_cad_build.py) now cover a solid,
   a compound, a shape with both properties and a shape with neither, plus the
   full list of datum types that must and must not be skipped.

## Related

- [2026-09-21_fingerprints-measure-real-models.md](../log/2026-09-21_fingerprints-measure-real-models.md)
- [agent-cad.md, Fingerprints](../agent-cad.md)
