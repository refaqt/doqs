"""Measure a FreeCAD document into a committed geometric fingerprint.

Runs inside FreeCAD, from the module root of a machine repository:

    FreeCADCmd cad/build_model.py      # build_model.py calls write() for you

Or against the document already open in the GUI:

    exec(open("doqs/scripts/cad_fingerprint.py").read())
    write()

Why this exists: an agent cannot see a model, and a screenshot is both the most
expensive way to look at one and the worst way to answer the questions that
actually matter.  A 1920x1080 viewport costs ~2,700 tokens and still will not
tell you whether a rail is 500 mm long.  The numbers below cost tens of tokens
and answer it exactly.  The same file is a geometric regression gate in CI.

``doqs/scripts/validate_cad.py`` reads the result back and fails the build when a
committed fingerprint no longer matches the `.FCStd` it describes.

FreeCAD is imported lazily inside the functions that need it, so this module
imports cleanly under plain Python and its CSV handling stays unit-testable.
"""

import csv
from pathlib import Path

import cad_rules

#: Exports hashed alongside the .FCStd so a hand-edited STEP is caught too.
EXPORT_SUFFIXES = (".step", ".stp", ".stl", ".dxf")


def _cad_dir(cad_dir=None):
    """The module's `cad/` directory. Defaults to `cwd/cad` (run from the root)."""
    return Path(cad_dir) if cad_dir else Path.cwd() / "cad"


def read_params(cad_dir=None, path=None):
    """cad/params.csv -> {alias: value}, skipping the generated `#` header."""
    path = Path(path) if path else _cad_dir(cad_dir) / "params.csv"
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        lines = [line for line in f if not line.lstrip().startswith("#")]
    rows = list(csv.reader(lines))
    if not rows:
        return {}
    header, body = rows[0], rows[1:]
    index = {name: i for i, name in enumerate(header)}
    if "alias" not in index or "value" not in index:
        return {}
    params = {}
    for row in body:
        if not row or not row[index["alias"]].strip():
            continue
        raw = row[index["value"]].strip()
        try:
            params[row[index["alias"]].strip()] = float(raw)
        except ValueError:
            params[row[index["alias"]].strip()] = raw
    return params


def _measure_shape(shape, rules):
    """Bounding box, mass properties and topology counts for one shape."""
    box = shape.BoundBox
    com = shape.CenterOfMass
    return {
        "valid": bool(shape.isValid()),
        "closed": bool(shape.isClosed()),
        "volume": float(shape.Volume),
        "area": float(shape.Area),
        # Centre of mass is what catches a mirrored or rotated part whose
        # volume, area and bounding box are all unchanged.
        "com": [float(com.x), float(com.y), float(com.z)],
        "bbox": [
            float(box.XMin), float(box.YMin), float(box.ZMin),
            float(box.XMax), float(box.YMax), float(box.ZMax),
        ],
        "counts": {
            "solids": len(shape.Solids),
            "shells": len(shape.Shells),
            "faces": len(shape.Faces),
            "edges": len(shape.Edges),
            "verts": len(shape.Vertexes),
        },
    }


def _shaped_objects(doc, rules):
    """Objects worth measuring: a real Shape, and not a datum or origin."""
    for obj in doc.Objects:
        type_id = getattr(obj, "TypeId", "")
        if type_id.startswith(rules.SKIPPED_TYPE_PREFIXES):
            continue
        shape = getattr(obj, "Shape", None)
        if shape is None or shape.isNull():
            continue
        yield obj, shape


def measure(doc=None, params=None):
    """Measure every shaped object in `doc` into a fingerprint payload."""
    import FreeCAD

    rules = cad_rules
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        raise RuntimeError("No active FreeCAD document.")

    objects = {}
    errors = []
    for obj, shape in _shaped_objects(doc, rules):
        try:
            objects[obj.Name] = {
                "type": obj.TypeId,
                "label": obj.Label,
                **_measure_shape(shape, rules),
            }
        except Exception as err:  # a broken feature must not abort the run
            errors.append(f"{obj.Name}: {err}")
        if getattr(obj, "State", None) and "Invalid" in obj.State:
            errors.append(f"{obj.Name}: object state is Invalid")

    saved = bool(doc.FileName) and not doc.isTouched()
    sources = {}
    if saved:
        fcstd = Path(doc.FileName)
        if fcstd.is_file():
            sources[fcstd.name] = rules.file_digest(fcstd)
            for export in sorted(fcstd.parent.iterdir()):
                if (
                    export.is_file()
                    and export.suffix.lower() in EXPORT_SUFFIXES
                    and export.stem == fcstd.stem
                ):
                    sources[export.name] = rules.file_digest(export)

    return {
        "schema": rules.FINGERPRINT_SCHEMA,
        "document": doc.Name,
        # False means the numbers came from an unsaved in-memory document, so
        # they cannot be reproduced from the committed .FCStd. validate_cad.py
        # rejects committing one: rebuild headless before you commit.
        "saved": saved,
        "sources": sources,
        "params": params if params is not None else read_params(),
        "objects": objects,
        "errors": errors,
    }


def write(doc=None, path=None, params=None, cad_dir=None):
    """Measure and write `cad/<document>.fingerprint.json`. Returns the payload."""
    import FreeCAD

    rules = cad_rules
    doc = doc or FreeCAD.ActiveDocument
    data = measure(doc, params=params)
    if path is None:
        target = (
            rules.fingerprint_path(Path(doc.FileName))
            if doc.FileName
            else _cad_dir(cad_dir) / f"{doc.Name}{rules.FINGERPRINT_SUFFIX}"
        )
    else:
        target = Path(path)
    payload = rules.write_fingerprint(target, data)
    print(f"Fingerprinted {len(payload['objects'])} objects -> {target}")
    for err in payload["errors"]:
        print(f"  warning: {err}")
    return payload


if __name__ == "__main__":
    write()
