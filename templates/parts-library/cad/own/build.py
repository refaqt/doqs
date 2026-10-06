"""Build one model of ours in a parts library, from `<pn>.params.csv`.

Copy this file to `modules/<brand>/modules/<family>/cad/own/<pn>.build.py`,
next to `<pn>.FCStd`, and replace `build()` and `AXES`.  The file name says
which model it builds, so several own models can share one `cad/own/` folder.
Run it headless from the library root:

    FreeCADCmd modules/<brand>/modules/<family>/cad/own/<pn>.build.py

A good run ends with "Rebuilt and saved <pn>".  A run that built nothing prints
an ERROR and exits 1.  Never build or change an own model by hand in the GUI,
and never save it again after the build: `doqs check` compares it with its
fingerprint.

Before you model, fill `<pn>.features.csv`: every dimension in the catalogue
table and every feature the figure shows.  Model every row that is not
left-out.  A feature that sticks out of the part is never left out.

See `doqs/docs/parts-library.md`, "Our own models".
"""

import sys
from pathlib import Path

#: The axes and origin of this model, in words.  They must be the same as in
#: the brand's own model, so ours can replace it in an assembly.
#: `doqs compare-own <family> <pn>` checks that they are.
AXES = "TODO: which way X, Y and Z point, and where the origin is"

try:
    _HERE = Path(__file__).resolve().parent
except NameError:  # exec()'d from the FreeCAD console
    _HERE = Path.cwd()


def _doqs_scripts(start):
    """Find `doqs/scripts/` by walking up from this folder."""
    for base in [start, *start.parents]:
        candidate = base / "doqs" / "scripts"
        if (candidate / "cad_build.py").is_file():
            return candidate
    raise RuntimeError(
        f"doqs/scripts/cad_build.py not found above {start} — "
        "run from inside a parts library with the doqs submodule checked out."
    )


sys.path.insert(0, str(_doqs_scripts(_HERE)))

from cad_build import bind, body, dim, main, part, sheet  # noqa: E402


def build(doc, params):
    """Rebuild this model from `params`, read from `<pn>.params.csv`.

    Use only values from `params`.  Each one is marked catalogue, estimated or
    measured there.  Get the Body with `body(doc)`: it sits inside a Part
    container, so an assembly can place the model as one object.

    Drive every size by an expression over the `Params` sheet, as in a
    machine part: `dim(sketch, constraint, "Params.rail_width")` and
    `bind(pad, "Length", "Params.rail_length")`.  Fully constrain each sketch.
    Pattern repeated holes from a count and a pitch, never typed one by one.
    """
    raise NotImplementedError(
        "Replace build() with this model's geometry, and AXES with its axes."
    )


# Keep this line exactly as it is.  Do not put it under
# `if __name__ == "__main__":` -- FreeCADCmd 1.1 sets __name__ to the file
# name, so that test is false and the build is skipped without a word.
main(build, globals(), cad_dir=_HERE)
