"""A fake ``FreeCADGui``: the window a job macro closes at the end. See ``FreeCAD.py``."""
import FreeCAD


class _MainWindow:
    def close(self):
        FreeCAD._journal("closeMainWindow")


def getMainWindow():
    return _MainWindow()
