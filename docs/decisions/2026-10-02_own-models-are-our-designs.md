# ADR-011 — An own model in a parts library is our design, and is checked like one

- **Date:** 2026-10-02
- **Status:** Accepted
- **Changes:** [ADR-004 a shared library for parts we buy](2026-09-18_parts-library.md), for `cad/own/` only
- **Works with:** [ADR-009 a fixed method for taking in a supplier's files](2026-09-29_component-intake.md)

## Context

ADR-004 says the CAD check skips a parts library. Its files come from brands,
there is no build script behind them, and a checksum in `vendor-index.csv`
already proves each file is unchanged.

ADR-009 then added `cad/own/`: models we draw ourselves from the catalogue,
when the brand's own file may not be shared. Those models are ours. They have a
build script, and they are meant to replace the brand's model in an assembly.
The CAD check still skipped them, because it skipped the whole library.

The first own models in the library were wrong in ways nothing could see: other
axes than the brand model, an optional unit on one end, table dimensions left
out, features that stick out of the part left out, and a model saved again by
hand after its build.

## Decision

1. The CAD check skips the brand's files in a library, as before, but checks
   every `cad/own/<pn>.FCStd` like a part in a machine: a build script
   `<pn>.build.py`, a parameter file `<pn>.params.csv`, a fingerprint from a
   saved build that matches the file, a Part container on top, and no FreeCAD
   backups or Python caches in git.
2. Several own models share one `cad/own/` folder. Each file carries the part
   number in its name, and the build reads the name of its script to know which
   model it builds.
3. Before modelling, `<pn>.features.csv` lists every feature: what the table
   sizes, what the figure shows without a size, and what only the text names.
   A feature that sticks out of the part may never be left out.
4. Every value says where it came from: `catalogue`, `estimated` (read off a
   figure, a placeholder only) or `measured` (on a real part, by a named person,
   on a date).
5. An own model uses the same axes and origin as the brand model. Its build
   script states them in `AXES`, and its check list holds the overall size
   along each axis and its mirror planes.
6. `doqs compare-own` compares the two models in a separate FreeCAD run and
   turns every measurement into words inside that run. Only pass, fail,
   not-confirmed and the method reach our files. `compare_` joins the script
   naming contract as an eighth verb.

## Consequences

A library whose own models were made before this decision fails `doqs check`
until each model has a build script, a parameter file, a feature list, a
fingerprint, and a check list in the new shape. That is the point: the models
were not checked before.

The comparison needs FreeCAD and the private library, so it does not run in CI.
CI checks only that the record is complete and that no `pass` lacks a method.
