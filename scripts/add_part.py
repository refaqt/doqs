"""Take a supplier's part into the parts libraries, private first, then public.

    python doqs/scripts/add_part.py --private ../stoq-private --public ../stoq \\
        --brand hiwin --family hgl-block --pn HGL15CAZBC+E2 \\
        --description "HGL15 flange block" --spec "size 15, long" --mass-g 180 \\
        --step HGL15.step --datasheet hgl.pdf --terms-pdf terms.pdf \\
        --source-url https://... --terms-url https://... \\
        --decision customers --basis terms --reviewer "First Last"

`doqs add-part` runs the same thing. It does what docs/parts-library.md asks
for, in order, and nothing by hand: the brand and family folders, the STEP
and the datasheet at their paths, the `vendor-index.csv` rows with checksum
and size, the `bom/parts.csv` row, the dated `[[terms-review]]` entries, the
evidence copy of the terms, and the `.gitignore` lines in the public library
for a file that may not be shared. Rows are append-only: an existing row is
left alone, a different one for the same part is refused.

The decision says what the public library gets:

- ``public``: the files are committed in both libraries (``redistributable``).
- ``customers`` or ``internal``: the files are committed in the private
  library only (``internal``); the public library keeps the rows and ignores
  the paths (``fetch-only`` with a public address, else ``private``).

A named person still approves the terms review in the pull request. The
FreeCAD wrapper is the next step: `doqs wrap`.
"""
from __future__ import annotations

import argparse
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path

import apply_unshare
import install_module
import library_rules as lr
import okh_rules
from intake_rules import REVIEW_BASES, REVIEW_DECISIONS, latest_review_of
from naming_rules import MODULE_SLUG, PARTS_TABLE_HEADERS, is_parts_library, is_private_library
from report_rules import Report
from validate_variants import VENDOR_INDEX_HEADERS

SCRIPTS = Path(__file__).resolve().parent
_SAFE = re.compile(r"[^A-Za-z0-9._+-]+")


class IntakeError(ValueError):
    pass


def _safe_name(name: str) -> str:
    return _SAFE.sub("-", name).strip("-")


def _family_dir(library: Path, brand: str, family: str) -> Path:
    return library / "modules" / brand / "modules" / family


def _copy(report: Report, src: Path, dst: Path, dry_run: bool) -> None:
    if dst.is_file():
        if lr.sha256_and_size(src) == lr.sha256_and_size(dst):
            report.kept(dst, "same file")
            return
        raise IntakeError(f"{report.rel(dst)} exists with other content; a brand's file is never overwritten")
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    report.wrote(dst)


def _add_review(report: Report, brand_okh: Path, kind: str, decision: str, basis: str,
                source: str, evidence: str, reviewer: str, reviewed: datetime.date,
                dry_run: bool) -> None:
    text = brand_okh.read_text(encoding="utf-8")
    data = okh_rules.load(text)
    latest = latest_review_of(data, kind)
    if latest and latest.get("decision") == decision and latest.get("basis") == basis \
            and str(latest.get("source", "")) == source:
        report.kept(brand_okh, f"{kind} review already says {decision}")
        return
    fields = {"kind": kind, "decision": decision, "basis": basis, "source": source,
              "evidence": evidence, "reviewer": reviewer,
              "reviewed": okh_rules.RawValue(reviewed.isoformat())}
    new = okh_rules.append_table(text, "[[terms-review]]", fields,
                                 comment=f"Proposed by doqs add-part on {reviewed.isoformat()}; a named person approves it in the pull request.",
                                 match={"kind": kind, "decision": decision, "basis": basis, "source": source})
    if kind == "cad":
        try:
            new = okh_rules.set_key(new, "redistribute", decision == "public", "[brand]")
        except okh_rules.OkhError:
            report.warn(f"{report.rel(brand_okh)} has no [brand] table to set redistribute on")
    if new != text:
        if not dry_run:
            brand_okh.write_text(new, encoding="utf-8")
        report.changed(brand_okh)


def intake(*, private: Path | None, public: Path | None, brand: str, family: str, pn: str,
           description: str, spec: str = "", mass_g: str = "", step: Path | None = None,
           datasheets: list[Path] | None = None, terms_pdf: Path | None = None,
           licence: Path | None = None, source_url: str = "", terms_url: str = "",
           decision: str = "customers", basis: str = "terms", reviewer: str = "",
           brand_name: str | None = None, website: str = "", family_name: str | None = None,
           function: str | None = None, revision: str = "A", notes: str = "",
           reviewed: datetime.date | None = None, retrieved_utc: str | None = None,
           validate: bool = True, dry_run: bool = False) -> Report:
    """Record one part in the private library and the public library."""
    report = Report("add-part", root=str(private or public or Path.cwd()), dry_run=dry_run)
    datasheets = datasheets or []
    reviewed = reviewed or lr.today()
    retrieved_utc = retrieved_utc or lr.utc_now()

    # --- inputs ---------------------------------------------------------
    for slug, what in ((brand, "brand"), (family, "family")):
        if not MODULE_SLUG.match(slug):
            report.fail(f"{slug!r} is not a {what} slug (kebab-case)")
    if not pn.strip() or any(c.isspace() for c in pn):
        report.fail("the part number may not be empty or hold spaces")
    if decision not in REVIEW_DECISIONS:
        report.fail(f"decision must be one of {REVIEW_DECISIONS}")
    if basis not in REVIEW_BASES:
        report.fail(f"basis must be one of {REVIEW_BASES}")
    if not reviewer.strip():
        report.fail("--reviewer must name the person who approves the terms review")
    if decision == "public" and basis == "none":
        report.warn("decision public with basis none: nothing allows sharing; the validator flags this")
    if basis == "permission" and terms_pdf is None and licence is None:
        report.fail("basis permission needs the written permission as --terms-pdf or --licence")
    for path in [step, terms_pdf, licence, *datasheets]:
        if path is not None and not Path(path).is_file():
            report.fail(f"file not found: {path}")
    libraries: list[tuple[Path, bool]] = []
    for root, expect_private in ((private, True), (public, False)):
        if root is None:
            continue
        root = Path(root).resolve()
        if not is_parts_library(root):
            report.fail(f"{root} is not a parts library (no library.toml)")
            continue
        is_private = is_private_library(root)
        if is_private != expect_private:
            which = "--private" if expect_private else "--public"
            report.fail(f"{root} is {'not ' if expect_private else ''}marked private = true "
                        f"in library.toml, so it cannot be {which}")
            continue
        libraries.append((root, is_private))
    if not libraries:
        report.fail("name at least one library with --private or --public")
    if not report.ok:
        return report

    has_url = bool(source_url.strip())
    evidence_rel = ""
    private_root = next((p for p, priv in libraries if priv), None)

    # --- evidence in the private library -------------------------------
    if private_root is not None:
        for src, suffix in ((terms_pdf, None), (licence, ".license")):
            if src is None:
                continue
            src = Path(src)
            name = f"{reviewed.isoformat()}_{_safe_name(src.stem)}{suffix or src.suffix}"
            dst = private_root / "evidence" / brand / name
            try:
                _copy(report, src, dst, dry_run)
            except IntakeError as exc:
                report.fail(str(exc))
                return report
            if not evidence_rel:
                evidence_rel = f"evidence/{brand}/{name}"
    elif terms_pdf is not None or licence is not None:
        report.warn("no private library given: the terms evidence is not stored anywhere")

    # --- each library, private first -------------------------------------
    for root, is_private in libraries:
        terms = lr.terms_for(decision, has_public_url=has_url, private_library=is_private)
        commit_files = lr.is_committed(terms)
        brand_report = install_module.install_brand(root, brand, name=brand_name, website=website,
                                                    cad_terms=terms_url, dry_run=dry_run)
        family_report = install_module.install_family(root, brand, family, name=family_name,
                                                      function=function, dry_run=dry_run)
        for sub in (brand_report, family_report):
            report.written += [f"{root.name}/{w}" for w in sub.written]
            report.edited += [f"{root.name}/{w}" for w in sub.edited]
            report.errors += sub.errors
        if not report.ok:
            return report
        family_dir = _family_dir(root, brand, family)
        saved_root = report.root
        report.root = str(root)
        try:
            ignored: list[str] = []
            rows: list[dict] = []
            step_rel = ""
            if step is not None:
                step = Path(step)
                step_rel = f"cad/original/{_safe_name(pn)}{step.suffix.lower()}"
                rows.append(lr.vendor_row(brand, pn, step_rel, step, source_url, terms, retrieved_utc))
                if commit_files:
                    _copy(report, step, family_dir / step_rel, dry_run)
                else:
                    ignored.append((family_dir / step_rel).relative_to(root).as_posix())
            sheet_rels: list[str] = []
            for sheet in datasheets:
                sheet = Path(sheet)
                rel = f"docs/datasheets/{_safe_name(sheet.name)}"
                sheet_rels.append(rel)
                rows.append(lr.vendor_row(brand, pn, rel, sheet, source_url, terms, retrieved_utc))
                if commit_files:
                    _copy(report, sheet, family_dir / rel, dry_run)
                else:
                    ignored.append((family_dir / rel).relative_to(root).as_posix())
            index = family_dir / "vendor-index.csv"
            for row in rows:
                if dry_run:
                    report.changed(index)
                elif lr.append_row(index, VENDOR_INDEX_HEADERS, row, "pn"):
                    report.changed(index)
                else:
                    report.kept(index, f"{row['relpath']} already listed")
            table = family_dir / "bom" / "parts.csv"
            part_row = lr.parts_row(pn, description, spec=spec, unit_mass_g=mass_g, cad="",
                                    datasheet=sheet_rels[0] if sheet_rels else "", terms=terms,
                                    revision=revision, notes=notes)
            if dry_run:
                report.changed(table)
            elif lr.append_row(table, PARTS_TABLE_HEADERS, part_row, "pn",
                               template=lr.template_text("bom/parts.csv")):
                report.changed(table)
            else:
                report.kept(table, f"{pn} already listed")
            brand_okh = root / "modules" / brand / "okh.toml"
            if step is not None:
                _add_review(report, brand_okh, "cad", decision, basis, terms_url, evidence_rel,
                            reviewer, reviewed, dry_run)
            if datasheets:
                _add_review(report, brand_okh, "documentation", decision, basis, terms_url,
                            evidence_rel, reviewer, reviewed, dry_run)
            if ignored and not dry_run:
                added = apply_unshare.add_to_gitignore(root, ignored)
                if added:
                    report.changed(root / ".gitignore")
            elif ignored:
                report.changed(root / ".gitignore")
            report.facts[root.name] = {"terms": terms, "step": step_rel, "datasheets": sheet_rels,
                                       "family": family_dir.relative_to(root).as_posix()}
        except (IntakeError, lr.LibraryError, okh_rules.OkhError) as exc:
            report.fail(f"{root.name}: {exc}")
            return report
        finally:
            report.root = saved_root
        if validate and not dry_run:
            _validate(report, root, brand)

    report.facts.update({"brand": brand, "family": family, "pn": pn, "decision": decision,
                         # Every repository this report wrote in; `root` names only the first.
                         "roots": [str(root) for root, _ in libraries]})
    report.then(f"Build the FreeCAD wrapper: doqs wrap --library {private or public} "
                f"--part {brand}/{family}#{pn} --frames IF_...")
    report.then("Open the pull requests, private library first. The reviewer named in the "
                "terms review approves it there.")
    return report


def _validate(report: Report, root: Path, brand: str) -> None:
    """Run the library gates and keep the lines about this brand."""
    for gate in ("validate_okh.py", "validate_variants.py"):
        result = subprocess.run([sys.executable, str(SCRIPTS / gate), "--root", str(root)],
                                capture_output=True, text=True, cwd=root)
        if result.returncode == 0:
            continue
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        mine = [l for l in lines if f"modules/{brand}" in l or f"modules\\{brand}" in l]
        if mine:
            for line in mine:
                report.fail(f"{root.name} {gate}: {line}")
        else:
            report.warn(f"{root.name} {gate} fails on other entries (not this part); see its output")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--private", type=Path, default=None, help="Private library checkout")
    parser.add_argument("--public", type=Path, default=None, help="Public library checkout")
    parser.add_argument("--brand", required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--pn", required=True, help="The brand's part number, verbatim")
    parser.add_argument("--description", required=True)
    parser.add_argument("--spec", default="")
    parser.add_argument("--mass-g", default="")
    parser.add_argument("--step", type=Path, default=None)
    parser.add_argument("--datasheet", type=Path, action="append", default=[])
    parser.add_argument("--terms-pdf", type=Path, default=None, help="Saved copy of the terms page")
    parser.add_argument("--licence", type=Path, default=None, help="The supplier's licence text")
    parser.add_argument("--source-url", default="", help="Where the brand publishes the file")
    parser.add_argument("--terms-url", default="", help="The terms page that was read")
    parser.add_argument("--decision", default="customers", choices=REVIEW_DECISIONS)
    parser.add_argument("--basis", default="terms", choices=REVIEW_BASES)
    parser.add_argument("--reviewer", default="", help="The person who approves the review")
    parser.add_argument("--brand-name", default=None)
    parser.add_argument("--website", default="")
    parser.add_argument("--family-name", default=None)
    parser.add_argument("--function", default=None)
    parser.add_argument("--revision", default="A")
    parser.add_argument("--notes", default="")
    parser.add_argument("--no-validate", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    report = intake(
        private=args.private, public=args.public, brand=args.brand, family=args.family,
        pn=args.pn, description=args.description, spec=args.spec, mass_g=args.mass_g,
        step=args.step, datasheets=args.datasheet, terms_pdf=args.terms_pdf, licence=args.licence,
        source_url=args.source_url, terms_url=args.terms_url, decision=args.decision,
        basis=args.basis, reviewer=args.reviewer, brand_name=args.brand_name,
        website=args.website, family_name=args.family_name, function=args.function,
        revision=args.revision, notes=args.notes, validate=not args.no_validate,
        dry_run=args.dry_run)
    return report.emit(args.json)


if __name__ == "__main__":
    sys.exit(main())
