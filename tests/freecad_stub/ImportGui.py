"""A fake ``ImportGui``: the STEP importer that keeps colours. See ``FreeCAD.py``.

``insert`` adds one ``Part::Feature`` per solid the STEP would hold. A test
writes a JSON file with a ``solids`` list in place of a real STEP; a file
without it imports as one solid named after the file.
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
    except (OSError, ValueError):
        names = [stem]
    for name in names:
        obj = doc.addObject("Part::Feature", "Part__Feature")
        obj.Label = name
    FreeCAD._journal("insert", path=str(path), doc=doc_name, solids=len(names))
