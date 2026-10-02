# 2026-10-02 — Our own models of a rail and a block were wrong, and no check saw it

## What happened

In the parts library, an agent drew our own models of a HIWIN rail and block
from the catalogue, because the brand's own file may not be shared. The first
versions were wrong in many ways at once:

- The block had an optional lubrication unit on one end. The part number did not
  ask for it.
- The models used other axes than the brand's model, so ours could not take its
  place in an assembly.
- The agent built them by hand in the GUI. There was no build script to rebuild
  or review.
- Seven dimensions from the catalogue table were left out.
- Every feature the figure shows without a size was left out: the reference
  edge, the end caps, the grease nipple, the heads of the seal screws, the plug
  and the ports. Some of these stick out of the part, so an assembly would miss
  a collision.
- The catalogue figure is drawn for size 25 and used for every size. Sizes read
  off it for size 20 were wrong.
- The comparison with the brand's model called a length a pass after it left
  out the end seals, which the catalogue length includes.
- A model was saved again after its build. Nothing noticed.

doqs caught none of it. Its checks skipped the whole parts library, own models
included. One more gap sat beside it: under FreeCAD 1.1, the headless command
that rebuilds a model silently built nothing, so a rebuild could not be trusted
either.

## Why it went wrong

1. The rule "a parts library holds supplier files, so skip its CAD" was written
   before own models existed. When own models arrived, nobody asked whether that
   rule still fit them. It did not: they are our designs.
2. The check list only asked for dimensions the agent chose to list. Nothing
   asked for the features the agent did not list, and those are the ones that
   matter: the unsized ones, and the ones that stick out.
3. A value read off a figure looked the same as a value from a table. Nothing
   recorded where a value came from, so nobody could see which values were
   guesses.
4. The comparison did not say how it measured, so "pass" could mean anything.
5. FreeCADCmd 1.1 sets `__name__` to the file name, not `"__main__"`. The build
   template still used `if __name__ == "__main__":`. The run exited 0 with no
   output, and silence looked like success.

## Prevention rule

1. **A check that skips a folder must say why, and the reason must still fit
   everything in that folder.** When a new kind of file moves into a skipped
   folder, review the skip. Own models are now checked like any part of ours:
   a build script, parameters, a current fingerprint from a saved build, a Part
   on top, and no backups or caches in git.
2. **List features before modelling.** `<pn>.features.csv` names every table
   dimension and every feature the figure shows. A feature that sticks out of
   the part may never be left out.
3. **Every value says where it came from:** catalogue, estimated or measured.
   An estimate is a placeholder. Check a figure's scale against several sized
   dimensions before you read anything off it.
4. **A pass needs a method.** The check list must hold the overall size along
   each axis, as the catalogue defines it, and the part's mirror planes.
5. **A run that did nothing must fail loudly.** A build script ends with
   `main(build, globals())`. A headless run that finishes no build prints an
   error and exits 1, and `doqs check` fails a script with the old ending.

Tests in [`tests/test_own_models.py`](../../tests/test_own_models.py) cover each
rule.

## Related

- [ADR-011 — An own model in a parts library is our design](../decisions/2026-10-02_own-models-are-our-designs.md)
- [parts-library.md, Our own models](../parts-library.md#our-own-models)
- [agent-cad.md, The last line of a build script](../agent-cad.md#the-last-line-of-a-build-script)
- [2026-09-21_fingerprint-measured-nothing.md](2026-09-21_fingerprint-measured-nothing.md) — the same lesson: a tool that does nothing must say so
