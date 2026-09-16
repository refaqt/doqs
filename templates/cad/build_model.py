"""Rebuild a part's geometry from `cad/params.csv`, in the GUI or headless.

Copy this file to `<module>/cad/build_model.py` and replace `build()` with your
part.  Everything around `build()` is the part you should not rewrite: it is what
lets an agent edit this model while you have the file open in FreeCAD.

Two contexts, one script:

*Interactive* — FreeCAD is running and the document is open.  The script edits
the document **you are looking at**, in memory, inside a single undo
transaction, and **never saves**.  Your unsaved work survives; one Ctrl+Z
reverts the agent's change; the `.FCStd` on disk is untouched until you press
Ctrl+S yourself.

*Headless* — no GUI.  The script opens the `.FCStd` from disk, rebuilds, saves,
and writes the fingerprint.  This is the CI path.

    FreeCADCmd cad/build_model.py

Never run the headless path against a document you have open in the GUI: FreeCAD
does not notice that a file changed on disk and the next save from either side
silently overwrites the other (FreeCAD issue #8924).  That is why the agent
drives the interactive path instead, and why `execute_code_headless` is denied
in `.claude/settings.json`.  See `doqs/docs/agent-cad.md`.

The geometry itself is the reviewable artefact: this file is a text diff in the
pull request, where the `.FCStd` is an opaque binary blob.
"""

import sys
from pathlib import Path

#: Name of the document when building headless. Defaults to the file stem.
DOCUMENT = None


def _here():
    try:
        return Path(__file__).resolve().parent
    except NameError:  # exec()'d from the FreeCAD console
        return Path.cwd() / "cad"


def _load(name):
    """Import a sibling `cad/` module whether exec()'d or run as a script."""
    directory = str(_here())
    if directory not in sys.path:
        sys.path.insert(0, directory)
    return __import__(name)


def _fcstd():
    """The .FCStd this script builds: the single one beside it in `cad/`."""
    candidates = sorted(_here().glob("*.FCStd"))
    if not candidates:
        raise RuntimeError(f"No .FCStd found in {_here()}")
    if len(candidates) > 1 and DOCUMENT:
        return _here() / f"{DOCUMENT}.FCStd"
    if len(candidates) > 1:
        raise RuntimeError(
            f"{len(candidates)} .FCStd files in {_here()}; set DOCUMENT in this script."
        )
    return candidates[0]


def open_document():
    """Return `(document, interactive)`.

    Interactive means a GUI document is already open — the human's document.
    In that case we work on it in memory and never touch the file on disk.
    """
    import FreeCAD

    if getattr(FreeCAD, "GuiUp", False) and FreeCAD.ActiveDocument is not None:
        return FreeCAD.ActiveDocument, True
    path = _fcstd()
    name = path.stem
    for doc in FreeCAD.listDocuments().values():
        if doc.FileName and Path(doc.FileName) == path:
            return doc, bool(getattr(FreeCAD, "GuiUp", False))
    return FreeCAD.openDocument(str(path)), False


def sheet(doc, name="Params"):
    """The parameter Spreadsheet, whose aliases drive sketch expressions."""
    found = doc.getObjectsByLabel(name)
    if not found:
        raise RuntimeError(
            f"No Spreadsheet named {name!r} in {doc.Name}. "
            "Add one (Spreadsheet workbench) before building."
        )
    return found[0]


# ---------------------------------------------------------------------------
# Replace everything in build() with your part.
# ---------------------------------------------------------------------------

def build(doc, params):
    """Rebuild this part's geometry from `params`.

    `params` is `{alias: value}` read from `cad/params.csv`.  Prefer driving
    sketch constraints through Spreadsheet expressions (`Params.rail_length`)
    over hard-coding numbers here — see
    `doqs/docs/architecture.md#linking-csv-parameters-to-freecad`.

    Build idempotently: regenerate features rather than mutating them in place,
    so a rerun is a no-op rather than a slow accumulation.

    Assembly-driven parts: master sketches belong in a dedicated `Body_master`
    constrained to that Body's own origin planes, never the `Assembly` object's.
    See `doqs/docs/decisions/2026-06-24_freecad-master-sketches-body.md`.
    """
    raise NotImplementedError(
        "Replace build() with this part's geometry. The scaffolding around it "
        "(transactions, save discipline, fingerprinting) is already correct."
    )


# ---------------------------------------------------------------------------


def run(build_fn=build):
    """Rebuild, then fingerprint. Saves only when there is no GUI document."""
    fingerprint = _load("fingerprint")
    doc, interactive = open_document()
    params = fingerprint._read_params()

    # One transaction means the whole rebuild is a single Ctrl+Z for the human
    # working alongside the agent.
    doc.openTransaction("agent: build_model")
    try:
        build_fn(doc, params)
        doc.recompute()
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()

    failed = [o.Name for o in doc.Objects if getattr(o, "State", None) and "Invalid" in o.State]
    if failed:
        raise RuntimeError(f"Objects invalid after recompute: {', '.join(failed)}")

    if interactive:
        # Deliberately not saving. The document on disk is the human's to write.
        print(
            f"Rebuilt {doc.Name} in the open GUI document — not saved. "
            "Review it, then save yourself (Ctrl+Z reverts)."
        )
        fingerprint.write(doc, params=params)
    else:
        doc.save()
        fingerprint.write(doc, params=params)
        print(f"Rebuilt and saved {doc.Name}")
    return doc


if __name__ == "__main__":
    run()
