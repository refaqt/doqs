"""Put a library part into a machine module: BOM row, manifest entry, SysML.

    python doqs/scripts/use_part.py --module modules/compact-stage \\
        --part stoq:hiwin/hgl-block#HGL15CAZBC+E2 --qty 4 --name "Guide block" \\
        --category MEC [--sysml GuideBlock] [--usages blockFrontLeft,blockFrontRight] \\
        [--bump-pin merged|<sha>] [--generate]

`doqs use-part` runs the same thing. In order:

1. With `--bump-pin`, move the mounted library (`modules/stoq`) to the
   commit named, or to the newest commit on its `origin/main` (`merged`).
   A commit that is not on `origin/main` is refused: a machine never points
   at an unmerged branch. See docs/using-doqs.md.
2. Find the part in the mounted library. A part the pinned library does not
   have is an error that names the fix (the pin bump).
3. Add a `bom/bom.csv` row with the next free id for the category, the
   brand, the part number, the mass and spec from the library, and the
   reference in the `part` cell. A row for the same reference is left alone.
4. Add `[[bought-part]] bom, part, sysml` to `okh.toml`.
5. Add `part def <Sysml>` and one usage per name to `architecture/<module>.sysml`.
6. With `--generate`, run `doqs generate`.

Ports, connections and frames come from `doqs add-interface`.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import install_module
import okh_rules
import sysml_rules
from naming_rules import BOM_HEADERS, BOM_ID, BOM_PREFIXES, LIBRARY_PART_REF, repo_root_from_script
from report_rules import Report
from validate_variants import library_part, mounted_libraries

SCRIPTS = Path(__file__).resolve().parent
TOOLING_PINS = ("doqs", ".agents")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def bump_pin(root: Path, mount: str, target: str, *, allow_unmerged: bool = False,
             dry_run: bool = False) -> tuple[str | None, str]:
    """Move a submodule pin. Returns ``(sha, message)``; ``sha`` is None on refusal.

    ``target`` is ``merged`` (the newest commit of ``origin/main``) or a commit.
    The commit must be on ``origin/main`` unless ``allow_unmerged`` is set.
    The gitlink is staged with ``--force``, because a tooling submodule may be
    marked ``ignore = all`` in `.gitmodules`.
    """
    sub = root / mount
    if not (sub / ".git").exists():
        return None, f"{mount} is not a checked-out submodule (run: git submodule update --init {mount})"
    fetched = _git(sub, "fetch", "-q", "origin")
    if fetched.returncode != 0:
        return None, f"could not fetch {mount}: {fetched.stderr.strip()}"
    if target == "merged":
        sha = _git(sub, "rev-parse", "origin/main").stdout.strip()
    else:
        resolved = _git(sub, "rev-parse", "--verify", f"{target}^{{commit}}")
        if resolved.returncode != 0:
            return None, f"{target!r} is not a commit of {mount}"
        sha = resolved.stdout.strip()
    on_main = _git(sub, "merge-base", "--is-ancestor", sha, "origin/main").returncode == 0
    if not on_main and not allow_unmerged:
        return None, (f"{sha[:10]} is not on origin/main of {mount}. A machine points only at "
                      "merged library commits; merge the library pull request first.")
    current = _git(sub, "rev-parse", "HEAD").stdout.strip()
    if current == sha:
        return sha, f"{mount} already at {sha[:10]}"
    dirty = _git(sub, "status", "--porcelain").stdout.strip()
    if dirty:
        return None, (f"{mount} has local changes; move them to the library checkout first:\n"
                      + dirty)
    if dry_run:
        return sha, f"{mount}: would move {current[:10]} -> {sha[:10]}"
    moved = _git(sub, "checkout", "-q", sha)
    if moved.returncode != 0:
        return None, f"could not check out {sha[:10]} in {mount}: {moved.stderr.strip()}"
    staged = _git(root, "add", "--force", "--", mount)
    if staged.returncode != 0:
        return None, f"could not stage the pin: {staged.stderr.strip()}"
    note = " (not on origin/main!)" if not on_main else ""
    return sha, f"{mount}: {current[:10]} -> {sha[:10]}{note}; staged"


def next_bom_id(rows: list[dict], prefix: str) -> str:
    """The next free id for a prefix: ``MEC-003`` after ``MEC-002``."""
    highest = 0
    for row in rows:
        m = BOM_ID.match((row.get("id") or "").strip())
        if m and m.group(1) == prefix:
            highest = max(highest, int(m.group(2)))
    return f"{prefix}-{highest + 1:03d}"


def use_part(root: Path, module: Path, part: str, *, qty: str = "1", name: str | None = None,
             category: str = "MEC", unit: str = "pc", equiv_class: str = "", notes: str = "",
             sysml: str | None = None, usages: list[str] | None = None, library: str | None = None,
             bump: str | None = None, allow_unmerged: bool = False, generate: bool = False,
             dry_run: bool = False) -> Report:
    report = Report("use-part", root=str(root), dry_run=dry_run)
    if not LIBRARY_PART_REF.match(part):
        report.fail(f"{part!r} must look like stoq:<brand>/<family>#<part number>")
        return report
    if category not in BOM_PREFIXES:
        report.fail(f"category must be one of {sorted(BOM_PREFIXES)}")
        return report
    module_dir = (root / module).resolve()
    okh = module_dir / "okh.toml"
    if not okh.is_file():
        report.fail(f"no okh.toml at {module_dir}")
        return report
    lib_name, _, ref = part.partition(":")
    brand_slug = ref.split("/", 1)[0]
    pn = ref.split("#", 1)[1]
    mounts = mounted_libraries(root)
    mount = library or next((m for m in mounts if Path(m).name == lib_name), None)
    if mount is None:
        report.fail(f"no parts library named {lib_name!r} is mounted (mounted: {mounts or 'none'})")
        return report

    if bump:
        sha, message = bump_pin(root, mount, bump, allow_unmerged=allow_unmerged, dry_run=dry_run)
        if sha is None:
            report.fail(message)
            return report
        report.facts["pin"] = sha
        report.warn(message) if "not on origin/main" in message else report.then(message)
        if "->" in message:
            report.changed(root / mount)

    row, detail = library_part(root, mount, ref)
    if row is None:
        report.fail(f"{detail}. If the library has it on a newer commit, run with --bump-pin merged.")
        return report
    family_okh = root / mount / detail / "okh.toml"
    brand_name = brand_slug
    if family_okh.is_file():
        brand_name = str(okh_rules.load(family_okh.read_text(encoding="utf-8")).get("brand", {}).get("name", brand_slug))
    name = name or str(row.get("description") or pn)
    slug = module_dir.name
    package = install_module.pascal_case(slug)
    sysml = sysml or install_module.pascal_case(detail.split("/")[-1])
    usages = usages or [sysml[:1].lower() + sysml[1:]]

    # --- BOM -----------------------------------------------------------
    bom = module_dir / "bom" / "bom.csv"
    text = okh.read_text(encoding="utf-8")
    if not bom.is_file():
        if not dry_run:
            bom.parent.mkdir(parents=True, exist_ok=True)
            bom.write_text(",".join(BOM_HEADERS) + "\n", encoding="utf-8")
        report.wrote(bom)
    if okh_rules.get_key(text, "bom") != "bom/bom.csv":
        text = okh_rules.set_key(text, "bom", "bom/bom.csv")
    from library_rules import read_rows, append_row
    headers, rows = read_rows(bom) if bom.is_file() else (BOM_HEADERS, [])
    if headers and tuple(headers) != BOM_HEADERS:
        report.fail(f"{report.rel(bom)}: header is {list(headers)}; validate_names.py says how to migrate")
        return report
    existing = next((r for r in rows if (r.get("part") or "").strip() == part), None)
    if existing:
        bom_id = (existing.get("id") or "").strip()
        report.kept(bom, f"{bom_id} already buys {part}")
    else:
        bom_id = next_bom_id(rows, category)
        new_row = {
            "id": bom_id, "name": name, "spec": str(row.get("spec") or ""), "category": category,
            "qty": str(qty), "unit": unit, "unit_mass_g": str(row.get("unit_mass_g") or ""),
            "equiv_class": equiv_class, "brand": brand_slug.upper() if brand_name == brand_slug else brand_name.split()[0],
            "brand_pn": pn, "part": part, "notes": notes,
        }
        if not dry_run:
            append_row(bom, BOM_HEADERS, new_row, "id")
        report.changed(bom)

    # --- okh.toml ------------------------------------------------------
    new_text = okh_rules.append_table(text, "[[bought-part]]",
                                      {"bom": bom_id, "part": part, "sysml": sysml},
                                      match={"part": part})
    if new_text != okh.read_text(encoding="utf-8"):
        if not dry_run:
            okh.write_text(new_text, encoding="utf-8")
        report.changed(okh)
    else:
        report.kept(okh, "entry exists")

    # --- SysML ---------------------------------------------------------
    arch = module_dir / "architecture" / f"{slug}.sysml"
    if arch.is_file():
        arch_text = arch.read_text(encoding="utf-8")
        try:
            updated = sysml_rules.add_part_def(
                arch_text, package, sysml,
                doc=f"{name}, bought: {part}. From the parts library in {mount}/.")
            for usage in usages:
                updated = sysml_rules.add_part_usage(updated, f"{package}::{package}", usage, sysml)
        except sysml_rules.SysmlError as exc:
            report.warn(f"SysML not updated: {exc}")
            updated = arch_text
        if updated != arch_text:
            if not dry_run:
                arch.write_text(updated, encoding="utf-8")
            report.changed(arch)
        else:
            report.kept(arch, "part def and usages exist")
    else:
        report.warn(f"no architecture/{slug}.sysml; add `part def {sysml}` by hand")

    if generate and not dry_run:
        result = subprocess.run([sys.executable, str(SCRIPTS.parent / "doqs.py"), "generate",
                                 "--root", str(root)], capture_output=True, text=True)
        if result.returncode != 0:
            report.warn("doqs generate reported a problem:\n" + result.stdout[-2000:])
        else:
            report.facts["generated"] = True
    report.facts.update({"bom_id": bom_id, "part": part, "sysml": sysml, "usages": usages,
                         "library": mount, "family": detail})
    report.then(f"Connect it: doqs add-interface --module {module.as_posix()} --name <Name> "
                f"--a <ownPart>.<port> --b {usages[0]}.<port>")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--module", type=Path, required=True, help="Module folder, relative to the root")
    parser.add_argument("--part", required=True, help="stoq:<brand>/<family>#<part number>")
    parser.add_argument("--qty", default="1")
    parser.add_argument("--name", default=None, help="Everyday name in the BOM (default: the library description)")
    parser.add_argument("--category", default="MEC", help=f"BOM id prefix: one of {sorted(BOM_PREFIXES)}")
    parser.add_argument("--unit", default="pc")
    parser.add_argument("--equiv-class", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--sysml", default=None, help="Part def name (default: PascalCase of the family)")
    parser.add_argument("--usages", default="", help="Comma-separated usage names in the assembly")
    parser.add_argument("--library", default=None, help="Mount path of the library (default: by name)")
    parser.add_argument("--bump-pin", default=None, help="'merged' or a commit of the library")
    parser.add_argument("--allow-unmerged", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_script()
    usages = [u.strip() for u in args.usages.split(",") if u.strip()]
    report = use_part(root, args.module, args.part, qty=args.qty, name=args.name,
                      category=args.category, unit=args.unit, equiv_class=args.equiv_class,
                      notes=args.notes, sysml=args.sysml, usages=usages, library=args.library,
                      bump=args.bump_pin, allow_unmerged=args.allow_unmerged,
                      generate=args.generate, dry_run=args.dry_run)
    return report.emit(args.json)


if __name__ == "__main__":
    sys.exit(main())
