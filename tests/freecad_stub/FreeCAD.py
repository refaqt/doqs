"""A fake ``FreeCAD`` module, so a generated macro can be run as plain Python.

DOQS drives FreeCAD through generated macros, and a macro is the one piece of
this repository that cannot be reached by importing a module: it is written to
a file and handed to a separate ``FreeCADCmd`` process.  That is why the
``/tmp/params.csv`` bug in ``export_variant.py`` survived a merged pull
request.  Point ``PYTHONPATH`` at this directory and pass ``--freecad`` the
path to a Python interpreter, and the macro runs end to end against these
stubs instead.

**What this proves, and what it does not.**  It asserts *DOQS* behaviour —
which file was opened, which aliases were written at which values, where the
STEP went, and whether ``save()`` was ever called.  It asserts nothing about
FreeCAD: not ``Import.export``'s format selection, not ``sheet.set`` with
unit-bearing strings, not the real ``openDocument``/``closeDocument``
signatures, and not whether a composition assembly carries a ``Params``
spreadsheet at all.  Those need a real binary; see ``docs/variants.md``.

Everything observable is appended to the JSON-lines journal named by
``DOQS_FREECAD_STUB_LOG``.  A test reads it back to make its assertions,
because the macro runs in a child process and nothing else crosses that
boundary.

Environment knobs, each of which exists for one named test:

``DOQS_FREECAD_STUB_LOG``          where to journal; no journal when unset.
``DOQS_FREECAD_STUB_FAIL``         ``open`` or ``export`` — raise at that stage.
``DOQS_FREECAD_STUB_SWALLOW_EXIT`` print the traceback but exit 0, the way
                                   FreeCADCmd does, so a caller that trusts the
                                   exit code is caught believing a failed run.
``DOQS_FREECAD_STUB_NO_SHEET``     build a document with no ``Params`` sheet.
``DOQS_FREECAD_STUB_EMPTY``        build a document with no solid objects.

A document file that holds JSON with a ``shape`` key opens as one Part
container with that shape. ``Part.py`` explains the shape format; it exists
for ``doqs compare-own``.
"""
import json
import os
import sys
import traceback

GuiUp = False
ActiveDocument = None

_DOCUMENTS = {}


def _journal(event, **fields):
    path = os.environ.get("DOQS_FREECAD_STUB_LOG")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"event": event, **fields}, sort_keys=True) + "\n")


def _maybe_fail(stage):
    if os.environ.get("DOQS_FREECAD_STUB_FAIL") == stage:
        raise RuntimeError(f"stub FreeCAD was told to fail at {stage!r}")


if os.environ.get("DOQS_FREECAD_STUB_SWALLOW_EXIT"):
    # FreeCADCmd does not reliably exit non-zero when a macro raises. Reproduce
    # that here so the tests can prove the exit code is not what decides success.
    def _swallow(exc_type, exc, tb):
        traceback.print_exception(exc_type, exc, tb)
        sys.stderr.flush()
        os._exit(0)

    sys.excepthook = _swallow


class _Shape:
    def __init__(self, null):
        self._null = null

    def isNull(self):
        return self._null


class _Object:
    def __init__(self, name, null_shape=False, type_id="Part::Feature", shape=None,
                 shaped=True):
        self.Name = name
        self.Label = name
        self.TypeId = type_id
        self.State = []
        self.Group = []
        self.Visibility = False
        self.ViewObject = None
        self.expressions = {}
        if shaped:
            self.Shape = shape if shape is not None else _Shape(null_shape)

    def addObject(self, obj):
        if obj not in self.Group:
            self.Group.append(obj)
        _journal("group", container=self.Name, member=obj.Name)

    def setExpression(self, path, expr):
        self.expressions[path] = expr
        _journal("setExpression", obj=self.Name, path=path, expr=expr)


#: Types that FreeCAD gives no Shape of their own in this stub.
_UNSHAPED = ("App::Part", "App::Link", "Spreadsheet::Sheet", "Part::LocalCoordinateSystem")


def _shape_description(path):
    """The JSON shape a test wrote into a document file, or None."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and "shape" in data else None


class _Sheet:
    """Stands in for a Spreadsheet: records every aliased cell written to it."""

    Label = "Params"
    TypeId = "Spreadsheet::Sheet"
    Name = "Params"

    def __init__(self):
        self.cells = {}
        self.aliases = {}
        self.Visibility = False
        self.ViewObject = None
        self.Group = []

    def set(self, alias, value):
        self.cells[alias] = value
        _journal("set", alias=alias, value=value)

    def setAlias(self, cell, alias):
        self.aliases[cell] = alias
        _journal("setAlias", cell=cell, alias=alias)


class Document:
    def __init__(self, path, blank=False):
        self.FileName = "" if blank else str(path)
        self.Name = str(path) if blank else os.path.splitext(os.path.basename(str(path)))[0]
        self.Objects = []
        self._sheets = []
        if blank:
            return
        described = _shape_description(path)
        if described is not None:
            import Part

            self.Objects.append(
                _Object("Part", type_id="App::Part", shape=Part.Shape(described["shape"])))
            self._sheets = []
            return
        if not os.environ.get("DOQS_FREECAD_STUB_EMPTY"):
            self.Objects.append(_Object("Body"))
        # A null-shape object so the macro's filter is genuinely exercised.
        self.Objects.append(_Object("Sketch", null_shape=True))
        self._sheets = [] if os.environ.get("DOQS_FREECAD_STUB_NO_SHEET") else [_Sheet()]

    def getObjectsByLabel(self, label):
        return [o for o in [*self._sheets, *self.Objects] if getattr(o, "Label", None) == label]

    def addObject(self, type_id, name):
        # FreeCAD keeps internal names unique: Frame, Frame001, Frame002.
        taken = {o.Name for o in [*self.Objects, *self._sheets]}
        unique, n = name, 0
        while unique in taken:
            n += 1
            unique = f"{name}{n:03d}"
        if type_id == "Spreadsheet::Sheet":
            obj = _Sheet()
            obj.Name = unique
            obj.Label = name
            self._sheets.append(obj)
        else:
            obj = _Object(unique, type_id=type_id, shaped=type_id not in _UNSHAPED)
            obj.Label = name
            self.Objects.append(obj)
        _journal("addObject", type=type_id, name=name)
        return obj

    def recompute(self):
        _journal("recompute", doc=self.Name)

    def isTouched(self):
        return False

    def save(self):
        _journal("save", doc=self.Name, file=self.FileName)
        # Mutate the file too, so a test can assert on bytes rather than trust
        # the journal alone.
        with open(self.FileName, "a", encoding="utf-8") as f:
            f.write("saved-by-stub\n")

    def saveAs(self, path):
        self.FileName = str(path)
        self.Name = os.path.splitext(os.path.basename(str(path)))[0]
        _journal("saveAs", doc=self.Name, file=self.FileName)
        with open(self.FileName, "w", encoding="utf-8") as f:
            json.dump({"stub": "saved", "objects": [
                {"name": o.Name, "type": o.TypeId, "label": o.Label,
                 "visible": bool(getattr(o, "Visibility", False)),
                 "group": [m.Name for m in getattr(o, "Group", [])]}
                for o in [*self.Objects, *self._sheets]]}, f, indent=1)

    def openTransaction(self, name):
        _journal("openTransaction", name=name)

    def commitTransaction(self):
        _journal("commitTransaction")

    def abortTransaction(self):
        _journal("abortTransaction")


def openDocument(path):
    _maybe_fail("open")
    doc = Document(path)
    _DOCUMENTS[doc.Name] = doc
    _journal("openDocument", path=str(path))
    return doc


def newDocument(name="Unnamed"):
    doc = Document(name, blank=True)
    _DOCUMENTS[doc.Name] = doc
    _journal("newDocument", name=name)
    return doc


def closeDocument(name):
    _DOCUMENTS.pop(name, None)
    _journal("closeDocument", name=name)


def listDocuments():
    return dict(_DOCUMENTS)
