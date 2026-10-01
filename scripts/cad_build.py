"""Scaffolding for a module's `cad/build_model.py`.

A module's build script supplies `build(doc, params)` — its geometry, and the
reviewable text diff in a pull request where the `.FCStd` is an opaque binary
blob.  Everything around it lives here, because it is identical in every module
and must stay in step with the fingerprint schema in `cad_rules.py`.

Two contexts, one entry point:

*Interactive* — FreeCAD is running and the document is open.  `run()` edits the
document **you are looking at**, in memory, inside a single undo transaction,
and **never saves**.  Your unsaved work survives; one Ctrl+Z reverts the
agent's change; the `.FCStd` on disk is untouched until you press Ctrl+S.

*Headless* — no GUI.  `run()` opens the `.FCStd` from disk, rebuilds, saves,
and writes the fingerprint.  This is the CI path:

    FreeCADCmd cad/build_model.py

Never run the headless path against a document you have open in the GUI:
FreeCAD does not notice that a file changed on disk and the next save from
either side silently overwrites the other (FreeCAD issue #8924).  That is why
the agent drives the interactive path instead, and why `execute_code_headless`
is denied in `.claude/settings.json`.  See `doqs/docs/agent-cad.md`.

FreeCAD is imported lazily inside the functions that need it, so this module
imports cleanly under plain Python and its path handling stays unit-testable.
"""

from pathlib import Path

import cad_fingerprint
from cad_rules import (
    BODY_TYPE,
    PART_TYPE,
    bodies_outside_part,
    is_assembly_path,
    visibility_for,
)


def _cad_dir(cad_dir=None):
    """The module's `cad/` directory. Defaults to `cwd/cad` (run from the root)."""
    return Path(cad_dir) if cad_dir else Path.cwd() / "cad"


def fcstd_path(cad_dir=None, document=None):
    """The .FCStd this build drives: the single one in the module's `cad/`.

    `document` names the stem when a module keeps more than one.
    """
    directory = _cad_dir(cad_dir)
    candidates = sorted(directory.glob("*.FCStd"))
    if not candidates:
        raise RuntimeError(f"No .FCStd found in {directory}")
    if len(candidates) > 1 and document:
        return directory / f"{document}.FCStd"
    if len(candidates) > 1:
        raise RuntimeError(
            f"{len(candidates)} .FCStd files in {directory}; "
            "pass document= to build_model.run()."
        )
    return candidates[0]


def open_document(cad_dir=None, document=None):
    """Return `(document, interactive)`.

    Interactive means a GUI document is already open — the human's document.
    In that case we work on it in memory and never touch the file on disk.
    """
    import FreeCAD

    if getattr(FreeCAD, "GuiUp", False) and FreeCAD.ActiveDocument is not None:
        return FreeCAD.ActiveDocument, True
    path = fcstd_path(cad_dir, document)
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


def tree(doc):
    """``(name, type_id, children)`` for every object, as ``cad_rules`` reads it."""
    return [
        (o.Name, o.TypeId, [c.Name for c in (getattr(o, "Group", None) or [])])
        for o in doc.Objects
    ]


def _set_visible(obj, flag):
    """Show or hide one object, in the file and on screen.

    ``Visibility`` on the object itself is saved in the document, so this also
    works headless, where there is no screen and no view data.
    """
    obj.Visibility = flag
    view = getattr(obj, "ViewObject", None)
    if view is not None:
        view.Visibility = flag


def _show(obj):
    """Show a new container and keep its coordinate system hidden."""
    _set_visible(obj, True)
    origin = getattr(obj, "Origin", None)
    if origin is not None:
        for item in [origin, *(getattr(origin, "OriginFeatures", None) or [])]:
            _set_visible(item, False)


def show_new_objects(doc, before):
    """Show the parts, bodies and assemblies a build created; hide their origins.

    ``before`` holds the object names that existed before the build. Only new
    objects change, so an object the person hid on purpose stays hidden.
    """
    for obj in doc.Objects:
        if obj.Name in before:
            continue
        flag = visibility_for(obj.TypeId)
        if flag is not None:
            _set_visible(obj, flag)
        tip = getattr(obj, "Tip", None) if flag else None
        if tip is not None:
            # A visible Body shows nothing while its last feature is hidden.
            _set_visible(tip, True)


def part(doc, label=None):
    """The Part container at the top of this part's tree. Created if missing.

    A part document keeps its Bodies inside a Part, so an Assembly can insert
    and place it as one object. `label` defaults to the document name.
    """
    label = label or doc.Name
    for obj in doc.getObjectsByLabel(label):
        if obj.TypeId == PART_TYPE:
            return obj
    container = doc.addObject(PART_TYPE, "Part")
    container.Label = label
    _show(container)
    return container


def body(doc, label="Body", container=None):
    """A Body inside the Part container. Created if missing.

    An existing Body with this label that no Part holds is moved into the
    container, so an old document is repaired on the next build.
    """
    container = container or part(doc)
    for obj in doc.getObjectsByLabel(label):
        if obj.TypeId == BODY_TYPE:
            if obj.Name in bodies_outside_part(tree(doc)):
                container.addObject(obj)
            return obj
    new = doc.addObject(BODY_TYPE, "Body")
    new.Label = label
    container.addObject(new)
    _show(new)
    return new


def check_part_container(doc):
    """Raise when a Body sits outside a Part container in a part document."""
    if is_assembly_path(Path(doc.FileName or "")):
        return
    loose = bodies_outside_part(tree(doc))
    if loose:
        raise RuntimeError(
            f"Body not inside a Part container: {', '.join(loose)}. "
            "The top object of a part must be a Part. Get the Body with "
            "body(doc) from cad_build, which puts it inside part(doc)."
        )


def run(build_fn, cad_dir=None, document=None):
    """Rebuild via `build_fn`, then fingerprint.

    Saves only when there is no GUI document: an open document is the human's
    to write, and writing it from here is the data-loss path described above.
    """
    doc, interactive = open_document(cad_dir, document)
    params = cad_fingerprint.read_params(cad_dir)

    # One transaction means the whole rebuild is a single Ctrl+Z for the human
    # working alongside the agent.
    before = {o.Name for o in doc.Objects}
    doc.openTransaction("agent: build_model")
    try:
        build_fn(doc, params)
        doc.recompute()
        check_part_container(doc)
        show_new_objects(doc, before)
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()

    failed = [
        o.Name for o in doc.Objects
        if getattr(o, "State", None) and "Invalid" in o.State
    ]
    if failed:
        raise RuntimeError(f"Objects invalid after recompute: {', '.join(failed)}")

    if interactive:
        # Deliberately not saving. The document on disk is the human's to write.
        print(
            f"Rebuilt {doc.Name} in the open GUI document — not saved. "
            "Review it, then save yourself (Ctrl+Z reverts)."
        )
        cad_fingerprint.write(doc, params=params, cad_dir=cad_dir)
    else:
        doc.save()
        cad_fingerprint.write(doc, params=params, cad_dir=cad_dir)
        print(f"Rebuilt and saved {doc.Name}")
    return doc
