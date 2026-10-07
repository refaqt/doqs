"""Build the FreeCAD wrapper of a library part from the brand's STEP file.

    python doqs/scripts/export_wrapper.py --library ../stoq-private \\
        --part hiwin/hgl-block#HGL15CAZBC+E2 --frames IF_rail,IF_carriage \\
        [--mirror ../stoq] [--mode auto|rpc|gui|cmd] [--freecad PATH]

`doqs wrap` runs the same thing. The wrapper is `cad/parts/<pn>.FCStd` in
the family folder: one Part container labelled with the part number, the
brand's solids with their colours, and one `IF_` frame per attachment place,
at the origin until the designer places it in FreeCAD. The `cad` cell of the
part's row then points at it.

Colours survive only through the GUI importer, so the job runs in the open
FreeCAD window (through the RPC server of the freecad-mcp add-on) or in a
window started for the job. FreeCADCmd is refused.

With `--mirror`, the other library gets the same wrapper when it may hold
it: always when that library is private, and in the public one only when
the brand's newest `cad` decision is `public`. Otherwise the public row still
names the path and `.gitignore` keeps the file out.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import apply_unshare
import freecad_rules
import library_rules as lr
from cad_rules import FRAME_PREFIX, FRAME_TYPE, PART_TYPE, document_tree, frames as read_frames, object_labels
from intake_rules import latest_review
from naming_rules import is_parts_library, is_private_library
from report_rules import Report
from validate_variants import family_path_of

SCRIPTS = Path(__file__).resolve().parent

MACRO_BODY = '''
import cad_wrap_step
cad_wrap_step.run({step!r}, {out!r}, {label!r}, {frames!r})
'''


def render_wrap_macro(scripts: Path, *, step: Path, out: Path, label: str,
                      frames: list[str], close_gui: bool) -> str:
    """The macro text, pure so a test can run it against the stub."""
    body = MACRO_BODY.format(step=str(step), out=str(out), label=label, frames=list(frames))
    return freecad_rules.render_macro(scripts, body, close_gui=close_gui)


def split_reference(part: str) -> tuple[str, str, str]:
    """``hiwin/hgl-block#HGL15`` -> ``("hiwin", "hgl-block", "HGL15")``."""
    if "#" not in part:
        raise ValueError(f"{part!r} must look like brand/family#part-number")
    path, pn = part.split("#", 1)
    if "/" not in path:
        raise ValueError(f"{part!r} must look like brand/family#part-number")
    brand, family = path.split("/", 1)
    return brand, family, pn


def _family_dir(library: Path, brand: str, family: str) -> Path:
    return library / "modules" / brand / "modules" / family


def _find_step(family_dir: Path, pn: str) -> Path | None:
    _, rows = lr.read_rows(family_dir / "vendor-index.csv")
    for row in rows:
        rel = (row.get("relpath") or "").strip()
        if (row.get("pn") or "").strip() == pn and rel.lower().endswith((".step", ".stp")):
            return family_dir / rel
    for suffix in (".step", ".stp", ".STEP", ".STP"):
        candidate = family_dir / "cad" / "original" / f"{pn}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def tree_from_output(output: str) -> dict | None:
    """The tree the macro printed, or ``None``."""
    for line in output.splitlines():
        if line.startswith("DOQS_TREE="):
            try:
                return json.loads(line[len("DOQS_TREE="):])
            except json.JSONDecodeError:
                return None
    return None


def check_wrapper(out: Path, frames: list[str], printed: dict | None) -> list[str]:
    """Why the wrapper is not right: no Part on top, missing frames."""
    problems: list[str] = []
    if not out.is_file() or out.stat().st_size == 0:
        return [f"{out} was not written"]
    objects = document_tree(out)
    labels = object_labels(out)
    if objects:
        found = [(n, labels.get(n, n)) for n, t, _ in objects if t == FRAME_TYPE]
        held = {m for _, _, members in objects for m in members}
        tops = [(n, t) for n, t, _ in objects if n not in held]
    elif printed:
        objects = [tuple(o) for o in printed.get("objects", [])]
        labels = printed.get("labels", {})
        found = [(n, labels.get(n, n)) for n, t, _ in objects if t == FRAME_TYPE]
        held = {m for _, _, members in objects for m in members}
        tops = [(n, t) for n, t, _ in objects if n not in held]
    else:
        return [f"{out} could not be read and the macro printed no tree"]
    top_parts = [n for n, t in tops if t == PART_TYPE]
    if len(top_parts) != 1:
        problems.append(f"expected one Part container on top, found {len(top_parts)}: {tops}")
    have = {label for _, label in found}
    for label in frames:
        if label not in have:
            problems.append(f"frame {label} is missing")
    return problems


def wrap_part(library: Path, part: str, *, frames: list[str], label: str | None = None,
              out: Path | None = None, mirror: Path | None = None, mode: str = "auto",
              freecad: str | None = None, dry_run: bool = False) -> Report:
    report = Report("wrap", root=str(library), dry_run=dry_run)
    library = library.resolve()
    if not is_parts_library(library):
        report.fail(f"{library} is not a parts library")
        return report
    try:
        brand, family, pn = split_reference(part)
    except ValueError as exc:
        report.fail(str(exc))
        return report
    for frame in frames:
        if not frame.startswith(FRAME_PREFIX):
            report.fail(f"frame {frame!r} must start with {FRAME_PREFIX}, like IF_mount_bottom")
    if not report.ok:
        return report
    family_dir = _family_dir(library, brand, family)
    table = family_dir / "bom" / "parts.csv"
    _, rows = lr.read_rows(table)
    row = next((r for r in rows if (r.get("pn") or "").strip() == pn), None)
    if row is None:
        report.fail(f"{pn} is not a row of {report.rel(table)}; run `doqs add-part` first")
        return report
    step = _find_step(family_dir, pn)
    if step is None or not step.is_file():
        report.fail(f"no STEP file for {pn} under {report.rel(family_dir / 'cad' / 'original')}. "
                    "Fetch it from the brand, or `doqs restore-private --from <private library>`.")
        return report
    label = label or pn
    out = (out or family_dir / "cad" / "parts" / f"{pn}.FCStd").resolve()
    report.facts.update({"step": report.rel(step), "document": report.rel(out), "frames": frames})
    if out.is_file():
        report.kept(out, "exists; delete it to wrap again")
    elif dry_run:
        report.wrote(out)
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        macro = render_wrap_macro(SCRIPTS, step=step, out=out, label=label, frames=frames,
                                  close_gui=(mode == "gui"))
        if mode == "auto":
            # A window started for the job must close itself; the open window must not.
            macro_rpc = render_wrap_macro(SCRIPTS, step=step, out=out, label=label, frames=frames, close_gui=False)
            macro_gui = render_wrap_macro(SCRIPTS, step=step, out=out, label=label, frames=frames, close_gui=True)
            result = freecad_rules.run_macro(macro_rpc, mode="rpc", freecad=freecad, needs_gui=True) \
                if freecad_rules.rpc_available() else None
            if result is None or not result.ok:
                result = freecad_rules.run_macro(macro_gui, mode="gui", freecad=freecad, needs_gui=True)
        else:
            result = freecad_rules.run_macro(macro, mode=mode, freecad=freecad, needs_gui=True)
        for step_line in result.steps:
            report.facts.setdefault("freecad_steps", []).append(step_line)
        if not result.ok:
            report.fail(f"FreeCAD did not wrap {pn}: {result.error}")
            return report
        problems = check_wrapper(out, frames, tree_from_output(result.output))
        if problems:
            for problem in problems:
                report.fail(problem)
            return report
        report.wrote(out)
        report.facts["freecad"] = result.mode
    cad_rel = out.relative_to(family_dir).as_posix() if out.is_relative_to(family_dir) else str(out)
    if not dry_run and lr.set_cell(table, "pn", pn, "cad", cad_rel):
        report.changed(table)
    else:
        report.kept(table, "cad already set") if not dry_run else report.changed(table)

    if mirror is not None:
        _mirror(report, library, mirror.resolve(), brand, family, pn, out, cad_rel, dry_run)
    report.then("Open the wrapper in FreeCAD and place each frame with the catalogue values; "
                "joints attach to these frames.")
    return report


def _mirror(report: Report, library: Path, other: Path, brand: str, family: str, pn: str,
            out: Path, cad_rel: str, dry_run: bool) -> None:
    if not is_parts_library(other):
        report.fail(f"{other} is not a parts library")
        return
    other_family = _family_dir(other, brand, family)
    other_table = other_family / "bom" / "parts.csv"
    if not other_table.is_file():
        report.warn(f"{other.name} has no row for {pn}; run `doqs add-part` for both libraries")
        return
    target = other_family / cad_rel
    may_hold = is_private_library(other)
    if not may_hold:
        review = latest_review(other / "modules" / brand / "okh.toml", "cad")
        may_hold = bool(review and review.get("decision") == "public")
    saved = report.root
    report.root = str(other)
    try:
        if may_hold:
            if target.is_file():
                report.kept(target, "exists")
            else:
                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(out, target)
                report.wrote(target)
        else:
            rel = target.relative_to(other).as_posix()
            if not dry_run and apply_unshare.add_to_gitignore(other, [rel]):
                report.changed(other / ".gitignore")
            report.warn(f"{other.name}: the cad decision is not public, so {rel} stays out of git there")
        if not dry_run and lr.set_cell(other_table, "pn", pn, "cad", cad_rel):
            report.changed(other_table)
    finally:
        report.root = saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--library", type=Path, required=True, help="The library that holds the STEP")
    parser.add_argument("--part", required=True, help="brand/family#part-number")
    parser.add_argument("--frames", default="", help="Comma-separated IF_ labels")
    parser.add_argument("--label", default=None, help="Label of the Part container (default: the part number)")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--mirror", type=Path, default=None, help="The other library checkout")
    parser.add_argument("--mode", default="auto", choices=freecad_rules.MODES)
    parser.add_argument("--freecad", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    frames = [f.strip() for f in args.frames.split(",") if f.strip()]
    report = wrap_part(args.library, args.part, frames=frames, label=args.label, out=args.out,
                       mirror=args.mirror, mode=args.mode, freecad=args.freecad, dry_run=args.dry_run)
    return report.emit(args.json)


if __name__ == "__main__":
    sys.exit(main())
