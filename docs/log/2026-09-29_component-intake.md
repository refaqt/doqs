# 2026-09-29 — Taking in a supplier's files now follows fixed rules

**Role(s):** software

## What happened

A parts library could only say "we may publish this file" or "we store the
address". The checks now support a full method for taking in a new part.

Work done:

- Each brand records a dated licence decision for its geometry and for its
  documentation, with the name of the person who approved it and a saved copy of
  the terms. A shared file fails the check without such a decision.
- Two new sharing values: `private` for a file with no public address, and
  `own-model` for a model we drew ourselves from the datasheet.
- Our own models live in `cad/own/`, carry CC BY-SA 4.0, and need a check list
  that names the datasheet page for every dimension.
- A check fails if git tracks a file we may not share.
- A new command, `doqs restore-private`, copies those files from the private
  library into place and checks each checksum first.
- `docs/parts-library.md`, `docs/using-doqs.md` and the library templates
  describe all of it. 32 new tests cover it.

## Decisions

See [ADR-009](../decisions/2026-09-29_component-intake.md). The command is
called `restore-private`, not `private-sync`, because every script name starts
with one of a fixed set of verbs, and it does the same kind of work as
`restore-build`.

## Next Steps

`stoq` adopts this in its own pull request: the written method, the reviews for
HIWIN and MAXWELL, and the private library layout. A FreeCAD script that fills
in the pass or fail results of a check list comes later.

## Related

- [ADR-009](../decisions/2026-09-29_component-intake.md)
- [parts-library.md, Taking in a supplier's files](../parts-library.md#taking-in-a-suppliers-files)
