# 2026-11-09 — FreeCADCmd builds did nothing, and turned frames lost their angle

## What happened

In aqtuator, an agent built the cooling block and two cable clamps. Two doqs problems got in the
way:

1. `freecadcmd build_model.py` built nothing. Every run ended with "this FreeCADCmd run built
   nothing". The agent had to start the scripts through a small wrapper of its own.
2. After a rebuild, two mounting frames of the cooling block that turn 90° pointed the wrong way.
   They only turned again after a second recompute. Until then, the fixed joints of two Festo
   fittings in the assembly were wrong.

## Why it went wrong

1. `main()` skips the build when Python imports the script, so that a test can import it without
   side effects. To tell an import from a run, doqs looked at the module "spec": we believed only
   an import sets one with the module's own name. FreeCADCmd 1.1.4 runs a `.py` file as a real
   import, from C++. So every headless run looked like an import. Our test only used plain Python.
2. On every rebuild, `frame()` set the angle to 0 and then set the angle expression again. The
   expression text had not changed, so FreeCAD did not evaluate it on the next recompute. The angle
   stayed 0. A new frame was fine: FreeCAD evaluates a new expression.

## What we changed

`main()` now looks at who asked for the import. A Python import has Python code that asked for
it. FreeCADCmd has none. `frame()` now sets the real angle at once, read from the expression.
Each fix has a test. Both were also checked in FreeCADCmd 1.1.4.

## Rule

Check a change to how a build script starts with a real `freecadcmd build_model.py` run, not only
with plain Python. Check a change to a frame or a joint with a rebuild of an existing document,
not only with a new one.

<details>
<summary>Technical notes</summary>

- A probe under FreeCADCmd 1.1.4 prints `__name__ == "probe"` and
  `__spec__ == ModuleSpec(name='probe', ...)`, with only `<frozen importlib...>` frames above the
  module frame. `python -c "import probe"` has a `<string>` frame above them.
- `_is_import()` now walks out to the script's `<module>` frame and checks for a non-importlib
  caller. If it cannot find the script frame, it still answers "import", so a real import never
  builds by accident.
- `_angle_in_degrees()` uses `evalExpression()`. On a new document it may fail before the first
  recompute; then it uses 0 and the first recompute evaluates the new expression, as before.

</details>
