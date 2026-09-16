"""Rebuild this part's geometry from `cad/params.csv`, in the GUI or headless.

Copy this file to `<module>/cad/build_model.py` and replace `build()` with your
part.  This file is the reviewable artefact in a pull request: a text diff,
where the `.FCStd` beside it is an opaque binary blob.

The scaffolding — transactions, save discipline, fingerprinting — lives in
`doqs/scripts/cad_build.py` and updates with the submodule.  Do not copy it
here.  Run headless with:

    FreeCADCmd cad/build_model.py

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

from cad_build import run, sheet  # noqa: E402


def build(doc, params):
    """Rebuild this part's geometry from `params`.

    `params` is `{alias: value}` read from `cad/params.csv`.  Prefer driving
    sketch constraints through Spreadsheet expressions (`Params.rail_length`)
    over hard-coding numbers here — see
    `doqs/docs/architecture.md#linking-csv-parameters-to-freecad`.  `sheet(doc)`
    returns that Spreadsheet.

    Build idempotently: regenerate features rather than mutating them in place,
    so a rerun is a no-op rather than a slow accumulation.

    Assembly-driven parts: master sketches belong in a dedicated `Body_master`
    constrained to that Body's own origin planes, never the `Assembly` object's.
    See `doqs/docs/decisions/2026-06-24_freecad-master-sketches-body.md`.
    """
    raise NotImplementedError(
        "Replace build() with this part's geometry. The scaffolding around it "
        "(transactions, save discipline, fingerprinting) is already correct in "
        "doqs/scripts/cad_build.py."
    )


if __name__ == "__main__":
    run(build, cad_dir=_HERE)
