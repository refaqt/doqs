"""Rebuild this part's geometry from `cad/params.csv`, in the GUI or headless.

Copy this file to `<module>/cad/build_model.py` and replace `build()` with your
part.  This file is the reviewable artefact in a pull request: a text diff,
where the `.FCStd` beside it is an opaque binary blob.

The scaffolding — transactions, save discipline, fingerprinting — lives in
`doqs/scripts/cad_build.py` and updates with the submodule.  Do not copy it
here.  Run headless with:

    FreeCADCmd cad/build_model.py

A good run ends with "Rebuilt and saved <document>".  A run that built nothing
prints an ERROR and exits 1.

See `doqs/docs/agent-cad.md` for why the interactive path never saves.
"""

import sys
from pathlib import Path

try:
    _HERE = Path(__file__).resolve().parent
except NameError:  # exec()'d from the FreeCAD console
    _HERE = Path.cwd() / "cad"


def _doqs_scripts(start):
    """Find `doqs/scripts/` by walking up from this module's `cad/`."""
    for base in [start, *start.parents]:
        candidate = base / "doqs" / "scripts"
        if (candidate / "cad_build.py").is_file():
            return candidate
    raise RuntimeError(
        f"doqs/scripts/cad_build.py not found above {start} — "
        "run from inside a machine repository with the doqs submodule checked out."
    )


sys.path.insert(0, str(_doqs_scripts(_HERE)))

from cad_build import bind, body, dim, frame, main, part, sheet  # noqa: E402


def build(doc, params):
    """Rebuild this part's geometry from `params`.

    `params` is `{alias: value}` read from `cad/params.csv`.  `sheet(doc)`
    returns the `Params` Spreadsheet that holds the same values.

    Every dimension has a reason.  An independent value is a row in
    `cad/params/default.csv` with a `basis` and a `source` (a requirement, a
    supplier part, a standard, a simulation or a design choice).  Everything
    else follows from those rows by a formula.  So in this file:

    * Fully constrain every sketch: nothing may move.  Use relations first
      (coincident, equal, symmetric, horizontal), then dimensions.
    * Never type a number into a dimension.  Add it with
      `dim(sketch, constraint, "Params.<alias>")`, and drive feature sizes
      with `bind(feature, "Length", "Params.<alias>")`.  A formula is fine:
      `"Params.plate_w - 2 * Params.edge_margin"`.
    * Repeated features: draw one, then pattern it.  For 8 holes at one pitch,
      `bind(pattern, "Occurrences", "Params.hole_count")` and
      `bind(pattern, "Length", "(Params.hole_count - 1) * Params.hole_pitch")`.
      Never 7 typed spacings.  In a sketch, tie copies with `Equal` and give
      one of them the dimension.

    The build prints every typed number and every free sketch, and
    `validate_cad.py` reports them from the fingerprint.  See
    `doqs/docs/decisions/2026-10-06_every-dimension-has-a-source.md`.

    Build idempotently: regenerate features rather than mutating them in place,
    so a rerun is a no-op rather than a slow accumulation.

    The top object of a part is a Part container, never a Body.  Get the Body
    with `body(doc)`: it creates the Part (`part(doc)`) and puts the Body inside
    it, and reuses both on a rerun.  `run()` stops and undoes the build if a
    Body is left outside a Part.  See
    `doqs/docs/decisions/2026-10-01_part-container-on-top.md`.

    `run()` makes each new Part, Body, Assembly, Link, imported solid and
    mounting frame visible, and keeps the coordinate systems of the
    containers (origin axes, planes and point) hidden.

    Mounting frames: give the part one named frame for each place where
    another part attaches, like `frame(doc, "IF_mount_bottom",
    x="Params.rail_l / 2", z="Params.rail_h")`.  Place it with the same
    parameters as the holes or the face it stands for, so it moves with them.
    Assembly joints attach to these frames, never to a face, an edge or a
    point.  A frame name is part of the module's interface: renaming or
    removing one breaks every assembly that uses it.  See
    `doqs/docs/decisions/2026-10-06_joints-attach-to-frames.md`.

    Assembly-driven parts: master sketches belong in a dedicated `Body_master`
    constrained to that Body's own origin planes, never the `Assembly` object's.
    See `doqs/docs/decisions/2026-06-24_freecad-master-sketches-body.md`.
    """
    raise NotImplementedError(
        "Replace build() with this part's geometry. The scaffolding around it "
        "(transactions, save discipline, fingerprinting) is already correct in "
        "doqs/scripts/cad_build.py."
    )


# Keep this line exactly as it is.  Do not put it under
# `if __name__ == "__main__":` -- FreeCADCmd 1.1 sets __name__ to "build_model",
# so that test is false and the build is skipped without a word.  main() builds
# unless this file is being imported.
main(build, globals(), cad_dir=_HERE)
