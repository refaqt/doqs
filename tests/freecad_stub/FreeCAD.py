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
    def __init__(self, name, null_shape=False):
        self.Name = name
        self.Shape = _Shape(null_shape)


class _Sheet:
    """Stands in for a Spreadsheet: records every aliased cell written to it."""

    Label = "Params"

    def __init__(self):
        self.cells = {}

    def set(self, alias, value):
        self.cells[alias] = value
        _journal("set", alias=alias, value=value)


class Document:
    def __init__(self, path):
        self.FileName = str(path)
        self.Name = os.path.splitext(os.path.basename(str(path)))[0]
        self.Objects = []
        if not os.environ.get("DOQS_FREECAD_STUB_EMPTY"):
            self.Objects.append(_Object("Body"))
        # A null-shape object so the macro's filter is genuinely exercised.
        self.Objects.append(_Object("Sketch", null_shape=True))
        self._sheets = [] if os.environ.get("DOQS_FREECAD_STUB_NO_SHEET") else [_Sheet()]

    def getObjectsByLabel(self, label):
        return [s for s in self._sheets if s.Label == label]

    def recompute(self):
        _journal("recompute", doc=self.Name)

    def save(self):
        _journal("save", doc=self.Name, file=self.FileName)
        # Mutate the file too, so a test can assert on bytes rather than trust
        # the journal alone.
        with open(self.FileName, "a", encoding="utf-8") as f:
            f.write("saved-by-stub\n")

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


def closeDocument(name):
    _DOCUMENTS.pop(name, None)
    _journal("closeDocument", name=name)


def listDocuments():
    return dict(_DOCUMENTS)
