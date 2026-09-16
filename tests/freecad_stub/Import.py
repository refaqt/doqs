"""A fake ``Import`` module — the STEP/IGES exporter. See ``FreeCAD.py``."""
import FreeCAD


def export(objects, path):
    FreeCAD._maybe_fail("export")
    FreeCAD._journal("export", path=str(path), objects=len(objects))
    with open(path, "w", encoding="utf-8") as f:
        f.write("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n")
