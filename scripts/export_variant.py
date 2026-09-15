"""Export geometry for one composition and model, on demand.

Variant exports are **not** committed per model.  A family with a handful of
lengths and a few compositions would otherwise carry a growing matrix of STEP
files that every core change invalidates.  Geometry is regenerated when someone
needs it, and only pinned where a real machine was built — under
``builds/<id>/exports/``.

Requires a FreeCAD binary.  The resolver steps run without one, so a dry run
still tells you exactly what would be produced.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from naming_rules import repo_root_from_script
from param_rules import ParamError, resolve_model

MACRO = '''
import FreeCAD, Import, Mesh, os
doc = FreeCAD.openDocument({source!r})
exec(open({sync!r}).read())
doc.recompute()
objects = [o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]
Import.export(objects, {step!r})
FreeCAD.closeDocument(doc.Name)
'''


def find_freecad(explicit: str | None) -> str | None:
    for candidate in ([explicit] if explicit else []) + ["freecadcmd", "FreeCADCmd", "freecad"]:
        if candidate and shutil.which(candidate):
            return shutil.which(candidate)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Export one variant's geometry.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--module", type=Path, required=True,
                        help="Composition (or core) module, relative to --root")
    parser.add_argument("--model", default="default")
    parser.add_argument("--source", default=None,
                        help="FCStd to open (default: cad/assemblies/<module>.FCStd)")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output .step (default: <module>/cad/exports/<model>/<module>.step)")
    parser.add_argument("--freecad", default=None, help="Path to the FreeCAD binary")
    parser.add_argument("--dry-run", action="store_true",
                        help="Resolve parameters and report, without running FreeCAD")
    args = parser.parse_args()

    root = args.root.resolve() if args.root else repo_root_from_script()
    module_dir = (root / args.module).resolve()
    name = module_dir.name

    try:
        params = resolve_model(module_dir, args.model)
    except ParamError as exc:
        print(f"FAIL  {args.module.as_posix()}")
        print(f"      {exc}")
        return 1

    source = Path(args.source) if args.source else module_dir / "cad" / "assemblies" / f"{name}.FCStd"
    out = args.out or module_dir / "cad" / "exports" / args.model / f"{name}.step"
    sync = module_dir / "cad" / "sync_params.py"

    print(f"module {args.module.as_posix()}  model {args.model}  "
          f"({len(params)} parameters)")
    print(f"source {source}")
    print(f"out    {out}")

    if args.dry_run:
        print("ok    dry run — nothing exported")
        return 0
    if not source.exists():
        print(f"FAIL  source not found: {source}")
        return 1
    if not sync.exists():
        print(f"FAIL  {sync} not found — copy it from doqs/templates/cad/sync_params.py")
        return 1

    binary = find_freecad(args.freecad)
    if binary is None:
        print("FAIL  no FreeCAD binary found; pass --freecad PATH, or use --dry-run")
        return 1

    # The active params.csv drives the model, so resolve it first.
    resolver = Path(__file__).resolve().parent / "resolve_params.py"
    subprocess.run([sys.executable, str(resolver), "--root", str(root),
                    "--module", str(args.module), "--model", args.model], check=True)

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as macro:
        macro.write(MACRO.format(source=str(source), sync=str(sync), step=str(out)))
        macro_path = macro.name
    try:
        result = subprocess.run([binary, macro_path])
    finally:
        Path(macro_path).unlink(missing_ok=True)

    if result.returncode != 0 or not out.exists():
        print(f"FAIL  export failed for {args.module.as_posix()} @ {args.model}")
        return 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
