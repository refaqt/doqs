"""Add one interface between two parts: SysML, manifest entry, and frames.

    python doqs/scripts/add_interface.py --module modules/compact-stage --name RailMount \\
        --a base.referenceRailMount --b referenceRail.baseMount \\
        [--doc "..."] [--attribute "holePitch : LengthValue = 60 [mm]"] \\
        [--outside provides|consumes] [--no-frames] [--library-checkout ../stoq-private]

`doqs add-interface` runs the same thing. From one request it writes the
three places an interface lives, with the names one rule gives them
(docs/decisions/2026-10-07_port-and-frame-share-a-name.md):

1. SysML: `port def RailMountInterface_v1` in the module's package (if
   missing), a plain port on side A, a conjugate port on side B, and a
   `connect` in the assembly's part def.
2. `okh.toml`: with `--outside`, a `[[provides-interface]]` or
   `[[consumes-interface]]` entry.
3. FreeCAD: a mounting frame `IF_<port>` in each part's file, at the origin.
   An own part gets it through its build script (a `frame()` call) and
   through FreeCAD on the saved document. A library part's wrapper lives in
   the mounted library, which a machine never edits: the frame is applied in
   the library checkout named by `--library-checkout`, or reported as the
   next step, so it goes through the library's pull request.

The designer then places each frame in FreeCAD. A rerun changes nothing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import cad_build
import freecad_rules
import install_module
import interface_rules as ir
import okh_rules
import sysml_rules
from naming_rules import repo_root_from_script
from report_rules import Report
from validate_variants import library_part, mounted_libraries

SCRIPTS = Path(__file__).resolve().parent

#: Applies frames to a saved document. Headless is fine: a frame needs no
#: colours. The document is saved only when this run opened it; a document
#: already open in the window is edited in memory and the person saves it.
FRAMES_MACRO = '''
import cad_build, cad_fingerprint
path = {path!r}
labels = {labels!r}
open_already = [d for d in FreeCAD.listDocuments().values() if d.FileName and d.FileName.replace("\\\\", "/") == path.replace("\\\\", "/")]
doc = open_already[0] if open_already else FreeCAD.openDocument(path)
before = {{o.Name for o in doc.Objects}}
doc.openTransaction("doqs add-interface: frames")
for label in labels:
    cad_build.frame(doc, label)
doc.recompute()
cad_build.show_new_objects(doc, before)
doc.commitTransaction()
if open_already:
    print("DOQS_SAVED=false")
else:
    doc.save()
    if {fingerprint!r}:
        try:
            params = cad_fingerprint.read_params(path=cad_build.params_path({cad_dir!r}, fcstd=path))
            cad_fingerprint.write(doc, params=params, cad_dir={cad_dir!r})
        except Exception as exc:
            print("fingerprint not written:", exc)
    print("DOQS_SAVED=true")
    FreeCAD.closeDocument(doc.Name)
'''

_BUILD_DEF = re.compile(r"^def build\(doc, params\):\n", re.M)
_DOCSTRING_END = re.compile(r'^    """.*?"""\n', re.M | re.S)
FRAME_CALL_COMMENT = "    # Mounting frames added by doqs add-interface; place them with Params.\n"


def add_frame_call(script: str, label: str) -> str:
    """Insert ``frame(doc, "IF_x")`` at the start of ``build()``. Unchanged when present."""
    if re.search(rf'frame\(\s*doc\s*,\s*["\']{re.escape(label)}["\']', script):
        return script
    m = _BUILD_DEF.search(script)
    if not m:
        raise ValueError("no `def build(doc, params):` in the build script")
    pos = m.end()
    doc_m = _DOCSTRING_END.match(script, pos)
    if doc_m:
        pos = doc_m.end()
    line = f'    frame(doc, "{label}")\n'
    if FRAME_CALL_COMMENT in script:
        anchor = script.index(FRAME_CALL_COMMENT) + len(FRAME_CALL_COMMENT)
        # After the last existing frame call under the comment.
        rest = script[anchor:]
        n = 0
        for raw in rest.splitlines(keepends=True):
            if raw.startswith("    frame(doc,"):
                n += len(raw)
            else:
                break
        return script[:anchor + n] + line + script[anchor + n:]
    return script[:pos] + FRAME_CALL_COMMENT + line + script[pos:]


def _parse_side(side: str) -> tuple[str, str]:
    if "." not in side:
        raise ValueError(f"{side!r} must be <usage>.<port>, like base.referenceRailMount")
    usage, port = side.rsplit(".", 1)
    if not ir.is_port_name(port):
        raise ValueError(f"{port!r} must be a lowerCamelCase port name")
    return usage, port


def _part_file(root: Path, module_dir: Path, okh_text: str, part_def: str) -> tuple[Path | None, str]:
    """``(file, kind)`` for a part def: ``own`` from [[part]], ``library`` from [[bought-part]]."""
    data = okh_rules.load(okh_text)
    for entry in data.get("part", []) or []:
        if entry.get("sysml") == part_def:
            sources = entry.get("source") or []
            if sources:
                return module_dir / sources[0], "own"
    for entry in data.get("bought-part", []) or []:
        if entry.get("sysml") == part_def:
            ref = str(entry.get("part", ""))
            lib_name, _, part = ref.partition(":")
            mount = next((m for m in mounted_libraries(root) if Path(m).name == lib_name), None)
            if mount is None:
                return None, "library"
            row, family = library_part(root, mount, part)
            if row and (row.get("cad") or "").strip():
                return root / mount / family / row["cad"].strip(), "library"
            return None, "library"
    return None, "unknown"


def add_interface(root: Path, module: Path, name: str, a: str, b: str, *, major: int = 1,
                  doc: str | None = None, attributes: list[str] | None = None,
                  outside: str | None = None, frames: bool = True,
                  library_checkout: Path | None = None, mode: str = "auto",
                  freecad: str | None = None, dry_run: bool = False) -> Report:
    report = Report("add-interface", root=str(root), dry_run=dry_run)
    module_dir = (root / module).resolve()
    okh = module_dir / "okh.toml"
    slug = module_dir.name
    arch = module_dir / "architecture" / f"{slug}.sysml"
    if not okh.is_file() or not arch.is_file():
        report.fail(f"{report.rel(module_dir)} needs okh.toml and architecture/{slug}.sysml")
        return report
    try:
        usage_a, port_a = _parse_side(a)
        usage_b, port_b = _parse_side(b)
    except ValueError as exc:
        report.fail(str(exc))
        return report
    if outside not in (None, "provides", "consumes"):
        report.fail("--outside must be provides or consumes")
        return report
    package = install_module.pascal_case(slug)
    assembly = f"{package}::{package}"
    port_def = ir.port_def_name(name, major)
    text = arch.read_text(encoding="utf-8")
    tree = sysml_rules.parse(text)
    sides = []
    for usage, port in ((usage_a, port_a), (usage_b, port_b)):
        node = sysml_rules.find(tree, f"{assembly}.{usage}")
        if node is None or node.kind != "part" or not node.type_name:
            report.fail(f"{assembly} has no part usage {usage!r}; run `doqs use-part` or "
                        "`doqs scaffold part` first")
            return report
        part_def = node.type_name.split("::")[-1]
        if sysml_rules.find(tree, f"{package}::{part_def}") is None:
            report.fail(f"part def {part_def} is not in {report.rel(arch)}; a library part's "
                        "ports must be declared here for now")
            return report
        sides.append((usage, port, part_def))

    # --- SysML ---------------------------------------------------------
    try:
        updated = sysml_rules.add_port_def(text, package, port_def, doc=doc, attributes=tuple(attributes or ()))
        (usage_a, port_a, def_a), (usage_b, port_b, def_b) = sides
        updated = sysml_rules.add_port(updated, f"{package}::{def_a}", port_a, port_def, conjugated=False)
        updated = sysml_rules.add_port(updated, f"{package}::{def_b}", port_b, port_def, conjugated=True)
        updated = sysml_rules.add_connect(updated, assembly, f"{usage_a}.{port_a}", f"{usage_b}.{port_b}",
                                          comment=f"{name}: {usage_a} to {usage_b}")
    except sysml_rules.SysmlError as exc:
        report.fail(str(exc))
        return report
    if updated != text:
        if not dry_run:
            arch.write_text(updated, encoding="utf-8")
        report.changed(arch)
    else:
        report.kept(arch, "interface exists")

    # --- okh.toml ------------------------------------------------------
    okh_text = okh.read_text(encoding="utf-8")
    if outside:
        entry = ir.okh_entry(port_def)
        if doc:
            entry["description"] = doc
        new_okh = okh_rules.append_table(okh_text, f"[[{outside}-interface]]", entry,
                                         match={"name": entry["name"], "version": entry["version"]})
        if new_okh != okh_text:
            if not dry_run:
                okh.write_text(new_okh, encoding="utf-8")
            report.changed(okh)
        else:
            report.kept(okh, "entry exists")

    # --- frames --------------------------------------------------------
    report.facts.update({"port_def": port_def, "a": a, "b": b, "frames": {}})
    if frames:
        for usage, port, part_def in sides:
            label = ir.frame_label(port)
            file, kind = _part_file(root, module_dir, okh_text, part_def)
            report.facts["frames"][label] = {"part": part_def, "file": report.rel(file) if file else None, "kind": kind}
            if file is None:
                report.warn(f"{part_def}: no file known for the frame {label} "
                            f"({'no [[part]] or [[bought-part]] names it' if kind == 'unknown' else 'library row has no cad'})")
                continue
            if kind == "own":
                _own_frame(report, root, module_dir, file, label, mode, freecad, dry_run)
            else:
                _library_frame(report, root, file, label, library_checkout, mode, freecad, dry_run)
    report.then("Open each part in FreeCAD and place its new frame with expressions over Params.")
    return report


def _own_frame(report: Report, root: Path, module_dir: Path, file: Path, label: str,
               mode: str, freecad: str | None, dry_run: bool) -> None:
    script = file.parent / "build_model.py"
    if script.is_file():
        source = script.read_text(encoding="utf-8")
        try:
            new_source = add_frame_call(source, label)
        except ValueError as exc:
            report.warn(f"{report.rel(script)}: {exc}")
            new_source = source
        if new_source != source:
            if not dry_run:
                script.write_text(new_source, encoding="utf-8")
            report.changed(script)
        else:
            report.kept(script, f"calls frame {label}")
    if not file.is_file():
        report.warn(f"{report.rel(file)} does not exist yet; the frame is added when it does")
        return
    _apply_frames(report, file, [label], fingerprint=True, cad_dir=cad_build.module_cad_dir(file.parent),
                  mode=mode, freecad=freecad, dry_run=dry_run)


def _library_frame(report: Report, root: Path, file: Path, label: str, checkout: Path | None,
                   mode: str, freecad: str | None, dry_run: bool) -> None:
    rel_in_library = None
    for mount in mounted_libraries(root):
        try:
            rel_in_library = file.resolve().relative_to((root / mount).resolve())
            break
        except ValueError:
            continue
    if checkout is None or rel_in_library is None:
        report.then(f"Library part: add the frame {label} to {report.rel(file)} in the library "
                    "checkout and open its pull request (or pass --library-checkout).")
        return
    target = checkout.resolve() / rel_in_library
    if not target.is_file():
        report.warn(f"{target} is missing in the library checkout; fetch or restore it first")
        return
    saved = report.root
    report.root = str(checkout.resolve())
    try:
        _apply_frames(report, target, [label], fingerprint=False, cad_dir=target.parent,
                      mode=mode, freecad=freecad, dry_run=dry_run)
    finally:
        report.root = saved
    report.then(f"Open the library pull request with the new frame {label}, then bump the pin.")


def render_frames_macro(scripts: Path, *, path: Path, labels: list[str], fingerprint: bool,
                        cad_dir: Path) -> str:
    body = FRAMES_MACRO.format(path=str(path), labels=list(labels), fingerprint=fingerprint,
                               cad_dir=str(cad_dir))
    return freecad_rules.render_macro(scripts, body)


def _apply_frames(report: Report, file: Path, labels: list[str], *, fingerprint: bool, cad_dir: Path,
                  mode: str, freecad: str | None, dry_run: bool) -> None:
    from cad_rules import frames as read_frames

    have = {label for _, label in read_frames(file)}
    missing = [l for l in labels if l not in have]
    if not missing:
        report.kept(file, f"has {', '.join(labels)}")
        return
    if dry_run:
        report.changed(file)
        return
    macro = render_frames_macro(SCRIPTS, path=file, labels=missing, fingerprint=fingerprint, cad_dir=cad_dir)
    result = freecad_rules.run_macro(macro, mode=mode, freecad=freecad, needs_gui=False)
    if not result.ok:
        report.fail(f"FreeCAD did not add {', '.join(missing)} to {report.rel(file)}: {result.error}")
        return
    if "DOQS_SAVED=false" in result.output:
        report.warn(f"{report.rel(file)} is open in FreeCAD: the frame is added there but not saved. "
                    "Save it (Ctrl+S) and rebuild the fingerprint.")
    else:
        report.changed(file)
        fp = file.with_name(file.stem + ".fingerprint.json")
        if fingerprint and fp.is_file():
            report.changed(fp)
    report.facts.setdefault("freecad", result.mode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--name", required=True, help="Interface name, like RailMount")
    parser.add_argument("--major", type=int, default=1)
    parser.add_argument("--a", required=True, help="<usage>.<port> on the providing side")
    parser.add_argument("--b", required=True, help="<usage>.<port> on the conjugate side")
    parser.add_argument("--doc", default=None)
    parser.add_argument("--attribute", action="append", default=[], help='Like "holePitch : LengthValue = 60 [mm]"')
    parser.add_argument("--outside", default=None, choices=["provides", "consumes"])
    parser.add_argument("--no-frames", action="store_true")
    parser.add_argument("--library-checkout", type=Path, default=None)
    parser.add_argument("--mode", default="auto", choices=freecad_rules.MODES)
    parser.add_argument("--freecad", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_script()
    report = add_interface(root, args.module, args.name, args.a, args.b, major=args.major, doc=args.doc,
                           attributes=args.attribute, outside=args.outside, frames=not args.no_frames,
                           library_checkout=args.library_checkout, mode=args.mode, freecad=args.freecad,
                           dry_run=args.dry_run)
    return report.emit(args.json)


if __name__ == "__main__":
    sys.exit(main())
