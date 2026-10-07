"""Wrap a supplier's STEP file as a FreeCAD part document. Runs inside FreeCAD.

The GUI importer (``ImportGui``) keeps the colours of the brand's model; the
headless one does not. So this runs in the open FreeCAD window or in a window
started for the job, never in FreeCADCmd. ``export_wrapper.py`` renders the
call into a macro and starts it.

The result follows the part rules: one Part container on top, labelled with
the part number; the imported solids inside it; one mounting frame
(``IF_...``) per place where another part attaches, at the origin until the
designer places it; everything visible. See docs/agent-cad.md.
"""
from __future__ import annotations

import json

import cad_build
import cad_rules


def wrap(step: str, out: str, label: str, frames: list[str]) -> dict:
    """Import ``step`` into a new document saved at ``out``. Returns the tree."""
    import FreeCAD
    import ImportGui

    doc = FreeCAD.newDocument(label)
    before = {o.Name for o in doc.Objects}
    ImportGui.insert(step, doc.Name)
    new = [o for o in doc.Objects if o.Name not in before]
    if not new:
        raise RuntimeError(f"nothing was imported from {step}")
    held = set()
    for obj in new:
        for member in getattr(obj, "Group", None) or []:
            held.add(member.Name)
    tops = [o for o in new if o.Name not in held]
    if len(tops) == 1 and tops[0].TypeId == cad_rules.PART_TYPE:
        # The importer made its own container; it becomes the part.
        container = tops[0]
        container.Label = label
    else:
        container = cad_build.part(doc, label)
        for obj in tops:
            container.addObject(obj)
    for frame_label in frames:
        cad_build.frame(doc, frame_label, container=container)
    doc.recompute()
    cad_build.show_new_objects(doc, before)
    doc.saveAs(out)
    tree = cad_build.tree(doc)
    labels = {o.Name: getattr(o, "Label", o.Name) for o in doc.Objects}
    FreeCAD.closeDocument(doc.Name)
    return {"objects": tree, "labels": labels}


def run(step: str, out: str, label: str, frames: list[str]) -> None:
    """Wrap, then print the tree as one line a caller can read back."""
    result = wrap(step, out, label, frames)
    print("DOQS_TREE=" + json.dumps(result, sort_keys=True))
