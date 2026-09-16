"""Export geometry for one composition and model, on demand.

Variant exports are **not** committed per model.  A family with a handful of
lengths and a few compositions would otherwise carry a growing matrix of STEP
files that every core change invalidates.  Geometry is regenerated when someone
needs it, and only pinned where a real machine was built — under
``builds/<id>/exports/``.

Three things this never does, each of which it used to:

* **It does not write into the module.**  The active parameter set is resolved
  into a temporary directory, so exporting ``500mm`` cannot switch the model
  someone is working at, and the family a machine consumes stays untouched.
* **It does not save the document it opens.**  ``Import.export`` works on
  in-memory objects; the committed ``.FCStd`` is the human's to write.
* **It does not trust the exit code.**  FreeCAD writes to a staging file that
  is moved into place only if it appears, so a failed run can neither report
  success nor destroy a pinned export already sitting at ``--out``.

Parameters come from the module that owns them: a composition is thin by
design and names its core in ``[composition]``.  See ``param_rules.params_owner``.

Requires a FreeCAD binary.  The resolver steps run without one, so a dry run
still tells you exactly what would be produced.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import resolve_params
from naming_rules import repo_root_from_script
from param_rules import ParamError, params_owner, resolve_model

#: The macro runs from a generated file, so nothing in it may infer a location
#: from ``__file__`` — that is how ``params.csv`` once resolved to
#: ``/tmp/params.csv``.  ``scripts`` goes onto ``sys.path`` explicitly and the
#: resolved parameter CSV is passed by absolute path.
MACRO = '''
import sys
import FreeCAD, Import
sys.path.insert(0, {scripts!r})
import cad_sync_params
doc = FreeCAD.openDocument({source!r})
# save=False: the committed .FCStd is the human's to write. See cad_build.run().
cad_sync_params.sync_active(doc=doc, csv_path={params_csv!r}, save=False)
doc.recompute()
objects = [o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]
if not objects:
    raise RuntimeError("nothing to export: no object with a non-null Shape in " + doc.Name)
Import.export(objects, {step!r})
FreeCAD.closeDocument(doc.Name)
'''


def render_macro(*, scripts: Path, source: Path, params_csv: Path, step: Path) -> str:
    """The macro text for one export.  Pure, so tests can compile and run it."""
    return MACRO.format(
        scripts=str(scripts), source=str(source),
        params_csv=str(params_csv), step=str(step),
    )


def find_freecad(explicit: str | None) -> str | None:
    for candidate in ([explicit] if explicit else []) + ["freecadcmd", "FreeCADCmd", "freecad"]:
        if candidate and shutil.which(candidate):
            return shutil.which(candidate)
    return None


def _rel(root: Path, path: Path) -> str:
    """Repo-root-relative when possible, absolute otherwise — for printing."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export one variant's geometry.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--module", type=Path, required=True,
                        help="Composition or core module, relative to --root. A "
                             "composition's parameters are read from the core its "
                             "[composition] table names.")
    parser.add_argument("--model", default="default")
    parser.add_argument("--source", default=None,
                        help="FCStd to open, relative to the current directory "
                             "(default: <module>/cad/assemblies/<module>.FCStd)")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output .step, relative to the current directory "
                             "(default: <module>/cad/exports/<model>/<module>.step)")
    parser.add_argument("--freecad", default=None, help="Path to the FreeCAD binary")
    parser.add_argument("--dry-run", action="store_true",
                        help="Resolve parameters and report, without running FreeCAD")
    args = parser.parse_args()

    root = args.root.resolve() if args.root else repo_root_from_script()
    module_dir = (root / args.module).resolve()
    name = module_dir.name

    try:
        core_dir = params_owner(module_dir)
        params = resolve_model(core_dir, args.model)
        active_csv = resolve_params.render_active(core_dir, args.model)
    except ParamError as exc:
        print(f"FAIL  {args.module.as_posix()}")
        print(f"      {exc}")
        return 1

    source = (Path(args.source) if args.source
              else module_dir / "cad" / "assemblies" / f"{name}.FCStd").resolve()
    out = (args.out or module_dir / "cad" / "exports" / args.model / f"{name}.step").resolve()
    scripts_dir = Path(__file__).resolve().parent

    print(f"module {args.module.as_posix()}  model {args.model}  "
          f"({len(params)} parameters)")
    if core_dir != module_dir:
        print(f"params {_rel(root, core_dir)}  (the core this composition names)")
    print(f"source {source}")
    print(f"out    {out}")

    if args.dry_run:
        print("ok    dry run — nothing exported")
        return 0
    if not source.exists():
        print(f"FAIL  source not found: {source}")
        return 1
    binary = find_freecad(args.freecad)
    if binary is None:
        print("FAIL  no FreeCAD binary found; pass --freecad PATH, or use --dry-run")
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    # Staging sits next to the real output so the final move is an atomic,
    # same-filesystem rename — and so a failed run can neither leave a partial
    # STEP behind nor destroy a pinned builds/<id>/exports/ file already there.
    staging = Path(tempfile.mkdtemp(prefix=f".{out.stem}-", dir=out.parent))
    try:
        staged = staging / out.name        # keeps the suffix: Import picks format by it
        params_csv = staging / "params.csv"
        params_csv.write_text(active_csv, encoding="utf-8")

        macro_path = staging / "export-macro.py"
        macro_path.write_text(render_macro(
            scripts=scripts_dir, source=source, params_csv=params_csv, step=staged,
        ), encoding="utf-8")

        result = subprocess.run([binary, str(macro_path)])
        if result.returncode != 0 or not staged.exists() or staged.stat().st_size == 0:
            wrote = "no file" if not staged.exists() else "an empty file"
            print(f"FAIL  export failed for {args.module.as_posix()} @ {args.model}")
            print(f"      {binary} exited {result.returncode} and wrote {wrote}; "
                  f"{out} was left untouched")
            return 1
        try:
            os.replace(staged, out)
        except OSError as exc:
            print(f"FAIL  could not move the export into place: {exc}")
            return 1
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
