"""A fake ``Part`` module, for ``doqs compare-own``. See ``FreeCAD.py``.

A shape is a JSON object that a test writes into the model file:

    {"box": [xmin, ymin, zmin, xmax, ymax, zmax], "centre": [x, y, z],
     "volume": 1000.0, "overlap": 0.98,
     "missing": [{"box": [...], "volume": 20.0}]}

``cut()`` hands back the ``missing`` pieces: the parts of this shape that the
other one does not have. ``common()`` hands back ``overlap`` times the smaller
volume. That is all a comparison needs, and it proves only what DOQS does with
the answers, never that FreeCAD gives them.
"""
import json

import FreeCAD


class Vector:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class BoundBox:
    def __init__(self, box):
        self.XMin, self.YMin, self.ZMin, self.XMax, self.YMax, self.ZMax = box


class Shape:
    def __init__(self, data):
        self._data = data
        self.BoundBox = BoundBox(data.get("box", [0, 0, 0, 0, 0, 0]))
        self.Volume = float(data.get("volume", 0.0))

    @property
    def CenterOfMass(self):
        centre = self._data.get("centre")
        if centre is None:
            raise AttributeError("CenterOfMass")
        return Vector(*centre)

    @property
    def Solids(self):
        return [Shape(piece) for piece in self._data.get("solids", [])]

    def cut(self, other):
        return Shape({"solids": self._data.get("missing", [])})

    def common(self, other):
        share = float(self._data.get("overlap", 1.0))
        return Shape({"volume": share * min(self.Volume, other.Volume)})


def read(path):
    FreeCAD._journal("read", path=str(path))
    with open(path, encoding="utf-8") as f:
        return Shape(json.load(f)["shape"])


def getShape(obj):
    return obj.Shape


def makeCompound(shapes):
    # One Part container is all a test model holds.
    return shapes[0]
