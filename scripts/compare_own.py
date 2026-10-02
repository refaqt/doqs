"""Compare a model we drew with the brand's own model, without copying from it.

    bash doqs.sh compare-own hiwin/hgr-rail HGR20R1000 --from ../stoq-private

It runs a headless FreeCAD in a temporary folder outside both repositories. That
FreeCAD loads a copy of the brand's STEP from the private library and a
read-only copy of our model, measures both, and turns the measurements into
words before anything leaves it (`compare_rules.py`). So no brand value is ever
printed, logged or saved.

What it writes, into `cad/own/<pn>.checks.csv` only:

* `result` and `method` of the `envelope X`, `envelope Y`, `envelope Z` and
  `symmetry ...` rows, and their `checked_utc`. Other rows stay as they are.

What it says, in words:

* whether both models use the same axes and origin,
* the mirror planes of each model,
* every brand feature that sticks out of our model and has no counterpart.

It never saves either model. It checks our model against its fingerprint and
the brand's file against its recorded checksum before it starts, and checks
all of them again after FreeCAD has finished. If anything changed, it writes
nothing.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import io
import json
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import compare_rules
from cad_rules import FingerprintError, file_digest, fingerprint_path, load_fingerprint
from intake_rules import CHECKS_HEADERS, CHECKS_SUFFIX, ENVELOPE_ROW, OWN_MODEL_DIR, SYMMETRY_ROW
from naming_rules import csv_reader_skipping_comments, repo_root_from_script
from validate_variants import VENDOR_INDEX, family_path_of

#: Suffixes of a brand's 3D file that FreeCAD reads with `Part.read`.
STEP_SUFFIXES = (".step", ".stp")

#: A piece of the brand model smaller than this, in cubic millimetres, is
#: modelling noise (a fillet, a thread), not a feature that can collide.
MIN_PIECE_VOLUME = 1.0

ENVELOPE_METHOD = (
    "Extent along {axis} of the bounding box of all solids, measured the same "
    "way on both models in a headless FreeCAD run by doqs compare-own")
SYMMETRY_METHOD = (
    "Bounding box and centre of mass compared with their mirror image in the "
    "{plane} plane through the origin, on both models, by doqs compare-own")
NO_SYMMETRY_METHOD = (
    "Bounding box and centre of mass checked for a mirror plane through the "
    "origin (YZ, XZ, XY), on both models, by doqs compare-own")

#: Runs inside FreeCAD. It prints nothing and writes only the words that
#: `compare_rules.verdicts` returns. It never calls save().
MACRO = '''
import json
import sys
sys.path.insert(0, {scripts!r})
import FreeCAD
import Part
import compare_rules


def box(shape):
    b = shape.BoundBox
    return [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]


def centre(shape):
    for name in ("CenterOfMass", "CenterOfGravity"):
        try:
            point = getattr(shape, name)
        except (AttributeError, RuntimeError):
            continue
        return [point.x, point.y, point.z]
    return None


brand = Part.read({brand!r})
doc = FreeCAD.openDocument({own!r})
parts = [o for o in doc.Objects if o.TypeId == "App::Part"]
if not parts:
    raise RuntimeError("our model has no Part container")
own = Part.makeCompound([Part.getShape(o) for o in parts])
missing = [box(p) for p in brand.cut(own).Solids if p.Volume > {min_volume!r}]
overlap = brand.common(own).Volume / max(brand.Volume, own.Volume)
result = compare_rules.verdicts(
    own_box=box(own), own_centre=centre(own),
    brand_box=box(brand), brand_centre=centre(brand),
    overlap=overlap, missing=missing, tol={tol!r},
)
FreeCAD.closeDocument(doc.Name)
with open({out!r}, "w", encoding="utf-8") as f:
    json.dump(result, f)
'''


class CompareError(Exception):
    """A reason not to compare, or not to trust a comparison."""


def find_freecad(explicit: str | None) -> str | None:
    for candidate in ([explicit] if explicit else []) + ["freecadcmd", "FreeCADCmd"]:
        if candidate and shutil.which(candidate):
            return shutil.which(candidate)
    return None


def brand_step(family_dir: Path, pn: str) -> tuple[str, str]:
    """The brand's STEP for this part, from vendor-index.csv: (relpath, sha256)."""
    index = family_dir / VENDOR_INDEX
    if not index.is_file():
        raise CompareError(f"no {VENDOR_INDEX} in {family_dir}")
    for row in csv_reader_skipping_comments(index.read_text(encoding="utf-8")):
        relpath = (row.get("relpath") or "").strip()
        if (row.get("pn") or "").strip() == pn and relpath.lower().endswith(STEP_SUFFIXES):
            digest = (row.get("sha256") or "").strip().lower()
            if not digest:
                raise CompareError(f"{VENDOR_INDEX}: {pn} has no recorded checksum")
            return relpath, digest
    raise CompareError(
        f"{VENDOR_INDEX}: no STEP file recorded for {pn}. Add its row, with the "
        "checksum, before you compare.")


def fingerprint_matches(fcstd: Path) -> None:
    """Our model must be exactly what its last build saved."""
    try:
        data = load_fingerprint(fingerprint_path(fcstd))
    except FingerprintError as err:
        raise CompareError(f"{err}. Build the model first.") from err
    if not data.get("saved"):
        raise CompareError(f"{fcstd.name}: its fingerprint is not from a saved build")
    if (data.get("sources") or {}).get(fcstd.name) != file_digest(fcstd):
        raise CompareError(
            f"{fcstd.name} changed since its build. Rebuild it with its build script "
            "before you compare.")


def digests(paths: list[Path]) -> dict[str, str]:
    return {str(p): file_digest(p) for p in paths}


def temporary_folder(*outside: Path) -> Path:
    """A fresh folder that is not inside any of the given repositories."""
    folder = Path(tempfile.mkdtemp(prefix="doqs-compare-")).resolve()
    for repo in outside:
        if folder.is_relative_to(repo.resolve()):
            shutil.rmtree(folder, ignore_errors=True)
            raise CompareError(
                f"the temporary folder {folder} is inside {repo}. Set TMPDIR to a "
                "folder outside the repositories.")
    return folder


def run_freecad(binary: str, own: Path, brand: Path, tol: float, show_output: bool,
                outside: tuple[Path, ...] = ()) -> dict:
    """Measure both models in a headless FreeCAD. Returns the verdicts."""
    work = temporary_folder(*outside)
    try:
        own_copy = work / own.name
        brand_copy = work / brand.name
        shutil.copyfile(own, own_copy)
        shutil.copyfile(brand, brand_copy)
        for copy in (own_copy, brand_copy):
            copy.chmod(stat.S_IRUSR | stat.S_IRGRP)
        out = work / "verdicts.json"
        macro = work / "compare_macro.py"
        macro.write_text(MACRO.format(
            scripts=str(Path(__file__).resolve().parent), brand=str(brand_copy),
            own=str(own_copy), out=str(out), tol=tol, min_volume=MIN_PIECE_VOLUME,
        ), encoding="utf-8")
        result = subprocess.run([binary, str(macro)], capture_output=True, text=True, cwd=work)
        if show_output:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
        # FreeCADCmd does not always exit non-zero when a macro fails, so the
        # verdict file decides, not the exit code.
        if not out.is_file():
            raise CompareError(
                "FreeCAD did not finish the comparison. Run again with "
                "--show-freecad-output to see why. That output can hold brand "
                "values: never paste it into the repository.")
        verdicts = json.loads(out.read_text(encoding="utf-8"))
    finally:
        for copy in work.iterdir():
            copy.chmod(stat.S_IRUSR | stat.S_IWUSR)
        shutil.rmtree(work, ignore_errors=True)
    if compare_rules.holds_a_number(verdicts):
        raise CompareError("the comparison returned a number. Nothing was written.")
    return verdicts


def update_checks(text: str, verdicts: dict, now: str) -> tuple[str, list[str]]:
    """New checks.csv text, and one line per row that changed."""
    lines = text.splitlines(keepends=True)
    head = 0
    while head < len(lines) and lines[head].lstrip().startswith("#"):
        head += 1
    reader = csv_reader_skipping_comments("".join(lines[head:]))
    if tuple(h.strip() for h in (reader.fieldnames or [])) != CHECKS_HEADERS:
        raise CompareError(f"the check list header must be exactly {list(CHECKS_HEADERS)}")
    rows = list(reader)
    report = []
    for row in rows:
        dim = (row.get("dimension") or "").strip()
        envelope = ENVELOPE_ROW.match(dim)
        symmetry = SYMMETRY_ROW.match(dim)
        if envelope:
            axis = envelope.group(1)
            result = verdicts["envelope"][axis]
            method = ENVELOPE_METHOD.format(axis=axis)
        elif symmetry:
            plane = symmetry.group(1)
            result = compare_rules.symmetry_verdict(
                plane, verdicts["symmetry_own"], verdicts["symmetry_brand"])
            method = NO_SYMMETRY_METHOD if plane == "none" else SYMMETRY_METHOD.format(plane=plane)
        else:
            continue
        row["result"], row["method"], row["checked_utc"] = result, method, now
        report.append(f"{result:<13} {dim}")
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(CHECKS_HEADERS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) or "" for k in CHECKS_HEADERS})
    return "".join(lines[:head]) + out.getvalue(), report


def describe(verdicts: dict) -> list[str]:
    """The report in words."""
    lines = [f"axes   {verdicts['axes']}"]
    own = ", ".join(verdicts["symmetry_own"]) or "none"
    brand = ", ".join(verdicts["symmetry_brand"]) or "none"
    lines.append(f"mirror planes: brand model {brand}; ours {own}")
    for sides in verdicts["protrusions"]:
        lines.append(
            f"MISSING a brand feature sticks out of our model on the "
            f"{' and '.join(sides)} side, and ours has nothing there. Find it in "
            "the catalogue figure, add a row to the feature list and model it.")
    if not verdicts["protrusions"]:
        lines.append("ok     no brand feature sticks out of our model")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("family", help="Brand and family, like hiwin/hgr-rail")
    parser.add_argument("pn", help="Part number of our own model, like HGR20R1000")
    parser.add_argument("--from", dest="private", type=Path, required=True,
                        help="Checkout of the private library that keeps the brand's STEP")
    parser.add_argument("--root", type=Path, default=None,
                        help="Parts library root (default: parent of doqs/ submodule)")
    parser.add_argument("--freecad", default=None, help="Path to FreeCADCmd")
    parser.add_argument("--tolerance", type=float, default=0.1,
                        help="Largest difference, in mm, that still counts as the same (default 0.1)")
    parser.add_argument("--show-freecad-output", action="store_true",
                        help="Print what FreeCAD printed. It can hold brand values.")
    args = parser.parse_args(argv)
    root = (args.root or repo_root_from_script()).resolve()
    private = args.private.resolve()

    family_rel = family_path_of(args.family)
    family_dir = root / family_rel
    own = family_dir / "cad" / OWN_MODEL_DIR / f"{args.pn}.FCStd"
    checks = own.with_name(args.pn + CHECKS_SUFFIX)
    try:
        if not own.is_file():
            raise CompareError(f"our model not found: {own.relative_to(root)}")
        if not checks.is_file():
            raise CompareError(f"check list not found: {checks.relative_to(root)}")
        relpath, recorded = brand_step(family_dir, args.pn)
        brand = private / family_rel / relpath
        if not brand.is_file():
            raise CompareError(f"the brand's file is not in the private library: {brand}")
        if file_digest(brand) != recorded:
            raise CompareError(
                f"{brand.name} in the private library does not match its recorded "
                "checksum. Find out which is right before you compare.")
        fingerprint_matches(own)
        binary = find_freecad(args.freecad)
        if binary is None:
            raise CompareError("no FreeCAD binary found; pass --freecad PATH")

        watched = [own, fingerprint_path(own), brand]
        before = digests(watched)
        verdicts = run_freecad(binary, own, brand, args.tolerance,
                               args.show_freecad_output, outside=(root, private))
        if digests(watched) != before:
            raise CompareError(
                "a model or its fingerprint changed while FreeCAD ran. Nothing was "
                "written. Restore the files with git and run again.")
        fingerprint_matches(own)

        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        text, changed = update_checks(checks.read_text(encoding="utf-8"), verdicts, now)
    except CompareError as err:
        print(f"FAIL  {err}")
        return 1
    checks.write_text(text, encoding="utf-8")

    print(f"compared {args.family} {args.pn} with the brand's model")
    for line in changed:
        print(f"       {line}")
    if not changed:
        print("WARN   the check list has no envelope or symmetry rows to write")
    for line in describe(verdicts):
        print(line)
    print(f"wrote  {checks.relative_to(root)} (results and methods only)")
    bad = (not verdicts["same_axes"] or verdicts["protrusions"]
           or any(line.startswith("fail") for line in changed))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
