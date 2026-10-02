# 2026-10-02 — Our own models in a parts library are now checked

**Role(s):** software

## What happened

Models we draw ourselves in a parts library are now checked like our other
parts. Before, the checks skipped them, and wrong models of a HIWIN rail and
block got through. The incident is in
[the mistake log](../mistakes/2026-10-02_own-models-were-not-checked.md).

Work done:

- The headless rebuild works under FreeCAD 1.1. A run that builds nothing now
  prints an error and exits 1, and the check fails a build script with the old
  ending.
- Each own model needs a build script that states its axes, a parameter file,
  a current fingerprint from a saved build, a Part container on top, a feature
  list and a check list. Several models can share one folder.
- Every value says whether it comes from the catalogue, from a figure, or from
  a measurement of a real part.
- A pass in the check list needs a method, and the list must hold the overall
  size along each axis and the mirror planes.
- `doqs unshare` takes files out of git when their terms change, after it checks
  that the private library holds the same file.
- `doqs compare-own` compares an own model with the brand's model in a separate
  FreeCAD run, and writes only results and methods.
- 66 new tests. The comparison and the build are tested against a fake FreeCAD,
  not a real one.

## Decisions

See [ADR-011](../decisions/2026-10-02_own-models-are-our-designs.md).

## Next Steps

The own models in `stoq` fail `doqs check` after the next tools update, until
each has its new files. Then run `doqs compare-own` on each with a real FreeCAD.

## Related

- [parts-library.md, Our own models](../parts-library.md#our-own-models)
- [agent-cad.md, The last line of a build script](../agent-cad.md#the-last-line-of-a-build-script)
