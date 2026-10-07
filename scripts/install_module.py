"""Scaffold a module, an own part, a library brand or a library family.

    python doqs/scripts/install_module.py module <slug> --name "Guide Block" --function "..."
    python doqs/scripts/install_module.py part <module> <part> [--sysml GuideBlock]
    python doqs/scripts/install_module.py brand <brand> --library ../stoq --name "HIWIN" ...
    python doqs/scripts/install_module.py family <brand> <family> --library ../stoq --name ...

`doqs scaffold ...` runs the same thing. Every folder and file follows
docs/architecture.md, so the gates pass on the result. A file that exists is
left alone, so a rerun changes nothing. The report (`--json` for tools) says
what was written and what to do next.

An own part gets an empty FreeCAD document with a Part container and a
`Params` spreadsheet, made by FreeCAD (the open window, a window started
for the job, or FreeCADCmd). Pass `--no-cad` to skip it, and run the
printed command later.
"""
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

import freecad_rules
import okh_rules
import sysml_rules
from naming_rules import MODULE_SLUG, repo_root_from_script, validate_module_slug
from param_rules import PARAM_HEADERS
from report_rules import Report

SCRIPTS = Path(__file__).resolve().parent
TEMPLATES = SCRIPTS.parent / "templates"

HARDWARE_LICENSE = "CERN-OHL-S-2.0"
LIBRARY_LICENSE = "CC-BY-SA-4.0"
DEFAULT_IMPORTS = ("ScalarValues::*", "ISQ::*", "SI::*")

LOG_INDEX = (
    "# Activity log\n\n"
    "Date-ordered record of work. Entries: `YYYY-MM-DD_topic.md`. Every entry needs **Role(s)**.\n"
    "Write entries in B2 English. Follow `.agents/rules/communication.md`.\n\n"
    "| Date | Topic | Role(s) | Images |\n| ---- | ----- | ------- | -----: |\n"
)
DECISIONS_INDEX = (
    "# Decisions\n\n"
    "Records of why a choice was made. One file per decision: `YYYY-MM-DD_topic.md`.\n"
    "Write entries in B2 English. Follow `.agents/rules/communication.md`.\n\n"
    "| Date | Decision |\n| ---- | -------- |\n"
)
MISTAKES_INDEX = (
    "# Mistakes\n\n"
    "Incidents worth not repeating. One file per incident: `YYYY-MM-DD_topic.md`.\n"
    "**Read these before starting work.**\n"
    "Write entries in B2 English. Follow `.agents/rules/communication.md`.\n\n"
    "| Date | Entry |\n| ---- | ----- |\n"
)
PARAMS_HEADER = (
    "# Independent values of this module, one per row. basis: requirement |\n"
    "# catalogue | estimated | measured | standard | simulation | design.\n"
    "# source names the reason: a requirement, a supplier part, a standard, a\n"
    "# simulation case or a design note. See doqs/docs/architecture.md.\n"
    + ",".join(PARAM_HEADERS) + "\n"
)
BOM_HEADER = "id,name,spec,category,qty,unit,unit_mass_g,equiv_class,brand,brand_pn,part,notes\n"

#: The macro that makes an empty part document: a Part container on top and a
#: Params spreadsheet with one aliased cell per parameter.
PART_MACRO = '''
import cad_build, cad_fingerprint
doc = FreeCAD.newDocument({name!r})
container = cad_build.part(doc, {label!r})
sheet = doc.addObject("Spreadsheet::Sheet", "Params")
sheet.Label = "Params"
for row, (alias, value, unit) in enumerate({aliases!r}, start=1):
    sheet.set("A%d" % row, alias)
    sheet.set("B%d" % row, (value + " " + unit).strip() if unit else value)
    sheet.setAlias("B%d" % row, alias)
doc.recompute()
doc.saveAs({path!r})
try:
    cad_fingerprint.write(doc, params={params!r}, cad_dir={cad_dir!r})
except Exception as exc:
    print("fingerprint not written:", exc)
FreeCAD.closeDocument(doc.Name)
'''


class ScaffoldError(ValueError):
    pass


def pascal_case(slug: str) -> str:
    """``guide-block`` -> ``GuideBlock``."""
    return "".join(w[:1].upper() + w[1:] for w in slug.replace("_", "-").split("-") if w)


def title_case(slug: str) -> str:
    """``guide-block`` -> ``Guide Block``."""
    return " ".join(w[:1].upper() + w[1:] for w in slug.split("-") if w)


def _write(report: Report, path: Path, text: str, dry_run: bool) -> bool:
    if path.exists():
        report.kept(path, "exists")
        return False
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    report.wrote(path)
    return True


def _edit(report: Report, path: Path, new_text: str, dry_run: bool) -> bool:
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    if old == new_text:
        report.kept(path, "already there")
        return False
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    report.changed(path)
    return True


def _load(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _repo_url(parent_okh: Path, slug: str) -> str:
    """The `repo` of a new module from its parent's: `<repo>/tree/main/modules/<slug>`."""
    data = _load(parent_okh)
    repo = str(data.get("repo", "")).rstrip("/")
    if "/tree/main/" in repo:
        return f"{repo}/modules/{slug}"
    return f"{repo}/tree/main/modules/{slug}"


def _component_url(repo_url: str) -> str:
    return repo_url.replace("/tree/main/", "/blob/main/") + "/okh.toml"


def _licensor(parent_okh: Path, explicit: str | None):
    if explicit:
        return explicit
    return _load(parent_okh).get("licensor", "Your Name")


# --------------------------------------------------------------------------
# A machine module
# --------------------------------------------------------------------------

def install_module(root: Path, slug: str, *, parent: Path | None = None, name: str | None = None,
                   function: str | None = None, licensor: str | None = None,
                   dry_run: bool = False) -> Report:
    """Create `modules/<slug>/` under the root or under a parent module."""
    report = Report("scaffold module", root=str(root), dry_run=dry_run)
    if not validate_module_slug(slug):
        report.fail(f"{slug!r} is not a module slug (kebab-case, like guide-block)")
        return report
    parent_dir = (root / parent).resolve() if parent else root.resolve()
    parent_okh = parent_dir / "okh.toml"
    if not parent_okh.is_file():
        report.fail(f"no okh.toml at {parent_dir}")
        return report
    module = parent_dir / "modules" / slug
    name = name or title_case(slug)
    function = function or f"{name}. Describe what this module does."
    repo_url = _repo_url(parent_okh, slug)
    package = pascal_case(slug)

    manifest = okh_rules.render_manifest({
        "okhv": "OKH-LOSHv1.0", "name": name, "repo": repo_url, "version": "0.1.0",
        "license": HARDWARE_LICENSE, "licensor": _licensor(parent_okh, licensor),
        "function": function, "bom": "bom/bom.csv",
    }, comment=(f"Module {slug}. Hardware licence; firmware/software is GPL-3.0 and\n"
                "docs/media is CC BY-SA 4.0. See README.md / LICENSE."))
    manifest += (
        "\n# Interfaces of the whole module. They mirror the port defs in\n"
        f"# architecture/{slug}.sysml. `doqs add-interface --outside` adds them.\n"
        "\n# Parts we make, one [[part]] each. `doqs scaffold part` adds them.\n"
    )
    _write(report, module / "okh.toml", manifest, dry_run)
    _write(report, module / "README.md",
           f"# {name}\n\n{function}\n\nThe layout follows `doqs/docs/architecture.md`.\n", dry_run)
    _write(report, module / "bom" / "bom.csv", BOM_HEADER, dry_run)
    _write(report, module / "cad" / "params" / "default.csv", PARAMS_HEADER, dry_run)
    for folder in ("cad/parts", "cad/assemblies"):
        target = module / folder
        if not target.is_dir():
            if not dry_run:
                target.mkdir(parents=True, exist_ok=True)
                (target / ".gitkeep").write_text("", encoding="utf-8")
            report.wrote(target / ".gitkeep")
    _write(report, module / "architecture" / f"{slug}.sysml",
           sysml_rules.new_module_text(package, package, function, imports=DEFAULT_IMPORTS), dry_run)
    _write(report, module / "docs" / "log" / "README.md", LOG_INDEX, dry_run)
    _write(report, module / "docs" / "decisions" / "README.md", DECISIONS_INDEX, dry_run)
    _write(report, module / "docs" / "mistakes" / "README.md", MISTAKES_INDEX, dry_run)

    parent_text = parent_okh.read_text(encoding="utf-8")
    new_text = okh_rules.append_table(parent_text, "[[hasComponent]]",
                                      {"component": _component_url(repo_url)})
    _edit(report, parent_okh, new_text, dry_run)
    report.facts.update({"module": report.rel(module), "package": package})
    report.then("Run `doqs generate` so the licence stubs are written, then `doqs check`.")
    report.then(f"Add parts with `doqs scaffold part {report.rel(module)} <part>`.")
    return report


# --------------------------------------------------------------------------
# An own part inside a module
# --------------------------------------------------------------------------

def _aliases(params_csv: Path) -> list[tuple[str, str, str]]:
    from param_rules import load_param_csv

    if not params_csv.is_file():
        return []
    rows = load_param_csv(params_csv)
    return [(alias, str(row.get("value", "")), str(row.get("unit", ""))) for alias, row in rows.items()]


def part_macro(scripts: Path, *, name: str, label: str, path: Path, aliases, cad_dir: Path) -> str:
    params = {alias: _number(value) for alias, value, _ in aliases}
    body = PART_MACRO.format(name=name, label=label, aliases=list(aliases), path=str(path),
                             params=params, cad_dir=str(cad_dir))
    return freecad_rules.render_macro(scripts, body)


def _number(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def install_part(root: Path, module: Path, part: str, *, name: str | None = None,
                 sysml: str | None = None, usage: str | None = None, no_cad: bool = False,
                 freecad: str | None = None, mode: str = "auto", dry_run: bool = False) -> Report:
    """Create `cad/parts/<part>/` with a build script, a document, a part def and a usage."""
    report = Report("scaffold part", root=str(root), dry_run=dry_run)
    if not MODULE_SLUG.match(part):
        report.fail(f"{part!r} is not a part slug (kebab-case, like carriage-top)")
        return report
    module_dir = (root / module).resolve()
    okh = module_dir / "okh.toml"
    if not okh.is_file():
        report.fail(f"no okh.toml at {module_dir}")
        return report
    slug = module_dir.name
    name = name or title_case(part)
    sysml = sysml or pascal_case(part)
    usage = usage or (sysml[:1].lower() + sysml[1:])
    package = pascal_case(slug)
    folder = module_dir / "cad" / "parts" / part
    fcstd = folder / f"{part}.FCStd"

    seed = (TEMPLATES / "cad" / "build_model.py").read_text(encoding="utf-8")
    _write(report, folder / "build_model.py", seed, dry_run)

    text = okh.read_text(encoding="utf-8")
    new_text = okh_rules.append_table(text, "[[part]]", {
        "name": name, "source": [f"cad/parts/{part}/{part}.FCStd"], "sysml": sysml,
    }, match={"name": name})
    _edit(report, okh, new_text, dry_run)

    arch = module_dir / "architecture" / f"{slug}.sysml"
    if arch.is_file():
        arch_text = arch.read_text(encoding="utf-8")
        try:
            updated = sysml_rules.add_part_def(arch_text, package, sysml,
                                               doc=f"{name}. CAD: cad/parts/{part}/.")
            updated = sysml_rules.add_part_usage(updated, f"{package}::{package}", usage, sysml)
        except sysml_rules.SysmlError as exc:
            report.warn(f"SysML not updated: {exc}")
            updated = arch_text
        _edit(report, arch, updated, dry_run)
    else:
        report.warn(f"no architecture/{slug}.sysml; add `part def {sysml}` by hand")

    params_csv = module_dir / "cad" / "params.csv"
    if not params_csv.is_file():
        params_csv = module_dir / "cad" / "params" / "default.csv"
    if fcstd.is_file():
        report.kept(fcstd, "exists")
    elif no_cad or dry_run:
        report.wrote(fcstd) if dry_run else None
        report.then(f"Create the document: `doqs scaffold part {module.as_posix()} {part}` "
                    "without --no-cad, or open FreeCAD and add a Part container and a Params sheet.")
    else:
        folder.mkdir(parents=True, exist_ok=True)
        macro = part_macro(SCRIPTS, name=part, label=part, path=fcstd,
                           aliases=_aliases(params_csv), cad_dir=module_dir / "cad")
        result = freecad_rules.run_macro(macro, mode=mode, freecad=freecad, needs_gui=False)
        if result.ok and fcstd.is_file():
            report.wrote(fcstd)
            report.facts["freecad"] = result.mode
            fingerprint = folder / f"{part}.fingerprint.json"
            if fingerprint.is_file():
                report.wrote(fingerprint)
            else:
                report.warn("no fingerprint was written; run the build script headless once")
        else:
            report.fail(f"FreeCAD did not create {report.rel(fcstd)}: {result.error}")
            for step in result.steps:
                report.warn(step)
    report.facts.update({"part": part, "sysml": sysml, "usage": usage, "document": report.rel(fcstd)})
    report.then(f"Write build() in {report.rel(folder / 'build_model.py')}: every size from Params, "
                "frames for every place another part attaches.")
    return report


# --------------------------------------------------------------------------
# A parts library: brand and family
# --------------------------------------------------------------------------

def _library_repo(library: Path) -> str:
    okh = library / "okh.toml"
    if okh.is_file():
        return str(_load(okh).get("repo", "")).rstrip("/")
    return "https://github.com/ORG/stoq"


def _library_licensor(library: Path, explicit: str | None):
    if explicit:
        return explicit
    okh = library / "okh.toml"
    if okh.is_file():
        return _load(okh).get("licensor", "ORG")
    return "ORG"


def install_brand(library: Path, brand: str, *, name: str | None = None, website: str = "",
                  cad_terms: str = "", license_id: str | None = None, licensor: str | None = None,
                  private: bool | None = None, dry_run: bool = False) -> Report:
    """Create `modules/<brand>/` in a parts library."""
    from naming_rules import is_private_library

    report = Report("scaffold brand", root=str(library), dry_run=dry_run)
    if not validate_module_slug(brand):
        report.fail(f"{brand!r} is not a brand slug (kebab-case, like hiwin)")
        return report
    private = is_private_library(library) if private is None else private
    folder = library / "modules" / brand
    name = name or title_case(brand)
    fields = {
        "okhv": "OKH-LOSHv1.0", "name": name,
        "repo": f"{_library_repo(library)}/tree/main/modules/{brand}", "version": "0.1.0",
        "license": license_id or (f"LicenseRef-{brand}-terms" if private else LIBRARY_LICENSE),
        "licensor": _library_licensor(library, licensor),
        "function": f"Parts made by {name}.",
    }
    comment = ("A brand is the name on the part, not the supplier you buy from.\n"
               + ("Private library: the licence names the supplier's own terms." if private
                  else "CC BY-SA for the record we compile; the parts are not ours."))
    text = okh_rules.render_manifest(fields, comment=comment)
    text += "\n[brand]\n" + "".join(
        f"{k} = {okh_rules.format_value(v)}\n"
        for k, v in (("name", name), ("website", website or "https://example.com"),
                     ("cad-terms", cad_terms or "https://example.com/terms"), ("redistribute", False)))
    text += ("\n# One dated [[terms-review]] per kind of file (cad, documentation).\n"
             "# `doqs add-part` adds them; a named person approves them in the pull request.\n")
    _write(report, folder / "okh.toml", text, dry_run)
    _write(report, folder / "vendor-index.csv",
           "supplier,pn,relpath,bytes,sha256,source_url,terms,retrieved_utc\n", dry_run)
    datasheets = folder / "docs" / "datasheets"
    if not datasheets.is_dir():
        if not dry_run:
            datasheets.mkdir(parents=True, exist_ok=True)
            (datasheets / ".gitkeep").write_text("", encoding="utf-8")
        report.wrote(datasheets / ".gitkeep")
    report.facts["brand"] = report.rel(folder)
    return report


def install_family(library: Path, brand: str, family: str, *, name: str | None = None,
                   function: str | None = None, licensor: str | None = None,
                   dry_run: bool = False) -> Report:
    """Create `modules/<brand>/modules/<family>/` in a parts library."""
    from library_rules import template_text
    from naming_rules import is_private_library

    report = Report("scaffold family", root=str(library), dry_run=dry_run)
    if not validate_module_slug(family):
        report.fail(f"{family!r} is not a family slug (kebab-case, like hgl-block)")
        return report
    brand_dir = library / "modules" / brand
    brand_okh = brand_dir / "okh.toml"
    if not brand_okh.is_file():
        report.fail(f"no brand at {report.rel(brand_dir)}; run `doqs scaffold brand {brand}` first")
        return report
    brand_data = _load(brand_okh)
    brand_table = brand_data.get("brand", {})
    folder = brand_dir / "modules" / family
    name = name or f"{brand_data.get('name', title_case(brand))} {title_case(family)}"
    fields = {
        "okhv": "OKH-LOSHv1.0", "name": name,
        "repo": f"{_library_repo(library)}/tree/main/modules/{brand}/modules/{family}",
        "version": "0.1.0",
        "license": brand_data.get("license", LIBRARY_LICENSE),
        "licensor": _library_licensor(library, licensor) if not brand_data.get("licensor") else brand_data["licensor"],
        "function": function or f"{name}: describe the family.",
    }
    text = okh_rules.render_manifest(fields, comment="The family is the module. One orderable part number is a row in bom/parts.csv.")
    text += "\n[brand]\n" + "".join(
        f"{k} = {okh_rules.format_value(brand_table.get(k, v))}\n"
        for k, v in (("name", name), ("website", ""), ("cad-terms", ""), ("redistribute", False)))
    text += ("\n# Interfaces this family provides. `doqs add-interface` in a machine adds\n"
             "# the matching port def; declare the family's own here.\n")
    _write(report, folder / "okh.toml", text, dry_run)
    _write(report, folder / "bom" / "parts.csv", template_text("bom/parts.csv"), dry_run)
    _write(report, folder / "vendor-index.csv",
           "supplier,pn,relpath,bytes,sha256,source_url,terms,retrieved_utc\n", dry_run)
    for sub in ("cad/original", "cad/parts", "docs/datasheets"):
        target = folder / sub
        if not target.is_dir():
            if not dry_run:
                target.mkdir(parents=True, exist_ok=True)
                (target / ".gitkeep").write_text("", encoding="utf-8")
            report.wrote(target / ".gitkeep")
    report.facts["family"] = report.rel(folder)
    _ = is_private_library
    return report


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None, help="Machine repository root")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be written")
    subs = parser.add_subparsers(dest="what", required=True)

    module = subs.add_parser("module", help="A new module under modules/")
    module.add_argument("slug")
    module.add_argument("--parent", type=Path, default=None, help="Parent module, relative to the root")
    module.add_argument("--name", default=None)
    module.add_argument("--function", default=None)
    module.add_argument("--licensor", default=None)

    part = subs.add_parser("part", help="A new own part in a module")
    part.add_argument("module", type=Path, help="Module folder, relative to the root")
    part.add_argument("part", help="Part slug, like carriage-top")
    part.add_argument("--name", default=None)
    part.add_argument("--sysml", default=None, help="Part def name (default: PascalCase of the slug)")
    part.add_argument("--usage", default=None, help="Part usage name in the assembly")
    part.add_argument("--no-cad", action="store_true", help="Do not start FreeCAD")
    part.add_argument("--freecad", default=None, help="FreeCAD binary")
    part.add_argument("--mode", default="auto", choices=freecad_rules.MODES)

    brand = subs.add_parser("brand", help="A new brand in a parts library")
    brand.add_argument("brand")
    brand.add_argument("--library", type=Path, default=None, help="Library root (default: --root)")
    brand.add_argument("--name", default=None)
    brand.add_argument("--website", default="")
    brand.add_argument("--cad-terms", default="")
    brand.add_argument("--license", dest="license_id", default=None)
    brand.add_argument("--licensor", default=None)

    family = subs.add_parser("family", help="A new family under a brand")
    family.add_argument("brand")
    family.add_argument("family")
    family.add_argument("--library", type=Path, default=None)
    family.add_argument("--name", default=None)
    family.add_argument("--function", default=None)
    family.add_argument("--licensor", default=None)

    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_script()

    if args.what == "module":
        report = install_module(root, args.slug, parent=args.parent, name=args.name,
                                function=args.function, licensor=args.licensor, dry_run=args.dry_run)
    elif args.what == "part":
        report = install_part(root, args.module, args.part, name=args.name, sysml=args.sysml,
                              usage=args.usage, no_cad=args.no_cad, freecad=args.freecad,
                              mode=args.mode, dry_run=args.dry_run)
    elif args.what == "brand":
        library = (args.library or root).resolve()
        report = install_brand(library, args.brand, name=args.name, website=args.website,
                               cad_terms=args.cad_terms, license_id=args.license_id,
                               licensor=args.licensor, dry_run=args.dry_run)
    else:
        library = (args.library or root).resolve()
        report = install_family(library, args.brand, args.family, name=args.name,
                                function=args.function, licensor=args.licensor, dry_run=args.dry_run)
    return report.emit(args.json)


if __name__ == "__main__":
    sys.exit(main())
