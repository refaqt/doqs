"""A fake ``ImportGui``: the STEP importer that keeps colours. See ``FreeCAD.py``.

``insert`` adds one ``Part::Feature`` per solid the STEP would hold. A test
writes a JSON file with a ``solids`` list in place of a real STEP; a file
without it imports as one solid named after the file.

A ``container`` key makes the importer put the solids in its own
``App::Part`` with that label, the way the real one does for an assembly
STEP. Like in FreeCAD, the Part's ``Origin`` and its axes and planes are
document objects that are not in the Part's ``Group``.
"""
import json
import os

import FreeCAD


def insert(path, doc_name):
    FreeCAD._maybe_fail("insert")
    doc = FreeCAD._DOCUMENTS[doc_name]
    stem = os.path.splitext(os.path.basename(str(path)))[0]
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        names = data.get("solids") or [stem]
        container_label = data.get("container")
    except (OSError, ValueError):
        names, container_label = [stem], None
    container = None
    if container_label:
        container = doc.addObject("App::Part", "Part")
        container.Label = container_label
        origin = doc.addObject("App::Origin", "Origin")
        origin.OriginFeatures = [
            doc.addObject(type_id, name) for type_id, name in (
                ("App::Line", "X_Axis"), ("App::Line", "Y_Axis"), ("App::Line", "Z_Axis"),
                ("App::Plane", "XY_Plane"), ("App::Plane", "XZ_Plane"),
                ("App::Plane", "YZ_Plane"), ("App::Point", "Origin_Point"))]
        container.Origin = origin
    for name in names:
        obj = doc.addObject("Part::Feature", "Part__Feature")
        obj.Label = name
        if container is not None:
            container.Group.append(obj)
    FreeCAD._journal("insert", path=str(path), doc=doc_name, solids=len(names))
