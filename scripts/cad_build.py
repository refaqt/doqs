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

A build script ends with `main(build, globals())`, never with an
`if __name__ == "__main__":` guard.  FreeCADCmd 1.1 runs a script with
`__name__` set to the file name without its suffix, so that guard is false and
the run builds nothing, prints nothing and exits 0.  `main()` builds unless the
file is being imported, and a headless run that ends without a finished build
prints an error and exits 1.

Never run the headless path against a document you have open in the GUI:
FreeCAD does not notice that a file changed on disk and the next save from
either side silently overwrites the other (FreeCAD issue #8924).  That is why
the agent drives the interactive path instead, and why `execute_code_headless`
is denied in `.claude/settings.json`.  See `doqs/docs/agent-cad.md`.

FreeCAD is imported lazily inside the functions that need it, so this module
imports cleanly under plain Python and its path handling stays unit-testable.
"""

import atexit
import os
import sys
from pathlib import Path

import cad_fingerprint
from cad_rules import (
    BODY_TYPE,
    OWN_BUILD_SUFFIX,
    PART_TYPE,
    bodies_outside_part,
    is_assembly_path,
    visibility_for,
)

#: Builds that finished in this process: rebuilt, checked, fingerprinted. The
#: exit check below reads it.
_builds_done = 0


def _cad_dir(cad_dir=None):
    """The module's `cad/` directory. Defaults to `cwd/cad` (run from the root)."""
    return Path(cad_dir) if cad_dir else Path.cwd() / "cad"


def document_of_script(file):
    """`cad/own/HGR20R1000.build.py` -> `HGR20R1000`; None for `build_model.py`.

    A parts library keeps several own models in one `cad/own/` folder, each
    with its own build script. The script's name says which model it builds.
    """
    name = Path(file).name if file else ""
    if name.endswith(OWN_BUILD_SUFFIX) and len(name) > len(OWN_BUILD_SUFFIX):
        return name[: -len(OWN_BUILD_SUFFIX)]
    return None


def params_path(cad_dir=None, document=None, fcstd=None):
    """The parameter file a build reads.

    An own model in a parts library keeps `<pn>.params.csv` next to its
    `<pn>.FCStd`. A machine module keeps one `cad/params.csv`.
    """
    directory = _cad_dir(cad_dir)
    candidates = []
    if fcstd:
        candidates.append(Path(fcstd).with_name(Path(fcstd).stem + ".params.csv"))
    if document:
        candidates.append(directory / f"{document}.params.csv")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return directory / "params.csv"


def fcstd_path(cad_dir=None, document=None):
    """The .FCStd this build drives: the single one in the module's `cad/`.

    `document` names the stem when a folder keeps more than one.
    """
    directory = _cad_dir(cad_dir)
    candidates = sorted(directory.glob("*.FCStd"))
    if not candidates:
        raise RuntimeError(f"No .FCStd found in {directory}")
    if document:
        named = directory / f"{document}.FCStd"
        if not named.is_file():
            raise RuntimeError(f"No {named.name} in {directory}")
        return named
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


def bind(obj, prop, expr):
    """Drive ``obj.<prop>`` by an expression, like ``bind(pad, "Length", "Params.plate_t")``.

    Every size in a model is an expression over the parameter sheet, never a
    typed number. ``validate_cad.py`` reports a typed one. See
    docs/decisions/2026-10-06_every-dimension-has-a-source.md.
    """
    obj.setExpression(prop, expr)
    return obj


def dim(sketch, constraint, expr, name=None):
    """Add a dimension to ``sketch`` and drive it by ``expr``. Returns its index.

    ``constraint`` is a ``Sketcher.Constraint`` such as
    ``Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 1.0)``. Its number only
    seeds the solver: the expression sets the real value. Give a ``name`` when
    another dimension or feature reads this one.
    """
    index = sketch.addConstraint(constraint)
    if name:
        sketch.renameConstraint(index, name)
    sketch.setExpression(f"Constraints[{index}]", expr)
    return index


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
    global _builds_done
    doc, interactive = open_document(cad_dir, document)
    params = cad_fingerprint.read_params(
        path=params_path(cad_dir, document, getattr(doc, "FileName", "") or None))

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
    _builds_done += 1
    return doc


def _is_import(namespace):
    """True when Python is importing the build script, not running it.

    Only an import sets `__spec__` to a spec with the module's own name.
    `python file.py`, `runpy`, the FreeCAD console and FreeCADCmd all leave it
    unset or None, whatever they put in `__name__`.
    """
    spec = namespace.get("__spec__")
    return spec is not None and getattr(spec, "name", None) == namespace.get("__name__")


def main(build_fn, namespace, cad_dir=None, document=None):
    """The last line of every build script: `main(build, globals())`.

    It builds unless the script is being imported. It does not look at
    `__name__ == "__main__"`, because FreeCADCmd 1.1 sets `__name__` to the
    file name, so that test is false and the run quietly builds nothing.
    """
    if _is_import(namespace):
        return None
    file = namespace.get("__file__")
    if cad_dir is None and file:
        cad_dir = Path(file).resolve().parent
    return run(build_fn, cad_dir=cad_dir, document=document or document_of_script(file))


def _fail_if_nothing_built():
    """At the end of a headless run: no finished build is an error, not silence."""
    if _builds_done:
        return
    print(
        "ERROR: this FreeCADCmd run built nothing. Nothing was rebuilt, saved or "
        "fingerprinted. If an error is printed above, fix it. If not, the build "
        "script never called main(build, globals()): copy the last lines of "
        "doqs/templates/cad/build_model.py into it.",
        file=sys.stderr,
    )
    sys.stdout.flush()
    sys.stderr.flush()
    # FreeCADCmd does not always pass on a failure as an exit code, so leave
    # with one ourselves.
    os._exit(1)


def _arm_exit_check():
    """Watch a headless FreeCAD run that imports this module.

    Only there: a GUI session runs many builds and many other things, and plain
    Python (the test suite) has no FreeCAD at all.
    """
    freecad = sys.modules.get("FreeCAD")
    if freecad is None or getattr(freecad, "GuiUp", False):
        return
    atexit.register(_fail_if_nothing_built)


_arm_exit_check()
